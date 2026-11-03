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

    def get_state(self) -> bool:
        return bool(self._config.get("cookie"))

    def get_api(self) -> list[dict]:
        return [
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"],
             "auth": "bear", "summary": "状态与历史"},
            {"path": "/push", "endpoint": self.api_push, "methods": ["POST"],
             "auth": "bear", "summary": "秒传指定文件"},
            {"path": "/browse", "endpoint": self.api_browse, "methods": ["GET"],
             "auth": "bear", "summary": "浏览本地目录"},
            {"path": "/test", "endpoint": self.api_test, "methods": ["POST"],
             "auth": "bear", "summary": "测试115凭据"},
        ]

    def api_status(self) -> dict:
        return {
            "success": True,
            "has_cookie": bool(self._config.get("cookie")),
            "remote_dir": self._config["remote_dir"],
            "running": self._running,
            "progress": self._progress,
            "history": list(reversed(self._history[-100:])),
            "version": getattr(self, "plugin_version", ""),
        }

    def api_browse(self, path: str = "") -> dict:
        """List directories and files at the given local path."""
        roots = ["/media", "/mnt", "/downloads", "/data", "/volume1", "/opt"]
        if not path or path == "/":
            entries = []
            for root in roots:
                if os.path.isdir(root):
                    entries.append({"name": root, "path": root, "is_dir": True, "size": 0})
            # Also include configured paths
            for p in ["/media", "/mnt", "/downloads"]:
                if os.path.isdir(p) and not any(e["path"] == p for e in entries):
                    entries.append({"name": p, "path": p, "is_dir": True, "size": 0})
            return {"success": True, "path": "/", "parent": None, "entries": entries}
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return {"success": False, "message": f"目录不存在：{path}"}
        parent = os.path.dirname(path) if path != "/" else None
        entries = []
        exts = self._allowed_extensions()
        try:
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                if name.startswith("."):
                    continue
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
            return {"success": False, "message": f"无权访问：{path}"}
        return {"success": True, "path": path, "parent": parent,
                "entries": entries[:2000]}

    def api_push(self, paths: list[str] = None, remote_dir: str = None) -> dict:
        """Push selected files to 115."""
        if not paths:
            return {"success": False, "message": "未选择文件"}
        if not self._config.get("cookie"):
            return {"success": False, "message": "未配置 115 Cookie，请在设置中填写"}
        if self._running:
            return {"success": False, "message": "正在秒传中，请等待完成后再试"}
        remote = (remote_dir or self._config["remote_dir"]).strip() or "/"
        # Collect and deduplicate files
        files = self._collect_files(paths)
        if not files:
            return {"success": False, "message": "选中路径中没有符合条件的文件"}
        # Skip files that already succeeded in history
        done = {r["path"] for r in self._history if r.get("status") == "success"}
        skippable = [f for f in files if f in done]
        fresh = [f for f in files if f not in done]
        msg_parts = [f"已开始秒传 {len(fresh)} 个文件到 {remote}"]
        if skippable:
            msg_parts.append(f"（跳过 {len(skippable)} 个已成功的文件）")
        if not fresh:
            return {"success": True, "message": f"选中的 {len(files)} 个文件均已秒传成功，无需重复操作"}
        threading.Thread(target=self._push_files, args=(fresh, remote),
                         daemon=True).start()
        return {"success": True, "message": "".join(msg_parts)}

    def _collect_files(self, paths: list[str]) -> list[str]:
        """Deduplicate: if a directory is selected, don't also include its children individually."""
        exts = self._allowed_extensions()
        dirs = set()
        explicit_files = []
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                dirs.add(p)
            elif os.path.isfile(p):
                explicit_files.append(p)
        # Remove files whose parent dir is also selected (dir walk will cover them)
        filtered_files = []
        for f in explicit_files:
            if not any(f.startswith(d + os.sep) for d in dirs):
                if not exts or any(f.lower().endswith(f".{e}") for e in exts):
                    filtered_files.append(f)
        # Walk selected directories
        for d in sorted(dirs):
            # Skip subdirs of another selected dir
            if any(d.startswith(parent + os.sep) for parent in dirs if parent != d):
                continue
            for root, _subdirs, names in os.walk(d):
                for name in sorted(names):
                    if name.startswith("."):
                        continue
                    full = os.path.join(root, name)
                    if exts and not any(name.lower().endswith(f".{e}") for e in exts):
                        continue
                    filtered_files.append(full)
        # Final dedup preserving order
        seen = set()
        result = []
        for f in filtered_files:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return result

    def api_test(self) -> dict:
        if not self._config.get("cookie"):
            return {"success": False, "message": "未配置 Cookie"}
        try:
            client = P115WebClient(cookie=self._config["cookie"],
                                   user_agent=self._config.get("user_agent") or "")
            info = client.check_login()
            name = info.get("user_name") or info.get("user_id") or "已登录"
            return {"success": True, "message": f"✅ 登录有效：{name}"}
        except Exception as exc:
            return {"success": False, "message": f"❌ {exc}"}

    def _push_files(self, files: list[str], remote_dir: str):
        with self._lock:
            if self._running:
                return
            self._running = True
        consecutive_errors = 0
        MAX_CONSECUTIVE = 10
        try:
            client = self._get_client()
            dir_id = self._get_dir_id(client, remote_dir)
            total = len(files)
            success = failed = skipped = 0
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
                except P115WebError as exc:
                    record.update(status="failed", message=str(exc))
                    failed += 1
                    consecutive_errors += 1
                    logger.warning(f"{LOG}秒传失败 {name}: {exc}")
                except Exception as exc:
                    record.update(status="failed", message=str(exc))
                    failed += 1
                    consecutive_errors += 1
                    logger.warning(f"{LOG}秒传异常 {name}: {exc}")
                self._history.append(record)
                # Save after each file so progress survives a crash
                if i % 5 == 0 or i == total or record["status"] == "failed":
                    self._persist()
                # Abort if too many consecutive failures (likely auth/network issue)
                if consecutive_errors >= MAX_CONSECUTIVE:
                    self._progress = f"中止：连续 {MAX_CONSECUTIVE} 个文件失败，请检查网络或 Cookie · 成功{success} 失败{failed}"
                    logger.error(f"{LOG}连续失败 {MAX_CONSECUTIVE} 次，中止秒传")
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
        """Reuse client within a session; recreate only if cookie changes."""
        key = (self._config["cookie"], self._config.get("user_agent") or "")
        if not hasattr(self, "_client_cache") or self._client_cache[0] != key:
            self._client_cache = (key, P115WebClient(
                cookie=self._config["cookie"],
                user_agent=self._config.get("user_agent") or ""))
        return self._client_cache[1]

    def _get_dir_id(self, client, remote_dir: str) -> int:
        """Cache dir_id per remote_dir to avoid repeated API calls."""
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
            return set()
        return {e.strip().lower().lstrip(".") for e in raw.replace(",", " ").split() if e.strip()}

    @staticmethod
    def get_command() -> list[dict]:
        return []

    def stop_service(self) -> None:
        pass
