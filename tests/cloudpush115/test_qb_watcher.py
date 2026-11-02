"""qB regressions: fake WebAPI and real temporary files, never contact a server."""
import importlib
import sys
import types
from copy import deepcopy
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2] / 'plugins.v2' / 'cloudpush115'


@pytest.fixture
def qbmods(monkeypatch):
    package = types.ModuleType('qb_test_cp115')
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, 'qb_test_cp115', package)
    for name in list(sys.modules):
        if name.startswith('qb_test_cp115.'):
            monkeypatch.delitem(sys.modules, name)
    watcher = importlib.import_module('qb_test_cp115.qb_watcher')
    client = importlib.import_module('qb_test_cp115.qb_client')
    clock = {'mono': 0.0, 'wall': 1000.0}
    monkeypatch.setattr(watcher.time, 'monotonic', lambda: clock['mono'])
    monkeypatch.setattr(watcher.time, 'time', lambda: clock['wall'])
    return types.SimpleNamespace(w=watcher, c=client, clock=clock)


class QB:
    def __init__(self, torrents, files):
        self.torrents, self.files = torrents, files
        self.tags, self.reads, self.fail_tags = [], [], False
    def completed_torrents(self, done_tag='已整理'):
        return deepcopy([t for t in self.torrents if t['hash'] not in self.tags])
    def torrents_files(self, ident):
        self.reads.append(ident)
        return deepcopy(self.files[ident])
    def set_tag(self, ident, tag):
        if self.fail_tags:
            raise RuntimeError('tag unavailable')
        self.tags.append(ident)


def torrent(root, ident='abc', name='movie.mkv', size=4, **extra):
    return {'hash': ident, 'name': name, 'progress': 1, 'save_path': str(root),
            'content_path': str(root / name), **extra}


def file(name='movie.mkv', size=4, **extra):
    return {'name': name, 'size': size, 'progress': 1, 'priority': 1, **extra}


def test_first_sample_waits_then_succeeds_and_reports_reason(qbmods, tmp_path):
    (tmp_path / 'movie.mkv').write_bytes(b'test')
    qb = QB([torrent(tmp_path)], {'abc': [file()]})
    pushed, tasks, logs = [], [], []
    watcher = qbmods.w.QBWatcher(qb, lambda p, d: pushed.append((p, d)) or {'ok': True},
                               stable_interval=5, status_callback=tasks.append, logger=logs.append)
    watcher.process_once('/Remote')
    assert pushed == [] and not qb.tags
    assert '首次稳定观察' in watcher.snapshot()[0]['message']
    qbmods.clock['mono'] = 4.9
    watcher.process_once('/Remote')
    assert pushed == []
    qbmods.clock['mono'] = 5
    stats = watcher.process_once('/Remote')
    assert stats['pushed'] == 1 and qb.tags == ['abc'] and len(pushed) == 1
    assert watcher.snapshot()[0]['status'] == 'success'
    assert tasks[0]['id'] == 'abc' and all('message' in x for x in tasks)


def test_zero_stability_delay_is_effective(qbmods, tmp_path):
    (tmp_path / 'movie.mkv').write_bytes(b'test')
    qb = QB([torrent(tmp_path)], {'abc': [file()]})
    watcher = qbmods.w.QBWatcher(qb, lambda *a: {'ok': True}, stable_interval=0)
    assert watcher.process_once()['pushed'] == 1


def test_same_size_mtime_change_restarts_stable_period(qbmods, tmp_path):
    path = tmp_path / 'movie.mkv'
    path.write_bytes(b'test')
    qb = QB([torrent(tmp_path)], {'abc': [file()]})
    watcher = qbmods.w.QBWatcher(qb, lambda *a: {'ok': True}, stable_interval=5)
    watcher.process_once()
    before = path.stat().st_mtime_ns
    import os
    os.utime(path, ns=(before, before + 100_000_000))
    qbmods.clock['mono'] = 6
    watcher.process_once()
    assert not qb.tags and '修改时间有变化' in watcher.snapshot()[0]['message']
    qbmods.clock['mono'] = 11
    watcher.process_once()
    assert qb.tags == ['abc']


