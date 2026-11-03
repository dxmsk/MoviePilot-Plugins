"""Manual 115 push: user picks files, one click upload."""
from __future__ import annotations

import os
import threading
import time
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.log import logger
from app.plugins import _PluginBase

from .filehash import sha1_file
from .p115_web import P115WebClient, P115WebError

LOG = "【手动秒传115】"
DEFAULT_EXTS = {"mkv", "mp4", "avi", "ts", "rmvb", "wmv", "flv", "mov", "m4v",
                "srt", "ass", "ssa", "sub", "sup", "idx",
                "mp3", "flac", "aac", "wav", "m4a", "ogg", "wma",
                "nfo", "jpg", "jpeg", "png"}


def human_size(n: Any) -> str:
    try:
        b = int(n)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
        b /= 1024
    return f"{b:.1f} PB"


def stamp(t: Any = None) -> str:
    if t is None:
        t = time.time()
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(t)))
    except Exception:
        return str(t)


class RuntimeMixin:
    """Stateless manual push — no scheduler, no persistent queues."""

    STATE_KEY = "manualpush115_state"
    _lock = threading.Lock()

    def init_plugin(self, config: dict = None) -> None:
        config = config or {}
        self._config = {
            "cookie": str(config.get("cookie") or "").strip(),
            "user_agent": str(config.get("user_agent") or "").strip(),
            "remote_dir": str(config.get("remote_dir") or "/").strip() or "/",
            "extensions": str(config.get("extensions") or "").strip(),
        }
        stored = self.get_data(self.STATE_KEY) or {}
        self._history = list(stored.get("history") or [])[-500:]
        self._running = False
        self._progress = ""
        # Server-side browser state (survives page refresh)
        if not hasattr(self, "_browse_path"):
            self._browse_path = "/"
        if not hasattr(self, "_selected"):
            self._selected: dict[str, dict] = {}  # path → {name, is_dir, size}

    def get_state(self) -> bool:
        return bool(self._config.get("cookie"))

    def get_api(self) -> list[dict]:
        return [
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"],
             "auth": "bear", "summary": "状态与历史"},
            {"path": "/push", "endpoint": self.api_push, "methods": ["POST"],
             "auth": "bear", "summary": "秒传选中文件"},
            {"path": "/navigate", "endpoint": self.api_navigate, "methods": ["POST"],
             "auth": "bear", "summary": "浏览目录"},
            {"path": "/select", "endpoint": self.api_select, "methods": ["POST"],
             "auth": "bear", "summary": "选择/取消文件"},
            {"path": "/clear", "endpoint": self.api_clear, "methods": ["POST"],
             "auth": "bear", "summary": "清空选择"},
            {"path": "/test", "endpoint": self.api_test, "methods": ["POST"],
             "auth": "bear", "summary": "测试115凭据"},
            {"path": "/browse", "endpoint": self.api_browse, "methods": ["GET"],
             "auth": "bear", "summary": "浏览本地目录（JSON）"},
        ]

    # ---- API endpoints ----

    def api_status(self) -> dict:
        return {
            "success": True,
            "has_cookie": bool(self._config.get("cookie")),
            "remote_dir": self._config["remote_dir"],
            "running": self._running,
            "progress": self._progress,
            "history": list(reversed(self._history[-100:])),
            "selected_count": len(self._selected),
            "browse_path": self._browse_path,
            "version": getattr(self, "plugin_version", ""),
        }

    def api_navigate(self, path: str = "/") -> dict:
        path = os.path.abspath(path) if path and path != "/" else "/"
        if path != "/" and not os.path.isdir(path):
            return {"success": False, "message": f"目录不存在：{path}"}
        self._browse_path = path
        return {"success": True}

    def api_select(self, path: str = "", action: str = "toggle") -> dict:
        """action: toggle / select / deselect / select_all_files / deselect_all"""
        if action == "deselect_all":
            self._selected.clear()
            return {"success": True, "selected_count": 0}
        if action == "select_all_files":
            entries = self._list_dir(self._browse_path)
            for e in entries:
                self._selected[e["path"]] = e
            return {"success": True, "selected_count": len(self._selected)}
        path = os.path.abspath(path) if path else ""
        if not path or (not os.path.exists(path)):
            return {"success": False, "message": "路径无效"}
        if action == "deselect" or (action == "toggle" and path in self._selected):
            self._selected.pop(path, None)
        else:
            entry = {"path": path, "name": os.path.basename(path),
                     "is_dir": os.path.isdir(path), "size": 0}
            if os.path.isfile(path):
                try:
                    entry["size"] = os.path.getsize(path)
                except OSError:
                    pass
            self._selected[path] = entry
        return {"success": True, "selected_count": len(self._selected)}

    def api_push(self, remote_dir: str = None) -> dict:
        if not self._selected:
            return {"success": False, "message": "未选择文件，请先在文件浏览器中勾选"}
        if not self._config.get("cookie"):
            return {"success": False, "message": "未配置 115 Cookie，请在设置中填写"}
        if self._running:
            return {"success": False, "message": "正在秒传中，请等待完成"}
        remote = (remote_dir or self._config["remote_dir"]).strip() or "/"
        paths = list(self._selected.keys())
        files = self._collect_files(paths)
        done = {r["path"] for r in self._history if r.get("status") == "success"}
        fresh = [f for f in files if f not in done]
        skipped = len(files) - len(fresh)
        if not fresh:
            return {"success": True, "message": f"选中的 {len(files)} 个文件均已秒传成功"}
        self._selected.clear()
        threading.Thread(target=self._push_files, args=(fresh, remote), daemon=True).start()
        msg = f"已开始秒传 {len(fresh)} 个文件到 {remote}"
        if skipped:
            msg += f"（跳过 {skipped} 个已成功）"
        return {"success": True, "message": msg}

    def api_test(self) -> dict:
        if not self._config.get("cookie"):
            return {"success": False, "message": "未配置 Cookie"}
        try:
            client = self._get_client()
            info = client.check_login()
            name = info.get("user_name") or info.get("user_id") or "已登录"
            return {"success": True, "message": f"登录有效：{name}"}
        except Exception as exc:
            return {"success": False, "message": f"凭据无效：{exc}"}

    def api_browse(self, path: str = "") -> dict:
        """JSON API for directory listing (kept for external callers)."""
        path = os.path.abspath(path) if path and path != "/" else "/"
        if path != "/" and not os.path.isdir(path):
            return {"success": False, "message": f"目录不存在：{path}"}
        entries = self._list_dir(path)
        parent = os.path.dirname(path) if path != "/" else None
        return {"success": True, "path": path, "parent": parent, "entries": entries}

    # ---- internal helpers ----

    def _list_dir(self, path: str) -> list[dict]:
        if not path or path == "/":
            roots = ["/media", "/mnt", "/downloads", "/data", "/volume1", "/opt",
                     "/movie", "/tv", "/music", "/video"]
            return [{"name": r, "path": r, "is_dir": True, "size": 0}
                    for r in roots if os.path.isdir(r)]
        if not os.path.isdir(path):
            return []
        exts = self._allowed_extensions()
        entries = []
        try:
            for name in sorted(os.listdir(path)):
                if name.startswith("."):
                    continue
                full = os.path.join(path, name)
                if os.path.isdir(full):
                    entries.append({"name": name, "path": full, "is_dir": True, "size": 0})
                elif os.path.isfile(full):
                    if exts and not any(name.lower().endswith(f".{e}") for e in exts):
                        continue
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    entries.append({"name": name, "path": full, "is_dir": False,
                                    "size": size, "size_text": human_size(size)})
        except PermissionError:
            pass
        return entries[:2000]

    def _collect_files(self, paths: list[str]) -> list[str]:
        exts = self._allowed_extensions()
        dirs = set()
        explicit_files = []
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                dirs.add(p)
            elif os.path.isfile(p):
                explicit_files.append(p)
        filtered = []
        for f in explicit_files:
            if not any(f.startswith(d + os.sep) for d in dirs):
                if not exts or any(f.lower().endswith(f".{e}") for e in exts):
                    filtered.append(f)
        for d in sorted(dirs):
            if any(d.startswith(parent + os.sep) for parent in dirs if parent != d):
                continue
            for root, _subdirs, names in os.walk(d):
                for name in sorted(names):
                    if name.startswith("."):
                        continue
                    full = os.path.join(root, name)
                    if exts and not any(name.lower().endswith(f".{e}") for e in exts):
                        continue
                    filtered.append(full)
        seen = set()
        return [f for f in filtered if f not in seen and not seen.add(f)]

    def _push_files(self, files: list[str], remote_dir: str):
        with self._lock:
            if self._running:
                return
            self._running = True
        consecutive_errors = 0
        try:
            client = self._get_client()
            dir_id = self._get_dir_id(client, remote_dir)
            total = len(files)
            success = failed = 0
            for i, filepath in enumerate(files, 1):
                name = os.path.basename(filepath)
                try:
                    size = os.path.getsize(filepath)
                except OSError:
                    size = 0
                self._progress = f"{i}/{total} {name} ({human_size(size)}) · 成功{success} 失败{failed}"
                record = {"name": name, "path": filepath, "remote_dir": remote_dir,
                          "size": size, "time": stamp()}
                try:
                    if not os.path.isfile(filepath):
                        record.update(status="failed", message="文件不存在或已被移动")
                        failed += 1
                    else:
                        result = client.push_file(Path(filepath), remote_dir_id=dir_id)
                        if result.get("ok") or result.get("status") == 2:
                            record["status"] = "success"
                            record["message"] = "SHA1秒传成功" + ("（已存在）" if result.get("reuse") else "")
                            success += 1
                            consecutive_errors = 0
                        else:
                            record["status"] = "failed"
                            record["message"] = result.get("message") or str(result)
                            failed += 1
                            consecutive_errors += 1
                except Exception as exc:
                    record.update(status="failed", message=str(exc))
                    failed += 1
                    consecutive_errors += 1
                    logger.warning(f"{LOG}秒传失败 {name}: {exc}")
                self._history.append(record)
                if i % 5 == 0 or i == total or record["status"] == "failed":
                    self._persist()
                if consecutive_errors >= 10:
                    self._progress = f"中止：连续10个失败，请检查网络或Cookie · 成功{success} 失败{failed}"
                    logger.error(f"{LOG}连续失败10次，中止")
                    self._persist()
                    return
            self._progress = f"完成：{success} 成功，{failed} 失败（共 {total}）"
            logger.info(f"{LOG}{self._progress}")
            self._persist()
        except Exception as exc:
            self._progress = f"秒传异常：{exc}"
            logger.error(f"{LOG}{traceback.format_exc()}")
            self._persist()
        finally:
            self._running = False

    def _get_client(self):
        key = (self._config["cookie"], self._config.get("user_agent") or "")
        if not hasattr(self, "_client_cache") or self._client_cache[0] != key:
            self._client_cache = (key, P115WebClient(
                cookie=self._config["cookie"],
                user_agent=self._config.get("user_agent") or ""))
        return self._client_cache[1]

    def _get_dir_id(self, client, remote_dir: str) -> int:
        if not hasattr(self, "_dir_cache"):
            self._dir_cache = {}
        if remote_dir not in self._dir_cache:
            self._dir_cache[remote_dir] = client.get_dir_id_by_path(remote_dir)
        return self._dir_cache[remote_dir]

    def _persist(self):
        try:
            self.save_data(self.STATE_KEY, {"history": self._history[-500:]})
        except Exception as exc:
            logger.warning(f"{LOG}保存历史失败：{exc}")

    def _allowed_extensions(self) -> set:
        raw = self._config.get("extensions") or ""
        if not raw.strip():
            return DEFAULT_EXTS
        return {e.strip().lower().lstrip(".") for e in raw.replace(",", " ").split() if e.strip()}

    @staticmethod
    def get_command() -> list[dict]:
        return []

    def stop_service(self) -> None:
        pass
