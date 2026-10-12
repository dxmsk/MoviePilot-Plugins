"""
115 网盘轻量客户端（仅依赖标准库）。

实现：
- Cookie 登录态校验
- 目录创建 / 目录列表
- 秒传（SHA1 快传）—— 走 115 开放平台 Open API
    1) POST https://proapi.115.com/open/upload/init
       秒传成功（status == 2）直接返回 pickcode
    2) 若 status == 7，需要二次校验（签名区间读取文件内容计算 SHA1），
       再提交一次即可完成秒传
- 仅做"秒传"，绝不下载/上传文件本体，因此不会占用带宽、不移动原始文件。

说明：本模块只调用 115 官方 Open API（开放平台），需要用户提供
      access_token（开放平台令牌），比网页端加密接口更稳定可靠。
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

OPEN_API_BASE = "https://proapi.115.com"
WEB_API_BASE = "https://webapi.115.com"
# 秒传最小阈值：小于 1MB 无需二次校验；大于等于 1MB 且未命中秒传时需签名校验
SIGN_CHECK_THRESHOLD = 1024 * 1024


class P115Error(Exception):
    """115 接口调用异常。"""


class P115AuthError(P115Error):
    """鉴权失败。"""


class P115Client:
    """115 网盘客户端（Open API，侧重秒传）。"""

    def __init__(
        self,
        access_token: str = "",
        cookie: str = "",
        timeout: int = 30,
    ) -> None:
        self.access_token = (access_token or "").strip()
        self.cookie = (cookie or "").strip()
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # 底层请求
    # ------------------------------------------------------------------ #
    def _headers_open(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        }

    def _headers_web(self) -> Dict[str, str]:
        return {
            "Cookie": self.cookie,
            "User-Agent": USER_AGENT,
        }

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 2,
    ) -> Dict[str, Any]:
        """通用请求，返回解析后的 JSON dict。"""
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")

        last_err: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(
                    url, data=body, method=method, headers=headers or {}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as e:  # 带响应体的 HTTP 错误
                try:
                    raw = e.read()
                    payload = json.loads(raw.decode("utf-8"))
                    # 401/403 直接抛出鉴权异常
                    if e.code in (401, 403):
                        raise P115AuthError(
                            f"HTTP {e.code}: {payload.get('message') or payload}"
                        )
                    if attempt >= retries:
                        raise P115Error(f"HTTP {e.code}: {payload}")
                    last_err = P115Error(f"HTTP {e.code}: {payload}")
                except (ValueError, UnicodeDecodeError):
                    if attempt >= retries:
                        raise P115Error(f"HTTP {e.code}: {e.reason}")
                    last_err = P115Error(f"HTTP {e.code}: {e.reason}")
            except P115AuthError:
                raise
            except Exception as e:  # 网络等异常
                last_err = e
                if attempt >= retries:
                    raise P115Error(f"请求失败: {e}") from e
            time.sleep(0.8 * (attempt + 1))
        raise P115Error(str(last_err))

    # ------------------------------------------------------------------ #
    # 账号 / 目录
    # ------------------------------------------------------------------ #
    def check_login(self) -> Dict[str, Any]:
        """校验 Open API 令牌是否有效，返回用户信息。"""
        if not self.access_token:
            raise P115AuthError("未配置 115 开放平台 access_token")
        resp = self._request(
            f"{OPEN_API_BASE}/open/user/info",
            headers=self._headers_open(),
        )
        if not resp.get("state"):
            raise P115AuthError(resp.get("message") or "access_token 无效")
        return resp.get("data") or {}

    def get_dir_id_by_path(self, path: str, create: bool = True) -> int:
        """
        把 /电影/2024 这样的路径转换为目录 id。

        优先调用 open/folder/get_info 用 path 直接查询；
        查不到时逐级查找/创建（create=True）。
        """
        raw = (path or "").strip()
        if not raw or raw == "/":
            return 0
        norm = "/" + raw.strip("/")

        # 1) 直接用 path 查询（官方支持 path 参数）
        try:
            resp = self._request(
                f"{OPEN_API_BASE}/open/folder/get_info",
                headers=self._headers_open(),
                params={"path": norm},
            )
            if resp.get("state"):
                data = resp.get("data") or {}
                fid = data.get("file_id") or data.get("cid")
                if fid:
                    return int(fid)
        except P115Error:
            pass

        if not create:
            return 0

        # 2) 逐级查找或创建
        cid = 0
        for name in [p for p in norm.split("/") if p]:
            cid = self._find_or_make_dir(cid, name)
        return cid

    def cid_exists(self, cid: int) -> bool:
        try:
            resp = self._request(
                f"{OPEN_API_BASE}/open/folder/get_info",
                headers=self._headers_open(),
                params={"file_id": cid},
            )
            return bool(resp.get("state"))
        except P115Error:
            return False

    def _find_child_dir(self, parent_cid: int, name: str) -> Optional[int]:
        """在目录下查找同名子目录，返回 cid 或 None。"""
        offset = 0
        limit = 200
        for _ in range(50):
            resp = self._request(
                f"{OPEN_API_BASE}/open/ufile/files",
                headers=self._headers_open(),
                params={
                    "cid": parent_cid,
                    "limit": limit,
                    "offset": offset,
                    "show_dir": 1,
                    "record_open_time": 0,
                },
            )
            if not resp.get("state"):
                return None
            data = resp.get("data") or []
            if not data:
                return None
            for item in data:
                if item.get("fn") == name:
                    return int(item.get("fid") or 0)
            if len(data) < limit:
                return None
            offset += limit
        return None

    def _find_or_make_dir(self, parent_cid: int, name: str) -> int:
        found = self._find_child_dir(parent_cid, name)
        if found is not None:
            return found
        return self.make_dir(parent_cid, name)

    def make_dir(self, parent_cid: int, name: str) -> int:
        """创建目录，返回新目录 id。"""
        resp = self._request(
            f"{OPEN_API_BASE}/open/folder/add",
            method="POST",
            headers=self._headers_open(),
            data={"pid": parent_cid, "file_name": name},
        )
        if resp.get("state"):
            data = resp.get("data") or {}
            fid = data.get("cid") or data.get("file_id") or data.get("category_id")
            if fid:
                return int(fid)
            # 部分返回没有 id，回查一次
            found = self._find_child_dir(parent_cid, name)
            if found is not None:
                return found
            return 0
        # 已存在同名目录
        if "已存在" in str(resp.get("message", "")) or "exist" in str(resp).lower():
            found = self._find_child_dir(parent_cid, name)
            if found is not None:
                return found
        raise P115Error(f"创建目录失败: {resp.get('message') or resp}")

    # ------------------------------------------------------------------ #
    # 秒传
    # ------------------------------------------------------------------ #
    def push_file(
        self,
        local_path: "Path | str",
        remote_dir_id: int = 0,
    ) -> Dict[str, Any]:
        """统一入口：对本地文件执行秒传（与 P115WebClient.push_file 同名）。"""
        return self.quick_upload_file(local_path, remote_dir_id)

    def quick_upload_file(
        self,
        local_path: str,
        remote_dir_id: int = 0,
        remote_dir_name: str = "",
    ) -> Dict[str, Any]:
        """
        对本地单个文件执行秒传（SHA1 快传）。

        :param local_path: 本地文件绝对路径（只读取，不修改、不移动）
        :param remote_dir_id: 目标目录 id
        :param remote_dir_name: 目标目录名（仅用于返回信息）
        :return: {"ok": bool, "reuse": bool, "pickcode": str,
                  "need_check": bool, "message": str, "sha1": str, "size": int}
        """
        p = Path(local_path)
        if not p.is_file():
            return {
                "ok": False, "reuse": False, "pickcode": "",
                "need_check": False, "message": "本地文件不存在或不是文件",
                "sha1": "", "size": 0,
            }

        size = p.stat().st_size
        sha1 = self._sha1_file(p)

        payload: Dict[str, Any] = {
            "file_name": p.name,
            "fileid": sha1,
            "file_size": size,
            "target": f"U_1_{remote_dir_id}",
            "topupload": 1,
        }

        resp = self._upload_init(payload)

        # 秒传成功（服务器已有该文件）
        if resp.get("status") == 2:
            return {
                "ok": True, "reuse": True,
                "pickcode": resp.get("pick_code") or resp.get("pickcode") or "",
                "file_id": resp.get("file_id") or "",
                "need_check": False, "message": "秒传成功",
                "sha1": sha1, "size": size,
            }

        # 需要二次校验（文件 >= 1MB 且服务器未直接命中）
        if resp.get("status") == 7:
            sign_key = resp.get("sign_key") or ""
            sign_check = resp.get("sign_check") or ""
            sign_val = self._calc_sign_val(p, sign_check)
            if not sign_val:
                return {
                    "ok": False, "reuse": False, "pickcode": "",
                    "need_check": True, "message": "二次校验失败：无法读取文件区间",
                    "sha1": sha1, "size": size,
                }
            payload["sign_key"] = sign_key
            payload["sign_val"] = sign_val
            resp = self._upload_init(payload)
            if resp.get("status") == 2:
                return {
                    "ok": True, "reuse": True,
                    "pickcode": resp.get("pick_code") or resp.get("pickcode") or "",
                    "file_id": resp.get("file_id") or "",
                    "need_check": True, "message": "秒传成功（二次校验）",
                    "sha1": sha1, "size": size,
                }
            return {
                "ok": False, "reuse": False, "pickcode": "",
                "need_check": True,
                "message": f"秒传失败: {resp.get('message') or resp.get('status') or resp}",
                "sha1": sha1, "size": size,
            }

        # status == 1 需要真实上传（本插件不做）
        return {
            "ok": False, "reuse": False, "pickcode": "",
            "need_check": False,
            "message": f"未命中秒传（status={resp.get('status')}），需真实上传",
            "sha1": sha1, "size": size,
        }

    def _upload_init(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._request(
            f"{OPEN_API_BASE}/open/upload/init",
            method="POST",
            headers=self._headers_open(),
            data=payload,
        )
        if not resp.get("state"):
            msg = resp.get("message") or resp
            if "token" in str(msg).lower() or "授权" in str(msg):
                raise P115AuthError(str(msg))
            raise P115Error(str(msg))
        return resp.get("data") or {}

    @staticmethod
    def _calc_sign_val(path: Path, sign_check: str) -> str:
        """按 115 给出的区间读取文件片段并计算 SHA1。"""
        try:
            start_s, end_s = sign_check.split("-")
            start, end = int(start_s), int(end_s)
        except (ValueError, AttributeError):
            return ""
        length = end - start + 1
        try:
            with open(path, "rb") as f:
                f.seek(start)
                chunk = f.read(length)
            return hashlib.sha1(chunk).hexdigest().upper()
        except OSError:
            return ""

    @staticmethod
    def _sha1_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest().upper()
