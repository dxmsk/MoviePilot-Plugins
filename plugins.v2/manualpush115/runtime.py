"""On-demand local browser/search and isolated manual 115 transfer jobs."""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path

from fastapi import Body
try:
    from app.log import logger
except ImportError:
    from app.sdk.logging import logger

from .localfiles import LocalFiles, discover_roots
from .p115_web import P115WebClient, P115AuthError
from .remotefiles import browse_remote
from .settings import DEFAULTS, PushPayload, SettingsPayload, allowed_extensions, normalize_config, paths_list, remote_path
from .transfer import TransferMixin

LOG = "【手动秒传115】"
_BOOTSTRAP = threading.Lock()


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def reply(data=None, message="", success=True):
    return {"success": bool(success), "message": str(message), "data": data if data is not None else {}}


class RuntimeMixin(TransferMixin):
    STATE_KEY = "manualpush115_state"

    def _ensure_init(self):
        if getattr(self, "_initialized", False):
            return
        with _BOOTSTRAP:
            if getattr(self, "_initialized", False):
                return
            self._guard = threading.RLock()
            self._save_guard = threading.Lock()
            self._config_guard = threading.Lock()
            self._search_guard = threading.Lock()
            self._config = normalize_config(DEFAULTS)
            self._revision = 0
            self._history = []
            self._job = {"phase": "idle", "total": 0, "processed": 0, "success": 0,
                         "failed": 0, "skipped": 0, "remaining": 0, "errors": []}
            self._running = False
            self._cancel = threading.Event()
            self._worker = None
            self._requests = {}
            self._roots_cache = None
            self._persist_error = ""
            try:
                stored = self.get_data(self.STATE_KEY) or {}
                if isinstance(stored, dict):
                    self._history = [dict(row) for row in stored.get("history", []) if isinstance(row, dict)][-500:]
                    job = stored.get("job")
                    if isinstance(job, dict) and job.get("id"):
                        self._job.update(job)
                        if job.get("phase") in ("collecting", "running", "cancelling"):
                            self._job.update(phase="interrupted", current_file="", finished_at=stamp())
                            self._job["message"] = "上次任务在重启时中断；选择未完成文件后可再次补传"
            except Exception as exc:
                self._persist_error = "读取历史失败：" + str(type(exc).__name__)
            self._initialized = True

    def init_plugin(self, config=None):
        self._ensure_init()
        normalized = normalize_config(config or {})
        with self._guard:
            if normalized != self._config:
                self._revision += 1
            self._config = normalized
            self._roots_cache = None
            # A running transfer owns its configuration snapshot and survives a
            # settings save. Never reset its running flag/history here.

    def get_state(self):
        self._ensure_init()
        return bool(self._config.get("cookie"))

    def _error(self, exc, cfg=None):
        text = str(exc)
        cookie = str((cfg or self._config).get("cookie") or "")
        if cookie:
            text = text.replace(cookie, "[Cookie]")
        text = re.sub(r"(?i)\b(UID|CID|SEID|KID|token|userkey)\s*=\s*[^;\s&]+", r"\1=[已隐藏]", text)
        text = re.sub(r"(https?://[^?\s]+)\?[^\s]+", r"\1?[已隐藏]", text)
        return text[:700]

    def get_api(self):
        routes = [("status", self.api_status, ["GET"]), ("settings", self.api_settings, ["GET"]),
                  ("settings", self.api_save_settings, ["POST"]), ("roots", self.api_roots, ["GET"]),
                  ("browse", self.api_browse, ["GET"]), ("search", self.api_search, ["GET"]),
                  ("remote", self.api_remote, ["GET"]), ("push", self.api_push, ["POST"]),
                  ("cancel", self.api_cancel, ["POST"]), ("test", self.api_test, ["POST"])]
        return [{"path": "/" + name, "endpoint": fn, "methods": methods,
                 "auth": "bear", "summary": "手动秒传：" + name} for name, fn, methods in routes]

    def api_status(self):
        self._ensure_init()
        with self._guard:
            return reply({"plugin_id": type(self).__name__, "version": self.plugin_version,
                          "has_cookie": bool(self._config.get("cookie")),
                          "remote_dir": self._config["remote_dir"],
                          "local_paths": list(self._config["local_paths"]),
                          "failure_move_enabled": bool(self._config.get("failure_move_enabled")),
                          "failure_move_dir": self._config.get("failure_move_dir", ""),
                          "delete_on_success": bool(self._config.get("delete_on_success")),
                          "failure_move_preserve_structure": bool(self._config.get("failure_move_preserve_structure", True)),
                          "running": self._running,
                          "job": deepcopy(self._job), "history": deepcopy(self._history[-100:][::-1]),
                          "persist_error": self._persist_error})

    def api_settings(self):
        self._ensure_init()
        with self._guard:
            return reply({"settings": deepcopy(self._config), "revision": self._revision})

    def api_save_settings(self, payload: SettingsPayload):
        self._ensure_init()
        if isinstance(payload, dict):
            payload = SettingsPayload(**payload)
        try:
            with self._config_guard:
                with self._guard:
                    cfg = {**self._config, **payload.model_dump(exclude_unset=True)}
                cfg = normalize_config(cfg)
                self.update_config(deepcopy(cfg))
                self.init_plugin(cfg)
            return self.api_settings()
        except Exception as exc:
            return reply(message="保存设置失败：" + self._error(exc), success=False)

    def _root_data(self, force=False):
        with self._guard:
            cached, revision, cfg = self._roots_cache, self._revision, deepcopy(self._config)
            if not force and cached and cached[0] == revision and time.monotonic() - cached[1] < 30:
                return deepcopy(cached[2])
        data = discover_roots(cfg)
        with self._guard:
            if revision == self._revision:
                self._roots_cache = (revision, time.monotonic(), deepcopy(data))
        return data

    def _files(self, cfg=None, root_data=None):
        return LocalFiles((root_data or self._root_data())["roots"], allowed_extensions(cfg or self._config))

    def api_roots(self, force: bool = False):
        self._ensure_init()
        try:
            return reply(self._root_data(force))
        except Exception as exc:
            return reply(message="读取挂载根目录失败：" + self._error(exc), success=False)

    def api_browse(self, path: str = "", offset: int = 0, limit: int = 100):
        self._ensure_init()
        try:
            return reply(self._files().list(path, offset=offset, limit=limit))
        except Exception as exc:
            return reply(message="读取本地目录失败：" + self._error(exc), success=False)

    def api_search(self, query: str, path: str = "", recursive: bool = False, offset: int = 0, limit: int = 100):
        self._ensure_init()
        if not query.strip():
            return reply(message="请输入要查找的文件名", success=False)
        if not self._search_guard.acquire(blocking=False):
            return reply(message="上一次搜索仍在进行，请稍后重试", success=False)
        try:
            return reply(self._files().search(path, query, recursive=recursive, offset=offset, limit=limit))
        except Exception as exc:
            return reply(message="搜索失败：" + self._error(exc), success=False)
        finally:
            self._search_guard.release()

    def _make_client(self, cfg):
        return P115WebClient(cookie=cfg["cookie"], user_agent=cfg.get("user_agent") or "")

    def api_remote(self, cid: str = "0", offset: int = 0, limit: int = 100):
        self._ensure_init()
        with self._guard:
            cfg = deepcopy(self._config)
        if not cfg.get("cookie"):
            return reply(message="先在设置中保存 115 Cookie，再选择网盘目录", success=False)
        try:
            return reply(browse_remote(self._make_client(cfg), cid, offset, limit))
        except Exception as exc:
            return reply(message="读取115目录失败：" + self._error(exc, cfg), success=False)

    def api_test(self):
        self._ensure_init()
        with self._guard:
            cfg = deepcopy(self._config)
        if not cfg.get("cookie"):
            return reply(message="尚未保存115 Cookie", success=False)
        try:
            info = self._make_client(cfg).check_login()
            name = info.get("user_name") or info.get("user_id") or "已登录"
            return reply(message="登录有效：" + str(name))
        except Exception as exc:
            return reply(message="凭据测试失败：" + self._error(exc, cfg), success=False)

    def api_push(self, payload: PushPayload = Body(default=None)):
        self._ensure_init()
        if isinstance(payload, dict):
            payload = PushPayload(**payload)
        if not isinstance(payload, PushPayload):
            payload = PushPayload()
        try:
            with self._guard:
                cfg = deepcopy(self._config)
            paths = paths_list(payload.paths if "paths" in payload.model_fields_set else cfg.get("local_paths"))
            if not paths:
                return reply(message="请在首页选择文件或文件夹", success=False)
            if not cfg.get("cookie"):
                return reply(message="先在设置中保存115 Cookie", success=False)
            target = remote_path(payload.remote_dir or cfg["remote_dir"])
            if payload.remote_cid is not None and not str(payload.remote_cid).isdecimal():
                return reply(message="115 目录ID无效", success=False)
            root_data = self._root_data()
            files = self._files(cfg, root_data)
            paths = list(dict.fromkeys(files.validate(path) for path in paths))
            request_id = payload.request_id or uuid.uuid4().hex
            fingerprint = hashlib.sha256(repr((paths, target, payload.remote_cid, payload.force,
                                               payload.preserve_structure, self._account(cfg))).encode()).hexdigest()
            with self._guard:
                previous = self._requests.get(request_id)
                if previous:
                    if previous[0] != fingerprint:
                        return reply(message="重复请求标识对应的内容已变化，请重新提交", success=False)
                    return reply({"job_id": previous[1], "accepted": len(paths)}, "该请求已接收")
                if self._running:
                    return reply(message="已有秒传任务正在执行", success=False)
                job_id = uuid.uuid4().hex
                self._cancel = threading.Event()
                cancel = self._cancel
                self._job = {"id": job_id, "phase": "collecting", "total": 0, "processed": 0,
                             "success": 0, "failed": 0, "skipped": 0, "remaining": 0, "errors": [],
                             "current_file": "", "started_at": stamp(), "finished_at": "",
                             "remote_dir": target, "selected_paths": list(paths),
                             "message": "正在收集选中的文件；没有自动扫描其他目录"}
                self._running = True  # Claim BEFORE dispatch, not inside the new thread.
                self._requests[request_id] = (fingerprint, job_id)
                self._requests = dict(list(self._requests.items())[-100:])
                self._worker = threading.Thread(target=self._run_transfer,
                    args=(job_id, files, paths, target, payload.remote_cid, cfg,
                          payload.force, payload.preserve_structure, cancel),
                    name="manual115-" + job_id[:8], daemon=True)
                worker = self._worker
            self._persist()
            try:
                worker.start()
            except Exception:
                with self._guard:
                    self._running = False
                    self._requests.pop(request_id, None)
                    self._job.update(phase="failed", message="创建秒传任务失败", finished_at=stamp())
                self._persist()
                raise
            return reply({"job_id": job_id, "accepted": len(paths)}, "已接收，请查看首页任务进度")
        except Exception as exc:
            return reply(message="开始秒传失败：" + self._error(exc), success=False)

    def api_cancel(self):
        self._ensure_init()
        with self._guard:
            if not self._running:
                return reply(message="当前没有运行中的任务")
            self._cancel.set()
            self._job.update(phase="cancelling", message="停止请求已接收；当前文件完成后停止")
        return reply(message="停止请求已接收；当前文件完成后停止")

    @staticmethod
    def _account(cfg):
        # Keep only an irreversible scope digest in non-secret transfer history.
        from .p115_web import parse_cookie_string
        uid = parse_cookie_string(cfg.get("cookie") or "").get("UID", "").split("_")[0]
        return hashlib.sha256((uid or cfg.get("cookie") or "").encode()).hexdigest()

    def _persist(self):
        try:
            with self._save_guard:
                with self._guard:
                    data = {"history": deepcopy(self._history[-500:]), "job": deepcopy(self._job)}
                if self.save_data(self.STATE_KEY, data) is False:
                    raise RuntimeError('宿主返回保存失败')
                with self._guard:
                    self._persist_error = ""
                return True
        except Exception as exc:
            with self._guard:
                self._persist_error = "保存记录失败：" + self._error(exc)
            logger.warning(LOG + self._persist_error)

    @staticmethod
    def get_command():
        return []

    @staticmethod
    def get_service():
        return []

    def stop_service(self):
        self._ensure_init()
        self._cancel.set()
