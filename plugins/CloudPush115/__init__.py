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

from .p115_client import P115AuthError, P115Client, P115Error
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
    plugin_version = "1.3.0"
    plugin_author = "dxmsk"
    author_url = "https://github.com/dxmsk"
    plugin_config_prefix = "cloudpush115_"
    plugin_order = 20
    auth_level = 1

    LOG = "[115秒传] "

    # ---- 运行状态 ----
    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = False

    # ---- 115 账号 ----
    _login_mode: str = "open"         # open=开放平台token / cookie=网页Cookie
    _access_token: str = ""           # 开放平台 access_token
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

        self._login_mode = (config.get("login_mode") or "open").strip()
        self._access_token = (config.get("access_token") or "").strip()
        self._cookie = (config.get("cookie") or "").strip()
        self._user_agent = (config.get("user_agent") or "").strip()
        self._watch_paths = config.get("watch_paths") or ""
        self._remote_dir = config.get("remote_dir") or ""
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
            self.update_config({"onlyonce": False})
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
        if self._login_mode == "cookie":
            return bool(self._cookie)
        return bool(self._access_token)

    def _make_client(self):
        """按登录模式构造 115 客户端。"""
        if self._login_mode == "cookie":
            return P115WebClient(cookie=self._cookie, user_agent=self._user_agent)
        return P115Client(access_token=self._access_token)

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
            remote_dir_id = client.get_dir_id_by_path(self._remote_dir or "/")
        except (P115AuthError, P115WebError) as e:
            return {"ok": False, "message": f"115 鉴权失败: {e}"}
        except P115Error as e:
            remote_dir_id = 0
            logger.warning(f"{self.LOG}解析目标目录失败，使用根目录: {e}")
        try:
            result = client.push_file(local_path, remote_dir_id)
        except (P115AuthError, P115WebError, P115Error) as e:
            return {"ok": False, "message": str(e)}
        if result.get("ok"):
            p = str(local_path)
            self._done.add(p)
            self._queue.remove(p)
        return result

    def _qb_tick(self) -> None:
        if not (self._qb_enabled and self._qb_watcher):
            return
        if not self._has_credentials():
            return
        if not self._qb_lock.acquire(blocking=False):
            return
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
            self._qb_lock.release()

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
        """扫描目录并处理新文件（秒传）。"""
        if self._running:
            return
        if not force and not self.get_state():
            return
        with self._lock:
            self._running = True
        try:
            self._do_scan()
        except Exception as e:
            logger.error(f"{self.LOG}扫描出错: {e}", exc_info=True)
        finally:
            with self._lock:
                self._running = False

    def _do_scan(self) -> None:
        if not self._has_credentials():
            logger.error(f"{self.LOG}未配置 115 凭据（access_token 或 Cookie），跳过")
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
            remote_dir_id = client.get_dir_id_by_path(self._remote_dir)
        except (P115AuthError, P115WebError) as e:
            logger.error(f"{self.LOG}115 鉴权失败: {e}")
            self._notify_result("115 秒传鉴权失败", str(e), error=True)
            return
        except P115Error as e:
            logger.error(f"{self.LOG}解析目标目录失败: {e}")
            remote_dir_id = 0

        files = self._scanner.iter_files(watch_paths)
        todo = [f for f in files if f["path"] not in self._done]
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
        """重试到期的失败文件。"""
        if not self.get_state() or self._queue is None:
            return
        due = self._queue.due()
        if not due:
            return
        if not self._has_credentials():
            return
        try:
            client = self._make_client()
            remote_dir_id = client.get_dir_id_by_path(self._remote_dir)
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
                # 更新下一次重试时间
                self._queue.add(
                    path=path, name=item.get("name", ""), size=item.get("size", 0),
                    remote_dir=self._remote_dir, error=result.get("message", "未知错误"),
                )
        self._persist()
        if done_now and self._notify:
            self._notify_result("115 秒传重试", f"本轮重试成功 {done_now} 个")

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
        if self._login_mode != "cookie":
            return {"success": False,
                    "message": "目录浏览需要 Cookie 登录模式（开放平台令牌不支持列目录）"}
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

    def api_scan(self) -> Dict[str, Any]:
        threading.Thread(target=self._run_once_sync, daemon=True).start()
        return {"success": True, "message": "已触发扫描，请稍后查看日志"}

    def api_test(self) -> Dict[str, Any]:
        if not self._has_credentials():
            return {"success": False, "message": "未配置凭据（access_token 或 Cookie）"}
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

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
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
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{
                                    "component": "VSelect",
                                    "props": {
                                        "model": "login_mode",
                                        "label": "115 登录方式",
                                        "items": [
                                            {"title": "网页 Cookie（推荐，免申请）", "value": "cookie"},
                                            {"title": "开放平台 access_token", "value": "open"},
                                        ],
                                        "hint": "Cookie 模式用网页版登录态，无需申请开放平台应用。",
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
                                        "model": "user_agent",
                                        "label": "自定义 User-Agent（可选）",
                                        "placeholder": "留空使用默认 115Browser UA",
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
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VTextarea",
                                    "props": {
                                        "model": "cookie",
                                        "label": "115 网页 Cookie（选择 Cookie 登录时填写）",
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
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VAlert",
                                    "props": {
                                        "type": "info",
                                        "variant": "tonal",
                                        "title": "📱 扫码登录获取 Cookie",
                                        "text": ("点击下方「扫码登录」生成二维码 → 用 115 App 扫码并确认 → "
                                                 "再按提示复制 Cookie 填入上面的输入框。\n"
                                                 "（115 出于安全设计，网页扫码后的 Cookie 只给 115 浏览器 App，"
                                                 "插件无法直接读取，需手动复制一步。）"),
                                    },
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VBtn",
                                    "props": {
                                        "color": "primary",
                                        "variant": "flat",
                                        "block": True,
                                        "model": "__qrlogin__",
                                        "text": "扫码登录（生成二维码）",
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
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {
                                        "model": "access_token",
                                        "label": "115 开放平台 access_token（选择开放平台时填写）",
                                        "type": "password",
                                        "hint": "在 115 开放平台(https://open.115.com)申请的应用令牌；"
                                                "仅用于秒传接口，请妥善保管。",
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
                                        "model": "watch_paths",
                                        "label": "监控的本地目录（多个用逗号分隔）",
                                        "placeholder": "/media/电影,/media/电视剧",
                                        "hint": "只读取这些目录下的文件做秒传，绝不移动/删除原始文件。",
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
                                        "model": "remote_dir",
                                        "label": "115 目标目录",
                                        "placeholder": "/媒体/电影",
                                        "hint": "秒传到 115 网盘的哪个目录，不存在会自动创建。留空=根目录。"
                                                "也可在插件页面用「浏览目录」可视化选择。",
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
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VAlert",
                                    "props": {
                                        "type": "info",
                                        "variant": "tonal",
                                        "title": "📁 可视化选择 115 目录",
                                        "text": ("配置 Cookie 后，打开插件页面使用「浏览 115 目录」逐层点选目标目录，"
                                                 "会自动填好上面的「115 目标目录」。\n"
                                                 "（开放平台令牌不支持列目录，仅 Cookie 模式可用。）"),
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
                    # ---------------- qb 下载完成联动 ----------------
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
                                        "text": "qb 联动：qBittorrent 下载完成后立即秒传到 115；"
                                                "秒传成功即给种子打上「已整理」标签，"
                                                "使 MoviePilot 跳过整理（脱离整理队列）；"
                                                "秒传失败则不打标签，交由 MP 正常整理。",
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
            "login_mode": "cookie",
            "cookie": "",
            "user_agent": "",
            "access_token": "",
            "watch_paths": "",
            "remote_dir": "",
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
        state = "✅ 已启用" if self.get_state() else "❌ 未启用"
        retry_count = len(self._queue) if self._queue else 0
        done_count = len(self._done)
        cards = [
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 4},
                "content": [{
                    "component": "VAlert",
                    "props": {"type": "success" if self.get_state() else "warning",
                              "variant": "tonal", "text": f"插件状态: {state}"},
                }],
            },
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 4},
                "content": [{
                    "component": "VAlert",
                    "props": {"type": "info", "variant": "tonal",
                              "text": f"已秒传: {done_count} | 待重试: {retry_count}"},
                }],
            },
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 4},
                "content": [{
                    "component": "VAlert",
                    "props": {"type": "info", "variant": "tonal",
                              "text": f"最近扫描: {self._last_run or '尚未运行'}"},
                }],
            },
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 4},
                "content": [{
                    "component": "VAlert",
                    "props": {
                        "type": "success" if (self._qb_enabled and self._qb_host) else "secondary",
                        "variant": "tonal",
                        "text": (f"qb 联动: ✅ {self._qb_host}（间隔 {self._qb_interval}s）"
                                 if (self._qb_enabled and self._qb_host) else "qb 联动: ❌ 未启用"),
                    },
                }],
            },
        ]
        page: List[dict] = [{"component": "VRow", "content": cards}]

        # ---- 扫码登录 + 目录可视化选择 ----
        page.append({
            "component": "VRow",
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 5},
                    "content": [{
                        "component": "VCard",
                        "props": {"variant": "tonal", "color": "primary", "title": "📱 扫码登录 115"},
                        "content": [{
                            "component": "VCardText",
                            "content": [{
                                "component": "VHtml",
                                "props": {"html": _QR_LOGIN_HTML.replace(
                                    "__PREFIX__", self._plugin_id())},
                            }],
                        }],
                    }],
                },
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 7},
                    "content": [{
                        "component": "VCard",
                        "props": {"variant": "tonal", "title": "📁 浏览并选择 115 目标目录"},
                        "content": [{
                            "component": "VCardText",
                            "content": [{
                                "component": "VHtml",
                                "props": {"html": DIR_BROWSER_HTML},
                            }],
                        }],
                    }],
                },
            ],
        })

        if retry_count:
            items = self._queue.to_list()[:20]
            rows = []
            for it in items:
                rows.append({
                    "name": it.get("name", ""),
                    "attempts": it.get("attempts", 0),
                    "error": str(it.get("last_error", ""))[:60],
                })
            page.append({
                "component": "VRow",
                "content": [{
                    "component": "VCol",
                    "props": {"cols": 12},
                    "content": [{
                        "component": "VDataTable",
                        "props": {
                            "headers": [
                                {"title": "文件", "key": "name"},
                                {"title": "已重试", "key": "attempts"},
                                {"title": "最近错误", "key": "error"},
                            ],
                            "items": rows,
                            "density": "compact",
                            "hover": True,
                        },
                    }],
                }],
            })

        if self._history:
            page.append({
                "component": "VRow",
                "content": [{
                    "component": "VCol",
                    "props": {"cols": 12},
                    "content": [{
                        "component": "VDataTable",
                        "props": {
                            "headers": [
                                {"title": "文件", "key": "name"},
                                {"title": "大小", "key": "size"},
                                {"title": "结果", "key": "result"},
                                {"title": "时间", "key": "time"},
                            ],
                            "items": self._history[-15:],
                            "density": "compact",
                            "hover": True,
                        },
                    }],
                }],
            })

        page.append({
            "component": "VAlert",
            "props": {
                "type": "warning",
                "variant": "tonal",
                "text": "说明：本插件仅对文件做 SHA1「秒传」，不下载、不上传文件本体，"
                        "全程只读原始路径，绝不移动/修改/删除任何原始文件。"
                        "秒传失败的文件会进入重试队列，按你设置的间隔自动重试。",
            },
        })
        return page