def test_missing_one_of_two_manifest_files_never_tags_partial_torrent(qbmods, tmp_path):
    (tmp_path / 'Present.mkv').write_bytes(b'test')
    qb = QB([torrent(tmp_path, name='Bundle')], {'abc': [file('Present.mkv'), file('Missing.mkv')]})
    pushed = []
    watcher = qbmods.w.QBWatcher(qb, lambda *a: pushed.append(a) or {'ok': True}, stable_interval=0)
    watcher.process_once()
    snap = watcher.snapshot()[0]
    assert snap['ready'] == 1 and snap['total'] == 2
    assert '不存在' in snap['message'] and 'Missing.mkv' in snap['message']
    assert not pushed and not qb.tags


def test_explicit_mapping_longest_prefix_and_component_boundary(qbmods, tmp_path):
    deep = tmp_path / 'mapped'
    deep.mkdir(); (deep / 'movie.mkv').write_bytes(b'test')
    qb = QB([torrent(Path('/qb/downloads/films'))], {'abc': [file()]})
    paths = []
    watcher = qbmods.w.QBWatcher(qb, lambda p,d: paths.append(str(p)) or {'ok': True}, stable_interval=0,
                               path_mappings=f'/qb=>{tmp_path}/wrong\n/qb/downloads/films=>{deep}')
    watcher.process_once()
    assert paths == [str(deep / 'movie.mkv')] and qb.tags
    assert str(watcher._mapped('/qbad/movie.mkv')) == '/qbad/movie.mkv'
    with pytest.raises(ValueError):
        qbmods.w.QBWatcher(qb, lambda *a: None, path_mappings='bad mapping')


def test_unstable_front_twenty_do_not_starve_task_twenty_one(qbmods, tmp_path):
    torrents, files = [], {}
    for n in range(21):
        name, ident = f'{n}.mkv', str(n)
        torrents.append(torrent(tmp_path, ident, name))
        files[ident] = [file(name)]
    (tmp_path / '20.mkv').write_bytes(b'test')
    qb = QB(torrents, files)
    watcher = qbmods.w.QBWatcher(qb, lambda *a: {'ok': True}, stable_interval=0)
    watcher.process_once(max_torrents=20)
    assert not qb.tags
    watcher.process_once(max_torrents=20)
    assert '20' in qb.tags


def test_tag_failure_retries_tag_without_reupload(qbmods, tmp_path):
    (tmp_path / 'movie.mkv').write_bytes(b'test')
    qb = QB([torrent(tmp_path)], {'abc': [file()]})
    qb.fail_tags = True
    pushed = []
    watcher = qbmods.w.QBWatcher(qb, lambda *a: pushed.append(a) or {'ok': True}, stable_interval=0, retry_interval=30)
    assert watcher.process_once()['failed'] == 1
    assert len(pushed) == 1 and watcher.snapshot()[0]['next_retry'] == 1030
    watcher.process_once()
    assert len(qb.reads) == 1
    qb.fail_tags = False; qbmods.clock['wall'] = 1030
    assert watcher.process_once()['pushed'] == 1
    assert len(pushed) == 1 and qb.tags == ['abc']


def test_failed_files_respect_retry_interval_and_do_not_hide_other_files(qbmods, tmp_path):
    for name in ('a.mkv', 'b.mkv'):
        (tmp_path / name).write_bytes(b'test')
    qb = QB([torrent(tmp_path, name='Bundle')], {'abc': [file('a.mkv'), file('b.mkv')]})
    calls = []
    def push(path, target):
        calls.append(path.name)
        return {'ok': path.name == 'a.mkv', 'message': 'server failure'}
    watcher = qbmods.w.QBWatcher(qb, push, stable_interval=0, retry_interval=90)
    watcher.process_once()
    assert calls == ['a.mkv', 'b.mkv'] and not qb.tags
    watcher.process_once()
    assert calls == ['a.mkv', 'b.mkv']
    qbmods.clock['wall'] = 1090
    watcher.process_once()
    assert calls == ['a.mkv', 'b.mkv', 'b.mkv']
    assert watcher.snapshot()[0]['attempts'] == 2


def test_missing_and_incomplete_diagnostics_are_distinct(qbmods, tmp_path):
    p = tmp_path / 'movie.mkv'; p.write_bytes(b'xx')
    qb = QB([torrent(tmp_path)], {'abc': [file(progress=0.9)]})
    watcher = qbmods.w.QBWatcher(qb, lambda *a: {'ok': True}, stable_interval=0)
    watcher.process_once(); assert '尚未完成' in watcher.snapshot()[0]['message']
    qb.files['abc'][0]['progress'] = 1
    watcher.process_once(); assert '大小未就绪' in watcher.snapshot()[0]['message']
    p.unlink()
    watcher.process_once(); assert '不存在' in watcher.snapshot()[0]['message']
    assert qb.tags == []


