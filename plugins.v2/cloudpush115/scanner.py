"""只读媒体索引与可持久化失败队列；仅依赖 Python 标准库。

扫描结果不缓存；每轮重新读取 size / mtime_ns / inode，调用方可据此识别
同一路径的内容变化。队列不持有线程或锁，并发访问由调用方统一加锁。
"""

from __future__ import annotations

from copy import deepcopy
import logging
import math
import os
import re
import stat
import time
from typing import Any, Callable, Dict, Iterator, List, Optional

# 常见的视频 / 字幕 / 音频扩展名（不区分大小写）
DEFAULT_EXTENSIONS = [
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "ts", "m2ts", "iso", "rmvb", "webm",
    "mpg", "mpeg", "m4v", "vob", "3gp", "strm",
    "srt", "ass", "ssa", "sub", "idx", "sup", "vtt",
    "mp3", "flac", "aac", "m4a", "ape", "wav", "dts",
]


class MediaScanner:
    """按路径去重的流式扫描器，不读取内容、不修改源文件。"""

    def __init__(self, extensions: Optional[List[str]] = None) -> None:
        exts = extensions or DEFAULT_EXTENSIONS
        self.extensions = {e.strip().lower().lstrip(".") for e in exts if e.strip()}

    def iter_files(self, watch_paths: List[str]) -> List[Dict[str, Any]]:
        """兼容旧接口；需要取消或逐条消费时请使用 walk_files。"""
        return list(self.walk_files(watch_paths))

    def walk_files(
        self,
        watch_paths: List[str],
        on_error: Optional[Callable[[str, str], None]] = None,
        stop: Optional[Callable[[], bool]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """逐文件返回绝对规范路径及本轮 stat 元数据，顺序不作保证。

        显式指定的根先 realpath（因此允许用户直接指定链接根）；遍历中
        遇到的文件/目录符号链接均不跟随，避免越界及循环。只遍历指定根，
        重叠目录和重复文件路径去重，硬链接的不同路径仍各自保留。
        错误调用 on_error(path, message)，未提供时使用标准 logging 报告；
        单项失败不终止其他项。回调自身的异常会传播。stop 在访问根及
        每次读取目录项前检查；取消或关闭生成器会关闭所有 scandir 句柄。
        """
        seen_files, seen_dirs = set(), set()

        def report(path: str, exc: Exception) -> None:
            if on_error is not None:
                on_error(path, str(exc))
            else:
                logging.getLogger(__name__).warning("扫描 %s 失败: %s", path, exc)

        def collect(path: str, info: os.stat_result) -> Optional[Dict[str, Any]]:
            suffix = os.path.splitext(path)[1].lower().lstrip(".")
            if path in seen_files or (self.extensions and suffix not in self.extensions):
                return None
            seen_files.add(path)
            return {
                "path": path,
                "name": os.path.basename(path),
                "size": int(info.st_size),
                "mtime": float(info.st_mtime),
                "mtime_ns": int(info.st_mtime_ns),
                "inode": int(info.st_ino),
            }

        for raw_root in watch_paths:
            if stop is not None and stop():
                return
            if raw_root is None or not os.fspath(raw_root).strip():
                continue
            root = os.path.abspath(os.fspath(raw_root).strip())
            stack = []
            try:
                try:
                    root = os.path.realpath(root)
                    if root in seen_dirs or root in seen_files:
                        continue
                    info = os.stat(root, follow_symlinks=False)
                except (OSError, ValueError) as exc:
                    report(root, exc)
                    continue
                if stat.S_ISREG(info.st_mode):
                    item = collect(root, info)
                    if item is not None:
                        yield item
                    continue
                if not stat.S_ISDIR(info.st_mode):
                    continue

                def descend(path: str) -> None:
                    if path in seen_dirs:
                        return
                    try:
                        entries = os.scandir(path)
                    except OSError as exc:
                        report(path, exc)
                        return
                    seen_dirs.add(path)
                    stack.append((path, entries))

                descend(root)
                while stack:
                    if stop is not None and stop():
                        return
                    directory, entries = stack[-1]
                    try:
                        entry = next(entries)
                    except StopIteration:
                        stack.pop()[1].close()
                        continue
                    except OSError as exc:
                        stack.pop()[1].close()
                        report(directory, exc)
                        continue
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        report(entry.path, exc)
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        descend(entry.path)
                    elif stat.S_ISREG(info.st_mode):
                        item = collect(entry.path, info)
                        if item is not None:
                            yield item
            finally:
                for _, entries in reversed(stack):
                    entries.close()


def _integer(value: Any, default: int = 0) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError, OverflowError):
        return default


def _epoch(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else default
    except (TypeError, ValueError, OverflowError):
        return default


def _size_bytes(value: Any) -> int:
    """兼容旧首页持久化的 human size；无法还原的值安全降为 0。"""
    if isinstance(value, str):
        try:
            # 整数字符串直接转换，避免大文件大小经过 float 丢失字节精度。
            return max(int(value), 0)
        except (ValueError, OverflowError):
            pass
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTPE]?)(?:I?B)?\s*",
                             value, re.IGNORECASE)
        if match:
            number, unit = match.groups()
            factor = 1024 ** ("KMGTPE".index(unit.upper()) + 1) if unit else 1
            try:
                return max(int(float(number) * factor), 0)
            except (ValueError, OverflowError):
                return 0
    return _integer(value)


