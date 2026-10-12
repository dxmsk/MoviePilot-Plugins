"""
扫描 / 重试队列模块。

职责：
- 扫描本地媒体目录，收集待秒传文件（只读，绝不修改原文件）
- 维护"失败重试"队列，按用户自定义的间隔重试
- 记录已成功秒传的文件，避免重复处理

所有状态通过 MoviePilot 的 save_data / get_data 持久化，
本模块自身不持有数据库，只提供纯逻辑 + 回调接口。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 常见的视频 / 字幕 / 音频扩展名（不区分大小写）
DEFAULT_EXTENSIONS = [
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "ts", "m2ts", "iso", "rmvb", "webm",
    "mpg", "mpeg", "m4v", "vob", "3gp", "strm",
    "srt", "ass", "ssa", "sub", "idx", "sup", "vtt",
    "mp3", "flac", "aac", "m4a", "ape", "wav", "dts",
]


class MediaScanner:
    """媒体文件扫描器。"""

    def __init__(self, extensions: Optional[List[str]] = None) -> None:
        exts = extensions or DEFAULT_EXTENSIONS
        self.extensions = {e.lower().lstrip(".") for e in exts if e.strip()}

    def iter_files(self, watch_paths: List[str]) -> List[Dict[str, Any]]:
        """
        扫描监控目录，返回文件信息列表。
        只读取元数据，不打开/修改文件内容。
        """
        results: List[Dict[str, Any]] = []
        seen = set()
        for wp in watch_paths:
            wp = (wp or "").strip()
            if not wp:
                continue
            root = Path(wp)
            if not root.exists():
                continue
            if root.is_file():
                self._collect(root, results, seen)
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    self._collect(path, results, seen)
        return results

    def _collect(self, path: Path, results: List[Dict[str, Any]], seen: set) -> None:
        suffix = path.suffix.lower().lstrip(".")
        if self.extensions and suffix not in self.extensions:
            return
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        try:
            st = path.stat()
        except OSError:
            return
        results.append({
            "path": key,
            "name": path.name,
            "size": st.st_size,
            "mtime": st.st_mtime,
        })


class RetryQueue:
    """
    失败重试队列。

    每条记录：
        {
          "path": 本地文件路径,
          "name": 文件名,
          "size": 文件大小,
          "remote_dir": 目标网盘目录,
          "attempts": 已尝试次数,
          "next_retry": 下次重试时间戳,
          "last_error": 最近一次错误,
        }
    """

    def __init__(
        self,
        retry_interval: int = 600,
        max_attempts: int = 0,
        pending: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        # 重试间隔（秒）—— 用户可自定义
        self.retry_interval = max(int(retry_interval), 30)
        # 最大重试次数，0 表示无限
        self.max_attempts = max(int(max_attempts), 0)
        self.pending: Dict[str, Dict[str, Any]] = {}
        for item in pending or []:
            if isinstance(item, dict) and item.get("path"):
                self.pending[item["path"]] = item

    def add(self, path: str, name: str, size: int,
            remote_dir: str, error: str) -> None:
        """加入（或更新）重试队列。"""
        now = time.time()
        item = self.pending.get(path) or {
            "path": path, "name": name, "size": size,
            "attempts": 0,
        }
        item["remote_dir"] = remote_dir
        item["attempts"] = int(item.get("attempts", 0)) + 1
        item["last_error"] = error
        item["next_retry"] = now + self.retry_interval
        item["updated_at"] = now
        self.pending[path] = item

    def remove(self, path: str) -> None:
        self.pending.pop(path, None)

    def due(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """返回当前到期、可以重试的记录。"""
        now = now if now is not None else time.time()
        out = []
        for path, item in list(self.pending.items()):
            if self.max_attempts and int(item.get("attempts", 0)) > self.max_attempts:
                # 超过最大次数，直接丢弃
                self.pending.pop(path, None)
                continue
            if float(item.get("next_retry", 0)) <= now:
                out.append(item)
        return out

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.pending.values())

    def __len__(self) -> int:
        return len(self.pending)
