# encoding: utf-8
"""有界 SHA1 缓存：相同文件重试时复用哈希，元数据变化即失效。"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Union

_MAX_ENTRIES = 2048
_cache: OrderedDict[tuple[str, int, int, int], str] = OrderedDict()
_lock = threading.Lock()


def _signature(path: Path) -> tuple[str, int, int, int]:
    st = path.stat()
    return (str(path.resolve()), st.st_size, st.st_mtime_ns, getattr(st, "st_ino", 0))


def sha1_file(path: Union[str, Path], chunk_size: int = 1024 * 1024) -> str:
    """返回大写 SHA1；缓存键含路径、大小、mtime_ns、inode，最多 2048 项。"""
    p = Path(path)
    before = _signature(p)
    with _lock:
        cached = _cache.get(before)
        if cached is not None:
            _cache.move_to_end(before)
            return cached
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    digest = h.hexdigest().upper()
    after = _signature(p)
    # 文件哈希期间发生变化时不缓存该结果。
    if before == after:
        with _lock:
            _cache[before] = digest
            _cache.move_to_end(before)
            while len(_cache) > _MAX_ENTRIES:
                _cache.popitem(last=False)
    return digest


def clear_cache() -> None:
    with _lock:
        _cache.clear()
