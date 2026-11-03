"""Manual 115 push: user picks files, one click upload.

Compatible with both MoviePilot V2 and V3.
V2: from app.plugins import _PluginBase; from app.log import logger
V3: from app.sdk.plugins import _PluginBase; from app.sdk.logging import logger
The try/except import pattern keeps a single codebase running on both hosts.
"""
from __future__ import annotations

import os
import threading
import time
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from app.log import logger
except ImportError:
    from app.sdk.logging import logger

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
            return "{:.1f} {}".format(b, unit) if unit != "B" else "{} B".format(b)
        b /= 1024
    return "{:.1f} PB".format(b)


def stamp(t: Any = None) -> str:
    if t is None:
        t = time.time()
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(t)))
    except Exception:
        return str(t)


class RuntimeMixin:
    """Stateless manual push — no scheduler, no persistent queues.

    All instance attributes are guarded by _ensure_init() so that get_page()
    and get_api() work even if the host calls them before init_plugin().
    """

    STATE_KEY = "manualpush115_state"
    _lock = threading.Lock()

    def _ensure_init(self) -> None:
        """Lazy-initialize all runtime attributes if init_plugin hasn't run yet."""
        if hasattr(self, "_mp115_initialized"):
            return
        self._config = {
            "cookie": "",
            "user_agent": "",
            "remote_dir": "/",
            "local_paths": [],
            "extensions": "",
        }  # type: Dict[str, Any]
        self._history = []  # type: List[Dict[str, Any]]
        self._running = False
        self._progress = ""
        self._mp115_initialized = True

    def init_plugin(self, config: dict = None) -> None:
        self._ensure_init()
        config = config or {}
        self._config = {
            "cookie": str(config.get("cookie") or "").strip(),
            "user_agent": str(config.get("user_agent") or "").strip(),
            "remote_dir": str(config.get("remote_dir") or "/").strip() or "/",
            "local_paths": config.get("local_paths") or [],
            "extensions": str(config.get("extensions") or "").strip(),
        }
        try:
            stored = self.get_data(self.STATE_KEY) or {}
        except Exception:
            stored = {}
        self._history = list(stored.get("history") or [])[-500:]
        self._running = False
        self._progress = ""

    def get_state(self) -> bool:
        self._ensure_init()
        return bool(self._config.get("cookie"))

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"],
             "auth": "bear", "summary": "状态与历史"},
            {"path": "/push", "endpoint": self.api_push, "methods": ["POST"],
             "auth": "bear", "summary": "秒传设置中选好的文件"},
            {"path": "/test", "endpoint": self.api_test, "methods": ["POST"],
             "auth": "bear", "summary": "测试115凭据"},
            {"path": "/browse", "endpoint": self.api_browse, "methods": ["GET"],
             "auth": "bear", "summary": "浏览本地目录（JSON）"},
        ]

    # ---- API endpoints ----

    def api_status(self) -> dict:
        self._ensure_init()
        return {
            "success": True,
            "has_cookie": bool(self._config.get("cookie")),
            "remote_dir": self._config.get("remote_dir") or "/",
            "running": self._running,
            "progress": self._progress,
            "history": list(reversed(self._history[-100:])),
            "local_paths": self._config.get("local_paths") or [],
            "version": getattr(self, "plugin_version", ""),
        }

    def api_push(self, remote_dir: str = None) -> dict:
        self._ensure_init()
        # Read paths from saved config (VSelect multiple in settings)
        paths = self._config.get("local_paths") or []
        if isinstance(paths, str):
            paths = [p.strip() for p in paths.replace(",", "\n").split("\n") if p.strip()]
        if not paths:
            return {"success": False, "message": "未选择本地路径，请在设置中选择文件或文件夹后保存"}
        if not self._config.get("cookie"):
            return {"success": False, "message": "未配置 115 Cookie，请在设置中填写"}
        if self._running:
            return {"success": False, "message": "正在秒传中，请等待完成"}
        remote = (remote_dir or self._config.get("remote_dir") or "/").strip() or "/"
        files = self._collect_files(paths)
        done = {r["path"] for r in self._history if r.get("status") == "success"}
        fresh = [f for f in files if f not in done]
        skipped = len(files) - len(fresh)
        if not fresh:
            return {"success": True, "message": "选中的 {} 个文件均已秒传成功".format(len(files))}
        threading.Thread(target=self._push_files, args=(fresh, remote), daemon=True).start()
        msg = "已开始秒传 {} 个文件到 {}".format(len(fresh), remote)
        if skipped:
            msg += "（跳过 {} 个已成功）".format(skipped)
        return {"success": True, "message": msg}

    def api_test(self) -> dict:
        self._ensure_init()
        if not self._config.get("cookie"):
            return {"success": False, "message": "未配置 Cookie"}
        try:
            client = self._get_client()
            info = client.check_login()
            name = info.get("user_name") or info.get("user_id") or "已登录"
            return {"success": True, "message": "登录有效：{}".format(name)}
        except Exception as exc:
            return {"success": False, "message": "凭据无效：{}".format(exc)}

    def api_browse(self, path: str = "") -> dict:
        self._ensure_init()
        path = os.path.abspath(path) if path and path != "/" else "/"
        if path != "/" and not os.path.isdir(path):
            return {"success": False, "message": "目录不存在：{}".format(path)}
        entries = self._list_dir(path)
        parent = os.path.dirname(path) if path != "/" else None
        return {"success": True, "path": path, "parent": parent, "entries": entries}

    # ---- internal helpers ----

    def _list_dir(self, path):
        # type: (str) -> List[Dict[str, Any]]
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
                    if exts and not any(name.lower().endswith("." + e) for e in exts):
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

    def _collect_files(self, paths):
        # type: (List[str]) -> List[str]
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
                if not exts or any(f.lower().endswith("." + e) for e in exts):
                    filtered.append(f)
        for d in sorted(dirs):
            if any(d.startswith(parent + os.sep) for parent in dirs if parent != d):
                continue
            for root, _subdirs, names in os.walk(d):
                for name in sorted(names):
                    if name.startswith("."):
                        continue
                    full = os.path.join(root, name)
                    if exts and not any(name.lower().endswith("." + e) for e in exts):
                        continue
                    filtered.append(full)
        seen = set()  # type: Set[str]
        result = []
        for f in filtered:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return result

    def _push_files(self, files, remote_dir):
        # type: (List[str], str) -> None
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
                self._progress = "{}/{} {} ({}) · 成功{} 失败{}".format(
                    i, total, name, human_size(size), success, failed)
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
                    logger.warning("{LOG}秒传失败 {name}: {exc}".format(LOG=LOG, name=name, exc=exc))
                self._history.append(record)
                if i % 5 == 0 or i == total or record["status"] == "failed":
                    self._persist()
                if consecutive_errors >= 10:
                    self._progress = "中止：连续10个失败 · 成功{} 失败{}".format(success, failed)
                    logger.error("{}连续失败10次，中止".format(LOG))
                    self._persist()
                    return
            self._progress = "完成：{} 成功，{} 失败（共 {}）".format(success, failed, total)
            logger.info("{}{}".format(LOG, self._progress))
            self._persist()
        except Exception as exc:
            self._progress = "秒传异常：{}".format(exc)
            logger.error("{}{}".format(LOG, traceback.format_exc()))
            self._persist()
        finally:
            self._running = False

    def _get_client(self):
        key = (self._config["cookie"], self._config.get("user_agent") or "")
        if not hasattr(self, "_client_cache") or getattr(self, "_client_cache", (None,))[0] != key:
            self._client_cache = (key, P115WebClient(
                cookie=self._config["cookie"],
                user_agent=self._config.get("user_agent") or ""))
        return self._client_cache[1]

    def _get_dir_id(self, client, remote_dir):
        # type: (Any, str) -> int
        if not hasattr(self, "_dir_cache"):
            self._dir_cache = {}
        if remote_dir not in self._dir_cache:
            self._dir_cache[remote_dir] = client.get_dir_id_by_path(remote_dir)
        return self._dir_cache[remote_dir]

    def _persist(self):
        try:
            self.save_data(self.STATE_KEY, {"history": self._history[-500:]})
        except Exception as exc:
            logger.warning("{}保存历史失败：{}".format(LOG, exc))

    def _allowed_extensions(self):
        # type: () -> Set[str]
        raw = self._config.get("extensions") or ""
        if not raw.strip():
            return DEFAULT_EXTS
        return {e.strip().lower().lstrip(".") for e in raw.replace(",", " ").split() if e.strip()}

    def _scan_local_options(self):
        # type: () -> List[Dict[str, str]]
        """Discover local mount points for VSelect. Uses DirectoryHelper like Qb115RapidUpload."""
        candidates = []

        # 1. Read from MoviePilot DirectoryHelper (most reliable)
        try:
            try:
                from app.helper.directory import DirectoryHelper
            except ImportError:
                from app.sdk.services import DirectoryHelper  # type: ignore
            helper = DirectoryHelper()
            # get_dirs() returns all configured directories
            for directory in (getattr(helper, "get_dirs", lambda: [])() or []):
                storage = str(getattr(directory, "storage", "local") or "local").strip().lower()
                if storage != "local":
                    continue
                for attr in ("download_path", "library_path", "path"):
                    path = str(getattr(directory, attr, "") or "").strip()
                    if path and os.path.isdir(path) and path not in candidates:
                        candidates.append(path)
            # get_local_download_dirs() if available
            for directory in (getattr(helper, "get_local_download_dirs", lambda: [])() or []):
                path = str(getattr(directory, "download_path", "") or "").strip()
                if path and os.path.isdir(path) and path not in candidates:
                    candidates.append(path)
        except Exception as exc:
            logger.debug("{}DirectoryHelper读取失败: {}".format(LOG, exc))

        # 2. Read from settings as fallback
        try:
            try:
                from app.core.config import settings as mp_settings
            except ImportError:
                from app.sdk.config import settings as mp_settings  # type: ignore
            for attr in ("LIBRARY_PATH", "DOWNLOAD_PATH", "MEDIA_PATH",
                         "LIBRARY_CATEGORY_PATH", "TRANSFER_PATH",
                         "library_path", "download_path"):
                val = getattr(mp_settings, attr, None)
                if val and isinstance(val, str) and os.path.isdir(val) and val not in candidates:
                    candidates.append(val)
                elif val and isinstance(val, (list, tuple)):
                    for v in val:
                        v = str(v).strip()
                        if v and os.path.isdir(v) and v not in candidates:
                            candidates.append(v)
        except Exception:
            pass

        # 3. Scan /proc/mounts for real mount points (docker bind mounts)
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mount_point = parts[1]
                        # Skip system mounts
                        if mount_point in ("/", "/proc", "/sys", "/dev", "/run", "/tmp",
                                           "/etc", "/var", "/usr", "/bin", "/sbin", "/lib"):
                            continue
                        if mount_point.startswith(("/proc/", "/sys/", "/dev/")):
                            continue
                        if os.path.isdir(mount_point) and mount_point not in candidates:
                            candidates.append(mount_point)
        except Exception:
            pass

        # 4. Common fallback paths
        for path in ["/media", "/mnt", "/downloads", "/data", "/volume1",
                     "/movie", "/tv", "/music", "/video", "/nas"]:
            if os.path.isdir(path) and path not in candidates:
                candidates.append(path)

        # 5. Include currently saved paths
        saved = self._config.get("local_paths") or []
        if isinstance(saved, str):
            saved = [s.strip() for s in saved.split("\n") if s.strip()]
        for s in saved:
            s = os.path.abspath(s)
            if os.path.isdir(s) and s not in candidates:
                candidates.append(s)

        # Build options: each candidate + first-level subdirs
        seen = set()  # type: Set[str]
        result = []
        for c in candidates:
            c = os.path.abspath(c)
            if c in seen:
                continue
            seen.add(c)
            result.append({"title": c, "value": c})
            try:
                for name in sorted(os.listdir(c))[:50]:
                    if name.startswith("."):
                        continue
                    full = os.path.join(c, name)
                    if os.path.isdir(full) and full not in seen:
                        seen.add(full)
                        result.append({"title": "  " + full, "value": full})
            except (PermissionError, OSError):
                pass
        return result[:500]

    @staticmethod
    def get_command():
        # type: () -> List[Dict[str, Any]]
        return []

    def _scan_remote_options(self):
        # type: () -> List[Dict[str, str]]
        """Read real 115 directories using saved Cookie. Returns VSelect items."""
        cookie = self._config.get("cookie") or ""
        if not cookie:
            return [{"title": "/（未配置 Cookie，请先保存）", "value": "/"}]
        try:
            client = self._get_client()
            result = [{"title": "/（根目录）", "value": "/"}]
            seen = {"/"}
            # Root level
            root_data = client.browse(0)
            for entry in root_data.get("entries") or []:
                path = "/" + entry["name"]
                if path not in seen:
                    seen.add(path)
                    result.append({"title": path, "value": path})
                    # One level deeper
                    try:
                        sub_data = client.browse(entry["cid"])
                        for sub in (sub_data.get("entries") or [])[:30]:
                            sub_path = path + "/" + sub["name"]
                            if sub_path not in seen:
                                seen.add(sub_path)
                                result.append({"title": "  " + sub_path, "value": sub_path})
                    except Exception:
                        pass
                if len(result) > 200:
                    break
            # Include saved value if not already present
            saved = self._config.get("remote_dir") or "/"
            if saved and saved not in seen:
                result.insert(1, {"title": saved, "value": saved})
            return result
        except Exception as exc:
            logger.debug("{}读取115目录失败：{}".format(LOG, exc))
            saved = self._config.get("remote_dir") or "/"
            return [
                {"title": "/（根目录）", "value": "/"},
                {"title": saved, "value": saved} if saved != "/" else None,
                {"title": "（读取失败：{}）".format(str(exc)[:60]), "value": saved},
            ]

    def stop_service(self):
        # type: () -> None
        pass
