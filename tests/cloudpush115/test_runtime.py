"""Real plugin classes with only the MoviePilot host and network replaced."""
from __future__ import annotations
from copy import deepcopy
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[2] / "plugins.v2" / "cloudpush115"


@pytest.fixture
def host(monkeypatch):
    def module(name, **values):
        result = types.ModuleType(name)
        result.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    class Base:
        def __init__(self):
            self.storage, self.config_store = {}, {}
            self.writes = []
        def get_data(self, key):
            return deepcopy(self.storage.get(key))
        def save_data(self, key, value):
            # Simulate durable serialization, not aliasing the caller's Python dict.
            value = json.loads(json.dumps(value, ensure_ascii=False))
            self.storage[key] = value
            self.writes.append((key, value))
        def update_config(self, value):
            self.config_store = deepcopy(value)
            return True
        def post_message(self, **kwargs):
            self.message = kwargs

    class Scheduler:
        def __init__(self, *args, **kwargs):
            self.jobs, self.running = [], False
        def add_job(self, fn, *args, **kwargs):
            self.jobs.append((fn, args, kwargs))
        def start(self):
            self.running = True
        def shutdown(self, wait=False):
            self.running = False

    module("app")
    module("app.plugins", _PluginBase=Base)
    module("app.core")
    module("app.core.config", settings=types.SimpleNamespace(TZ="UTC"))
    module("app.core.event", Event=object, eventmanager=types.SimpleNamespace(register=lambda *a, **kw: lambda fn: fn))
    module("app.log", logger=logging.getLogger("cp115-tests"))
    module("app.schemas")
    module("app.schemas.types", EventType=types.SimpleNamespace(PluginAction="PluginAction"), NotificationType=types.SimpleNamespace(Plugin="Plugin"))
    name = "cp115_test_host"
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            monkeypatch.delitem(sys.modules, key)
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, package)
    spec.loader.exec_module(package)
    runtime = sys.modules[name + ".runtime"]
    monkeypatch.setattr(runtime, "BackgroundScheduler", Scheduler)

    def factory(config=None, storage=None):
        plugin = package.CloudPush115()
        if storage is not None:
            plugin.storage = deepcopy(storage)
        plugin.enqueued = []
        monkeypatch.setattr(plugin, "_enqueue", lambda kind: plugin.enqueued.append(kind) or True)
        plugin.init_plugin(config or {})
        return plugin

    return types.SimpleNamespace(new=factory, runtime=runtime, package=package,
                                 config=sys.modules[name + ".config"], ui=sys.modules[name + ".ui"])