class RetryQueue:
    """保留失败记录的重试队列，pending 始终为 path -> item 字典。

    attempts 计失败次数，首次失败为 1。max_attempts=N>0 表示首次失败后
    最多重试 N 次，只有 attempts>N 才 exhausted；0 表示无限重试。
    busy / suspended 不自动出队；exhausted 优先于其他状态且不自动删除。
    路径键保持调用方传入值，建议直接使用扫描器返回的绝对路径。
    """

    def __init__(
        self,
        retry_interval: int = 600,
        max_attempts: int = 0,
        pending: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        # 保留 1.5.5 的配置语义：最短间隔 30 秒，0 次上限表示无限。
        self.retry_interval = max(_integer(retry_interval, 600), 30)
        self.max_attempts = _integer(max_attempts)
        self.pending: Dict[str, Dict[str, Any]] = {}
        # 旧 list 持久化和 path -> item 映射均可恢复，单个坏项不影响其他项。
        if isinstance(pending, dict):
            records = pending.items()
        elif isinstance(pending, (list, tuple)):
            records = ((None, item) for item in pending)
        else:
            records = ()
        for path, raw in records:
            item = self._normalize(raw, path)
            if item is not None:
                self.pending[item["path"]] = item

    def _status(self, item: Dict[str, Any]) -> str:
        if self.max_attempts and _integer(item.get("attempts")) > self.max_attempts:
            return "exhausted"
        status = item.get("status")
        status = status.strip().lower() if isinstance(status, str) else ""
        # 提高上限或改为无限后，旧 exhausted 标记不得继续锁死队列。
        return "pending" if status in ("", "exhausted") else status

    def _normalize(self, raw: Any, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """只规范化副本；也用于只读快照，不回写 pending。"""
        if not isinstance(raw, dict):
            return None
        path = raw.get("path", path)
        if not isinstance(path, str) or not path.strip() or "\x00" in path:
            return None
        try:
            item = deepcopy(raw)
        except (TypeError, ValueError, RecursionError):
            return None
        item["path"] = path
        item["name"] = str(item.get("name") or os.path.basename(path))
        item["size"] = _size_bytes(item.get("size", 0))
        item["remote_dir"] = item.get("remote_dir", "")
        item["attempts"] = _integer(item.get("attempts"))
        updated = _epoch(item.get("updated_at"))
        item["updated_at"] = updated
        fallback = updated + self.retry_interval if updated else 0.0
        item["next_retry"] = _epoch(item.get("next_retry"), fallback)
        # last_error 是旧接口的主字段；error 是供新首页使用的同步别名。
        error = item.get("last_error") or item.get("error") or ""
        item["error"] = item["last_error"] = str(error)
        item.setdefault("source", "local")
        item["status"] = self._status(item)
        return item

    def add(self, path: str, name: str, size: int,
            remote_dir: str, error: str, **metadata: Any) -> None:
        """记录一次失败，保留未覆盖的元数据；计数和间隔不能被 metadata 绕过。"""
        if not isinstance(path, str) or not path.strip() or "\x00" in path:
            raise ValueError("path must be a non-empty string without NUL")
        now = time.time()
        item = self.get(path) or {"path": path, "attempts": 0, "source": "local"}
        attempts = item["attempts"] + 1
        item.update(deepcopy(metadata))
        item.update({
            "path": path, "name": name, "size": _size_bytes(size),
            "remote_dir": remote_dir, "attempts": attempts,
            "error": str(error or ""), "last_error": str(error or ""),
            "next_retry": now + self.retry_interval, "updated_at": now,
        })
        item["status"] = self._status(item)
        self.pending[path] = item

    def remove(self, path: str) -> None:
        self.pending.pop(path, None)

    def due(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """只读深拷贝：next_retry<=now 且非 busy/suspended/exhausted 的项。

        耗尽项永久保留，防止下次全扫描把它当作新文件立即重试。
        """
        now = _epoch(now, time.time())
        return [item for item in self.to_list()
                if item["status"] not in ("busy", "suspended", "exhausted")
                and item["next_retry"] <= now]

    def to_list(self) -> List[Dict[str, Any]]:
        """可直接持久化/展示的深拷贝，包含耗尽项及 error/last_error 双字段。"""
        result = []
        for path, raw in self.pending.items():
            item = self._normalize(raw, path)
            if item is not None:
                result.append(item)
        return result

    def get(self, path: str) -> Optional[Dict[str, Any]]:
        """返回独立快照；调用方修改结果不会修改队列。"""
        return self._normalize(self.pending.get(path), path)

    def defer(self, path: str, error: str = "", now: Optional[float] = None) -> bool:
        """不消耗重试次数；仅已到期项推迟一个完整间隔。

        未来预约不挪动，避免轮询不断延期造成饥饿。非空 error 更新错误，
        busy/suspended/exhausted 不会解除。返回是否实际修改；不存在为 False。
        """
        item = self.get(path)
        if item is None:
            return False
        now = _epoch(now, time.time())
        changed = False
        if item["next_retry"] <= now:
            item["next_retry"] = now + self.retry_interval
            changed = True
        if error and str(error) != item["error"]:
            item["error"] = item["last_error"] = str(error)
            changed = True
        if changed:
            item["updated_at"] = now
            self.pending[path] = item
        return changed

    def retry_now(self, path: str, reset_attempts: bool = True) -> bool:
        """显式手动重排：解除暂停/忙碌，默认清零失败数并立即到期。

        保留目标目录、来源、错误及其他元数据。reset_attempts=False 保留
        失败预算；若已耗尽则不修改并返回 False。不存在同样返回 False。
        """
        item = self.get(path)
        if item is None or (not reset_attempts and item["status"] == "exhausted"):
            return False
        if reset_attempts:
            item["attempts"] = 0
        item["status"] = "pending"
        item["next_retry"] = item["updated_at"] = time.time()
        self.pending[path] = item
        return True

    def __len__(self) -> int:
        """包含耗尽和暂停项；移除仅由 remove 显式执行。"""
        return len(self.pending)
