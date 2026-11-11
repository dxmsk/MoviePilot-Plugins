import importlib
from pathlib import Path
import pytest
from test_runtime import host, Client, configure_client


def setup(host, tmp_path, **kw):
    root = tmp_path / 'media'
    root.mkdir()
    path = root / 'a.mkv'
    path.write_bytes(b'fixture')
    cfg = {'cookie': 'UID=fixture', 'watch_paths': str(root), **kw}
    plugin = host.new(cfg)
    return plugin, path


@pytest.mark.parametrize('delete', [False, True])
def test_cloud_delete_opt_in(host, tmp_path, monkeypatch, delete):
    p, path = setup(host, tmp_path, delete_on_success=delete)
    configure_client(p, Client(), monkeypatch)
    result = p._transfer(p._file_item(str(path)), p._config)
    assert result['ok'] is True and path.exists() is not delete
    assert p._history[-1]['status'] == 'success'


def test_cloud_delete_error_is_success(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, delete_on_success=True)
    configure_client(p, Client(), monkeypatch)
    actions = importlib.import_module(type(p).__module__ + '.actions')
    monkeypatch.setattr(actions, 'delete_source', lambda *a: (_ for _ in ()).throw(PermissionError('denied')))
    result = p._transfer(p._file_item(str(path)), p._config)
    assert result['ok'] is True and result['delete_status'] == 'failed' and path.exists()
    assert p._history[-1]['status'] == 'success'


def test_cloud_move_retry_and_no_repeated_move(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, failure_move_enabled=True, failure_move_on='each_failure', failure_move_dir=str(tmp_path / 'failed'))
    client = Client({'ok': False, 'message': 'timeout'})
    configure_client(p, client, monkeypatch)
    p._index_local(p._config, p._generation)
    first = p._transfer(p._file_item(str(path)), p._config)
    moved = first['path']
    assert not path.exists() and Path(moved).exists()
    assert str(path) not in p._queue.pending and moved in p._queue.pending
    p._index_local(p._config, p._generation)
    assert moved in p._inventory
    p._transfer(p._queue.get(moved), p._config, source='retry')
    assert len(list((tmp_path / 'failed').iterdir())) == 1
    client.answer = {'ok': True}
    assert p._transfer(p._queue.get(moved), p._config, source='retry')['ok'] is True
    assert not p._queue.pending


def test_exhausted_moves_after_retry_budget(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, max_attempts=1, failure_move_enabled=True,
        failure_move_on='exhausted', failure_move_dir=str(tmp_path / 'failed'))
    configure_client(p, Client({'ok': False}), monkeypatch)
    p._transfer(p._file_item(str(path)), p._config)
    assert path.exists()
    result = p._transfer(p._queue.get(str(path)), p._config, source='retry')
    assert not path.exists() and p._queue.get(result['path'])['status'] == 'exhausted'


def test_qb_deleted_file_resolves_after_restart(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, delete_on_success=True)
    configure_client(p, Client(), monkeypatch)
    size = path.stat().st_size
    assert p._transfer(p._file_item(str(path)), p._config, source='qb')['ok'] is True
    restored = host.new(p._config, p.storage)
    resolved = restored._resolve_qb_file({'path': str(path), 'size': size, 'progress': 1}, '/')
    assert resolved['confirmed'] and resolved['ready']
    wrong = restored._resolve_qb_file({'path': str(path), 'size': size + 1, 'progress': 1}, '/')
    assert not wrong.get('confirmed')


def test_qb_move_keeps_original_association(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, failure_move_enabled=True, failure_move_on='each_failure', failure_move_dir=str(tmp_path / 'failed'))
    configure_client(p, Client({'ok': False}), monkeypatch)
    result = p._transfer(p._file_item(str(path)), p._config, source='qb')
    restored = host.new(p._config, p.storage)
    resolved = restored._resolve_qb_file({'path': str(path), 'size': 7, 'progress': 1}, '/')
    assert resolved['path'] == result['path'] and Path(resolved['path']).exists()
    assert not resolved.get('confirmed')


def test_archive_configuration_boundary(host, tmp_path):
    normalize = host.config.normalize_config
    with pytest.raises(ValueError):
        normalize({'failure_move_enabled': True, 'failure_move_dir': str(tmp_path), 'max_attempts': 0})
    with pytest.raises(ValueError):
        normalize({'failure_move_enabled': True, 'failure_move_on': 'each_failure', 'failure_move_dir': str(tmp_path / 'failed'), 'watch_paths': str(tmp_path)})


def test_scheduler_qb_generation_contract(host, monkeypatch):
    p = host.new({'qb_enabled': True})
    calls = []
    monkeypatch.setattr(p, '_run_qb', lambda cfg, gen: calls.append(gen))
    fn, args, kw = next(job for job in p._scheduler.jobs if job[2]['id'] == 'cloudpush115_qb')
    fn(*kw['args'])
    assert calls == [p._generation]


def test_qb_partial_delete_restart_then_all_success(host, tmp_path, monkeypatch):
    from test_qb_watcher import QB, torrent, file
    p, first = setup(host, tmp_path, delete_on_success=True)
    second = first.with_name('b.mkv')
    second.write_bytes(b'fixture')
    client = Client(lambda path: {'ok': path.name == 'a.mkv'})
    configure_client(p, client, monkeypatch)
    qb = QB([torrent(first.parent, name='Bundle')], {'abc': [file('a.mkv', 7), file('b.mkv', 7)]})
    watcher_type = importlib.import_module(type(p).__module__ + '.qb_watcher').QBWatcher
    watcher = watcher_type(qb, p._qb_push_one, stable_interval=0, resolve_file=p._resolve_qb_file)
    assert watcher.process_once('/')['failed'] == 1
    assert not first.exists() and second.exists() and not qb.tags
    restored = host.new(p._config, p.storage)
    retry_client = Client()
    configure_client(restored, retry_client, monkeypatch)
    watcher = watcher_type(qb, restored._qb_push_one, stable_interval=0, resolve_file=restored._resolve_qb_file)
    assert watcher.process_once('/')['pushed'] == 1
    assert qb.tags == ['abc'] and not second.exists()
    assert len(retry_client.calls) == 1 and retry_client.calls[0][0] == str(second)


def test_cloud_changed_file_and_storage_failure_keep_source(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, delete_on_success=True, failure_move_enabled=True,
        failure_move_on='each_failure', failure_move_dir=str(tmp_path / 'failed'))
    def change(file):
        file.write_bytes(b'changed')
        return {'ok': True}
    configure_client(p, Client(change), monkeypatch)
    result = p._transfer(p._file_item(str(path)), p._config)
    assert not result['ok'] and result['move_status'] == 'failed' and path.exists()
    configure_client(p, Client(), monkeypatch)
    monkeypatch.setattr(p, 'save_data', lambda *a: False)
    result = p._transfer(p._file_item(str(path)), p._config)
    assert result['ok'] and result['delete_status'] == 'failed' and path.exists()


def test_stale_scan_snapshot_after_qb_delete_does_not_enqueue_missing(host, tmp_path, monkeypatch):
    p, path = setup(host, tmp_path, delete_on_success=True)
    client = Client()
    configure_client(p, client, monkeypatch)
    item = p._file_item(str(path))
    assert p._transfer(item, p._config, source='qb')['ok']
    assert p._transfer(item, p._config, source='local')['ok']
    assert not p._queue.pending and len(client.calls) == 1