def nodes(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from nodes(item)


def text_of(value):
    return "\n".join(str(x["text"]) for x in nodes(value) if "text" in x)


class Client:
    def __init__(self, answer=None):
        self.answer, self.targets, self.calls = answer, [], []
    def get_dir_id_by_path(self, path):
        self.targets.append(path)
        return len(self.targets)
    def push_file(self, path, remote_id):
        self.calls.append((str(path), remote_id))
        return self.answer(path) if callable(self.answer) else (self.answer or {"ok": True, "message": "秒传成功", "reuse": True})


def configure_client(plugin, client, monkeypatch):
    monkeypatch.setattr(plugin, "_make_client", lambda cfg=None: client)


def test_manual_config_migration_and_once_full_replacement(host):
    original = {"enabled": True, "onlyonce": True, "cookie": "UID=123_A; CID=xxx; SEID=yyy",
                "watch_paths": ["/Movies", "/TV"], "remote_dir": "/Films", "qb_settle": 0,
                "qb_password": "test-password", "scan_interval": "19", "notify": True,
                "extension_option": {"keep": 1}}
    p = host.new(original)
    saved = p.config_store
    assert saved["onlyonce"] is False and saved["cookie"] == original["cookie"]
    assert saved["watch_paths"] == "/Movies\n/TV" and saved["qb_password"] == original["qb_password"]
    assert saved["qb_settle"] == 0 and saved["extension_option"] == {"keep": 1}
    assert "scan" in p.enqueued
    p2 = host.new(saved, p.storage)
    assert p2._current_config() == saved
    form, default = p.get_form()
    fields = {x["props"]["model"]: x for x in nodes(form) if x.get("props", {}).get("model")}
    assert fields["watch_paths"]["component"] == "VTextarea"
    assert default["watch_paths"] == "" and "access_token" not in fields
    assert fields['failure_move_on']['component'] == 'VSelect'
    assert not any(x.get('component') == 'VSelect' and x.get('props', {}).get('model') != 'failure_move_on' for x in nodes(form))
    assert not any(x.get("component") in {"VHtml", "VExpansionPanels"} for x in nodes(form))


def test_legacy_success_retry_migrate_and_render_actual_text(host):
    storage = {"history": [None, {"path": "/m/a.mkv", "name": "success.mkv", "size": "1.5GB", "result": "成功", "message": "actual success", "time": "2026-01-01 01:02:03"},
                           {"name": "poll", "result": "qB状态", "message": "waiting"}],
               "retry_queue": [{"path": "/m/f.mkv", "name": "failed.mkv", "attempts": 2, "next_retry": 123456, "last_error": "network timeout", "remote_dir": "/Original"}],
               "done_files": ["/m/a.mkv"]}
    p = host.new({}, storage)
    snap = p._snapshot()
    assert len(snap["history"]) == 1 and snap["history"][0]["size"] == 1610612736
    assert snap["retry_queue"][0]["remote_dir"] == "/Original"
    page = p.get_page()
    assert all(t in text_of(page) for t in ("success.mkv", "failed.mkv", "network timeout", "整理条目", "本地待处理队列"))
    assert not any(n.get("component") in {"VDataTable", "VHtml"} for n in nodes(page))
    assert any(n.get("component") == "tbody" for n in nodes(page))
    assert any(n.get("component") == "tr" for n in nodes(page))
    assert storage["history"] == p.storage["history"]  # old records retained for rollback


def test_empty_sections_are_visible_even_when_plugin_disabled(host):
    p = host.new()
    page = text_of(p.get_page())
    assert all(title in page for title in ("整理条目", "待重试队列", "本地待处理队列", "本地监控路径", "qB 联动任务"))
    assert "尚无秒传结果" in page and "尚未完成本地索引" in page
    col, attrs, contents = p.get_dashboard("main")
    assert attrs["refresh"] == 10 and "本地待处理队列" in text_of(contents)
    assert p.get_dashboard("not-a-key") is None


def test_read_pages_never_scan_network_or_write(host, monkeypatch):
    p = host.new({"watch_paths": "/media", "cookie": "Cookie-for-test"})
    before = deepcopy(p.storage)
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected IO while reading page")
    monkeypatch.setattr(host.runtime.os, "scandir", forbidden)
    monkeypatch.setattr(host.runtime, "P115WebClient", forbidden)
    monkeypatch.setattr(p, "save_data", forbidden)
    for _ in range(3):
        p.get_form(); p.get_page(); p.get_dashboard("main"); p.api_status()
    assert p.storage == before


def test_index_success_retry_and_live_processing_snapshots(host, tmp_path, monkeypatch):
    root = tmp_path / "media"
    root.mkdir()
    good, bad, remaining = root / "good.mkv", root / "bad.mkv", root / "remaining.srt"
    for f in (good, bad, remaining):
        f.write_bytes(b"abcdef")
    p = host.new({"enabled": True, "watch_paths": str(root), "cookie": "UID=123_A; CID=x; SEID=y", "remote_dir": "/Target", "retry_interval": 600})
    assert p._index_local(p._config, p._generation)
    snap = p._snapshot()
    assert snap["stats"]["local"] == 3 and snap["stats"]["indexed"] == 3
    assert {x['name'] for x in snap['local_queue']} == {good.name, bad.name, remaining.name}
    in_flight = []
    def answer(path):
        in_flight.append(p._snapshot())
        return {"ok": path.name != "bad.mkv", "message": "bad network" if path.name == "bad.mkv" else "秒传成功"}
    client = Client(answer)
    configure_client(p, client, monkeypatch)
    p._pending_jobs[("scan", p._generation)] = None
    p._drain_jobs()
    assert all(any(x['status'] == 'processing' for x in x['local_queue']) for x in in_flight)
    snap = p._snapshot()
    assert snap['stats']['success'] == 2 and snap['retry_count'] == 1 and len(snap['history']) == 3
    assert snap['retry_queue'][0]['name'] == 'bad.mkv' and snap['retry_queue'][0]['message'] == 'bad network'
    count = len(client.calls)
    p._run_retries(p._config, p._generation)
    assert len(client.calls) == count  # Not before the user-configured interval.
    p._index_local(p._config, p._generation)
    p._upload_local(p._config, p._generation)
    assert len(client.calls) == count  # No bypass of retry interval through full scan.
    p._queue.pending[str(bad)]['next_retry'] = 0
    client.answer = {'ok': True, 'message': 'retry success'}
    p._run_retries(p._config, p._generation)
    assert p._snapshot()['retry_count'] == 0
    assert p._snapshot()['stats']['success'] == 3
    assert 'retry success' in text_of(p.get_page())
    assert p.storage['state_v2']['history'][-1]['status'] == 'success'


def test_only_index_does_not_upload_and_survives_restart(host, tmp_path, monkeypatch):
    file = tmp_path / "test.mkv"
    file.write_bytes(b"ab")
    p = host.new({"watch_paths": str(tmp_path)})
    monkeypatch.setattr(p, '_make_client', lambda cfg: pytest.fail('index called cloud'))
    p._index_local(p._config, p._generation)
    assert p._snapshot()['local_queue'][0]['status'] == 'blocked'
    p._upload_local(p._config, p._generation)
    assert not p._snapshot()['history']
    p2 = host.new(p._config, p.storage)
    assert p2._snapshot()['local_queue'][0]['name'] == 'test.mkv'
    assert 'test.mkv' in text_of(p2.get_dashboard('main')[2])


def test_target_failure_stays_on_requested_directory(host, tmp_path, monkeypatch):
    f = tmp_path / 'movie.mkv'
    f.write_bytes(b'test')
    p = host.new({'cookie': 'UID=1_A; CID=x; SEID=y', 'watch_paths': str(tmp_path), 'remote_dir': '/Wrong'})
    class Broken(Client):
        def get_dir_id_by_path(self, path):
            raise host.runtime.P115WebError('directory unavailable')
    client = Broken()
    configure_client(p, client, monkeypatch)
    p._index_local(p._config, p._generation)
    p._upload_local(p._config, p._generation)
    assert client.calls == []
    snap = p._snapshot()
    assert snap['retry_queue'][0]['remote_dir'] == '/Wrong'
    assert 'directory unavailable' in snap['history'][0]['message']
    assert 'NameError' not in str(snap)


def test_changed_file_or_target_invalidates_success_ledger(host, tmp_path, monkeypatch):
    file = tmp_path / 'movie.mkv'
    file.write_bytes(b'v1')
    p = host.new({'cookie': 'UID=1_A; CID=x; SEID=y', 'watch_paths': str(tmp_path), 'remote_dir': '/First'})
    client = Client()
    configure_client(p, client, monkeypatch)
    def scan():
        p._index_local(p._config, p._generation)
        p._upload_local(p._config, p._generation)
    scan(); scan()
    assert len(client.calls) == 1
    file.write_bytes(b'new edition larger')
    scan()
    assert len(client.calls) == 2
    p.init_plugin({**p._config, 'remote_dir': '/Second'})
    scan()
    assert len(client.calls) == 3 and client.targets == ['/First', '/Second']


def test_retry_preserves_original_target_and_exhaustion(host, tmp_path, monkeypatch):
    f = tmp_path / 'fail.mkv'
    f.write_bytes(b'fail')
    p = host.new({'cookie': 'UID=1_A; CID=x; SEID=y', 'watch_paths': str(tmp_path), 'remote_dir': '/Original', 'max_attempts': 1})
    client = Client({'ok': False, 'message': 'fail'})
    configure_client(p, client, monkeypatch)
    p._index_local(p._config, p._generation); p._upload_local(p._config, p._generation)
    p.init_plugin({**p._config, 'remote_dir': '/Changed'})
    p._queue.pending[str(f)]['next_retry'] = 0
    p._run_retries(p._config, p._generation)
    snap = p._snapshot()
    assert snap['retry_queue'][0]['status'] == 'exhausted'
    assert client.targets == ['/Original']
    before = len(client.calls)
    p._index_local(p._config, p._generation); p._upload_local(p._config, p._generation)
    p._run_retries(p._config, p._generation)
    assert len(client.calls) == before
    assert p.api_retry({'path': str(f)})['success']
    assert p._queue.get(str(f))['attempts'] == 0


def test_cfg_change_during_upload_does_not_mix_next_file(host, tmp_path, monkeypatch):
    for n in ('a.mkv', 'b.mkv'):
        (tmp_path / n).write_bytes(b'data')
    p = host.new({'cookie': 'UID=1_A; CID=x; SEID=y', 'watch_paths': str(tmp_path), 'remote_dir': '/Original'})
    def response(path):
        p.init_plugin({**p._config, 'remote_dir': '/New'})
        return {'ok': True, 'message': 'success with original config'}
    client = Client(response)
    configure_client(p, client, monkeypatch)
    cfg, gen = deepcopy(p._config), p._generation
    p._index_local(cfg, gen); p._upload_local(cfg, gen)
    assert len(client.calls) == 1
    assert p._snapshot()['history'][0]['remote_dir'] == '/Original'
    assert p._config['remote_dir'] == '/New'


def test_read_failure_does_not_overwrite_existing_persistent_data(host, monkeypatch):
    p = host.package.CloudPush115()
    original = {'history': [{'name': 'preserve', 'result': '成功'}]}
    p.storage = deepcopy(original)
    monkeypatch.setattr(p, 'get_data', lambda key: (_ for _ in ()).throw(OSError('db offline')))
    monkeypatch.setattr(p, '_enqueue', lambda kind: pytest.fail('must not execute after failed state read'))
    p.init_plugin({'enabled': True, 'watch_paths': '/media'})
    assert p.storage == original and p.writes == []
    assert '未覆盖原记录' in p.api_status()['storage_error']


def test_corrupt_new_state_never_replaced_with_empty_legacy(host):
    p = host.new(storage={'state_v2': {'schema': 'broken', 'history': ['valuable']}})
    assert p.storage['state_v2']['history'] == ['valuable']
    assert not p._loaded and not p.writes
    assert p.api_status()['storage_error']


def test_failed_persistence_preserves_memory_and_can_retry(host, monkeypatch):
    p = host.new()
    actual_save = p.save_data
    monkeypatch.setattr(p, 'save_data', lambda *a: False)
    p._append_history({'path': '/m.mkv', 'name': 'm.mkv', 'size': 2}, {'message': 'ok'}, True)
    assert p._snapshot()['history'][0]['name'] == 'm.mkv'
    assert p._snapshot()['storage_error']
    monkeypatch.setattr(p, 'save_data', actual_save)
    assert p._persist()
    assert p.storage['state_v2']['history'][0]['name'] == 'm.mkv'
    assert not p._snapshot()['storage_error']


def test_history_is_not_poll_log_and_instances_isolate_mutable_state(host):
    a, b = host.new(), host.new()
    a._append_history({'path': '/good', 'name': 'good'}, {'message': 'success'}, True)
    for i in range(1000):
        a._qb_log('waiting again')
        a._qb_status({'id': 'one', 'name': 'qb task', 'status': 'waiting', 'message': '首次观察', 'ready': 0, 'total': 1})
    assert len(a._history) == 1 and a._snapshot()['stats']['qb'] == 1
    assert not b._history and not b._qb_tasks and a._state_lock is not b._state_lock
    assert '首次观察' in text_of(a.get_page())


def test_scope_change_blocks_old_retry_without_sending(host, tmp_path, monkeypatch):
    f = tmp_path / 'm.mkv'; f.write_bytes(b'test')
    p = host.new({'cookie': 'UID=1_A; CID=x; SEID=y', 'watch_paths': str(tmp_path)})
    failed = Client({'ok': False, 'message': 'fail'})
    configure_client(p, failed, monkeypatch)
    p._index_local(p._config, p._generation); p._upload_local(p._config, p._generation)
    p.init_plugin({**p._config, 'cookie': 'UID=2_A; CID=x; SEID=y'})
    p._queue.pending[str(f)]['next_retry'] = 0
    p._run_retries(p._config, p._generation)
    assert len(failed.calls) == 1 and p._snapshot()['retry_queue'][0]['status'] == 'blocked'


def test_missing_root_visible_without_erasing_old_queue(host, tmp_path):
    root = tmp_path / 'share'; root.mkdir()
    f = root / 'file.mkv'; f.write_bytes(b'data')
    p = host.new({'watch_paths': str(root)})
    p._index_local(p._config, p._generation)
    f.unlink(); root.rmdir()
    p._index_local(p._config, p._generation)
    data = p._snapshot()
    assert data['roots'][0]['status'] == 'error'
    assert data['local_queue'][0]['name'] == 'file.mkv'
    assert data['local_queue'][0]['status'] == 'blocked'


def test_unreadable_or_bad_history_rows_do_not_blank_page(host):
    p = host.new(storage={'history': [None, 'bad', {}, {'path': {}, 'name': 'broken-size', 'size': '... GB', 'result': '失败'},
                                      {'name': 'valid', 'result': '成功', 'size': '2.2MB'}]})
    assert 'valid' in text_of(p.get_page())
    assert p._snapshot()['history'][0]['size'] == int(2.2 * 1024 ** 2)
    assert host.config.integer(1782909083456723789) == 1782909083456723789
    assert host.config.byte_size('9007199254740993') == 9007199254740993


def test_api_contract_get_is_readonly_post_body_accepted(host):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    p = host.new({'watch_paths': '/media'})
    app = FastAPI()
    for route in p.get_api():
        app.add_api_route('/api/v1/plugin/CloudPush115' + route['path'], route['endpoint'], methods=route['methods'])
    client = TestClient(app)
    initial = deepcopy(p.storage)
    assert client.get('/api/v1/plugin/CloudPush115/status').json()['schema'] == 2
    assert client.get('/api/v1/plugin/CloudPush115/refresh').json()['success']
    assert client.get('/api/v1/plugin/CloudPush115/scan').status_code == 405
    assert p.storage == initial
    assert client.post('/api/v1/plugin/CloudPush115/index', json={}).json()['success']
    assert p.enqueued[-1] == 'index'
    assert client.post('/api/v1/plugin/CloudPush115/scan', json={}).json()['success']
    assert client.post('/api/v1/plugin/CloudPush115/retry', json={'path': '/missing'}).status_code == 200


def test_only_details_have_action_buttons_dashboard_no_dead_controls(host):
    p = host.new()
    detail_actions = [x for x in nodes(p.get_page()) if x.get('events')]
    dashboard_actions = [x for x in nodes(p.get_dashboard('main')[2]) if x.get('events')]
    assert len(detail_actions) == 4 and dashboard_actions == []
    assert any(x['events']['click']['api'].endswith('/refresh') for x in detail_actions)


def test_background_jobs_serialized_and_stop_cancels_queued_work(host, monkeypatch):
    import threading
    p = host.new()
    calls = []
    entered, release = threading.Event(), threading.Event()
    def blocked_index(cfg, gen):
        calls.append(('index', gen)); entered.set(); release.wait(2)
        return p._is_current(gen)
    monkeypatch.setattr(p, '_index_local', blocked_index)
    monkeypatch.setattr(p, '_upload_local', lambda *a: calls.append(('upload', a[1])))
    enqueue = host.runtime.RuntimeMixin._enqueue.__get__(p)
    assert enqueue('index')
    assert entered.wait(2)
    for _ in range(30):
        enqueue('scan')
    assert len(p._pending_jobs) == 1
    worker = p._worker
    p.stop_service(); release.set(); worker.join(3)
    assert not worker.is_alive() and [x[0] for x in calls] == ['index']
    assert not p._pending_jobs and not p._running


def test_checkpoint_reloads_success_without_duplicate_transfer(host, tmp_path, monkeypatch):
    f = tmp_path / 'movie.mkv'; f.write_bytes(b'test')
    cfg = {'cookie': 'UID=1_A; CID=x; SEID=y', 'watch_paths': str(tmp_path), 'remote_dir': '/Original'}
    p = host.new(cfg)
    first = Client(); configure_client(p, first, monkeypatch)
    p._index_local(p._config, p._generation); p._upload_local(p._config, p._generation)
    p2 = host.new(p._config, p.storage)
    later = Client(); configure_client(p2, later, monkeypatch)
    p2._index_local(p2._config, p2._generation); p2._upload_local(p2._config, p2._generation)
    assert later.calls == [] and p2._snapshot()['done_count'] == 1
    assert 'movie.mkv' in text_of(p2.get_page())


@pytest.mark.parametrize('code,expected', [(1, True), (0, False), (6, False), (401, False), (None, False)])
def test_unknown_115_status_not_misreported_as_server_miss(host, tmp_path, monkeypatch, code, expected):
    f = tmp_path / 'probe.mkv'; f.write_bytes(b'abc')
    client = host.runtime.P115WebClient.__new__(host.runtime.P115WebClient)
    monkeypatch.setattr(client, 'upload_init', lambda body: {'status': code, 'message': 'test response'})
    result = client.push_file(f)
    assert result['ok'] is False and result['not_found'] is expected
    if not expected:
        assert '未命中秒传' not in result['message']


def test_second_signature_rejects_file_changed_during_challenge(host, tmp_path, monkeypatch):
    f = tmp_path / 'probe.mkv'; f.write_bytes(b'abc')
    client = host.runtime.P115WebClient.__new__(host.runtime.P115WebClient)
    calls = []
    def init(payload):
        calls.append(payload)
        f.write_bytes(b'changed')
        return {'status': 7, 'sign_key': 'synthetic', 'sign_check': '0-1'}
    monkeypatch.setattr(client, 'upload_init', init)
    result = client.push_file(f)
    assert result['ok'] is False and '二次校验失败' in result['message']
    assert len(calls) == 1


def test_empty_files_are_skipped_without_network(host, tmp_path, monkeypatch):
    f = tmp_path / 'empty.mkv'; f.touch()
    client = host.runtime.P115WebClient.__new__(host.runtime.P115WebClient)
    monkeypatch.setattr(client, 'upload_init', lambda *a: pytest.fail('empty file sent'))
    assert client.push_file(f)['skipped'] is True


def test_qb_diagnostics_are_durable_and_distinct_from_transfers(host, monkeypatch):
    p = host.new({'cookie': 'UID=1_A; CID=x; SEID=y', 'qb_enabled': True, 'qb_host': 'http://qb'})
    class Watcher:
        def __init__(self, client, callback, **kwargs):
            self.status = kwargs['status_callback']
        def process_once(self, remote_dir=''):
            self.status(self.snapshot()[0])
        def snapshot(self):
            return [{'id': 'test-hash', 'name': 'Task.Waiting.mkv', 'path': '/qb/Task.Waiting.mkv', 'source': 'qb', 'ready': 0, 'total': 1,
                     'status': 'waiting', 'message': 'MP内文件不存在，请核对挂载和路径映射'}]
    monkeypatch.setattr(host.runtime, 'QBWatcher', Watcher)
    p._run_qb(p._config, p._generation); p._persist()
    data = p._snapshot()
    assert len(data['qb_queue']) == 1 and not data['history']
    assert 'Task.Waiting.mkv' in text_of(p.get_page())
    assert '路径映射' in text_of(p.get_page())
    p2 = host.new(p._config, p.storage)
    assert p2._snapshot()['qb_queue'][0]['ready'] == 0
