import importlib
import hashlib
import errno
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest


def modules(env):
    package = type(env.plugin).__module__
    return importlib.import_module(package + '.fileactions'), importlib.import_module(package + '.filehash')


def run(env, **options):
    cfg = dict(env.plugin._config)
    cfg.update(options)
    env.plugin.init_plugin(cfg)
    path = env.root / 'a.mkv'
    path.write_bytes(b'fixture content')
    assert env.plugin.api_push({'paths': [str(path)]})['success']
    return path, env.finish()['history'][-1]


@pytest.mark.parametrize('delete', [False, True])
def test_opt_in_delete(env, delete):
    path, row = run(env, delete_on_success=delete)
    assert path.exists() is not delete
    assert row['status'] == 'success'
    if delete:
        assert row['delete_status'] == 'success'
        assert any(x['history'] and x['history'][-1]['delete_status'] == 'pending' for x in env.plugin.writes)


def test_network_failure_archives_not_deletes(env, tmp_path):
    def fail(path):
        raise OSError('timeout')
    env.client.answer = fail
    path, row = run(env, failure_move_enabled=True, failure_move_dir=str(tmp_path / 'failed'), delete_on_success=True)
    assert row['status'] == 'failed' and row['move_status'] == 'success'
    assert row['original_path'] == str(path) and Path(row['path']).read_bytes() == b'fixture content'
    assert not path.exists()


def test_delete_error_keeps_remote_success(env, monkeypatch):
    transfer = importlib.import_module(type(env.plugin).__module__ + '.transfer')
    monkeypatch.setattr(transfer, 'delete_source', lambda *a: (_ for _ in ()).throw(PermissionError('denied')))
    path, row = run(env, delete_on_success=True)
    assert path.exists() and row['status'] == 'success' and row['delete_status'] == 'failed'


def test_changed_file_never_deleted(env):
    def change(path):
        path.write_bytes(b'new content')
        return {'ok': True}
    env.client.answer = change
    path, row = run(env, delete_on_success=True)
    assert path.exists() and row['status'] == 'failed'


def test_save_failure_keeps_source(env, monkeypatch):
    monkeypatch.setattr(env.plugin, 'save_data', lambda *a: False)
    path, row = run(env, delete_on_success=True)
    assert path.exists() and row['status'] == 'success' and row['delete_status'] == 'failed'


def test_collision_symlink_and_change(env, tmp_path):
    actions, _ = modules(env)
    target = tmp_path / 'failed'
    target.mkdir()
    (target / 'a.mkv').write_bytes(b'old')
    for _ in range(2):
        src = env.root / 'a.mkv'
        src.write_bytes(b'new')
        moved, sig = actions.move_failed(src, str(target), expected=actions.signature(src), token='same')
        assert Path(moved).read_bytes() == b'new'
    assert len(list(target.iterdir())) == 3 and (target / 'a.mkv').read_bytes() == b'old'
    src.write_bytes(b'old')
    before = actions.signature(src)
    src.write_bytes(b'changed')
    assert actions.delete_source(src, before)[0] is False
    with pytest.raises(RuntimeError):
        actions.move_failed(src, str(target), expected=before)
    link = env.root / 'link.mkv'
    link.symlink_to(src)
    with pytest.raises(ValueError):
        actions.signature(link)


@pytest.mark.parametrize('broken', [False, True])
def test_cross_device_copy_failure_preserves_source(env, tmp_path, monkeypatch, broken):
    actions, _ = modules(env)
    src = env.root / 'cross.mkv'
    src.write_bytes(b'cross device fixture')
    real_link = actions.os.link
    def link(a, b, **kw):
        if Path(a) == src:
            raise OSError(errno.EXDEV, 'cross device')
        return real_link(a, b, **kw)
    monkeypatch.setattr(actions.os, 'link', link)
    if broken:
        monkeypatch.setattr(actions, '_copy', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
        with pytest.raises(OSError):
            actions.move_failed(src, str(tmp_path / 'archive'), expected=actions.signature(src))
        assert src.read_bytes() == b'cross device fixture'
        assert not list((tmp_path / 'archive').iterdir())
    else:
        moved, _ = actions.move_failed(src, str(tmp_path / 'archive'), expected=actions.signature(src))
        assert not src.exists() and Path(moved).read_bytes() == b'cross device fixture'


def test_hash_concurrent_single_read_and_invalidation(env, monkeypatch):
    _, hashes = modules(env)
    hashes.clear_cache()
    path = env.root / 'hash.mkv'
    data = b'sha1 fixture' * 100000
    path.write_bytes(data)
    real = hashes._read_sha1
    calls = []
    def read(p, chunk):
        calls.append(chunk)
        return real(p, chunk)
    monkeypatch.setattr(hashes, '_read_sha1', read)
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(hashes.sha1_file, [path] * 16))
    assert set(answers) == {hashlib.sha1(data).hexdigest().upper()}
    assert calls == [4 * 1024 * 1024]
    path.write_bytes(b'changed')
    assert hashes.sha1_file(path) == hashlib.sha1(b'changed').hexdigest().upper()
    assert len(calls) == 2


def test_config_false_and_absolute_path(env):
    normalize = env.settings.normalize_config
    assert normalize({'delete_on_success': 'false'})['delete_on_success'] is False
    with pytest.raises(ValueError):
        normalize({'failure_move_dir': 'relative'})
    with pytest.raises(ValueError):
        normalize({'failure_move_enabled': True})


def test_cross_plugin_hash_cache_and_device_signature(env, monkeypatch):
    import importlib.util
    from types import SimpleNamespace
    _, manual = modules(env)
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('standalone_cloud_hash', root / 'plugins.v2/cloudpush115/filehash.py')
    cloud = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cloud)
    manual.clear_cache()
    path = env.root / 'shared.mkv'
    path.write_bytes(b'cross plugin')
    digest = manual.sha1_file(path)
    monkeypatch.setattr(cloud, '_read_sha1', lambda *a: pytest.fail('second full read'))
    assert cloud.sha1_file(path) == digest
    before = manual._signature(path)
    fake = SimpleNamespace(stat=lambda: SimpleNamespace(st_dev=before[1]+1, st_ino=before[2], st_size=before[3], st_mtime_ns=before[4]), resolve=lambda: path.resolve())
    assert manual._signature(fake) != before


def test_failed_archive_not_collected_again(env, tmp_path):
    target = env.root / 'failed'
    target.mkdir()
    (target / 'old.mkv').write_bytes(b'old')
    env.plugin.init_plugin({**env.plugin._config, 'failure_move_enabled': True, 'failure_move_dir': str(target)})
    (env.root / 'new.mkv').write_bytes(b'new')
    assert env.plugin.api_push({'paths': [str(env.root)]})['success']
    status = env.finish()
    assert status['job']['total'] == 1
    assert len(env.client.calls) == 1


def test_move_link_error_preserves_source(env, tmp_path, monkeypatch):
    actions, _ = modules(env)
    path = env.root / 'locked.mkv'
    path.write_bytes(b'keep')
    monkeypatch.setattr(actions.os, 'link', lambda *a, **kw: (_ for _ in ()).throw(PermissionError('denied')))
    with pytest.raises(PermissionError):
        actions.move_failed(path, str(tmp_path / 'archive'), expected=actions.signature(path))
    assert path.read_bytes() == b'keep'
