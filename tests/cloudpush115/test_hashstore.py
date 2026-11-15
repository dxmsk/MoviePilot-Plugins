import hashlib
import importlib
import os
from test_runtime import host


def test_hash_cache_survives_memory_reset(host, tmp_path, monkeypatch):
    hashes = importlib.import_module(host.package.__name__ + '.filehash')
    hashes.configure_cache(tmp_path / 'cache')
    path = tmp_path / 'movie.mkv'
    path.write_bytes(b'first pass')
    hashes.clear_cache()
    expected = hashlib.sha1(path.read_bytes()).hexdigest().upper()
    assert hashes.sha1_file(path) == expected
    hashes.clear_cache()  # Same disk state, cold process-equivalent memory.
    monkeypatch.setattr(hashes, '_read_sha1', lambda *a: (_ for _ in ()).throw(AssertionError('unexpected full read')))
    assert hashes.sha1_file(path) == expected


def test_hash_disk_cache_invalidates_when_mtime_restored(host, tmp_path, monkeypatch):
    hashes = importlib.import_module(host.package.__name__ + '.filehash')
    hashes.configure_cache(tmp_path / 'cache')
    path = tmp_path / 'movie.mkv'
    path.write_bytes(b'original')
    old = path.stat()
    hashes.clear_cache()
    first = hashes.sha1_file(path)
    path.write_bytes(b'replaced')  # Same length, restore mtime; ctime must still invalidate.
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    hashes.clear_cache()
    assert hashes.sha1_file(path) == hashlib.sha1(b'replaced').hexdigest().upper()
    assert hashes.sha1_file(path) != first


def test_hash_disk_failure_does_not_block_upload(host, tmp_path):
    hashes = importlib.import_module(host.package.__name__ + '.filehash')
    bad = tmp_path / 'not-a-directory'
    bad.write_text('x')
    hashes.configure_cache(bad)
    path = tmp_path / 'movie.mkv'
    path.write_bytes(b'read normally')
    hashes.clear_cache()
    assert hashes.sha1_file(path) == hashlib.sha1(path.read_bytes()).hexdigest().upper()
