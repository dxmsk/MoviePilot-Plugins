"""
115 网盘秒传插件（MoviePilot V2）。

功能：
1. 选择 MoviePilot 媒体库 / 任意本地路径，秒传到 115 网盘指定目录；
   —— 秒传（SHA1 快传），不下载、不上传文件本体，节省带宽与时间。
2. 秒传失败可自定义重试间隔与最大次数，后台自动重试；
3. 全程只读原始文件，绝不移动 / 修改 / 删除原始路径与文件；
4. 支持手动立即执行、仅运行一次、查看重试队列与历史。
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

from .p115_web import P115WebClient, P115WebError
from .qb_client import QBClient, QBError, QBAuthError
from .qb_watcher import QBWatcher
from . import p115_qrlogin as qrlogin
from .dirbrowser_html import DIR_BROWSER_HTML
from .qrlogin_html import QR_LOGIN_HTML as _QR_LOGIN_HTML
from .scanner import MediaScanner, RetryQueue


class CloudPush115(_PluginBase):
    # ---- 插件元信息 ----
    plugin_name = "115网盘秒传"
    plugin_desc = (
        "把 MoviePilot 媒体库（或任意本地路径）中的文件以【秒传】方式推送到 115 网盘，"
        "不下载、不上传文件本体。支持秒传失败自定义间隔重试，全程只读、不移动原始文件。"
    )
    plugin_icon = "clouddisk.png"
    plugin_version = "1.5.0"
    plugin_author = "Minis"
    author_url = "https://github.com/jxxghp/MoviePilot"
    plugin_config_prefix = "cloudpush115_"
    plugin_order = 20
    auth_level = 1

    LOG = "[115秒传] "

    # ---- 运行状态 ----
    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = False

    # ---- 115 账号 ----
    _cookie: str = ""                 # 网页 Cookie
    _user_agent: str = ""             # 自定义 UA（可选）

    # ---- 路径配置 ----
    _watch_paths: str = ""            # 监控的本地目录（逗号或换行分隔）
    _remote_dir: str = ""             # 115 目标目录，如 /媒体/电影
    _extensions: str = ""             # 只处理这些扩展名（留空=内置视频/字幕/音频列表）

    # ---- 重试配置 ----
    _retry_interval: int = 600        # 秒传失败重试间隔(秒)
    _max_attempts: int = 0            # 最大重试次数，0=无限
    _scan_interval: int = 60          # 扫描间隔(分钟)
    _retry_notfound: bool = True      # 未命中秒传(status=1)是否也重试

    # ---- 高级 ----
    _limit_speed: bool = False        # 保留字段（秒传无带宽占用）
    _stop_on_error: bool = False

    # ---- qb 联动（下载完成即秒传，成功则从整理队列移除）----
    _qb_enabled: bool = False         # 启用 qb 下载完成联动
    _qb_host: str = ""                # qBittorrent 地址，如 http://192.168.1.10:8080
    _qb_username: str = "admin"
    _qb_password: str = ""
    _qb_done_tag: str = "已整理"      # 秒传成功后打的标签（=MP的整理完成标签）
    _qb_interval: int = 10            # qb 监听间隔(秒)
    _qb_settle: int = 5               # 文件落地稳定等待(秒)
    _qb_watcher = None

    # 运行时
    _scheduler: Optional[BackgroundScheduler] = None
    _lock = threading.Lock()
    _scanner: Optional[MediaScanner] = None
    _qb_lock = threading.Lock()
    _queue: Optional[RetryQueue] = None
    _qr_session: Optional[dict] = None   # 扫码登录会话（路 A）
    _done: set = set()                 # 已成功秒传的文件路径集合
    _history: List[Dict[str, Any]] = []
    _last_run: str = ""
    _running = False

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    def init_plugin(self, config: dict = None) -> None:
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._onlyonce = bool(config.get("onlyonce"))
        self._notify = bool(config.get("notify"))

        # 仅使用网页 Cookie；保留旧字段兼容已安装配置，但不再读取 open token。
        self._cookie = (config.get("cookie") or "").strip()
        self._user_agent = (config.get("user_agent") or "").strip()
        self._client_cache = None
        self._client_cache_key = None
        self._remote_dir_cache = {}
        self._local_dir_cache = {}
        self._remote_dir_options_cache = []
        raw_paths = config.get("watch_paths") or ""
        self._watch_paths = ",".join(str(p) for p in raw_paths) if isinstance(raw_paths, (list, tuple, set)) else str(raw_paths)
        self._remote_dir = config.get("remote_dir") or ""
        self._local_browse_path = config.get("local_browse_path") or ""
        self._remote_browse_cid = str(config.get("remote_browse_cid") or "0")
        self._remote_browse_path = config.get("remote_browse_path") or "/"
        self._remote_cid_paths = {"0": "/"}
        self._remote_parent_map = {"0": None}
        self._remote_dir_options_cache = [{"title": "🏠 根目录 /", "value": "/"}]
        threading.Thread(target=self._warm_directory_options, daemon=True,
                         name="CloudPush115DirectoryCache").start()
        self._extensions = config.get("extensions") or ""
        self._retry_interval = max(int(config.get("retry_interval") or 600), 30)
        self._max_attempts = max(int(config.get("max_attempts") or 0), 0)
        self._scan_interval = max(int(config.get("scan_interval") or 60), 1)
        self._retry_notfound = bool(config.get("retry_notfound", True))

        # qb 联动
        self._qb_enabled = bool(config.get("qb_enabled"))
        self._qb_host = (config.get("qb_host") or "").strip()
        self._qb_username = (config.get("qb_username") or "admin").strip()
        self._qb_password = config.get("qb_password") or ""
        self._qb_done_tag = (config.get("qb_done_tag") or "已整理").strip()
        self._qb_interval = max(int(config.get("qb_interval") or 10), 3)
        self._qb_settle = max(int(config.get("qb_settle") or 5), 0)

        # Migrate legacy comma-separated watch_paths to the V2 VSelect-multiple list model.
        if isinstance(raw_paths, str) and raw_paths.strip():
            try:
                self.update_config(self._current_config())
            except Exception as e:
                logger.warning(f"{self.LOG}监控路径配置格式迁移失败: {e}")

        # 载入持久化状态
        try:
            self._done = set(self.get_data("done_files") or [])
        except Exception:
            self._done = set()
        try:
            pending = self.get_data("retry_queue") or []
        except Exception:
            pending = []
        try:
            self._history = list(self.get_data("history") or [])
        except Exception:
            self._history = []

        ext_list = [e.strip() for e in self._extensions.replace("，", ",").split(",")
                    if e.strip()] or None
        self._scanner = MediaScanner(ext_list)
        self._queue = RetryQueue(
            retry_interval=self._retry_interval,
            max_attempts=self._max_attempts,
            pending=pending,
        )

        # 停止旧调度
        self.stop_service()

        # 仅运行一次
        if self._onlyonce:
            self._onlyonce = False
            # V2 update_config replaces the whole config dict; always persist every field.
            self.update_config(self._current_config())
            threading.Thread(target=self._run_once_sync, daemon=True,
                             name="CloudPush115Once").start()

        # 周期调度：扫描 + 重试
        if self._enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(
                self._tick,
                "interval",
                minutes=self._scan_interval,
                coalesce=True,
                max_instances=1,
                id="cloudpush115_scan",
            )
            self._scheduler.add_job(
                self._retry_tick,
                "interval",
                seconds=min(max(self._retry_interval // 2, 30), 300),
                coalesce=True,
                max_instances=1,
                id="cloudpush115_retry",
            )
            self._scheduler.start()
            logger.info(f"{self.LOG}插件已启用，扫描间隔 {self._scan_interval} 分钟，"
                        f"重试间隔 {self._retry_interval} 秒")

        # qb 下载完成联动（独立于目录扫描）
        if self._qb_enabled:
            self._start_qb_watcher()

    def _has_credentials(self) -> bool:
        return bool(self._cookie)

    def _make_client(self):
        """按登录模式获取当前配置对应的复用客户端。"""
        key = ("cookie", self._cookie, self._user_agent)
        if self._client_cache is not None and self._client_cache_key == key:
            return self._client_cache
        client = P115WebClient(cookie=self._cookie, user_agent=self._user_agent)
        self._client_cache = client
        self._client_cache_key = key
        self._remote_dir_cache.clear()
        return client

    def _remote_dir_id(self, client):
        """缓存当前目标目录 ID；配置或客户端变化时自然失效。"""
        key = (id(client), self._remote_dir)
        if key not in self._remote_dir_cache:
            self._remote_dir_cache[key] = client.get_dir_id_by_path(self._remote_dir)
        return self._remote_dir_cache[key]

    # ------------------------------------------------------------------ #
    # qb 下载完成联动
    # ------------------------------------------------------------------ #
    def _start_qb_watcher(self) -> None:
        """启动 qb 监听调度（下载完成→秒传→成功则打「已整理」标签脱离 MP 整理队列）。"""
        host, username, password = self._qb_host, self._qb_username, self._qb_password
        # 未手填 qb 地址时，尝试自动读取 MoviePilot 的下载器配置（仅取 qbittorrent）
        if not host:
            auto = self._auto_qb_config()
            if auto:
                host, username, password = auto
                logger.info(f"{self.LOG}自动读取 MoviePilot 下载器配置: {host}")
        if not host:
            logger.warning(f"{self.LOG}qb 联动已启用但未配置 qb 地址，跳过")
            return
        try:
            qb = QBClient(host=host, username=username, password=password)
        except Exception as e:
            logger.error(f"{self.LOG}qb 客户端初始化失败: {e}")
            return

        ext_list = [e.strip() for e in self._extensions.replace("，", ",").split(",")
                    if e.strip()] or None
        self._qb_watcher = QBWatcher(
            qb=qb,
            push_callback=self._qb_push_one,
            media_exts=ext_list,
            logger=lambda m: logger.info(f"{self.LOG}[qb] {m}"),
            done_tag=self._qb_done_tag,
            stable_checks=2,
            stable_interval=max(self._qb_settle // 2, 1),
        )
        if self._scheduler is None:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.start()
        self._scheduler.add_job(
            self._qb_tick,
            "interval",
            seconds=self._qb_interval,
            coalesce=True,
            max_instances=1,
            id="cloudpush115_qb",
        )
        logger.info(f"{self.LOG}qb 联动已启用 @ {self._qb_host}，"
                    f"监听间隔 {self._qb_interval} 秒，完成标签「{self._qb_done_tag}」")

    def _auto_qb_config(self):
        """从 MoviePilot 下载器配置里自动取第一个 qbittorrent 的连接信息。"""
        try:
            from app.runtime.extensions.service import ServiceConfigHelper
            for conf in ServiceConfigHelper.get_downloader_configs():
                ctype = getattr(conf, "type", "") or ""
                if "qbittorrent" in str(ctype).lower():
                    config = getattr(conf, "config", {}) or {}
                    host = config.get("host") or config.get("url") or ""
                    if not host:
                        continue
                    user = config.get("username") or config.get("user") or ""
                    pwd = config.get("password") or ""
                    return host, user, pwd
        except Exception as e:
            logger.debug(f"{self.LOG}自动读取下载器配置失败（忽略）: {e}")
        return None

    def _qb_push_one(self, local_path, remote_dir: str = "") -> Dict[str, Any]:
        """单个文件秒传回调（供 QBWatcher 调用）。"""
        client = self._make_client()
        try:
            remote_dir_id = self._remote_dir_id(client)
        except P115AuthError as e:
            return {"ok": False, "message": f"115 鉴权失败: {e}"}
        except (P115WebError, P115Error) as e:
            # 目录解析失败（如并发创建冲突）不致命中止，退回根目录继续秒传
            remote_dir_id = 0
            logger.warning(f"{self.LOG}解析目标目录失败，改用根目录秒传: {e}")
        try:
            result = client.push_file(local_path, remote_dir_id)
        except P115AuthError as e:
            return {"ok": False, "message": f"115 鉴权失败: {e}"}
        except (P115WebError, P115Error) as e:
            return {"ok": False, "message": str(e)}
        if result.get("ok"):
            p = str(local_path)
            self._done.add(p)
            self._queue.remove(p)
            try:
                size = local_path.stat().st_size
            except (OSError, AttributeError):
                size = 0
            self._append_history({
                "name": getattr(local_path, "name", str(local_path)),
                "path": p,
                "size": size,
            }, result, True)
        return result

    def _qb_tick(self) -> None:
        if not (self._qb_enabled and self._qb_watcher):
            return
        if not self._has_credentials():
            return
        # 与目录扫描/失败重试共用任务锁，避免同一文件并行秒传。
        if not self._lock.acquire(blocking=False):
            return
        self._running = True
        try:
            stats = self._qb_watcher.process_once(remote_dir=self._remote_dir)
            if stats.get("pushed") or stats.get("failed"):
                logger.info(f"{self.LOG}qb 联动: 检查 {stats['checked']}，"
                            f"秒传成功 {stats['pushed']}，失败 {stats['failed']}，"
                            f"跳过 {stats['skipped']}")
            self._persist()
        except QBAuthError as e:
            logger.error(f"{self.LOG}qb 鉴权失败: {e}")
        except QBError as e:
            logger.error(f"{self.LOG}qb 查询失败: {e}")
        except Exception as e:
            logger.error(f"{self.LOG}qb 联动异常: {e}")
        finally:
            self._running = False
            self._lock.release()

    def get_state(self) -> bool:
        if not self._has_credentials():
            return False
        # 目录扫描模式需要 watch_paths；qb 联动模式需要 qb 配置（可自动读取）
        if self._enabled and self._watch_paths:
            return True
        if self._qb_enabled and (self._qb_host or self._auto_qb_config()):
            return True
        return False

    def stop_service(self) -> None:
        if self._scheduler:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._scheduler = None
        self._qb_watcher = None
        self._persist()

    def _persist(self) -> None:
        try:
            self.save_data("done_files", list(self._done))
            if self._queue is not None:
                self.save_data("retry_queue", self._queue.to_list())
            self.save_data("history", self._history[-500:])
        except Exception as e:
            logger.warning(f"{self.LOG}持久化状态失败: {e}")

    # ------------------------------------------------------------------ #
    # 后台任务
    # ------------------------------------------------------------------ #
    def _run_once_sync(self) -> None:
        self._tick(force=True)

    def _tick(self, force: bool = False) -> None:
        """扫描目录并处理新文件；原子抢锁，避免手动触发与定时任务重复跑。"""
        if not force and not self.get_state():
            return
        if not self._lock.acquire(blocking=False):
            return
        self._running = True
        try:
            self._do_scan()
        except Exception as e:
            logger.error(f"{self.LOG}扫描出错: {e}", exc_info=True)
        finally:
            self._running = False
            self._lock.release()

    def _do_scan(self) -> None:
        if not self._has_credentials():
            logger.error(f"{self.LOG}未配置 115 网页 Cookie，跳过")
            return
        if not self._watch_paths:
            logger.error(f"{self.LOG}未配置监控目录，跳过")
            return

        watch_paths = [p.strip() for p in
                       self._watch_paths.replace("，", ",").replace("\n", ",").split(",")
                       if p.strip()]
        if not watch_paths:
            return

        client = self._make_client()

        # 解析目标目录 id（按需创建）
        try:
            remote_dir_id = self._remote_dir_id(client)
        except (P115AuthError, P115WebError) as e:
            logger.error(f"{self.LOG}115 鉴权失败: {e}")
            self._notify_result("115 秒传鉴权失败", str(e), error=True)
            return
        except P115Error as e:
            logger.error(f"{self.LOG}解析目标目录失败: {e}")
            remote_dir_id = 0

        files = self._scanner.iter_files(watch_paths)
        # 已入重试队列的文件由 _retry_tick 按 next_retry 管理，避免全量扫描绕过用户设置的重试间隔。
        queued_paths = set(self._queue.pending) if self._queue else set()
        todo = [f for f in files if f["path"] not in self._done
                and f["path"] not in queued_paths]
        if not todo:
            logger.info(f"{self.LOG}暂无新增文件待秒传（共 {len(files)} 个，已处理 {len(self._done)}）")
            self._last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._persist()
            return

        logger.info(f"{self.LOG}发现 {len(todo)} 个新文件待秒传")
        ok_count, fail_count = 0, 0
        for item in todo:
            if self._stop_on_error and fail_count > 0:
                break
            try:
                result = client.push_file(item["path"], remote_dir_id)
            except (P115AuthError, P115WebError) as e:
                logger.error(f"{self.LOG}鉴权失败，终止本轮: {e}")
                break
            except P115Error as e:
                result = {"ok": False, "message": str(e), "sha1": "", "size": item["size"]}

            if result.get("ok"):
                ok_count += 1
                self._done.add(item["path"])
                self._queue.remove(item["path"])
                self._append_history(item, result, True)
                logger.info(f"{self.LOG}秒传成功: {item['name']}")
                continue

            fail_count += 1
            msg = str(result.get("message", "未知错误"))
            # status=1 表示服务器确实没有该文件（非暂时性失败）。
            # 是否继续重试由「未命中秒传也重试」开关决定，默认重试（尊重用户诉求）。
            not_found = "未命中秒传" in msg
            if not_found and not self._retry_notfound:
                logger.info(f"{self.LOG}未命中秒传，跳过不重试: {item['name']}")
                self._done.add(item["path"])
                self._queue.remove(item["path"])
                self._append_history(item, result, False, skipped=True)
                continue

            self._queue.add(
                path=item["path"], name=item["name"], size=item["size"],
                remote_dir=self._remote_dir, error=msg,
            )
            logger.warning(f"{self.LOG}秒传失败(将按 {self._retry_interval}s 重试): "
                           f"{item['name']} -> {msg}")
            self._append_history(item, result, False)

        self._last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._persist()

        if self._notify and (ok_count or fail_count):
            msg = (f"成功: {ok_count}\n失败(待重试): {fail_count}\n"
                   f"重试队列: {len(self._queue)}")
            self._notify_result("115 秒传完成", msg)

    def _retry_tick(self) -> None:
        """重试到期文件；与全量扫描共用任务锁，避免同一路径并发秒传。"""
        if not self.get_state() or self._queue is None or not self._has_credentials():
            return
        if not self._lock.acquire(blocking=False):
            return
        self._running = True
        try:
            due = self._queue.due()
            if not due:
                return
            try:
                client = self._make_client()
                remote_dir_id = self._remote_dir_id(client)
            except (P115AuthError, P115WebError, P115Error) as e:
                logger.error(f"{self.LOG}重试前初始化失败: {e}")
                return

            logger.info(f"{self.LOG}开始重试 {len(due)} 个失败文件")
            done_now = 0
            for item in due:
                path = item["path"]
                try:
                    result = client.push_file(path, remote_dir_id)
                except (P115Error, P115AuthError, P115WebError) as e:
                    result = {"ok": False, "message": str(e)}
                if result.get("ok"):
                    done_now += 1
                    self._done.add(path)
                    self._queue.remove(path)
                    self._append_history(
                        {"path": path, "name": item.get("name", ""), "size": item.get("size", 0)},
                        result, True,
                    )
                    logger.info(f"{self.LOG}重试成功: {item.get('name')}")
                else:
                    self._queue.add(
                        path=path, name=item.get("name", ""), size=item.get("size", 0),
                        remote_dir=self._remote_dir, error=result.get("message", "未知错误"),
                    )
            self._persist()
            if done_now and self._notify:
                self._notify_result("115 秒传重试", f"本轮重试成功 {done_now} 个")
        finally:
            self._running = False
            self._lock.release()

    def _append_history(self, item: Dict[str, Any], result: Dict[str, Any],
                        ok: bool, skipped: bool = False) -> None:
        self._history.append({
            "name": item.get("name", ""),
            "path": item.get("path", ""),
            "size": self._human_size(item.get("size", 0)),
            "result": "成功" if ok else ("跳过(未命中秒传)" if skipped else "失败"),
            "message": result.get("message", ""),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._history = self._history[-500:]

    # ------------------------------------------------------------------ #
    # 通知
    # ------------------------------------------------------------------ #
    def _notify_result(self, title: str, text: str, error: bool = False) -> None:
        try:
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"{title}",
                text=text,
            )
        except Exception as e:
            logger.warning(f"{self.LOG}发送通知失败: {e}")

    @staticmethod
    def _human_size(num: float) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if num < 1024:
                return f"{num:.1f}{unit}"
            num /= 1024
        return f"{num:.1f}PB"

    # ------------------------------------------------------------------ #
    # 命令 / API
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/115push",
                "event": EventType.PluginAction,
                "desc": "115秒传 - 立即执行一次扫描",
                "category": "插件命令",
                "data": {"action": "cloudpush115_scan"},
            },
            {
                "cmd": "/115status",
                "event": EventType.PluginAction,
                "desc": "115秒传 - 查看状态与重试队列",
                "category": "插件命令",
                "data": {"action": "cloudpush115_status"},
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/scan",
                "endpoint": self.api_scan,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "立即扫描并秒传",
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件状态",
            },
            {
                "path": "/test",
                "endpoint": self.api_test,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "测试 115 凭据是否有效",
            },
            {
                "path": "/qrlogin",
                "endpoint": self.api_qrlogin,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "生成 115 扫码登录二维码",
            },
            {
                "path": "/qrstatus",
                "endpoint": self.api_qrstatus,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "轮询扫码登录状态",
            },
            {
                "path": "/browse",
                "endpoint": self.api_browse,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "浏览 115 网盘目录（可视化选择）",
            },
            {
                "path": "/dirbrowser",
                "endpoint": self.api_dirbrowser,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "可视化目录选择器页面",
            },
            {
                "path": "/localbrowse",
                "endpoint": self.api_localbrowse,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "浏览服务器本地目录（可视化选择监控路径）",
            },
            {
                "path": "/addpath",
                "endpoint": self.api_addpath,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "把一个本地目录加入监控列表",
            },
            {
                "path": "/selectremote",
                "endpoint": self.api_selectremote,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "保存选中的115目标目录",
            },
            {
                "path": "/selectlocal",
                "endpoint": self.api_selectlocal,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "将当前本地目录设为监控目录",
            },
            {
                "path": "/localenter",
                "endpoint": self.api_localenter,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "打开本地目录的下一层",
            },
            {
                "path": "/remoteenter",
                "endpoint": self.api_remoteenter,
                "methods": ["GET", "POST"],
                "auth": "bear",
                "summary": "打开115网盘目录的下一层",
            },
        ]

    # ---------------------------------------------------------------- #
    # 可视化目录选择器（自包含 HTML 页面）
    # ---------------------------------------------------------------- #
    def _plugin_id(self) -> str:
        """MoviePilot 插件 API 路由里的 plugin_id（= 类名，用于拼 /api/v1/plugin/{id}）。"""
        return getattr(self, "plugin_id", None) or type(self).__name__

    def api_dirbrowser(self) -> Dict[str, Any]:
        """返回一个自包含 HTML 组件，用于在插件页面里可视化浏览/选择 115 目录。"""
        html = DIR_BROWSER_HTML.replace("__PREFIX__", self._plugin_id())
        return {"success": True, "html": html}

    # ---------------------------------------------------------------- #
    # 扫码登录（路 A）
    # ---------------------------------------------------------------- #
    def api_qrlogin(self) -> Dict[str, Any]:
        """生成扫码登录二维码，返回 PNG data URI + 会话信息。"""
        try:
            session = qrlogin.new_session()
        except Exception as e:
            return {"success": False, "message": f"生成二维码失败：{e}"}
        self._qr_session = session
        return {
            "success": True,
            "uid": session["uid"],
            "sign": session["sign"],
            "time": session["time"],
            "url": session["url"],
            "qrcode": session["qrcode_png"],  # data:image/png;base64,...
            "message": "请用 115 App 扫描二维码并在手机上确认登录",
        }

    def api_qrstatus(self, uid: str = "", sign: str = "", time: str = "") -> Dict[str, Any]:
        """轮询扫码状态。确认后提示用户复制 Cookie。"""
        sess = self._qr_session or {}
        uid = uid or sess.get("uid", "")
        sign = sign or sess.get("sign", "")
        try:
            t = int(time or sess.get("time") or 0)
        except (TypeError, ValueError):
            t = 0
        if not uid or not sign:
            return {"success": False, "status": "unknown",
                    "message": "缺少会话参数，请重新获取二维码"}
        try:
            st = qrlogin.poll_status(uid, sign, t)
        except Exception as e:
            return {"success": False, "status": "error", "message": str(e)}

        status = st["status"]
        if status == "confirmed":
            msg = ("✅ 手机已确认登录！\n\n"
                   "⚠️ 115 出于安全设计，网页扫码成功后 Cookie 只下发给 115 浏览器 App，"
                   "纯 HTTP 客户端无法直接获取。请按下面步骤复制 Cookie：\n"
                   "1. 在电脑浏览器登录 https://115.com（或用 115 App 内置浏览器）\n"
                   "2. F12 → Network → 刷新 → 点任意请求 → 复制 Request Headers 里的 Cookie\n"
                   "3. 粘贴到「115 网页 Cookie」输入框并保存")
        elif status == "scanned":
            msg = "📱 已扫码，请在手机上点击「确认登录」"
        elif status == "expired":
            msg = "⌛ 二维码已过期，请重新生成"
        else:
            msg = "请用 115 App 扫描二维码"
        return {"success": True, "status": status, "code": st["raw"].get("code"), "message": msg}

    # ---------------------------------------------------------------- #
    # 目录可视化浏览
    # ---------------------------------------------------------------- #
    def api_browse(self, cid: str = "0") -> Dict[str, Any]:
        """列出 115 网盘指定目录（cid）下的子目录，供可视化选择。"""
        if not self._cookie:
            return {"success": False, "message": "请先配置 115 网页 Cookie"}
        try:
            client = P115WebClient(cookie=self._cookie, user_agent=self._user_agent)
            data = client.browse(cid or "0")
            return {"success": True, "cid": data["cid"], "entries": data["entries"]}
        except P115AuthError as e:
            return {"success": False, "message": f"登录失效：{e}"}
        except Exception as e:
            return {"success": False, "message": f"读取目录失败：{e}"}

    def api_localbrowse(self, path: str = "") -> Dict[str, Any]:
        """列出服务器本地某目录下的子目录，供可视化选择监控路径。"""
        import os
        try:
            # 空路径=列出常见根 + 已配置的监控目录
            if not path:
                roots = []
                for c in ("/media", "/mnt", "/downloads", "/data", "/volume1", "/", "/opt"):
                    if os.path.isdir(c):
                        roots.append(c)
                cur = [p.strip() for p in
                       (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(",")
                       if p.strip()]
                entries = []
                seen = set()
                for r in roots + cur:
                    if r in seen or not os.path.isdir(r):
                        continue
                    seen.add(r)
                    entries.append({"name": r, "path": r, "watched": r in cur})
                return {"success": True, "path": "", "parent": "",
                        "entries": entries, "is_root": True}

            path = os.path.abspath(path)
            if not os.path.isdir(path):
                return {"success": False, "message": f"目录不存在或不可读: {path}"}
            cur = [p.strip() for p in
                   (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(",")
                   if p.strip()]
            entries = []
            try:
                for name in sorted(os.listdir(path), key=lambda s: s.lower()):
                    full = os.path.join(path, name)
                    if name.startswith(".") or not os.path.isdir(full):
                        continue
                    entries.append({"name": name, "path": full, "watched": full in cur})
            except PermissionError:
                return {"success": False, "message": f"无权限读取: {path}"}
            parent = os.path.dirname(path.rstrip("/")) or "/"
            return {"success": True, "path": path, "parent": parent,
                    "entries": entries, "is_root": False}
        except Exception as e:
            return {"success": False, "message": f"读取目录失败: {e}"}

    def api_addpath(self, path: str = "") -> Dict[str, Any]:
        """把一个本地目录追加到监控列表（watch_paths）并持久化。"""
        import os
        path = (path or "").strip()
        if not path:
            return {"success": False, "message": "路径为空"}
        if not os.path.isdir(path):
            return {"success": False, "message": f"目录不存在: {path}"}
        cur = [p.strip() for p in
               (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(",")
               if p.strip()]
        if path in cur:
            return {"success": True, "message": "该目录已在监控列表", "paths": cur}
        cur.append(path)
        self._watch_paths = ",".join(cur)
        try:
            self.update_config(self._current_config())
        except Exception as e:
            return {"success": False, "message": f"已加入内存但写配置失败: {e}", "paths": cur}
        return {"success": True, "message": f"已加入监控: {path}", "paths": cur}

    def api_localenter(self, path: str = "") -> Dict[str, Any]:
        """设置本地浏览当前位置；下一次打开设置页只显示此目录的直属子目录。"""
        import os
        path = os.path.abspath((path or "").strip()) if path else ""
        if path and not os.path.isdir(path):
            return {"success": False, "message": f"目录不存在：{path}"}
        self._local_browse_path = path
        try:
            self.update_config(self._current_config())
            return {"success": True, "message": path or "已回到挂载根目录", "path": path}
        except Exception as e:
            return {"success": False, "message": f"保存浏览位置失败：{e}"}

    def api_remoteenter(self, cid: str = "0", path: str = "/") -> Dict[str, Any]:
        """设置 115 网盘浏览当前位置；下一次打开设置页只显示该层目录。"""
        if not self._cookie:
            return {"success": False, "message": "请先保存 115 网页 Cookie"}
        cid = str(cid or "0")
        try:
            client = P115WebClient(cookie=self._cookie, user_agent=self._user_agent)
            data = client.browse(cid)
            self._remote_browse_cid = cid
            self._remote_browse_path = path or "/"
            self._remote_cid_paths[cid] = self._remote_browse_path
            entries = data.get("entries", [])
            for entry in entries:
                child_cid = str(entry.get("cid", ""))
                child_path = (self._remote_browse_path.rstrip("/") + "/" + str(entry.get("name", ""))).replace("//", "/")
                if self._remote_browse_path == "/": child_path = "/" + str(entry.get("name", ""))
                entry["path"] = child_path
                if child_cid:
                    self._remote_cid_paths[child_cid] = child_path
                    self._remote_parent_map[child_cid] = cid
            self._remote_dir_options_cache = entries
            self.update_config(self._current_config())
            return {"success": True, "cid": cid, "entries": data.get("entries", [])}
        except Exception as e:
            return {"success": False, "message": f"打开网盘目录失败：{e}"}

    def api_selectlocal(self, path: str = "") -> Dict[str, Any]:
        """将目录选择器所选路径设为唯一监控目录。"""
        import os
        path = os.path.abspath((path or "").strip()) if path else ""
        if not path or not os.path.isdir(path):
            return {"success": False, "message": "请选择有效的本地目录"}
        current = [p.strip() for p in (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(",") if p.strip()]
        if path not in current:
            current.append(path)
        self._watch_paths = ",".join(current)
        try:
            self.update_config(self._current_config())
            return {"success": True, "message": f"已添加监控目录：{path}", "path": path, "paths": current}
        except Exception as e:
            return {"success": False, "message": f"保存目录失败：{e}"}

    def api_selectremote(self, cid: str = "0", path: str = "") -> Dict[str, Any]:
        """保存用户选中的 115 目录路径。"""
        if not self._cookie:
            return {"success": False, "message": "请先填写并保存 115 网页 Cookie"}
        try:
            path = (path or self._remote_cid_paths.get(str(cid))
                    or self._remote_browse_path or "/")
            self._remote_dir = path
            self.update_config(self._current_config())
            return {"success": True, "message": f"已保存目标目录：{path}", "remote_dir": path}
        except Exception as e:
            return {"success": False, "message": f"保存目标目录失败：{e}"}

    def _current_config(self) -> Dict[str, Any]:
        """按表单字段类型重建完整配置；watch_paths 使用 VSelect multiple 的 list。"""
        return {
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "notify": self._notify,
            "cookie": self._cookie,
            "user_agent": self._user_agent,
            "watch_paths": [p.strip() for p in self._watch_paths.replace("，", ",").replace("\n", ",").split(",") if p.strip()],
            "remote_dir": self._remote_dir,
            "local_browse_path": self._local_browse_path,
            "remote_browse_cid": self._remote_browse_cid,
            "remote_browse_path": self._remote_browse_path,
            "extensions": self._extensions,
            "retry_interval": self._retry_interval,
            "max_attempts": self._max_attempts,
            "scan_interval": self._scan_interval,
            "retry_notfound": self._retry_notfound,
            "qb_enabled": self._qb_enabled,
            "qb_host": self._qb_host,
            "qb_username": self._qb_username,
            "qb_password": self._qb_password,
            "qb_done_tag": self._qb_done_tag,
            "qb_interval": self._qb_interval,
            "qb_settle": self._qb_settle,
        }

    def api_scan(self) -> Dict[str, Any]:
        threading.Thread(target=self._run_once_sync, daemon=True).start()
        return {"success": True, "message": "已触发扫描，请稍后查看日志"}

    def api_test(self) -> Dict[str, Any]:
        if not self._has_credentials():
            return {"success": False, "message": "请先填写并保存 115 网页 Cookie"}
        try:
            client = self._make_client()
            info = client.check_login()
            name = (info.get("user_name") or info.get("name")
                    or info.get("user_id") or info.get("data", {}).get("user_name")
                    if isinstance(info, dict) else info)
            return {"success": True, "message": f"登录有效，账号: {name}"}
        except Exception as e:
            return {"success": False, "message": f"登录校验失败: {e}"}

    def api_status(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "running": self._running,
            "done_count": len(self._done),
            "retry_count": len(self._queue) if self._queue else 0,
            "last_run": self._last_run,
            "history": self._history[-100:],
            "retry_queue": (self._queue.to_list() if self._queue else []),
        }

    # ------------------------------------------------------------------ #
    # 远程命令处理
    # ------------------------------------------------------------------ #
    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        event_data = event.event_data or {}
        action = event_data.get("action")
        if action == "cloudpush115_scan":
            self.post_message(mtype=NotificationType.Plugin,
                              title="115秒传",
                              text="已触发一次扫描，请稍后查看插件页/日志。")
            threading.Thread(target=self._run_once_sync, daemon=True).start()
        elif action == "cloudpush115_status":
            self.post_message(mtype=NotificationType.Plugin,
                              title="115秒传状态",
                              text=self._status_text())

    def _status_text(self) -> str:
        return (f"插件状态: {'已启用' if self.get_state() else '未启用'}\n"
                f"已秒传文件: {len(self._done)}\n"
                f"待重试: {len(self._queue) if self._queue else 0}\n"
                f"最近扫描: {self._last_run or '尚未运行'}")

    def _local_dir_items(self, max_items: int = 10**9, max_depth: int = 0) -> List[Dict[str, str]]:
        """缓存扫描 MP 本地配置根、Docker 所有挂载点和已选路径。"""
        import os, time
        cache = getattr(self, "_local_dir_cache", {})
        now = time.monotonic()
        if cache.get("expires", 0) > now:
            return cache.get("items", [])

        roots = []
        # Include every MoviePilot setting that points to an existing directory.
        for attr in dir(settings):
            if "PATH" not in attr.upper() and "DIR" not in attr.upper():
                continue
            try:
                value = getattr(settings, attr, None)
                if value:
                    path = os.fspath(value) if hasattr(value, "__fspath__") else str(value)
                    if path.startswith("/") and os.path.isdir(path):
                        roots.append(path)
            except Exception:
                continue
        roots.extend(("/media", "/mnt", "/downloads", "/data", "/volume1", "/opt"))

        # Docker/Podman bind mounts and named volumes visible inside this MP container.
        try:
            with open("/proc/self/mountinfo", "r", encoding="utf-8") as stream:
                for line in stream:
                    fields = line.split()
                    if len(fields) > 4:
                        mount = fields[4].replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")
                        separator = fields.index("-") if "-" in fields else len(fields)
                        fs_type = fields[separator + 1] if separator + 1 < len(fields) else ""
                        if (mount.startswith("/") and mount != "/"
                                and not mount.startswith(("/proc", "/sys", "/dev", "/run"))
                                and fs_type not in {"proc", "sysfs", "devtmpfs", "cgroup", "cgroup2", "securityfs", "debugfs"}):
                            roots.append(mount)
        except OSError:
            try:
                with open("/proc/mounts", "r", encoding="utf-8") as stream:
                    for line in stream:
                        fields = line.split()
                        if len(fields) > 2:
                            mount = fields[1].replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")
                            fs_type = fields[2]
                            if (mount.startswith("/") and mount != "/"
                                    and not mount.startswith(("/proc", "/sys", "/dev", "/run"))
                                    and fs_type not in {"proc", "sysfs", "devtmpfs", "cgroup", "cgroup2", "tmpfs"}):
                                roots.append(mount)
            except OSError:
                pass

        for saved in (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(","):
            saved = saved.strip()
            if saved: roots.append(saved)

        unique_roots = []
        seen_roots = set()
        for root in roots:
            root = os.path.abspath(os.path.expanduser(root))
            if root not in seen_roots and os.path.isdir(root):
                seen_roots.add(root); unique_roots.append(root)

        # 始终保留每个有效根路径（尤其是 mountinfo 中的 mount point）。
        items: Dict[str, str] = {root: root for root in unique_roots}
        queue = [(root, 0) for root in unique_roots]
        deadline = now + 2.0
        while queue and len(items) < max_items and time.monotonic() < deadline:
            folder, depth = queue.pop(0)
            items[folder] = folder
            if depth >= max_depth: continue
            try:
                with os.scandir(folder) as iterator:
                    children = sorted(iterator, key=lambda e: e.name.casefold())
            except OSError:
                continue
            for entry in children:
                if entry.name.startswith("."): continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        items[entry.path] = entry.path
                        if depth + 1 < max_depth and len(items) < max_items:
                            queue.append((entry.path, depth + 1))
                except OSError:
                    continue

        result = [{"title": p, "value": p} for p in sorted(items)]
        self._local_dir_cache = {"expires": now + 60, "items": result}
        return result

    def _warm_directory_options(self) -> None:
        """后台生成有限规模的网盘折叠树；设置页面构建不等待网络。"""
        if not self._cookie:
            return
        client = P115WebClient(cookie=self._cookie, user_agent=self._user_agent)
        budget = [10**9]
        base_path = getattr(self, "_remote_browse_path", "/") or "/"
        start_cid = str(getattr(self, "_remote_browse_cid", "0") or "0")

        def load(cid: str, path: str, depth: int) -> List[Dict[str, Any]]:
            if budget[0] <= 0:
                return []
            try:
                entries = client.browse(cid).get("entries", [])
            except Exception as e:
                logger.warning(f"{self.LOG}读取115目录失败 cid={cid}: {e}")
                return []
            result = []
            for entry in entries:
                if budget[0] <= 0: break
                budget[0] -= 1
                child_cid = str(entry.get("cid", ""))
                name = str(entry.get("name", ""))
                child_path = (path.rstrip("/") + "/" + name).replace("//", "/")
                if path == "/": child_path = "/" + name
                entry["path"] = child_path
                entry["children"] = load(child_cid, child_path, depth + 1) if child_cid else []
                if child_cid:
                    self._remote_cid_paths[child_cid] = child_path
                    self._remote_parent_map[child_cid] = cid
                result.append(entry)
            return result

        self._remote_dir_options_cache = load(start_cid, base_path, 0)

    def _remote_dir_items(self) -> List[Dict[str, str]]:
        """读取后台缓存；表单构建绝不访问网络。"""
        items = list(getattr(self, "_remote_dir_options_cache", []) or [])
        if not items:
            items = [{"title": "🏠 根目录 /", "value": "/"}]
        if self._remote_dir and all(x.get("value") != self._remote_dir for x in items):
            items.append({"title": self._remote_dir, "value": self._remote_dir})
        return items

    def _tree_node(self, entry: Dict[str, Any], remote: bool = False,
                   depth: int = 0, budget: Optional[List[int]] = None) -> Dict[str, Any]:
        """原生折叠目录节点：子目录藏在VExpansionPanel里，不摊平。"""
        import os
        if budget is None: budget = [10**9]
        path = str(entry.get("path", "") or "")
        cid = str(entry.get("cid", "0") or "0")
        name = str(entry.get("name", path if not remote else cid))
        params = {"cid": cid, "path": path or "/"} if remote else {"path": path}
        endpoint = "/selectremote" if remote else "/selectlocal"
        body = [{"component": "VBtn", "props": {"size": "small", "color": "success", "variant": "tonal", "prepend-icon": "mdi-check"},
                 "text": "选此目录", "events": {"click": {"api": f"plugin/{type(self).__name__}{endpoint}", "method": "post", "params": params}}}]
        children = entry.get("children", []) if remote else []
        if not remote and budget[0] > 0:
            try:
                with os.scandir(path) as it:
                    children = [{"name": e.name, "path": e.path} for e in sorted(it, key=lambda x:x.name.casefold())
                                if not e.name.startswith(".") and e.is_dir(follow_symlinks=False)]
            except OSError:
                children = []
        nested = []
        for child in children:
            if budget[0] <= 0: break
            budget[0] -= 1
            nested.append(self._tree_node(child, remote=remote, depth=depth+1, budget=budget))
        if nested:
            body.append({"component": "VExpansionPanels", "props": {"multiple": True, "variant": "accordion"}, "content": nested})
        return {"component": "VExpansionPanel", "content": [
            {"component": "VExpansionPanelTitle", "text": "📁 " + name},
            {"component": "VExpansionPanelText", "content": body},
        ]}

    def _local_tree_panel(self) -> Dict[str, Any]:
        budget = [10**9]
        roots = self._local_current_entries()
        return {"component": "VExpansionPanels", "props": {"multiple": True, "variant": "accordion"},
                "content": [self._tree_node(x, budget=budget) for x in roots]}

    def _remote_tree_panel(self) -> Dict[str, Any]:
        budget = [10**9]
        roots = self._remote_current_entries()
        return {"component": "VExpansionPanels", "props": {"multiple": True, "variant": "accordion"},
                "content": [self._tree_node(x, remote=True, budget=budget) for x in roots]}

    def _local_current_entries(self) -> List[Dict[str, str]]:
        """仅列出当前浏览位置的一层文件夹。根状态只列挂载根和已选路径。"""
        import os
        current = getattr(self, "_local_browse_path", "") or ""
        if not current:
            entries = []
            seen = set()
            for item in self._local_dir_items():
                path = item.get("value", "")
                if path and path not in seen:
                    seen.add(path)
                    entries.append({"name": path, "path": path})
            return entries
        try:
            with os.scandir(current) as it:
                return [{"name": e.name, "path": e.path}
                        for e in sorted(it, key=lambda x: x.name.casefold())
                        if not e.name.startswith(".") and e.is_dir(follow_symlinks=False)]
        except OSError:
            return []

    def _remote_current_entries(self) -> List[Dict[str, Any]]:
        """只返回用户当前 115 cid 的一层目录缓存。"""
        return list(getattr(self, "_remote_dir_options_cache", []) or [])

    def _directory_panel(self, title: str, icon: str, enter_api: str, select_api: str,
                         items: List[Dict[str, Any]], key: str, current: str,
                         parent_value: Optional[str] = None, parent_path: Optional[str] = None,
                         remote: bool = False) -> Dict[str, Any]:
        """构建V2原生目录浏览卡片，每次仅渲染当前层。"""
        body: List[dict] = []
        if parent_value is not None:
            params = {key: parent_value}
            if remote: params["path"] = parent_path or "/"
            body.append({"component": "VBtn", "props": {"variant": "text", "prepend-icon": "mdi-arrow-up", "class": "mb-2"},
                         "text": "返回上级 / 根目录", "events": {"click": {"api": f"plugin/{type(self).__name__}{enter_api}", "method": "post", "params": params}}})
        body.append({"component": "div", "props": {"class": "text-caption text-medium-emphasis mb-2"}, "text": f"当前位置：{current or '/（挂载根目录）'}"})
        if not items:
            body.append({"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "此处没有可进入的子文件夹。"}})
        for item in items[:300]:
            value = item.get("path") if key == "path" else item.get("cid")
            name = item.get("name") or str(value or "")
            enter_params = {key: value}
            select_params = {key: value}
            if remote:
                child_path = (current.rstrip("/") + "/" + name).replace("//", "/")
                if current in ("", "/"):
                    child_path = "/" + name
                enter_params["path"] = child_path
                select_params["path"] = child_path
            row = {"component": "VRow", "props": {"class": "align-center py-1", "dense": True}, "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "div", "props": {"class": "text-body-2 text-break"}, "text": "📁 " + name}]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [{"component": "VBtn", "props": {"variant": "tonal", "size": "small", "prepend-icon": "mdi-folder-open"}, "text": "进入", "events": {"click": {"api": f"plugin/{type(self).__name__}{enter_api}", "method": "post", "params": enter_params}}}]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [{"component": "VBtn", "props": {"variant": "tonal", "color": "success", "size": "small", "prepend-icon": "mdi-check"}, "text": "选此目录", "events": {"click": {"api": f"plugin/{type(self).__name__}{select_api}", "method": "post", "params": select_params}}}]},
            ]}
            body.append(row)
        return {"component": "VExpansionPanels", "props": {"variant": "accordion", "class": "mb-3"}, "content": [{
            "component": "VExpansionPanel", "content": [
                {"component": "VExpansionPanelTitle", "text": f"{icon} {title}"},
                {"component": "VExpansionPanelText", "content": body},
            ]
        }]}

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        import os
        local_entries = self._local_current_entries()
        remote_entries = self._remote_current_entries()
        local_selected = [p.strip() for p in (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(",") if p.strip()]
        local_parent = (os.path.dirname(self._local_browse_path.rstrip("/")) or "/") if self._local_browse_path else None
        if self._local_browse_path and local_parent == self._local_browse_path:
            local_parent = ""
        remote_parent = self._remote_parent_map.get(self._remote_browse_cid) if self._remote_browse_cid != "0" else None
        parent_path = self._remote_cid_paths.get(str(remote_parent), "/") if remote_parent is not None else None
        # Keep the existing side-by-side form layout and replace only the two path fields.
        local_panel = {"component": "div", "content": [
            {"component": "VAlert", "props": {"type": "success", "variant": "tonal",
                "text": "当前监控：" + ("，".join(local_selected) if local_selected else "未选择")}},
            self._local_tree_panel(),
        ]}
        remote_panel = {"component": "div", "content": [
            {"component": "VAlert", "props": {"type": "info", "variant": "tonal",
                "text": "当前目标：" + (self._remote_dir or "/（网盘根目录）")}},
            self._remote_tree_panel(),
        ]}
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "enabled", "label": "启用插件"},
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "onlyonce", "label": "仅运行一次"},
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "notify", "label": "发送通知"},
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VCard",
                        "props": {"variant": "tonal", "color": "primary", "class": "mb-4"},
                        "content": [
                            {"component": "VCardTitle", "text": "🔐 115 网页 Cookie 登录"},
                            {"component": "VCardText", "text": "只需网页 Cookie。粘贴 Cookie 并保存后，重新打开设置页加载 115 网盘目录。"},
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VTextarea",
                                    "props": {
                                        "model": "cookie",
                                        "label": "115 网页 Cookie（必填）",
                                        "rows": 3,
                                        "hint": "从浏览器 F12 → Network 复制 Cookie，或粘贴 EditThisCookie 导出的文本。"
                                                "至少包含 UID / CID / SEID。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "props": {"class": "mt-2"},
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [local_panel]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [remote_panel]},
                        ],
                    },

                    {
                        "component": "VCard",
                        "props": {"variant": "tonal", "color": "primary", "class": "my-3"},
                        "content": [
                            {"component": "VCardTitle", "text": "⚙️ 扫描与重试"},
                            {"component": "VCardText", "text": "设置媒体类型、扫描频率和秒传失败后的重试策略。"},
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "extensions",
                                        "label": "处理的文件扩展名（留空=视频/字幕/音频默认列表）",
                                        "placeholder": "mp4,mkv,ass,srt",
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "scan_interval",
                                        "label": "扫描间隔（分钟）",
                                        "type": "number",
                                        "hint": "每隔多久扫描一次新文件。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "retry_interval",
                                        "label": "秒传失败重试间隔（秒）",
                                        "type": "number",
                                        "hint": "单个文件秒传失败后，等待多久再重试。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "max_attempts",
                                        "label": "最大重试次数（0=无限）",
                                        "type": "number",
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {
                                        "model": "retry_notfound",
                                        "label": "未命中秒传也重试",
                                        "hint": "关闭后，服务器明确没有该文件（status=1）时不再重试；"
                                                "网络错误/二次校验失败等暂时性失败始终会重试。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VCard",
                        "props": {"variant": "tonal", "color": "info", "class": "my-3"},
                        "content": [
                            {"component": "VCardTitle", "text": "🧲 qBittorrent 下载完成联动（可选）"},
                            {"component": "VCardText", "text": "开启后，下载完成自动秒传；成功时添加「已整理」标签。"},
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VAlert",
                                    "props": {
                                        "type": "info", "variant": "tonal",
                                        "text": "qBittorrent 下载完成后立即秒传；成功时标记已整理。未使用 qB 联动时，无需填写下方字段。",
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {
                                        "model": "qb_enabled",
                                        "label": "启用 qb 下载完成联动",
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 8},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "qb_host",
                                        "label": "qBittorrent 地址（留空=自动读取 MoviePilot 下载器配置）",
                                        "placeholder": "http://192.168.1.10:8080",
                                        "hint": "不含 /api，自动补全。若 MoviePilot 已配置 qb，可留空自动读取。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "qb_username",
                                        "label": "qb 用户名",
                                        "placeholder": "admin",
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "qb_password",
                                        "label": "qb 密码",
                                        "type": "password",
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "qb_done_tag",
                                        "label": "秒传成功标签",
                                        "placeholder": "已整理",
                                        "hint": "必须与 MoviePilot 的整理完成标签一致（默认「已整理」），"
                                                "打了此标签的种子 MP 不会再整理。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "qb_interval",
                                        "label": "qb 监听间隔（秒）",
                                        "type": "number",
                                        "hint": "每隔多久检查一次 qb 完成种子。越小越及时，建议 5~15。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "qb_settle",
                                        "label": "文件落地稳定等待（秒）",
                                        "type": "number",
                                        "hint": "检测到完成后，等待文件大小稳定再秒传，防止下载/解压未完成。",
                                        "persistent-hint": True,
                                    },
                                }],
                            },
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": False,
            "cookie": "",
            "user_agent": "",
            "watch_paths": [],
            "remote_dir": "",
            "local_browse_path": "",
            "remote_browse_cid": "0",
            "extensions": "",
            "scan_interval": 60,
            "retry_interval": 600,
            "max_attempts": 0,
            "retry_notfound": True,
            "qb_enabled": False,
            "qb_host": "",
            "qb_username": "admin",
            "qb_password": "",
            "qb_done_tag": "已整理",
            "qb_interval": 10,
            "qb_settle": 5,
        }

    def get_page(self) -> List[dict]:
        history = list(reversed(self._history[-100:]))
        retries = self._queue.to_list()[:50] if self._queue else []
        done_count = len(self._done)
        retry_count = len(self._queue) if self._queue else 0
        last_run = self._last_run or "尚未运行"
        status = "扫描中" if self._running else ("已启用" if self.get_state() else "未启用")
        paths = [p.strip() for p in (self._watch_paths or "").replace("，", ",").replace("\n", ",").split(",") if p.strip()]
        path_items = [{"path": p} for p in paths] or [{"path": "尚未配置监控目录，请在配置页添加本地路径"}]
        hist = []
        for h in history:
            r = str(h.get("result", ""))
            ok = ("成功" in r) or ("秒传" in r and "失败" not in r)
            hist.append({
                "name": str(h.get("name", "")),
                "path": str(h.get("path", "")),
                "size": self._format_size(h.get("size", 0)),
                "result": "✅ " + r if ok else "⚠️ " + r,
                "time": str(h.get("time", "")),
            })
        retry_items = [{
            "name": str(x.get("name", "")),
            "attempts": x.get("attempts", 0),
            "error": str(x.get("last_error", ""))[:120],
        } for x in retries]

        def stat_card(icon, title, value, color):
            return {"component": "VCard", "props": {"variant": "tonal", "color": color, "class": "rounded-lg"},
                    "content": [{"component": "VCardText", "props": {"class": "d-flex align-center ga-3 py-4"},
                                 "content": [
                                     {"component": "VIcon", "props": {"icon": icon, "size": 32}},
                                     {"component": "div", "content": [
                                         {"component": "div", "props": {"class": "text-h5 font-weight-bold"}, "text": str(value)},
                                         {"component": "div", "props": {"class": "text-caption"}, "text": title},
                                     ]},
                                 ]}]}

        def section(title, icon, color, headers, items):
            return {"component": "VCard", "props": {"variant": "outlined", "class": "rounded-lg mb-4"},
                    "content": [
                        {"component": "VCardTitle", "props": {"class": "d-flex align-center text-subtitle-1 font-weight-bold"},
                         "content": [{"component": "VIcon", "props": {"icon": icon, "color": color, "class": "mr-2"}},
                                     {"component": "span", "text": title}]},
                        {"component": "VDataTable", "props": {"headers": headers, "items": items,
                                                                  "density": "comfortable", "hover": True,
                                                                  "items-per-page": 10}},
                    ]}

        return [
            {"component": "VCard", "props": {"variant": "tonal", "color": "primary", "class": "rounded-lg mb-4"},
             "content": [{"component": "VCardTitle", "props": {"class": "text-h5 font-weight-bold"}, "text": "☁️ 115 网盘秒传"},
                         {"component": "VCardSubtitle", "text": "SHA1 秒传 · 只读原文件 · qB 下载完成即推送"},
                         {"component": "VCardText", "props": {"class": "d-flex flex-wrap ga-2"}, "content": [
                             {"component": "VChip", "props": {"color": "success" if self.get_state() else "warning", "variant": "flat", "text": status}},
                             {"component": "VChip", "props": {"color": "info", "variant": "tonal", "text": "最近扫描：" + str(last_run)}},
                         ]}]},
            {"component": "VRow", "props": {"dense": True, "class": "mb-2"}, "content": [
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [stat_card("mdi-cloud-check", "已秒传", done_count, "success")]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [stat_card("mdi-restart", "待重试", retry_count, "warning")]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [stat_card("mdi-clock-outline", "最近扫描", last_run, "info")]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [stat_card("mdi-cog-refresh", "运行状态", status, "primary")]},
            ]},
            section("整理条目 · 最近 100 条", "mdi-history", "success", [
                {"title": "文件", "key": "name"}, {"title": "本地路径", "key": "path"},
                {"title": "大小", "key": "size"}, {"title": "结果", "key": "result"},
                {"title": "时间", "key": "time"},
            ], hist),
            section("待重试队列", "mdi-restart", "warning", [
                {"title": "文件", "key": "name"}, {"title": "已重试", "key": "attempts"},
                {"title": "最近错误", "key": "error"},
            ], retry_items),
            section("本地监控目录", "mdi-folder-search", "success", [
                {"title": "当前监控路径（可在配置页编辑）", "key": "path"},
            ], path_items),
            {"component": "VAlert", "props": {"type": "info", "variant": "tonal", "class": "rounded-lg",
              "icon": "mdi-information-outline", "text": "本页面使用 MoviePilot 原生 Vuetify 组件渲染。配置监控路径、115 Cookie/令牌和目标目录，请进入插件配置页修改；115 网盘目录由配置的目标路径自动创建。"}},
        ]

    @staticmethod
    def _format_size(size: Any) -> str:
        try:
            n = float(size or 0)
        except (TypeError, ValueError):
            return str(size or "")
        units = ("B", "KB", "MB", "GB", "TB")
        i = 0
        while n >= 1024 and i < len(units) - 1:
            n /= 1024
            i += 1
        return f"{n:.1f} {units[i]}" if i else f"{int(n)} B"
