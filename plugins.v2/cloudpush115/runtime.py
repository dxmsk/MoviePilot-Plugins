"""Serialized background jobs and durable, read-only snapshots for CloudPush115."""
from __future__ import annotations

import os
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body

try:
    from app.core.config import settings
except ImportError:
    from app.sdk.config import settings  # type: ignore

try:
    from app.log import logger
except ImportError:
    from app.sdk.logging import logger  # type: ignore

from .config import (DEFAULTS, account_scope, byte_size, clean_message, human_size,
                     normalize_config, normalize_history, remote_path, signature, split_paths,
                     stamp, task_key)
from .p115_web import P115AuthError, P115WebClient, P115WebError
from .qb_client import QBClient, QBError
from .qb_watcher import QBWatcher
from .scanner import MediaScanner, RetryQueue


class RuntimeMixin:
    STATE_KEY = "state_v2"
    LOG = "[115秒传] "

    def __init__(self):
        super().__init__()
        self._state_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._persist_lock = threading.RLock()
        self._config = dict(DEFAULTS)
        self._scheduler = None
        self._worker = None
        self._pending_jobs = {}
        self._generation = 0
        self._loaded = False
        self._storage_error = ""
        self._persist_error = ""
        self._history = []
        self._ledger = {}
        self._legacy_done = set()
        self._legacy_adopted = set()
        self._legacy_target = "/"
        self._legacy_scope = ""
        self._inventory = {}
        self._root_states = []
        self._qb_tasks = {}
        self._queue = RetryQueue()
        self._running = False
        self._phase = "idle"
        self._active_kind = ""
        self._last_scan = ""
        self._last_index = ""
        self._last_qb = ""
        self._last_error = ""
        self._qb_watcher = None
        self._qb_watcher_generation = -1
        self._qb_config_error = ""
        self._qb_running = False
        self._clients = {}
        self._remote_ids = {}
        self._job_context = threading.local()

    def init_plugin(self, config: dict = None) -> None:
        """Configuration reload never replaces a running job's configuration or state."""
        with self._lifecycle_lock:
            normalized = normalize_config(config)
            run_once = normalized["onlyonce"]
            normalized["onlyonce"] = False
            self._stop_scheduler()
            with self._state_lock:
                self._generation += 1
                self._config = normalized
                self._pending_jobs.clear()
                generation = self._generation
                self._qb_config_error = ""
            if not self._load_state():
                return
            with self._state_lock:
                pending = self._queue.to_list()
                self._queue = RetryQueue(normalized["retry_interval"], normalized["max_attempts"], pending)
            # Text inputs must persist text, including upgrades from old list fields.
            if config != normalized:
                try:
                    if self.update_config(deepcopy(normalized)) is False:
                        raise RuntimeError("宿主返回保存失败")
                except Exception as exc:
                    self._set_error("配置保存失败：" + clean_message(exc, normalized))
            self._configure_schedule(normalized, generation)
            if split_paths(normalized["watch_paths"]):
                self._enqueue("scan" if normalized["enabled"] or run_once else "index")
            else:
                self._enqueue("index")  # Clear stale local inventory without touching transfer history.
                if run_once:
                    self._set_error("未填写本地监控路径；仅运行一次未执行")
            if normalized["qb_enabled"]:
                self._enqueue("qb")
            self._persist()

    def _load_state(self) -> bool:
        if self._loaded:
            return True
        try:
            stored = self.get_data(self.STATE_KEY)
            if stored is not None and (not isinstance(stored, dict) or stored.get("schema") != 2):
                raise ValueError("state_v2 数据格式错误，已保留原数据")
            if stored is None:
                history = self.get_data("history") or []
                retries = self.get_data("retry_queue") or []
                done = self.get_data("done_files") or []
                stored = {"history": history, "retry_queue": retries, "legacy_done": done,
                          "legacy_scope": account_scope(self._config),
                          "legacy_target": self._config["remote_dir"]}
            with self._state_lock:
                self._history = normalize_history(stored.get("history", []))
                self._ledger = deepcopy(stored.get("ledger", {})) if isinstance(stored.get("ledger"), dict) else {}
                self._legacy_done = {x for x in stored.get("legacy_done", []) if isinstance(x, str)}
                self._legacy_adopted = {x for x in stored.get("legacy_adopted", []) if isinstance(x, str)}
                self._legacy_scope = str(stored.get("legacy_scope") or account_scope(self._config))
                self._legacy_target = remote_path(stored.get("legacy_target"))
                self._inventory = {x["path"]: deepcopy(x) for x in stored.get("local_queue", [])
                                   if isinstance(x, dict) and isinstance(x.get("path"), str)}
                for row in self._inventory.values():
                    if row.get("status") == "processing":
                        row.update(status="pending", message="上次执行中断，等待重新核对文件")
                self._root_states = [x for x in stored.get("roots", []) if isinstance(x, dict)]
                self._qb_tasks = {str(x["id"]): deepcopy(x) for x in stored.get("qb_queue", [])
                                  if isinstance(x, dict) and x.get("id")}
                self._queue = RetryQueue(self._config["retry_interval"], self._config["max_attempts"], stored.get("retry_queue", []))
                self._last_scan = str(stored.get("last_scan") or "")
                self._last_index = str(stored.get("last_index") or "")
                self._last_qb = str(stored.get("last_qb") or "")
                self._loaded = True
                self._storage_error = ""
            return True
        except Exception as exc:
            self._storage_error = "读取持久化数据失败，未覆盖原记录：" + clean_message(exc, self._config)
            logger.error(self.LOG + self._storage_error)
            return False

    def _persist(self) -> bool:
        if not self._loaded:
            return False
        # One JSON key = one coherent checkpoint; late writers capture the latest state.
        with self._persist_lock:
            with self._state_lock:
                state = deepcopy({"schema": 2, "history": self._history[-500:], "ledger": self._ledger,
                                  "legacy_done": sorted(self._legacy_done), "legacy_adopted": sorted(self._legacy_adopted),
                                  "legacy_scope": self._legacy_scope, "legacy_target": self._legacy_target,
                                  "retry_queue": self._queue.to_list(), "local_queue": list(self._inventory.values()),
                                  "qb_queue": list(self._qb_tasks.values()), "roots": self._root_states,
                                  "last_scan": self._last_scan, "last_index": self._last_index, "last_qb": self._last_qb})
            try:
                if self.save_data(self.STATE_KEY, state) is False:
                    raise RuntimeError("宿主返回保存失败")
                self._persist_error = ""
                return True
            except Exception as exc:
                self._persist_error = "记录写入失败，内存数据已保留：" + clean_message(exc, self._config)
                logger.error(self.LOG + self._persist_error)
                return False

    def _set_error(self, message: str):
        with self._state_lock:
            self._last_error = message
        logger.error(self.LOG + message)

    def _stop_scheduler(self):
        scheduler, self._scheduler = self._scheduler, None
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception as exc:
                logger.debug(self.LOG + "调度停止：" + str(exc))

    def _configure_schedule(self, cfg: dict, generation: int):
        if not (cfg["enabled"] or cfg["qb_enabled"]):
            return
        try:
            from .config import integer
            tz = getattr(settings, "TZ", None) or "Asia/Shanghai"
            scheduler = BackgroundScheduler(timezone=str(tz))
            scan_min = max(1, integer(cfg["scan_interval"], 60, 1))
            retry_sec = max(30, integer(cfg["retry_interval"], 600, 30))
            qb_sec = max(3, integer(cfg["qb_interval"], 5, 3))
            if cfg["enabled"]:
                scheduler.add_job(self._scheduled, "interval", minutes=scan_min,
                                  args=["scan", generation], id="cloudpush115_scan", coalesce=True, max_instances=1)
            if cfg["enabled"] or cfg["qb_enabled"]:
                scheduler.add_job(self._scheduled, "interval", seconds=min(60, retry_sec),
                                  args=["retry", generation], id="cloudpush115_retry", coalesce=True, max_instances=1)
            if cfg["qb_enabled"]:
                scheduler.add_job(self._qb_tick, "interval", seconds=qb_sec,
                                  args=[generation], id="cloudpush115_qb", coalesce=True, max_instances=1)
            self._scheduler = scheduler
            scheduler.start()
        except Exception as exc:
            self._set_error("启动调度失败：" + clean_message(exc, cfg))

    def _qb_tick(self, generation: int):
        """Runs on its own APScheduler thread; never queued behind scan/retry."""
        if not self._is_current(generation):
            return
        with self._state_lock:
            if self._qb_running:
                return
            self._qb_running = True
            cfg = deepcopy(self._config)
            self._job_context.config, self._job_context.generation = cfg, generation
        try:
            self._run_qb(cfg, generation)
        except Exception as exc:
            self._set_error("qB 任务异常：" + clean_message(exc, cfg))
        finally:
            with self._state_lock:
                self._qb_running = False
            self._persist()

    def _scheduled(self, kind: str, generation: int):
        if self._is_current(generation):
            self._enqueue(kind)

    def _is_current(self, generation: int) -> bool:
        return generation == self._generation

    def _enqueue(self, kind: str) -> bool:
        with self._state_lock:
            if not self._loaded:
                return False
            key = (kind, self._generation)
            if key in self._pending_jobs:
                return True
            self._pending_jobs[key] = None
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._drain_jobs, name="CloudPush115Worker", daemon=True)
                self._worker.start()
        return True

    def _drain_jobs(self):
        """Single worker serializes indexing, hashing, retries, qB and reload boundaries."""
        while True:
            with self._state_lock:
                if not self._pending_jobs:
                    self._worker = None
                    self._active_kind = ""
                    self._running = False
                    self._phase = "idle"
                    return
                kind, gen = next(iter(self._pending_jobs))
                self._pending_jobs.pop((kind, gen), None)
                if not self._is_current(gen):
                    continue
                cfg = deepcopy(self._config)
                self._job_context.config, self._job_context.generation = cfg, gen
                self._running, self._active_kind = True, kind
                self._phase = {"scan": "indexing", "index": "indexing", "qb": "qb", "retry": "retry"}[kind]
            try:
                if kind in {"scan", "index"}:
                    complete = self._index_local(cfg, gen)
                    if complete and kind == "scan" and self._is_current(gen):
                        self._upload_local(cfg, gen)
                elif kind == "retry":
                    self._run_retries(cfg, gen)
                elif kind == "qb":
                    self._run_qb(cfg, gen)
            except Exception as exc:
                self._set_error(f"{kind} 任务异常：" + clean_message(exc, cfg))
            finally:
                with self._state_lock:
                    self._running = False
                    self._phase = "idle"
                self._persist()

    def stop_service(self) -> None:
        with self._lifecycle_lock:
            self._stop_scheduler()
            with self._state_lock:
                self._generation += 1
                self._pending_jobs.clear()
            # A request already in flight can finish with its original target; the
            # generation barrier prevents the next file using stale configuration.
            self._persist()

    def get_state(self) -> bool:
        with self._state_lock:
            return bool(self._config["enabled"] or self._config["qb_enabled"])

    def _current_config(self) -> dict:
        with self._state_lock:
            return deepcopy(self._config)

    def _has_credentials(self) -> bool:
        return bool(self._config["cookie"])

    def _make_client(self, cfg: dict = None):
        cfg = cfg or getattr(self._job_context, "config", self._config)
        key = (cfg["cookie"], cfg["user_agent"])
        if key not in self._clients:
            client = P115WebClient(cookie=cfg["cookie"], user_agent=cfg["user_agent"])
            self._clients = {key: client}
        return self._clients[key]

    def _remote_dir_id(self, client, cfg: dict = None, target: str = None):
        cfg = cfg or getattr(self._job_context, "config", self._config)
        target = remote_path(target if target is not None else cfg["remote_dir"])
        key = (account_scope(cfg), target)
        if key not in self._remote_ids:
            self._remote_ids[key] = client.get_dir_id_by_path(target)
        return self._remote_ids[key]

    @staticmethod
    def _file_item(path: str) -> dict:
        p = Path(os.path.abspath(path))
        st = p.stat()
        if not p.is_file():
            raise FileNotFoundError("不是可读文件：" + str(p))
        return {"path": str(p), "name": p.name, "size": st.st_size,
                "mtime": st.st_mtime, "mtime_ns": st.st_mtime_ns, "inode": st.st_ino}

    def _completed(self, item: dict, cfg: dict, target: str) -> bool:
        ident = task_key(item["path"], target, account_scope(cfg))
        with self._state_lock:
            row = self._ledger.get(ident, {})
            return row.get("status") in {"success", "legacy"} and row.get("signature") == signature(item)

    def _queue_row(self, item: dict, status: str, message: str = "", **extra):
        with self._state_lock:
            row = {**self._inventory.get(item["path"], {}), **deepcopy(item),
                   "status": status, "message": message, "updated_at": time.time(), **extra}
            self._inventory[item["path"]] = row
        return row

    def _index_local(self, cfg: dict, gen: int) -> bool:
        roots = split_paths(cfg["watch_paths"])
        root_state = {p: {"path": p, "status": "indexing", "file_count": 0, "message": "正在读取目录"} for p in roots}
        with self._state_lock:
            self._root_states = list(root_state.values())
        discovered = {}
        failed_roots = set()

        def problem(path, message):
            owner = next((r for r in roots if path == r or str(path).startswith(r.rstrip("/") + "/")), str(path))
            failed_roots.add(owner)
            root_state.setdefault(owner, {"path": owner, "file_count": 0})
            root_state[owner].update(status="error", message=clean_message(message, cfg))

        scanner = MediaScanner([x.strip() for x in cfg["extensions"].replace("，", ",").split(",") if x.strip()] or None)
        target, scope = cfg["remote_dir"], account_scope(cfg)
        for item in scanner.walk_files(roots, on_error=problem, stop=lambda: not self._is_current(gen)):
            if not self._is_current(gen):
                return False
            item = dict(item)
            path = item["path"]
            for root in roots:
                if path == root or path.startswith(root.rstrip("/") + "/"):
                    root_state[root]["file_count"] += 1
            ident = task_key(path, target, scope)
            with self._state_lock:
                # Adopt path-only legacy markers once. Label them as legacy, not as
                # newly verified transfers. A later file/target change invalidates them.
                if (path in self._legacy_done and path not in self._legacy_adopted
                        and scope == self._legacy_scope and target == self._legacy_target):
                    self._legacy_adopted.add(path)
                    old = next((h for h in reversed(self._history) if h.get("path") == path), {})
                    old_status = "skipped" if old.get("status") == "skipped" else "legacy"
                    self._ledger.setdefault(ident, {"path": path, "target": target, "scope": scope,
                                                   "signature": signature(item), "status": old_status})
                ledger = self._ledger.get(ident, {})
                retry = self._queue.pending.get(path)
                if ledger.get("signature") == signature(item) and ledger.get("status") in {"success", "legacy", "skipped"}:
                    status = ledger["status"]
                    message = {"success": "已秒传", "legacy": "旧版已处理标记（未重新秒传）", "skipped": "已按设置跳过"}[status]
                elif retry:
                    status = "exhausted" if self._queue.max_attempts and int(retry.get("attempts", 0)) > self._queue.max_attempts else "retry"
                    message = str(retry.get("last_error") or "等待重试")
                else:
                    status, message = ("pending", "等待秒传") if cfg["cookie"] else ("blocked", "尚未填写115网页Cookie")
                discovered[path] = {**item, "source": "local", "status": status, "message": message,
                                    "remote_dir": target, "updated_at": time.time()}
        if not self._is_current(gen):
            return False
        for root in roots:
            if root not in failed_roots:
                count = root_state[root]["file_count"]
                root_state[root].update(status="ready", message=f"索引完成，匹配媒体文件 {count} 个")
        with self._state_lock:
            # An inaccessible share must not erase previously visible pending files.
            for path, old in self._inventory.items():
                if path not in discovered and any(path == r or path.startswith(r.rstrip("/") + "/") for r in failed_roots):
                    discovered[path] = {**old, "status": "blocked", "message": "监控目录暂时不可读，保留原队列"}
            self._inventory = discovered
            self._root_states = list(root_state.values())
            self._last_index = stamp(time.time())
            self._phase = "ready"
        self._persist()
        return True

    def _upload_local(self, cfg: dict, gen: int):
        with self._state_lock:
            pending = [deepcopy(x) for x in self._inventory.values() if x.get("status") in {"pending", "blocked", "waiting"}]
            self._phase = "uploading"
        if not cfg["cookie"]:
            self._set_error("请填写115网页Cookie；本地文件队列已建立，未提交秒传")
            return
        completed, failed = 0, 0
        for item in pending:
            if not self._is_current(gen):
                break
            if item.get("status") == "blocked" and "目录暂时不可读" in item.get("message", ""):
                continue
            result = self._transfer(item, cfg, source="local")
            completed += result.get("ok") is True
            failed += not result.get("ok") and not result.get("skipped")
            if result.get("auth_error"):
                break
        with self._state_lock:
            self._last_scan = stamp(time.time())
        if cfg["notify"] and (completed or failed):
            self._notify_result("115本地秒传完成", f"成功 {completed} · 失败 {failed}；队列详情见插件主页")

    def _transfer(self, item: dict, cfg: dict, source: str = "local", target: str = None) -> dict:
        target = remote_path(target if target is not None else cfg["remote_dir"])
        path = str(item["path"])
        scope = account_scope(cfg)
        local_source = source != "qb"
        try:
            live = self._file_item(path)
            item = {**item, **live}
            if self._completed(item, cfg, target):
                if local_source:
                    self._queue_row(item, "success", "此前已秒传", remote_dir=target)
                    with self._state_lock:
                        retry = self._queue.pending.get(path)
                        if retry and remote_path(retry.get("remote_dir")) == target and retry.get("scope", scope) == scope:
                            self._queue.remove(path)
                    self._persist()
                return {"ok": True, "reuse": True, "message": "已确认成功，避免重复提交"}
            if local_source:
                self._queue_row(item, "processing", "正在计算SHA1并提交秒传", remote_dir=target)
                self._persist()
            if not cfg["cookie"]:
                raise P115AuthError("未填写115网页Cookie")
            client = self._make_client(cfg)
            directory_id = self._remote_dir_id(client, cfg, target)
            result = dict(client.push_file(Path(path), directory_id))
        except P115AuthError as exc:
            result = {"ok": False, "auth_error": True, "message": "115登录校验失败：" + clean_message(exc, cfg)}
        except (P115WebError, OSError) as exc:
            result = {"ok": False, "message": clean_message(exc, cfg)}
        except Exception as exc:
            result = {"ok": False, "message": "秒传异常：" + clean_message(exc, cfg)}
        result["message"] = clean_message(result.get("message"), cfg)
        ok = result.get("ok") is True
        # Only an explicit upload status=1 is a server miss, not network/auth/unknown errors.
        missing = bool(result.get("not_found")) or result.get("status") == 1 or "未命中秒传（status=1）" in result["message"]
        skipped = bool(result.get("skipped")) or (missing and not cfg["retry_notfound"])
        ident = task_key(path, target, scope)
        with self._state_lock:
            if ok or skipped:
                self._ledger[ident] = {"path": path, "target": target, "scope": scope,
                                      "signature": signature(item), "status": "success" if ok else "skipped", "at": time.time()}
                pending_retry = self._queue.pending.get(path)
                if pending_retry and remote_path(pending_retry.get("remote_dir")) == target and pending_retry.get("scope", scope) == scope:
                    self._queue.remove(path)
            elif local_source:
                self._queue.add(path=path, name=item.get("name", Path(path).name), size=byte_size(item.get("size")),
                                remote_dir=target, error=result["message"], source="local", scope=scope,
                                signature=signature(item))
            inventory_row = self._inventory.get(path, {})
            if local_source or (ok and inventory_row.get("remote_dir") == target and signature(inventory_row) == signature(item)):
                state = "success" if ok else ("skipped" if skipped else "retry")
                self._queue_row(item, state, result["message"], remote_dir=target)
        self._append_history(item, result, ok, skipped=skipped, source=source, target=target)
        if ok:
            logger.info(self.LOG + f"秒传成功 [{source}]：{item.get('name', path)} -> {target}")
        if not ok and not skipped:
            self._set_error(f"{item.get('name', path)}：{result['message']}")
        if skipped:
            result["skipped"] = True
        return result

    def _run_retries(self, cfg: dict, gen: int):
        with self._state_lock:
            due = self._queue.due()
        if not cfg["cookie"]:
            if due:
                self._set_error("重试已保留：尚未填写115网页Cookie")
            return
        for item in due:
            if not self._is_current(gen):
                break
            if item.get("scope") and item["scope"] != account_scope(cfg):
                with self._state_lock:
                    stored = self._queue.pending.get(item["path"])
                    if stored:
                        stored["status"] = "blocked"
                        stored["last_error"] = "115账号已变化；保留原任务，需切回原账号后重试"
                continue
            result = self._transfer(item, cfg, source="retry", target=item.get("remote_dir", cfg["remote_dir"]))
            if result.get("auth_error"):
                break

    def _append_history(self, item: dict, result: dict, ok: bool, skipped: bool = False,
                        source: str = "local", target: str = None):
        now = time.time()
        status = "success" if ok else ("skipped" if skipped else "failed")
        row = {"id": uuid.uuid4().hex, "name": item.get("name") or Path(str(item.get("path", ""))).name,
               "path": str(item.get("path", "")), "size": byte_size(item.get("size")),
               "status": status, "result": {"success": "成功", "skipped": "跳过", "failed": "失败"}[status],
               "message": str(result.get("message", "")), "source": source,
               "remote_dir": target if target is not None else self._config["remote_dir"], "time": stamp(now), "timestamp": now}
        with self._state_lock:
            self._history.append(row)
            self._history = self._history[-500:]
        self._persist()

    def _auto_qb_config(self):
        try:
            try:
                from app.helper.service import ServiceConfigHelper
            except ImportError:
                from app.sdk.services import ServiceConfigHelper  # type: ignore
            for row in ServiceConfigHelper.get_downloader_configs():
                get = row.get if isinstance(row, dict) else lambda k, default=None: getattr(row, k, default)
                if not get("enabled", True) or "qbittorrent" not in str(get("type", "")).lower():
                    continue
                config = get("config", {}) or {}
                if not isinstance(config, dict):
                    config = config.model_dump() if hasattr(config, "model_dump") else {}
                host = config.get("host") or config.get("url")
                if not host:
                    continue
                if "://" not in str(host):
                    host = ("https://" if config.get("ssl") else "http://") + str(host)
                from urllib.parse import urlsplit
                port = config.get("port")
                if port and urlsplit(host).port is None:
                    host = host.rstrip("/") + ":" + str(port)
                return {"host": host, "username": config.get("username") or config.get("user") or "",
                        "password": config.get("password") or ""}
        except Exception as exc:
            logger.debug(self.LOG + "自动读取qB配置：" + clean_message(exc, self._config))
        return None

    def _qb_log(self, message: str):
        # Waiting logs belong to a coalesced task snapshot, not the transfer history.
        cfg = getattr(self._job_context, "config", self._config)
        logger.info(self.LOG + "[qb] " + clean_message(message, cfg))

    def _qb_status(self, task: dict):
        if not isinstance(task, dict) or not task.get("id"):
            return
        cfg = getattr(self._job_context, "config", self._config)
        row = deepcopy(task)
        row["message"] = clean_message(row.get("message"), cfg)
        row["updated_at"] = time.time()
        with self._state_lock:
            self._qb_tasks[str(row["id"])] = row

    def _qb_push_one(self, local_path, remote_dir: str = "") -> dict:
        cfg = deepcopy(getattr(self._job_context, "config", self._config))
        gen = getattr(self._job_context, "generation", self._generation)
        if not self._is_current(gen):
            return {"ok": False, "message": "配置已更新，本轮后续文件已暂停"}
        try:
            item = self._file_item(str(local_path))
        except OSError as exc:
            item = {"path": str(local_path), "name": Path(local_path).name, "size": 0}
            result = {"ok": False, "message": clean_message(exc, cfg)}
            self._append_history(item, result, False, source="qb", target=remote_dir or cfg["remote_dir"])
            return result
        return self._transfer(item, cfg, source="qb", target=remote_dir or cfg["remote_dir"])

    def _run_qb(self, cfg: dict, gen: int):
        if not cfg["qb_enabled"] or not self._is_current(gen):
            return
        if self._qb_watcher is None or self._qb_watcher_generation != gen:
            credentials = ({"host": cfg["qb_host"], "username": cfg["qb_username"], "password": cfg["qb_password"]}
                           if cfg["qb_host"] else self._auto_qb_config())
            if not credentials:
                self._qb_config_error = "qB已启用，但未找到有效下载器配置；填写qB地址或在MoviePilot设置下载器"
                self._set_error(self._qb_config_error)
                return
            self._qb_watcher = QBWatcher(
                QBClient(**credentials), self._qb_push_one,
                media_exts=[x.strip() for x in cfg["extensions"].split(",") if x.strip()] or None,
                logger=self._qb_log, done_tag=cfg["qb_done_tag"],
                stable_checks=1, stable_interval=cfg["qb_settle"],
                status_callback=self._qb_status, path_mappings=cfg["qb_path_mappings"],
                retry_interval=cfg["retry_interval"],
            )
            self._qb_watcher_generation = gen
        try:
            self._qb_watcher.process_once(remote_dir=cfg["remote_dir"])
            tasks = self._qb_watcher.snapshot()
            with self._state_lock:
                self._qb_tasks = {str(x["id"]): deepcopy(x) for x in tasks if isinstance(x, dict) and x.get("id")}
                self._last_qb = stamp(time.time())
                self._qb_config_error = ""
        except Exception as exc:
            self._qb_config_error = "qB联动失败：" + clean_message(exc, cfg)
            self._set_error(self._qb_config_error)

    def _snapshot(self, limit: int = 100) -> dict:
        """No filesystem scan, network calls, write-back or queue mutation in a page read."""
        with self._state_lock:
            history = deepcopy(list(reversed(self._history)))
            retries = self._queue.to_list()
            inventory = deepcopy(list(self._inventory.values()))
            qb_tasks = deepcopy(list(self._qb_tasks.values()))
            roots = deepcopy(self._root_states)
            cfg = deepcopy(self._config)
            local = [x for x in inventory if x.get("status") not in {"success", "legacy", "skipped", "retry", "exhausted"}]
            retry_paths = {x["path"] for x in retries}
            # Stale processing labels never hide a file after restart.
            for x in local:
                if x.get("status") == "processing" and not self._running:
                    x.update(status="pending", message="等待下一次处理")
            for row in retries:
                attempts = int(row.get("attempts") or 0)
                if row.get("scope") and row["scope"] != account_scope(cfg):
                    row.update(status="blocked", last_error="账号变化，原任务已保留并暂停")
                elif self._queue.max_attempts and attempts > self._queue.max_attempts:
                    row["status"] = "exhausted"
                else:
                    row["status"] = "retry"
                row["message"] = row.get("last_error", "")
                row["next_retry_text"] = stamp(row.get("next_retry"))
            for row in qb_tasks:
                if row.get("status") == "failed" and row.get("next_retry"):
                    retries.append({"path": row.get("path", ""), "name": row.get("name", ""),
                                    "source": "qb", "status": "retry", "message": row.get("message", ""),
                                    "next_retry": row["next_retry"], "next_retry_text": stamp(row["next_retry"]),
                                    "attempts": row.get("attempts", 0), "remote_dir": cfg["remote_dir"]})
            successes = {x.get("path") for x in self._ledger.values() if isinstance(x, dict) and x.get("status") == "success"}
            successes.update(x.get("path") for x in history if x.get("status") == "success")
            known_paths = {x.get("path") for x in history}
            legacy_paths = sorted(self._legacy_done - known_paths)
            legacy_records = [{"path": path, "name": Path(path).name, "status": "legacy",
                               "message": "旧版已处理标记；原成功/跳过明细已不在历史中，未伪造结果或时间"} for path in legacy_paths]
            stats = {"history": len(history), "success": len(successes - {None, ""}),
                     "local": len(local), "retry": len(retries), "qb": len(qb_tasks), "legacy": len(legacy_records),
                     "indexed": len(inventory), "roots": len(split_paths(cfg["watch_paths"]))}
            result = {"schema": 2, "enabled": cfg["enabled"], "qb_enabled": cfg["qb_enabled"],
                      "running": self._running, "phase": self._phase, "pending_jobs": [x[0] for x in self._pending_jobs],
                      "done_count": stats["success"], "retry_count": stats["retry"], "local_count": stats["local"],
                      "last_run": self._last_scan, "last_scan": self._last_scan, "last_index": self._last_index,
                      "last_qb": self._last_qb, "stats": stats, "history": history[:limit],
                      "retry_queue": deepcopy(retries[:limit]), "local_queue": local[:limit], "qb_queue": qb_tasks[:limit],
                      "legacy_processed": legacy_records[:limit],
                      "roots": roots, "watch_paths": split_paths(cfg["watch_paths"]), "remote_dir": cfg["remote_dir"],
                      "last_error": self._last_error, "storage_error": self._storage_error or self._persist_error,
                      "qb_error": self._qb_config_error, "limit": limit, "version": self.plugin_version,
                      "snapshot_at": stamp(time.time()), "has_cookie": bool(cfg["cookie"])}
        return result

    def get_api(self) -> list[dict]:
        return [
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"], "auth": "bear", "summary": "只读状态与队列快照"},
            {"path": "/scan", "endpoint": self.api_scan, "methods": ["POST"], "auth": "bear", "summary": "扫描并秒传本地文件"},
            {"path": "/index", "endpoint": self.api_index, "methods": ["POST"], "auth": "bear", "summary": "仅刷新本地待处理队列"},
            {"path": "/retry", "endpoint": self.api_retry, "methods": ["POST"], "auth": "bear", "summary": "重新尝试本地失败文件"},
            {"path": "/refresh", "endpoint": self.api_refresh, "methods": ["GET", "POST"], "auth": "bear", "summary": "刷新页面显示，不触发扫描"},
            {"path": "/test", "endpoint": self.api_test, "methods": ["POST"], "auth": "bear", "summary": "测试已保存的115网页Cookie"},
        ]

    def api_status(self, limit: int = 100, offset: int = 0, section: str = "") -> dict:
        from .config import integer
        limit, offset = min(500, integer(limit, 100, 1)), integer(offset)
        data = self._snapshot(limit=limit + offset)
        for name in ("history", "local_queue", "retry_queue", "qb_queue"):
            data[name] = data[name][offset:offset + limit]
        data.update(offset=offset, limit=limit, success=True)
        if section in ("history", "local_queue", "retry_queue", "qb_queue"):
            data["items"] = data[section]
        return data

    def api_scan(self) -> dict:
        if not split_paths(self._config["watch_paths"]):
            return {"success": False, "message": "未填写本地监控目录；qB联动队列由单独轮询维护"}
        ok = self._enqueue("scan")
        return {"success": ok, "message": "扫描任务已入队，进度显示在本地待处理队列" if ok else self._storage_error}

    def api_index(self) -> dict:
        ok = self._enqueue("index")
        return {"success": ok, "message": "已安排本地目录索引；只读文件元数据，不提交秒传" if ok else self._storage_error}

    def api_retry(self, payload: dict = Body(default=None), path: str = "") -> dict:
        data = payload if isinstance(payload, dict) else {}
        chosen = str(data.get("path") or path or "")
        count = 0
        with self._state_lock:
            for item in self._queue.to_list():
                if chosen and item["path"] != chosen:
                    continue
                if item.get("scope") and item["scope"] != account_scope(self._config):
                    continue
                self._queue.retry_now(item["path"], reset_attempts=True)
                count += 1
        self._persist()
        if count:
            self._enqueue("retry")
        return {"success": True, "message": f"已重新安排 {count} 个本地失败文件；qB失败按自身间隔重试"}

    def api_refresh(self) -> dict:
        return {"success": True, "message": "状态已刷新"}

    def api_test(self) -> dict:
        cfg = self._current_config()
        if not cfg["cookie"]:
            return {"success": False, "message": "请先填写并保存115网页Cookie"}
        try:
            client = P115WebClient(cookie=cfg["cookie"], user_agent=cfg["user_agent"])
            client.check_login()
            return {"success": True, "message": "115网页Cookie有效"}
        except Exception as exc:
            return {"success": False, "message": clean_message(exc, cfg)}

    def _tick(self, force: bool = False):
        if force or self._config["enabled"]:
            return self._enqueue("scan")
        return False

    def _run_once_sync(self):
        return self._enqueue("scan")

    def _retry_tick(self):
        return self._enqueue("retry")

    def _qb_tick(self):
        return self._enqueue("qb")

    def _plugin_action(self, event):
        action = (event.event_data or {}).get("action", "")
        if action == "cloudpush115_scan":
            return self.api_scan()
        if action == "cloudpush115_status":
            data = self._snapshot()
            self._notify_result("115秒传状态", f"成功 {data['done_count']} · 本地待处理 {data['local_count']} · 待重试 {data['retry_count']}")

    def _notify_result(self, title: str, text: str):
        try:
            from app.schemas.types import NotificationType
            self.post_message(mtype=NotificationType.Plugin, title=title, text=text)
        except Exception as exc:
            logger.warning(self.LOG + "发送通知失败：" + clean_message(exc, self._config))

    @staticmethod
    def get_command() -> List[dict]:
        from app.schemas.types import EventType
        return [{"cmd": "/115push", "event": EventType.PluginAction, "desc": "115秒传 - 扫描并上传", "category": "插件命令", "data": {"action": "cloudpush115_scan"}},
                {"cmd": "/115status", "event": EventType.PluginAction, "desc": "115秒传 - 队列状态", "category": "插件命令", "data": {"action": "cloudpush115_status"}}]
