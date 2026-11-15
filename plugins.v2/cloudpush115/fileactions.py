"""Opt-in file actions. Never overwrite, and never follow a source symlink.

Signatures use (size, mtime_ns, device, inode). Locks coordinate both plugins
in one host process; external writers must still quiesce their files.
"""
from __future__ import annotations

import errno
import hashlib
import os
import stat
import sys
import tempfile
import threading
import types
import uuid
from pathlib import Path

_shared = types.ModuleType('_push115_file_action_locks_v1')
_shared.locks = [threading.RLock() for _ in range(128)]
_shared = sys.modules.setdefault(_shared.__name__, _shared)


def path_lock(path):
    key = os.path.realpath(path).encode()
    return _shared.locks[int.from_bytes(hashlib.sha256(key).digest()[:2], 'big') % 128]


def signature(path):
    st = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError('只允许处理普通文件，拒绝软链')
    return (int(st.st_size), int(st.st_mtime_ns), int(st.st_dev), int(st.st_ino))


def validate_directory(value):
    if not isinstance(value, str) or '\x00' in value or (value and not os.path.isabs(value)):
        raise ValueError('失败目录必须是本地绝对路径')
    return os.path.realpath(value) if value else ''


def contains(directory, path):
    return bool(directory) and os.path.commonpath([os.path.realpath(directory), os.path.realpath(path)]) == os.path.realpath(directory)


def _copy(src, temp, expected):
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(src, flags), 'rb', buffering=0) as reader:
        st = os.fstat(reader.fileno())
        if (st.st_size, st.st_mtime_ns, st.st_dev, st.st_ino) != expected:
            raise RuntimeError('源文件在复制前发生变化')
        with open(temp, 'wb', buffering=0) as writer:
            buf = bytearray(4 * 1024 * 1024)
            view = memoryview(buf)
            while count := reader.readinto(buf):
                block = view[:count]
                digest.update(block)
                while block:
                    written = writer.write(block)
                    if not written:
                        raise OSError('复制写入不完整')
                    block = block[written:]
            os.fsync(writer.fileno())
    check = hashlib.sha256()
    with open(temp, 'rb') as reader:
        while block := reader.read(4 * 1024 * 1024):
            check.update(block)
    if check.digest() != digest.digest() or os.stat(temp).st_size != expected[0]:
        raise OSError('归档副本校验失败')
    os.chmod(temp, stat.S_IMODE(os.stat(src, follow_symlinks=False).st_mode))
    os.utime(temp, ns=(expected[1], expected[1]))


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def move_failed(path, target_dir, preserve_root=None, token='', expected=None):
    src = Path(os.path.abspath(path))
    with path_lock(src):
        before = signature(src)
        if expected is None or tuple(expected) != before:
            raise RuntimeError('文件签名未确认或已变化，保留源文件')
        target = Path(validate_directory(target_dir))
        if not target_dir:
            raise ValueError('未设置失败目录')
        if contains(target, src):
            return str(src), before  # Already archived: do not move on each retry.
        rel = Path(src.name)
        if preserve_root:
            try:
                rel = src.relative_to(Path(os.path.realpath(preserve_root)))
            except ValueError:
                pass
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not contains(target, dest.parent):
            raise ValueError('归档路径越出目标目录')
        temp = None
        published = False
        try:
            while True:
                try:
                    os.link(src, dest, follow_symlinks=False)
                    published = True
                    break
                except FileExistsError:
                    dest = dest.with_name(src.stem + '-' + uuid.uuid4().hex + src.suffix)
                except OSError as exc:
                    if exc.errno != errno.EXDEV:
                        raise
                    fd, temp = tempfile.mkstemp(prefix='.push115-', dir=dest.parent)
                    os.close(fd)
                    _copy(src, temp, before)
                    while True:
                        try:
                            os.link(temp, dest, follow_symlinks=False)
                            published = True
                            break
                        except FileExistsError:
                            dest = dest.with_name(src.stem + '-' + uuid.uuid4().hex + src.suffix)
                    break
            _sync_dir(dest.parent)
            if signature(src) != before:
                raise RuntimeError('文件移动期间发生变化，保留源文件')
            src.unlink()
            return str(dest), before
        except Exception:
            if published and src.exists():
                dest.unlink(missing_ok=True)
            raise
        finally:
            if temp:
                Path(temp).unlink(missing_ok=True)


def check_policy(path, protected=(), hardlink_only=False):
    if any(contains(root, path) for root in protected):
        raise ValueError('路径位于受保护源目录，保留原文件')
    st = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError('只允许处理普通文件，拒绝软链')
    if hardlink_only and st.st_nlink < 2:
        raise ValueError('硬链接数不足2，保留最后一份文件')


def hardlink_destination(path, target_dir, preserve_root=None):
    src = Path(os.path.abspath(path))
    target = Path(validate_directory(target_dir))
    rel = Path(src.name)
    if preserve_root:
        try:
            rel = src.relative_to(Path(os.path.abspath(preserve_root)))
        except ValueError:
            pass
    dest = target / rel
    if not contains(target, dest.parent):
        raise ValueError('归档路径越出目标目录')
    return str(dest)


def link_failed(path, destination, expected):
    """Publish exactly the registered link, keeping source; EXDEV is an error."""
    src, dest = Path(path), Path(destination)
    with path_lock(path):
        if signature(src) != tuple(expected):
            raise RuntimeError('文件签名已变化，保留原路径')
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dest, follow_symlinks=False)
        except FileExistsError:
            if signature(dest) != tuple(expected):
                raise FileExistsError('归档目标已存在且不是相同文件')
        if signature(src) != tuple(expected) or signature(dest) != tuple(expected):
            raise RuntimeError('硬链接创建期间文件发生变化')
        _sync_dir(dest.parent)
        return str(dest), tuple(expected)


def delete_source(path, expected=None, protected=(), hardlink_only=False):
    with path_lock(path):
        check_policy(path, protected, hardlink_only)
        current = signature(path)
        if expected is None or tuple(expected) != current:
            return False, '文件签名未确认或已变化，跳过删除'
        Path(path).unlink()
        return True, '登记的本地链接已删除'
