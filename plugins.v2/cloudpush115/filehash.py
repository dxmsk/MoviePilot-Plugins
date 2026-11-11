"""Bounded SHA1 cache with per-file in-flight deduplication.

The first caller reads the HDD sequentially; concurrent retries wait for the
same digest instead of seeking/reading the disk again. Metadata includes the
device and inode so mounted disks do not alias cached entries.
"""
from __future__ import annotations

import hashlib
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Union

_MAX_ENTRIES = 2048
_CHUNK = 4 * 1024 * 1024
_cache = OrderedDict()
_inflight = {}
# Both independently packaged plugins share only standard-library state.
import sys
import types
_shared = types.ModuleType('_push115_sha1_state_v1')
_shared.cache, _shared.inflight = _cache, _inflight
_shared.lock = threading.RLock()
_shared.disks = {}
_shared = sys.modules.setdefault(_shared.__name__, _shared)
_cache, _inflight, _lock = _shared.cache, _shared.inflight, _shared.lock


def _disk_lock(device):
    with _lock:
        return _shared.disks.setdefault(device, threading.Lock())


def _signature(path: Path):
    st = path.stat()
    return (str(path.resolve()), int(st.st_dev), int(st.st_ino), int(st.st_size), int(st.st_mtime_ns))


def _read_sha1(path: Path, chunk_size: int) -> str:
    h = hashlib.sha1()
    with path.open("rb", buffering=0) as stream:
        try:
            advice = getattr(os, "posix_fadvise", None)
            if advice and hasattr(os, "POSIX_FADV_SEQUENTIAL"):
                advice(stream.fileno(), 0, 0, os.POSIX_FADV_SEQUENTIAL)
        except (OSError, AttributeError):
            pass
        buffer = bytearray(chunk_size)
        view = memoryview(buffer)
        while count := stream.readinto(buffer):
            h.update(view[:count])
    return h.hexdigest().upper()


def sha1_file(path: Union[str, Path], chunk_size: int = _CHUNK) -> str:
    p = Path(path)
    while True:
        key = _signature(p)
        with _lock:
            cached = _cache.get(key)
            if cached is not None:
                _cache.move_to_end(key)
                return cached
            event = _inflight.get(key)
            if event is None:
                event = threading.Event()
                _inflight[key] = event
                break
        event.wait()
    try:
        with _disk_lock(key[1]):
            if key != _signature(p):
                raise OSError('文件在等待哈希时发生变化')
            digest = _read_sha1(p, max(64 * 1024, min(16 * 1024 * 1024, int(chunk_size))))
            if key != _signature(p):
                raise OSError('文件在哈希期间发生变化')
        with _lock:
            _cache[key] = digest
            _cache.move_to_end(key)
            while len(_cache) > _MAX_ENTRIES:
                _cache.popitem(last=False)
        return digest
    finally:
        with _lock:
            done = _inflight.pop(key, None)
            if done:
                done.set()


def clear_cache() -> None:
    with _lock:
        _cache.clear()
