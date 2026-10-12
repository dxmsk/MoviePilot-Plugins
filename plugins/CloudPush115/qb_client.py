# encoding: utf-8
"""
qBittorrent 轻量 HTTP 客户端（纯标准库）。

只实现本插件需要的接口：
  - login()                     登录
  - torrents_info(filter=...)   列出种子（含 name/progress/state/save_path/tags）
  - torrents_files(hash)        列出种子内文件
  - add_tags(hashes, tags)      加标签
  - completed_torrents()        已完成且无「已整理」标签的种子

不依赖 qbittorrent-api 第三方库，避免 MoviePilot 容器缺包。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError, URLError
from http.cookiejar import CookieJar


class QBError(Exception):
    """qBittorrent 调用异常。"""


class QBAuthError(QBError):
    """登录失败。"""


# MP 用来标记「整理完成」的标签（整理过的种子不会被再次整理）
DEFAULT_DONE_TAG = "已整理"


class QBClient:
    """极简 qBittorrent WebAPI 客户端。"""

    def __init__(self, host: str, username: str = "", password: str = "",
                 api_key: str = "", timeout: int = 15):
        self.host = (host or "").strip().rstrip("/")
        if not self.host:
            raise QBError("未配置 qBittorrent 地址")
        if not self.host.startswith(("http://", "https://")):
            self.host = "http://" + self.host
        self.username = username or ""
        self.password = password or ""
        self.api_key = api_key or ""          # qb 4.6+ 支持 API Key 免登录
        self.timeout = timeout
        self._logged_in = False
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    # ------------------------------------------------------------------ #
    # 底层请求
    # ------------------------------------------------------------------ #
    def _request(self, path: str, data: Optional[dict] = None,
                 method: str = "GET", raw: bool = False) -> Any:
        url = f"{self.host}/api/v2/{path}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = None
        if data is not None:
            body = urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
        except HTTPError as e:
            if e.code in (401, 403):
                raise QBAuthError(f"qBittorrent 鉴权失败({e.code})，请检查账号密码/API Key")
            raise QBError(f"qBittorrent 请求失败 {e.code}: {path}")
        except URLError as e:
            raise QBError(f"无法连接 qBittorrent({self.host}): {e.reason}")
        if raw:
            return text
        try:
            return json.loads(text) if text else {}
        except ValueError:
            return text

    def login(self) -> None:
        """登录（API Key 模式跳过）。"""
        if self.api_key:
            self._logged_in = True
            return
        if not self.username:
            raise QBAuthError("未配置 qBittorrent 用户名")
        text = self._request("auth/login",
                             {"username": self.username, "password": self.password},
                             method="POST", raw=True)
        if "Ok" not in (text or ""):
            raise QBAuthError("qBittorrent 登录失败，请检查用户名/密码")
        self._logged_in = True

    def _ensure(self) -> None:
        if not self._logged_in:
            self.login()

    # ------------------------------------------------------------------ #
    # 业务接口
    # ------------------------------------------------------------------ #
    def torrents_info(self, flt: Optional[str] = None,
                      hashes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """列出种子。flt: all/downloading/completed/... """
        self._ensure()
        params = {}
        if flt:
            params["filter"] = flt
        if hashes:
            params["hashes"] = "|".join(hashes)
        qs = ("?" + urlencode(params)) if params else ""
        data = self._request(f"torrents/info{qs}")
        return data if isinstance(data, list) else []

    def torrents_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """列出某个种子内的文件（name/size/progress/priority）。"""
        self._ensure()
        data = self._request(f"torrents/files?hash={torrent_hash}")
        return data if isinstance(data, list) else []

    def add_tags(self, hashes: List[str], tags: List[str]) -> None:
        """给种子加标签。"""
        if not hashes or not tags:
            return
        self._ensure()
        self._request("torrents/addTags",
                      {"hashes": "|".join(hashes), "tags": ",".join(tags)},
                      method="POST")

    def get_tags(self) -> List[str]:
        self._ensure()
        data = self._request("torrents/tags")
        return data if isinstance(data, list) else []

    def set_tag(self, torrent_hash: str, tag: str) -> None:
        self.add_tags([torrent_hash], [tag])

    def completed_torrents(self, done_tag: str = DEFAULT_DONE_TAG,
                           exclude_tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        返回「已完成」且尚未带 `done_tag` 标签的种子。
        这些就是 MoviePilot 认为「还没整理」、会去整理的种子。
        """
        exclude = set(exclude_tags or [])
        result = []
        for t in self.torrents_info(flt="completed"):
            tags = set((t.get("tags") or "").split(",")) if isinstance(t.get("tags"), str) else set(t.get("tags") or [])
            if done_tag in tags:
                continue
            if exclude and (tags & exclude):
                continue
            # 只处理确实 100% 完成的
            try:
                if float(t.get("progress", 1)) < 1.0:
                    continue
            except (TypeError, ValueError):
                pass
            result.append(t)
        return result


def extract_qb_config_from_mp() -> List[Dict[str, Any]]:
    """
    尽力从 MoviePilot 系统配置里读取 qBittorrent 下载器配置。
    兼容多种 MP 版本；读不到就返回空列表（由用户在插件里手填）。
    返回：[{name, host, username, password, api_key}]
    """
    configs: List[Dict[str, Any]] = []

    # 方式 1：新版 ServiceConfigHelper
    try:
        from app.runtime.extensions.service import ServiceConfigHelper  # type: ignore
        for c in ServiceConfigHelper.get_downloader_configs():
            if not str(getattr(c, "type", "")).lower().startswith("qb"):
                continue
            configs.append({
                "name": getattr(c, "name", ""),
                "host": getattr(c, "host", "") or "",
                "username": getattr(c, "username", "") or "",
                "password": getattr(c, "password", "") or "",
                "api_key": getattr(c, "apikey", "") or getattr(c, "api_key", "") or "",
            })
        if configs:
            return configs
    except Exception:
        pass

    # 方式 2：直接读 settings 原始字典
    try:
        from app.core.config import settings  # type: ignore
        raw = getattr(settings, "DOWNLOADER_CONF", None) or {}
        # 可能是 {"qbittorrent": [...] } 或 {name: {...}}
        candidates = []
        if isinstance(raw, dict):
            for k, v in raw.items():
                if "qb" in str(k).lower():
                    if isinstance(v, list):
                        candidates.extend(v)
                    elif isinstance(v, dict):
                        candidates.append(v)
        for c in candidates:
            if not isinstance(c, dict):
                continue
            configs.append({
                "name": c.get("name", "") or "qBittorrent",
                "host": c.get("host", "") or "",
                "username": c.get("username", "") or "",
                "password": c.get("password", "") or "",
                "api_key": c.get("apikey", "") or c.get("api_key", "") or "",
            })
    except Exception:
        pass

    return configs
