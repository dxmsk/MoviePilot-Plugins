# encoding: utf-8
"""
QB 下载完成 → 秒传联动核心。

流程：
  qb 种子完成（无「已整理」标签）
     ↓
  等文件落地稳定（大小一段时间不变）
     ↓
  立即算 SHA1 → 调 115 秒传
     ├─ 成功 ✅ → 给种子打「已整理」标签 → MP 不再整理它
     └─ 失败 ❌ → 不打标签 → MP 照常整理它
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .qb_client import QBClient, QBError, QBAuthError, DEFAULT_DONE_TAG


class QBWatcher:
    """qb 下载完成监听 + 秒传联动。"""

    def __init__(
        self,
        qb: QBClient,
        push_callback: Callable[[Path, str], Dict[str, Any]],
        media_exts: Optional[List[str]] = None,
        logger=None,
        done_tag: str = DEFAULT_DONE_TAG,
        stable_checks: int = 2,
        stable_interval: float = 2.0,
        min_size: int = 1024 * 1024,   # 小于 1MB 的忽略
    ):
        """
        :param qb: QBClient 实例
        :param push_callback: 秒传回调 (local_path, remote_dir) -> {ok: bool, reuse: bool, message: str, ...}
        :param media_exts: 需要秒传的扩展名（不带点），None=全部
        :param logger: 日志函数
        :param done_tag: 整理完成标签（打了就不处理）
        """
        self.qb = qb
        self.push = push_callback
        self.media_exts = [e.lower().lstrip(".") for e in (media_exts or [])]
        self.log = logger or (lambda *a, **k: None)
        self.done_tag = done_tag
        self.stable_checks = stable_checks
        self.stable_interval = stable_interval
        self.min_size = min_size

    # ------------------------------------------------------------------ #
    # 文件落地稳定检测
    # ------------------------------------------------------------------ #
    def _stable_and_ready(self, path: Path) -> bool:
        """连续检查文件大小是否稳定（防止下载/解压/改名未完成）。"""
        if not path.exists() or not path.is_file():
            return False
        last = -1
        for _ in range(self.stable_checks):
            try:
                size = path.stat().st_size
            except OSError:
                return False
            if size < self.min_size:
                return False
            if size != last and last != -1:
                return False       # 还在变化
            last = size
            time.sleep(self.stable_interval)
        return True

    def _is_media(self, path: Path) -> bool:
        if not self.media_exts:
            return True
        return path.suffix.lower().lstrip(".") in self.media_exts

    # ------------------------------------------------------------------ #
    # 从种子解析出「本地文件路径」
    # ------------------------------------------------------------------ #
    def _torrent_paths(self, torrent: Dict[str, Any]) -> List[Path]:
        """
        计算某个种子对应的本地文件路径列表。
        qb 的 content_path 是最终位置；save_path+name 是原始位置。
        优先用 content_path（多文件种子会指向目录）。
        """
        paths: List[Path] = []
        content = torrent.get("content_path") or ""
        save = torrent.get("save_path") or ""
        name = torrent.get("name") or ""

        cand = Path(content) if content else (Path(save) / name if save else None)
        if cand is None:
            return paths
        if cand.is_file():
            paths.append(cand)
        elif cand.is_dir():
            try:
                for root, _dirs, files in os.walk(cand):
                    for f in files:
                        paths.append(Path(root) / f)
            except OSError:
                pass
        else:
            # content_path 不存在时退回 save_path 下找
            alt = Path(save) / name
            if alt.is_dir():
                for root, _dirs, files in os.walk(alt):
                    for f in files:
                        paths.append(Path(root) / f)
        return paths

    # ------------------------------------------------------------------ #
    # 单轮处理
    # ------------------------------------------------------------------ #
    def process_once(self, remote_dir: str = "",
                     max_torrents: int = 20) -> Dict[str, int]:
        """
        扫描一次所有「已完成但未整理」的种子，尝试秒传。
        返回统计：{"checked","pushed","skipped","failed"}
        """
        stats = {"checked": 0, "pushed": 0, "skipped": 0, "failed": 0}
        try:
            torrents = self.qb.completed_torrents(done_tag=self.done_tag)
        except QBAuthError as e:
            self.log(f"qb 鉴权失败: {e}")
            raise
        except QBError as e:
            self.log(f"qb 查询失败: {e}")
            return stats

        for t in torrents[:max_torrents]:
            stats["checked"] += 1
            t_hash = t.get("hash") or ""
            t_name = t.get("name") or ""
            try:
                paths = self._torrent_paths(t)
            except Exception as e:
                self.log(f"解析路径失败 {t_name}: {e}")
                stats["failed"] += 1
                continue

            media = [p for p in paths if self._is_media(p)]
            if not media:
                self.log(f"跳过（无匹配媒体文件）: {t_name}")
                stats["skipped"] += 1
                continue

            # 需要所有媒体文件都落地稳定
            ready = [p for p in media if self._stable_and_ready(p)]
            if not ready:
                self.log(f"跳过（文件未就绪）: {t_name}")
                stats["skipped"] += 1
                continue

            all_ok = True
            detail = []
            for p in ready:
                try:
                    r = self.push(p, remote_dir)
                except Exception as e:
                    r = {"ok": False, "message": str(e)}
                if r.get("ok") and r.get("reuse"):
                    detail.append(f"✅{p.name}")
                elif r.get("ok"):
                    detail.append(f"✔{p.name}")
                else:
                    all_ok = False
                    detail.append(f"❌{p.name}:{r.get('message', '')}")

            if all_ok:
                # 全部秒传成功 → 打「已整理」标签 → MP 不再整理
                try:
                    self.qb.set_tag(t_hash, self.done_tag)
                    stats["pushed"] += 1
                    self.log(f"秒传成功并标记已整理: {t_name}  [{'; '.join(detail)}]")
                except QBError as e:
                    self.log(f"秒传成功但打标签失败: {t_name} -> {e}")
                    stats["pushed"] += 1
            else:
                stats["failed"] += 1
                self.log(f"秒传未全部成功，交给 MP 整理: {t_name}  [{'; '.join(detail)}]")

        return stats