def test_selected_media_only_policy_and_no_media_task_not_tagged(qbmods, tmp_path):
    (tmp_path / 'movie.mkv').write_bytes(b'test')
    qb = QB([torrent(tmp_path)], {'abc': [file(), file('unselected.mkv', priority=0)]})
    watcher = qbmods.w.QBWatcher(qb, lambda *a: {'ok': True}, stable_interval=0)
    assert watcher.process_once()['pushed'] == 1
    qb = QB([torrent(tmp_path)], {'abc': [file(priority=0)]})
    watcher = qbmods.w.QBWatcher(qb, lambda *a: pytest.fail('unselected file pushed'), stable_interval=0)
    assert watcher.process_once()['skipped'] == 1 and not qb.tags


def test_snapshot_is_copy_and_waiting_messages_do_not_spam(qbmods, tmp_path):
    qb = QB([torrent(tmp_path)], {'abc': [file()]})
    logs = []
    watcher = qbmods.w.QBWatcher(qb, lambda *a: {'ok': True}, logger=logs.append)
    watcher.process_once(); first = len(logs)
    for _ in range(5):
        watcher.process_once()
    assert len(logs) == first
    snap = watcher.snapshot(); snap[0]['files'][0]['path'] = 'changed'
    assert watcher.snapshot()[0]['files'][0]['path'] != 'changed'
    qb.torrents = []
    watcher.process_once()
    assert watcher.snapshot() == []


def test_manifest_path_traversal_is_rejected(qbmods, tmp_path):
    qb = QB([torrent(tmp_path)], {'abc': [file('../outside.mkv')]})
    watcher = qbmods.w.QBWatcher(qb, lambda *a: pytest.fail('invalid path pushed'), stable_interval=0)
    assert watcher.process_once()['failed'] == 1
    assert '不合法相对路径' in watcher.snapshot()[0]['message']


def test_skipped_upload_does_not_tag_or_poll_115_forever(qbmods, tmp_path):
    (tmp_path / 'movie.mkv').write_bytes(b'test')
    qb = QB([torrent(tmp_path)], {'abc': [file()]})
    calls = []
    watcher = qbmods.w.QBWatcher(qb, lambda *a: calls.append(a) or {'ok': False, 'skipped': True, 'message': 'not found'}, stable_interval=0)
    watcher.process_once(); watcher.process_once()
    assert len(calls) == 1 and not qb.tags and watcher.snapshot()[0]['status'] == 'skipped'


def test_client_does_not_treat_bad_progress_as_complete(qbmods, monkeypatch):
    client = qbmods.c.QBClient('http://qb')
    data = [{'hash': str(n), 'tags': '', 'progress': val} for n, val in enumerate([1, 0.9999, None, 'bad', float('nan'), float('inf')])]
    data += [{'hash': 'tagged', 'progress': 1, 'tags': ' 已整理, sonarr'}]
    monkeypatch.setattr(client, 'torrents_info', lambda **kw: data)
    assert [x['hash'] for x in client.completed_torrents()] == ['0']


def test_client_reauths_expired_session_once(qbmods, monkeypatch):
    client = qbmods.c.QBClient('http://qb', 'user', 'testpassword')
    client._logged_in = True
    count = []
    def request(path, data=None, method='GET', raw=False):
        count.append((path, method))
        if path == 'auth/login': return 'Ok.'
        if sum(p == path for p, _ in count) == 1: raise qbmods.c.QBAuthError('expired')
        return []
    monkeypatch.setattr(client, '_request', request)
    assert client.torrents_info() == []
    assert count == [('torrents/info', 'GET'), ('auth/login', 'POST'), ('torrents/info', 'GET')]


def test_client_bad_json_structure_not_silent_empty(qbmods, monkeypatch):
    client = qbmods.c.QBClient('http://qb')
    client._logged_in = True
    monkeypatch.setattr(client, '_request', lambda *a, **kw: '<html>login</html>')
    with pytest.raises(qbmods.c.QBError, match='不是JSON数组'):
        client.torrents_info()
    with pytest.raises(qbmods.c.QBError, match='不是JSON数组'):
        client.torrents_files('hash')
