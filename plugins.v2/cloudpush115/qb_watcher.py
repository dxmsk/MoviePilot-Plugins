"""qB completed-file verification, explicit path mapping and observable job states."""
from __future__ import annotations

import os
import math
import time
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

from .qb_client import QBClient, QBError, QBAuthError, DEFAULT_DONE_TAG
from .scanner import DEFAULT_EXTENSIONS


class QBWatcher:
    def __init__(self, qb: QBClient, push_callback, media_exts=None, logger=None,
                 done_tag=DEFAULT_DONE_TAG, stable_checks=2, stable_interval=2.0, min_size=1,
                 status_callback=None, path_mappings="", retry_interval=600):
        self.qb, self.push = qb, push_callback
        self.log = logger or (lambda message: None)
        self.status_callback = status_callback or (lambda task: None)
        self.done_tag = done_tag
        self.media_exts = {str(e).strip().lower().lstrip(".") for e in (media_exts or DEFAULT_EXTENSIONS)}
        self.stable_checks = max(1, int(stable_checks))
        self.stable_interval = max(0.0, float(stable_interval))
        self.min_size = max(1, int(min_size))
        self.retry_interval = max(30, int(retry_interval))
        self.mappings = self._parse_mappings(path_mappings)
        self._stability = OrderedDict()
        self._success_files = OrderedDict()
        self._tasks = {}
        self._messages = {}
        self._cursor = 0
        self._next_retry = {}
        self._attempts = {}
        self._skipped = {}

    @staticmethod
    def _parse_mappings(text):
        result = []
        for line in str(text or "").splitlines():
            if not line.strip():
                continue
            if "=>" not in line:
                raise ValueError("路径映射格式应为 /qB路径=>/MP路径")
            source, target = (p.strip().replace("\\", "/").rstrip("/") or "/" for p in line.split("=>", 1))
            if not source.startswith("/") or not target.startswith("/"):
                raise ValueError("路径映射两侧必须是绝对路径")
            result.append((source, target))
        return sorted(result, key=lambda x: len(x[0]), reverse=True)

    def _mapped(self, path):
        path = str(path).replace("\\", "/")
        for source, target in self.mappings:
            if path == source or path.startswith(source.rstrip("/") + "/"):
                suffix = path[len(source):].lstrip("/")
                return Path(os.path.normpath(target.rstrip("/") + "/" + suffix))
        return Path(os.path.normpath(path))

    @staticmethod
    def _number(value, default=0):
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError, OverflowError):
            return default

    def _files(self, torrent):
        raw = self.qb.torrents_files(str(torrent.get("hash") or ""))
        if not isinstance(raw, list):
            raise QBError("qB文件清单格式错误")
        result, ignored = [], 0
        save = str(torrent.get("save_path") or "")
        content = str(torrent.get("content_path") or "")
        for file in raw:
            if not isinstance(file, dict):
                continue
            name = str(file.get("name") or "").replace("\\", "/")
            if int(self._number(file.get("priority", 1))) == 0:
                ignored += 1
                continue
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise QBError("qB文件清单含不合法相对路径")
            if relative.suffix.lower().lstrip(".") not in self.media_exts:
                continue
            candidates = []
            if save:
                candidates.append(self._mapped(str(PurePosixPath(save) / relative)))
            if content:
                base = PurePosixPath(content)
                if len(raw) == 1 and (base.name == relative.name or base.suffix.lower().lstrip(".") in self.media_exts):
                    candidates.insert(0, self._mapped(content))
                else:
                    tail = PurePosixPath(*relative.parts[1:]) if relative.parts[0] == base.name else relative
                    candidates.append(self._mapped(str(base / tail)))
            candidates = list(dict.fromkeys(candidates))
            if not candidates:
                raise QBError("qB未提供save_path/content_path，无法定位MP内文件")
            # Only exact paths derived from the torrent's file manifest are used.
            path = next((p for p in candidates if p.is_file()), candidates[0])
            result.append({"path": str(path), "name": name, "size": int(self._number(file.get("size"))),
                           "progress": self._number(file.get("progress"), -1)})
        return result, ignored

    def _ready(self, file):
        path = Path(file["path"])
        result = {**file, "ready": False}
        if file["progress"] < 1:
            return {**result, "reason": "qB文件尚未完成"}
        try:
            info = path.stat()
            if not path.is_file():
                return {**result, "reason": "MP路径不是普通文件"}
        except PermissionError:
            self._stability.pop(str(path), None)
            return {**result, "reason": "MP无读取权限"}
        except OSError:
            self._stability.pop(str(path), None)
            return {**result, "reason": "MP内文件不存在，请核对挂载和qB→MP路径映射"}
        if info.st_size < self.min_size:
            return {**result, "reason": "文件为空或小于最小大小"}
        if file["size"] and info.st_size != file["size"]:
            self._stability.pop(str(path), None)
            return {**result, "reason": f"文件大小未就绪：MP {info.st_size} / qB {file['size']} 字节"}
        signature = (info.st_size, info.st_mtime_ns, info.st_ino)
        now, key = time.monotonic(), str(path)
        previous = self._stability.get(key)
        changed = previous is None or previous[0] != signature
        observed = (signature, now, 1) if changed else (signature, previous[1], previous[2] + 1)
        self._stability[key] = observed
        self._stability.move_to_end(key)
        while len(self._stability) > 8192:
            self._stability.popitem(last=False)
        result.update(signature=signature, size=info.st_size)
        if self.stable_interval == 0 or (now - observed[1] >= self.stable_interval and observed[2] >= self.stable_checks):
            return {**result, "ready": True, "reason": "就绪"}
        reason = "首次稳定观察" if previous is None else ("文件大小或修改时间有变化" if changed else "等待文件稳定")
        return {**result, "reason": f"{reason}，需要稳定 {self.stable_interval:g} 秒"}

    def _publish(self, torrent, status, message, files=None, **extra):
        ident = str(torrent.get("hash") or "")
        previous = self._tasks.get(ident, {})
        row = {**previous, "id": ident, "name": str(torrent.get("name") or ident), "source": "qb",
               "path": str(torrent.get("content_path") or torrent.get("save_path") or ""),
               "status": status, "message": message, "updated_at": time.time(), **extra}
        if files is not None:
            row.update(files=deepcopy(files), total=len(files), ready=sum(bool(x.get("ready")) for x in files))
            if files:
                row["path"] = files[0]["path"] if len(files) == 1 else str(Path(files[0]["path"]).parent)
        self._tasks[ident] = row
        marker = (status, message, row.get("ready"), row.get("total"))
        if self._messages.get(ident) != marker:
            self.log(f"{row['name']}：{message}（就绪 {row.get('ready', 0)}/{row.get('total', 0)}）")
            self._messages[ident] = marker
        self.status_callback(deepcopy(row))
        return row

    def snapshot(self):
        return deepcopy(list(self._tasks.values()))

    def process_once(self, remote_dir="", max_torrents=0):
        stats = {"checked": 0, "pushed": 0, "skipped": 0, "failed": 0}
        torrents = self.qb.completed_torrents(done_tag=self.done_tag)
        active = {str(x.get("hash")) for x in torrents if isinstance(x, dict) and x.get("hash")}
        for store in (self._tasks, self._messages, self._next_retry, self._attempts, self._skipped):
            for key in list(store):
                if key not in active:
                    store.pop(key, None)
        torrents = [x for x in torrents if isinstance(x, dict) and x.get("hash")]
        for torrent in torrents:
            if str(torrent["hash"]) not in self._tasks:
                self._publish(torrent, "waiting", "已发现已完成种子，等待本轮路径核对", total=0, ready=0)
        if torrents:
            start = self._cursor % len(torrents)
            ordered = (torrents[start:] + torrents[:start]) if max_torrents <= 0 else (torrents[start:] + torrents[:start])[:max(1, int(max_torrents))]
            self._cursor = (start + len(ordered)) % len(torrents)
        else:
            ordered = []
        for torrent in ordered:
            ident = str(torrent["hash"])
            stats["checked"] += 1
            if self._number(torrent.get("progress"), -1) < 1:
                self._publish(torrent, "waiting", "qB尚未确认种子完整完成")
                stats["skipped"] += 1
                continue
            until = self._next_retry.get(ident, 0)
            if until > time.time():
                stats["skipped"] += 1
                continue
            try:
                files, ignored = self._files(torrent)
                if not files:
                    self._publish(torrent, "skipped", f"无选中的匹配媒体文件；未选择文件 {ignored} 个", [])
                    stats["skipped"] += 1
                    continue
                details = [self._ready(x) for x in files]
                not_ready = [x for x in details if not x["ready"]]
                if not_ready:
                    first = not_ready[0]
                    self._publish(torrent, "waiting", f"{first['reason']}：{first['path']}", details)
                    stats["skipped"] += 1
                    continue
                fingerprints = tuple((x["path"], tuple(x["signature"])) for x in details)
                if self._skipped.get(ident) == (remote_dir, fingerprints):
                    stats["skipped"] += 1
                    continue
                self._publish(torrent, "uploading", f"媒体文件已就绪；仅处理选中文件（忽略 {ignored} 个未选文件）", details)
                all_ok, messages, permanent_skip = True, [], False
                for file in details:
                    key = (file["path"], tuple(file["signature"]), remote_dir)
                    if key in self._success_files:
                        self._success_files.move_to_end(key)
                        continue
                    try:
                        response = self.push(Path(file["path"]), remote_dir)
                    except Exception as exc:
                        response = {"ok": False, "message": str(exc)}
                    if response.get("ok") is True:
                        self._success_files[key] = True
                        while len(self._success_files) > 4096:
                            self._success_files.popitem(last=False)
                    else:
                        all_ok = False
                        permanent_skip |= bool(response.get("skipped"))
                        messages.append(file["name"] + "：" + str(response.get("message") or "秒传失败"))
                if all_ok:
                    # Only tag a torrent after all selected media files really succeeded.
                    self.qb.set_tag(ident, self.done_tag)
                    self._next_retry.pop(ident, None)
                    self._attempts.pop(ident, None)
                    self._publish(torrent, "success", "所有选中媒体文件秒传成功，已标记整理完成", details, next_retry=0)
                    stats["pushed"] += 1
                elif permanent_skip:
                    self._skipped[ident] = (remote_dir, fingerprints)
                    self._publish(torrent, "skipped", "; ".join(messages) + "；按未命中策略保留给MP整理，未打完成标签", details, next_retry=0)
                    stats["skipped"] += 1
                else:
                    raise QBError("; ".join(messages))
            except Exception as exc:
                self._attempts[ident] = self._attempts.get(ident, 0) + 1
                self._next_retry[ident] = time.time() + self.retry_interval
                self._publish(torrent, "failed", str(exc) + "；未打整理完成标签",
                              next_retry=self._next_retry[ident], attempts=self._attempts[ident])
                stats["failed"] += 1
        stats["tasks"] = self.snapshot()
        return stats
