from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import time
from test_runtime import host, Client, configure_client


def plugin(host, tmp_path):
    root = tmp_path / 'c'; root.mkdir()
    file = root / 'movie.mkv'; file.write_bytes(b'movie')
    p = host.new({'enabled': True, 'cookie': 'UID=fixture', 'watch_paths': str(root), 'realtime_settle': 1})
    p._stop_monitor()
    return p, file


def event(path, source='/source/download.mkv'):
    return SimpleNamespace(event_data={'fileitem': SimpleNamespace(path=source),
        'transferinfo': SimpleNamespace(success=True, target_item=SimpleNamespace(storage='local', path=str(path)), file_list_new=[str(path)])})


def ready(p, path):
    item = p._file_item(str(path))
    p._live_queue[str(path)]['due_at'] = 0
    from importlib import import_module
    sig = import_module(type(p).__module__ + '.fileactions').signature(path)
    p._live_queue[str(path)]['observed'] = list(sig)


def test_transfer_event_durable_no_hash_or_network_in_callback(host, tmp_path, monkeypatch):
    p, path = plugin(host, tmp_path)
    monkeypatch.setattr(p, '_transfer', lambda *a, **k: (_ for _ in ()).throw(AssertionError('inline upload')))
    p.on_transfer_complete(event(path))
    assert list(p._live_queue) == [str(path)]
    assert len(p.storage['state_v2']['live_queue']) == 1
    assert '/source/download.mkv' not in p._live_queue
    restored = host.new(p._config, p.storage); restored._stop_monitor()
    assert str(path) in restored._live_queue


def test_event_worker_checks_stability_then_processes_once(host, tmp_path, monkeypatch):
    p, path = plugin(host, tmp_path)
    c = Client({'ok': True}); configure_client(p, c, monkeypatch)
    p.on_transfer_complete(event(path))
    p._live_queue[str(path)]['due_at'] = 0
    p._drain_live(p._config, p._generation)
    assert not c.calls and p._live_queue[str(path)]['observed']
    p._live_queue[str(path)]['due_at'] = 0
    p._drain_live(p._config, p._generation)
    assert len(c.calls) == 1 and not p._live_queue
    p.on_transfer_complete(event(path)); ready(p, path)
    p._drain_live(p._config, p._generation)
    assert len(c.calls) == 1


def test_event_does_not_bypass_retry_deadline(host, tmp_path, monkeypatch):
    p, path = plugin(host, tmp_path)
    c = Client({'ok': False}); configure_client(p, c, monkeypatch)
    p._transfer(p._file_item(str(path)), p._config)
    deadline = deepcopy(p._queue.get(str(path)))
    p.on_transfer_complete(event(path)); ready(p, path)
    p._drain_live(p._config, p._generation)
    assert len(c.calls) == 1
    assert p._queue.get(str(path)) == deadline


def test_event_scope_and_extension_filters(host, tmp_path):
    p, path = plugin(host, tmp_path)
    p.on_transfer_complete(event(tmp_path / 'outside.mkv'))
    p.on_transfer_complete(event(path.with_suffix('.nfo')))
    p.on_transfer_complete(SimpleNamespace(event_data={'fileitem': SimpleNamespace(path=str(path))}))
    assert not p._live_queue
    p.on_transfer_complete(event(path))
    gen = p._generation
    p.stop_service()
    assert not p._ingest_path(str(path), gen)


def test_reload_stale_generation_cannot_enqueue(host, tmp_path):
    p, path = plugin(host, tmp_path)
    gen = p._generation
    p.init_plugin(p._config); p._stop_monitor()
    assert not p._ingest_path(str(path), gen)
    assert p._ingest_path(str(path), p._generation)


def test_cloud_storage_event_not_local_file(host, tmp_path):
    p, path = plugin(host, tmp_path)
    e = event(path); e.event_data['transferinfo'].target_item.storage = '115'
    p.on_transfer_complete(e)
    assert not p._live_queue


def test_native_monitor_callbacks_and_stop(host, tmp_path, monkeypatch):
    p, path = plugin(host, tmp_path)
    import importlib
    realtime = importlib.import_module(type(p).__module__ + '.realtime')
    monkeypatch.setattr(realtime.os, 'uname', lambda: SimpleNamespace(release='6.1-linux'))
    class Observer:
        def __init__(self): self.stopped = self.joined = False; self.handlers = []
        def schedule(self, handler, root, recursive): self.handlers.append(handler)
        def start(self): pass
        def stop(self): self.stopped = True
        def join(self, timeout): self.joined = True
    monkeypatch.setitem(sys.modules, 'watchdog.events', SimpleNamespace(FileSystemEventHandler=object))
    monkeypatch.setitem(sys.modules, 'watchdog.observers', SimpleNamespace(Observer=Observer))
    p._start_monitor(p._config, p._generation)
    observer = p._observer
    observer.handlers[0].on_created(SimpleNamespace(src_path=str(path), is_directory=False))
    assert str(path) in p._live_queue
    observer.handlers[0].on_moved(SimpleNamespace(dest_path=str(path), is_directory=False))
    p._stop_monitor()
    assert observer.stopped and observer.joined and p._observer is None


def test_real_watchdog_observes_new_hardlink(host, tmp_path):
    import os
    import pytest
    pytest.importorskip('watchdog.observers')
    p, existing = plugin(host, tmp_path)
    p._start_monitor(p._config, p._generation)
    if p._observer is None:
        pytest.skip('Host does not expose native file watching')
    source = tmp_path / 'source.mkv'; source.write_bytes(b'hardlink event')
    target = existing.parent / 'new.mkv'
    try:
        os.link(source, target)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and str(target) not in p._live_queue:
            time.sleep(.02)
        assert str(target) in p._live_queue
    finally:
        p._stop_monitor()


def test_live_tick_runs_existing_background_worker(host, tmp_path, monkeypatch):
    import threading
    p, path = plugin(host, tmp_path)
    c = Client({'ok': True}); configure_client(p, c, monkeypatch)
    p.on_transfer_complete(event(path)); ready(p, path)
    monkeypatch.setattr(p, '_enqueue', lambda kind: host.runtime.RuntimeMixin._enqueue(p, kind))
    p._live_tick(p._generation)
    worker = p._worker
    if worker:
        worker.join(timeout=3)
        assert not worker.is_alive()
    assert len(c.calls) == 1 and not p._live_queue
    assert p.storage['state_v2']['live_queue'] == []
