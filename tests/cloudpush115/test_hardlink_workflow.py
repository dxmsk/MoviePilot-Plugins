from copy import deepcopy
import importlib
import os
from pathlib import Path
import errno
import pytest
from test_runtime import host, Client, configure_client


def setup(host, tmp_path):
    source, watch, failed = [tmp_path / x for x in ('a', 'c', 'b')]
    source.mkdir(); watch.mkdir()
    original = source / 'movie.mkv'; original.write_bytes(b'original movie')
    managed = watch / 'movie.mkv'; os.link(original, managed)
    p = host.new({'cookie': 'UID=fixture', 'watch_paths': str(watch),
        'protected_paths': str(source), 'hardlink_only': True,
        'failure_move_enabled': True, 'failure_move_on': 'each_failure',
        'failure_action': 'hardlink', 'failure_move_dir': str(failed), 'delete_on_success': True})
    return p, original, managed, failed


def test_failed_link_preserves_source_and_success_cleans_both(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    c = Client({'ok': False, 'message': 'retry later'}); configure_client(p, c, monkeypatch)
    result = p._transfer(p._file_item(str(managed)), p._config)
    archived = Path(result['path'])
    assert original.exists() and managed.exists() and archived.exists()
    assert original.stat().st_ino == managed.stat().st_ino == archived.stat().st_ino
    assert p._transfer(p._file_item(str(managed)), p._config).get('relocated')
    assert len(c.calls) == 1
    c.answer = {'ok': True}
    restored = host.new(p._config, p.storage); configure_client(restored, c, monkeypatch)
    assert restored._transfer(restored._queue.get(str(archived)), restored._config, source='retry')['ok']
    assert original.read_bytes() == b'original movie'
    assert not managed.exists() and not archived.exists() and original.stat().st_nlink == 1
    assert not restored._queue.pending


def test_link_collision_no_overwrite(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    failed.mkdir(); collision = failed / managed.name; collision.write_bytes(b'keep other movie')
    configure_client(p, Client({'ok': False}), monkeypatch)
    result = p._transfer(p._file_item(str(managed)), p._config)
    assert Path(result['path']) != collision
    assert collision.read_bytes() == b'keep other movie'
    assert managed.exists() and original.exists()


def test_hardlink_cross_device_never_copies(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    actions = importlib.import_module(host.package.__name__ + '.fileactions')
    monkeypatch.setattr(actions.os, 'link', lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EXDEV, 'cross-device')))
    configure_client(p, Client({'ok': False}), monkeypatch)
    result = p._transfer(p._file_item(str(managed)), p._config)
    assert result['move_status'] == 'failed' and managed.exists() and original.exists()
    assert not list(failed.glob('*.mkv'))


def test_protected_source_never_deleted(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    configure_client(p, Client({'ok': True}), monkeypatch)
    result = p._transfer(p._file_item(str(original)), p._config)
    assert result['ok'] and original.exists() and result['delete_status'] == 'failed'


def test_last_link_is_kept(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    original.unlink()
    configure_client(p, Client({'ok': True}), monkeypatch)
    result = p._transfer(p._file_item(str(managed)), p._config)
    assert result['ok'] and managed.exists() and result['delete_status'] == 'failed'


def test_cleanup_restart_does_not_resubmit(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    c = Client({'ok': True}); configure_client(p, c, monkeypatch)
    actions = importlib.import_module(host.package.__name__ + '.actions')
    real = actions.delete_source
    monkeypatch.setattr(actions, 'delete_source', lambda *a, **k: (_ for _ in ()).throw(PermissionError('busy')))
    assert p._transfer(p._file_item(str(managed)), p._config)['ok']
    restored = host.new(p._config, p.storage); configure_client(restored, c, monkeypatch)
    monkeypatch.setattr(actions, 'delete_source', real)
    restored._recover_file_actions(restored._config, restored._generation)
    assert len(c.calls) == 1 and original.exists() and not managed.exists()


def test_replaced_alias_preserved_after_remote_success(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    c = Client({'ok': False}); configure_client(p, c, monkeypatch)
    archived = Path(p._transfer(p._file_item(str(managed)), p._config)['path'])
    managed.unlink(); managed.write_bytes(b'NEW file must survive')
    c.answer = {'ok': True}
    p._transfer(p._queue.get(str(archived)), p._config, source='retry')
    assert managed.read_bytes() == b'NEW file must survive' and original.exists() and not archived.exists()


def test_persist_failure_prevents_local_delete(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    configure_client(p, Client({'ok': True}), monkeypatch)
    monkeypatch.setattr(p, '_persist', lambda: False)
    result = p._transfer(p._file_item(str(managed)), p._config)
    assert result['ok'] and original.exists() and managed.exists()


def test_crash_after_success_before_action_intent_recovers(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    c = Client({'ok': True}); configure_client(p, c, monkeypatch)
    monkeypatch.setattr(p, '_file_action', lambda *a, **k: None)
    assert p._transfer(p._file_item(str(managed)), p._config)['ok']
    assert managed.exists()
    restored = host.new(p._config, p.storage)
    restored._recover_file_actions(restored._config, restored._generation)
    assert len(c.calls) == 1 and original.exists() and not managed.exists()


def test_preexisting_identical_hardlink_is_not_adopted(host, tmp_path, monkeypatch):
    p, original, managed, failed = setup(host, tmp_path)
    failed.mkdir(); external = failed / managed.name; os.link(original, external)
    c = Client({'ok': False}); configure_client(p, c, monkeypatch)
    archived = Path(p._transfer(p._file_item(str(managed)), p._config)['path'])
    assert archived != external
    c.answer = {'ok': True}
    p._transfer(p._queue.get(str(archived)), p._config, source='retry')
    assert external.exists() and original.exists() and not managed.exists() and not archived.exists()
