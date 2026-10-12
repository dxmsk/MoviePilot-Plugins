"""
115 网盘【网页版 Cookie】客户端（秒传专用）。

无需在 115 开放平台申请应用，直接用网页登录后的 Cookie 即可。
上传走加密接口 uplb.115.com/4.0/initupload.php（ECDH-AES 加密 + sig/token 签名）。

依赖：仅标准库 + 同包的 _crypto / aes 模块。
"""

from __future__ import annotations

import json
import time
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor

from ._crypto import (
    content_maybe_decrypt,
    ecdh_aes_decrypt,
    make_upload_payload,
)

# 网页 / proapi 基础域名
WEBAPI = "https://webapi.115.com"
PROAPI = "https://proapi.115.com"
UPLB = "https://uplb.115.com"
APP_VERSION = "36.2.28"

# 页面上传 User-Agent（115 会校验）
UPLOAD_UA = (
    f"Mozilla/5.0 115disk/{APP_VERSION} 115Browser/{APP_VERSION} "
    f"115wangpan_android/{APP_VERSION}"
)
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HAS_SHA1_THRESHOLD = 1024 * 1024  # 1 MB，超过需要二次校验区间哈希


class P115WebError(Exception):
    """115 网页接口异常。"""


class P115AuthError(P115WebError):
    """Cookie 失效 / 未登录。"""


def parse_cookie_string(raw: str) -> Dict[str, str]:
    """
    解析多种常见格式的 Cookie（覆盖用户实际会复制的各种形态）：
    - 浏览器请求头:        "UID=1; CID=2; SEID=3"（也支持 "Cookie: UID=1; CID=2"）
    - cURL / DevTools:     "Cookie: UID=1; CID=2" 或 "-H 'Cookie: ...'"
    - EditThisCookie JSON: [{"name":"UID","value":"1"}, ...]
    - Chrome DevTools 表:  "UID\t1\t.115.com\t/\t..." （Tab 分隔）
    - Netscape cookies.txt:"# Netscape...\n.115.com\tTRUE\t/\tFALSE\t0\tUID\t1"
    - 每行 key=value
    """
    text = (raw or "").strip()
    if not text:
        return {}

    cookies: Dict[str, str] = {}

    # ---------- 1. JSON（EditThisCookie / Cookie-Editor 导出） ----------
    if text[:1] in "[{":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get("cookies") or data.get("data") or [data]
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("key")
                value = item.get("value")
                if name is None or value is None:
                    continue
                # 只取 115 相关域（无域信息时全部保留）
                dom = str(item.get("domain") or "")
                if dom and "115" not in dom and "anxia" not in dom:
                    continue
                cookies[str(name).strip()] = str(value).strip()
            if cookies:
                return cookies
        except (ValueError, TypeError):
            pass  # 不是合法 JSON，继续走文本解析

    # ---------- 2. 文本格式 ----------
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 去掉 cURL / 复制残留的前缀：Cookie: / -H 'Cookie:' / set-cookie:
        low = line.lower()
        for pfx in ("-h ", "-h'", "cookie:", "set-cookie:", '"cookie:', "'cookie:"):
            if low.startswith(pfx):
                line = line[len(pfx):].strip()
                low = line.lower()
                break
        line = line.strip().strip('"').strip("'").strip()
        # 去掉 -H 后面可能残留的引号
        if line.lower().startswith("cookie:"):
            line = line[7:].strip()

        if "\t" in line:  # Chrome DevTools 表格 / Netscape
            parts = [p.strip() for p in line.split("\t")]
            # Chrome DevTools: Name  Value  Domain  Path  Expires  Size  ...
            if len(parts) >= 2 and parts[1]:
                cookies.setdefault(parts[0], parts[1])
            # Netscape: domain flag path secure expires name value
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]
            continue

        if ";" in line:  # 请求头 / 分号分隔
            for seg in line.split(";"):
                seg = seg.strip()
                if "=" in seg:
                    k, v = seg.split("=", 1)
                    cookies[k.strip()] = v.strip().strip('"')
            continue

        if "=" in line:  # 每行 key=value
            k, v = line.split("=", 1)
            cookies[k.strip()] = v.strip().strip('"')

    # 过滤掉明显不是 cookie 的键（DevTools 表格的大小/时间列、"域"列等）
    def _bad_key(k: str) -> bool:
        if not k:
            return True
        if any(c in k for c in (" ", "expires", "httponly", "path", "domain", "samesite")):
            return True
        if k.isdigit():                      # DevTools 的 Size/Expires 列
            return True
        if k.startswith(".") or "." in k:    # 域名字符串
            return True
        return False

    cookies = {k: v for k, v in cookies.items() if not _bad_key(k)}
    return cookies


class P115WebClient:
    """基于 Cookie 的 115 客户端。"""

    def __init__(self, cookie: str, user_agent: str = ""):
        self.cookies = parse_cookie_string(cookie)
        if not self.cookies:
            raise P115AuthError("Cookie 为空或格式无法识别")
        self.user_agent = user_agent or DEFAULT_UA
        self._jar = CookieJar()
        self._opener = build_opener(HTTPCookieProcessor(self._jar))
        self._user_id: Optional[str] = None
        self._user_key: Optional[str] = None
        # 把 Cookie 灌入 jar（对 115.com 全域生效）
        self._prime_cookies()

    # ---------------- 底层请求 ---------------- #
    def _prime_cookies(self) -> None:
        from http.cookiejar import Cookie
        for k, v in self.cookies.items():
            for domain in (".115.com",):
                c = Cookie(
                    version=0, name=k, value=v, port=None, port_specified=False,
                    domain=domain, domain_specified=True, domain_initial_dot=True,
                    path="/", path_specified=True, secure=True, expires=None,
                    discard=False, comment=None, comment_url=None, rest={},
                )
                self._jar.set_cookie(c)

    def _request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
        timeout: int = 30,
    ) -> bytes:
        hdrs = {"User-Agent": self.user_agent, "Accept": "*/*"}
        if headers:
            hdrs.update(headers)
        body = None
        if data is not None:
            if isinstance(data, (dict, list)):
                body = urlencode(data, doseq=True).encode("utf-8")
            elif isinstance(data, str):
                body = data.encode("utf-8")
            else:
                body = data
        req = Request(url, data=body, headers=hdrs, method=method)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            raise P115WebError(f"请求失败 {url}: {exc}") from exc

    def _get_json(self, url: str, params: Optional[dict] = None,
                  timeout: int = 30) -> dict:
        if params:
            url = url + ("&" if "?" in url else "?") + urlencode(params)
        raw = self._request(url, timeout=timeout)
        try:
            plain = content_maybe_decrypt(raw)
            return json.loads(plain)
        except Exception as exc:  # noqa: BLE001
            raise P115WebError(f"解析响应失败 {url}: {exc}") from exc

    def _post_json(self, url: str, data: dict, headers: Optional[dict] = None,
                   timeout: int = 30) -> dict:
        raw = self._request(url, method="POST", data=data, headers=headers,
                            timeout=timeout)
        try:
            plain = content_maybe_decrypt(raw)
            return json.loads(plain)
        except Exception as exc:  # noqa: BLE001
            raise P115WebError(f"解析响应失败 {url}: {exc}") from exc

    # ---------------- 登录校验 ---------------- #
    def check_login(self) -> Dict[str, Any]:
        """校验登录态，成功返回用户信息字典，失败抛 P115AuthError。"""
        data = self._get_json(f"{WEBAPI}/?ct=guide&ac=status")
        if not data.get("state"):
            raise P115AuthError("Cookie 已失效或无效（登录状态检查未通过）")
        info: Dict[str, Any] = {"state": True}
        try:
            u = self._get_json(f"{PROAPI}/2.0/user/info", {"app": "android"})
            if u.get("state"):
                d = u.get("data") or {}
                info.update(d)
                info["user_name"] = d.get("user_name") or d.get("name") or d.get("user_id")
        except P115WebError:
            pass
        return info

    def user_id(self) -> str:
        if self._user_id:
            return self._user_id
        data = self._get_json(f"{PROAPI}/2.0/user/info", {"app": "android"})
        if not data.get("state"):
            raise P115AuthError("获取用户信息失败，Cookie 可能已失效")
        info = data.get("data") or {}
        uid = info.get("user_id") or info.get("uid") or info.get("userid")
        if not uid:
            raise P115AuthError("响应中缺少 user_id")
        self._user_id = str(uid)
        return self._user_id

    def user_key(self) -> str:
        if self._user_key:
            return self._user_key
        data = self._get_json(f"{PROAPI}/2.0/user/upload_key", {"app": "android"})
        if not data.get("state"):
            raise P115AuthError("获取 upload_key 失败，Cookie 可能已失效")
        key = (data.get("data") or {}).get("userkey") or ""
        if not key:
            raise P115AuthError("响应中缺少 userkey")
        self._user_key = key
        return self._user_key

    # ---------------- 目录操作 ---------------- #
    def list_dir(self, cid: int | str = 0) -> Dict[str, Any]:
        """列出目录内容，返回 {fid: {name, is_dir}}。"""
        result: Dict[str, Any] = {}
        offset = 0
        while True:
            data = self._get_json(f"{WEBAPI}/files", {
                "aid": 1, "cid": cid, "o": "user_ptime", "asc": 0,
                "offset": offset, "show_dir": 1, "limit": 500,
            })
            if not data.get("state"):
                break
            items = data.get("data") or []
            for it in items:
                fid = str(it.get("fid") or it.get("cid") or "")
                if not fid:
                    continue
                result[fid] = {
                    "name": it.get("n") or it.get("fn") or "",
                    "is_dir": bool(it.get("fid") and not it.get("sha")),
                    "cid": str(it.get("cid") or ""),
                }
            if len(items) < 500:
                break
            offset += 500
        return result

    def browse(self, cid: int | str = 0) -> Dict[str, Any]:
        """
        浏览某一层目录，用于可视化目录选择。
        返回 {"cid": str, "entries": [ {"cid","name","is_dir","size","count"} ]}
        只返回目录（is_dir=True）——目标目录选择只需要目录。
        """
        raw = self._get_json(f"{WEBAPI}/files", {
            "aid": 1, "cid": cid, "o": "user_ptime", "asc": 0,
            "offset": 0, "show_dir": 1, "limit": 500,
        })
        if not raw.get("state"):
            msg = raw.get("message") or raw.get("error") or "读取目录失败"
            if raw.get("code") in (40101017, 40101001, 990002):
                raise P115AuthError(f"Cookie 可能已失效：{msg}")
            raise P115WebError(f"读取目录失败：{msg}")
        entries = []
        for it in (raw.get("data") or []):
            is_dir = bool(it.get("cid") and not it.get("sha"))
            if not is_dir:
                continue
            entries.append({
                "cid": str(it.get("cid") or it.get("fid") or ""),
                "name": it.get("n") or it.get("fn") or "",
                "is_dir": True,
                "size": 0,
                "count": it.get("count") or 0,
            })
        entries.sort(key=lambda x: x["name"])
        return {"cid": str(cid), "entries": entries}

    def path_of_cid(self, cid: int | str, max_depth: int = 32) -> str:
        """从根开始逐层查找，返回 cid 对应的路径字符串（best-effort）。"""
        if str(cid) in ("0", ""):
            return "/"
        # 逐层 BFS 找到目标 cid，记录路径
        queue = [(0, "/")]
        visited = set()
        while queue and max_depth > 0:
            max_depth -= 1
            nxt = []
            for cur, path in queue:
                if str(cur) in visited:
                    continue
                visited.add(str(cur))
                try:
                    data = self.browse(cur)
                except P115WebError:
                    continue
                for e in data["entries"]:
                    child_path = (path.rstrip("/") + "/" + e["name"])
                    if e["cid"] == str(cid):
                        return child_path
                    nxt.append((e["cid"], child_path))
            queue = nxt[:200]  # 限制广度，避免超时
        return ""

    def find_dir(self, parent_cid: int | str, name: str) -> Optional[int]:
        for fid, info in self.list_dir(parent_cid).items():
            if info["is_dir"] and info["name"] == name:
                return int(fid)
        return None

    def make_dir(self, parent_cid: int | str, name: str) -> int:
        data = self._post_json(f"{WEBAPI}/files/add",
                               {"cname": name, "pid": parent_cid})
        if data.get("state"):
            cid = (data.get("cid") or data.get("category_id")
                   or (data.get("data") or {}).get("cid"))
            if cid:
                return int(cid)
            found = self.find_dir(parent_cid, name)
            if found is not None:
                return found
        msg = str(data.get("error") or data.get("message") or "")
        if "已存在" in msg or "exist" in msg.lower():
            found = self.find_dir(parent_cid, name)
            if found is not None:
                return found
        raise P115WebError(f"创建目录失败: {msg or data}")

    def get_dir_id_by_path(self, path: str, create: bool = True) -> int:
        raw = (path or "").strip()
        if not raw or raw == "/":
            return 0
        cid = 0
        for name in [p for p in raw.split("/") if p]:
            found = self.find_dir(cid, name)
            if found is None:
                if not create:
                    return 0
                found = self.make_dir(cid, name)
            cid = found
        return cid

    # ---------------- 秒传 ---------------- #
    @staticmethod
    def _sha1_file(path: Path, chunk: int = 1 << 20) -> str:
        import hashlib
        h = hashlib.sha1()
        with open(path, "rb") as f:
            while True:
                block = f.read(chunk)
                if not block:
                    break
                h.update(block)
        return h.hexdigest().upper()

    @staticmethod
    def _calc_sign_val(path: Path, sign_check: str) -> str:
        try:
            start_s, end_s = sign_check.split("-")
            start, end = int(start_s), int(end_s)
        except (ValueError, AttributeError):
            return ""
        if start < 0 or end < start:
            return ""
        import hashlib
        h = hashlib.sha1()
        remaining = end - start + 1
        with open(path, "rb") as f:
            f.seek(start)
            while remaining > 0:
                block = f.read(min(1 << 20, remaining))
                if not block:
                    break
                h.update(block)
                remaining -= len(block)
        if remaining > 0:
            return ""
        return h.hexdigest().upper()

    def upload_init(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """调用加密上传初始化接口，返回明文 dict。"""
        payload = dict(payload)
        payload.setdefault("appid", 0)
        payload.setdefault("target", "U_1_0")
        payload.setdefault("sign_key", "")
        payload.setdefault("sign_val", "")
        payload.setdefault("topupload", "true")
        payload.setdefault("appversion", APP_VERSION)
        payload["userid"] = str(payload.get("userid") or self.user_id())
        payload["userkey"] = payload.get("userkey") or self.user_key()

        built = make_upload_payload(payload)
        url = f"{UPLB}/4.0/initupload.php?" + urlencode(built["params"])
        raw = self._request(
            url, method="POST", data=built["data"],
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "user-agent": UPLOAD_UA,
            },
        )
        try:
            return json.loads(ecdh_aes_decrypt(raw))
        except Exception as exc:  # noqa: BLE001
            raise P115WebError(f"解析上传响应失败: {exc}") from exc

    def push_file(
        self,
        path: Path,
        remote_dir_id: int = 0,
        total_min_size: int = 0,
    ) -> Dict[str, Any]:
        """
        秒传单个文件（不上传文件本体）。
        返回 {ok, reuse, pickcode, message, sha1, size, need_check}
        """
        path = Path(path)
        if not path.is_file():
            return {"ok": False, "reuse": False, "pickcode": "",
                    "message": "文件不存在或不是文件", "sha1": "", "size": 0,
                    "need_check": False}
        try:
            size = path.stat().st_size
        except OSError as exc:
            return {"ok": False, "reuse": False, "pickcode": "",
                    "message": f"读取文件失败: {exc}", "sha1": "", "size": 0,
                    "need_check": False}
        if size <= 0:
            return {"ok": False, "reuse": False, "pickcode": "",
                    "message": "空文件跳过", "sha1": "", "size": 0,
                    "need_check": False}
        if total_min_size and size < total_min_size:
            return {"ok": False, "reuse": False, "pickcode": "", "skipped": True,
                    "message": "小于最小大小，跳过", "sha1": "", "size": size,
                    "need_check": False}

        sha1 = self._sha1_file(path)
        payload = {
            "fileid": sha1,
            "filename": path.name,
            "filesize": size,
            "target": f"U_1_{remote_dir_id}",
            "sign_key": "",
            "sign_val": "",
        }
        resp = self.upload_init(payload)

        if resp.get("status") == 2:
            return {"ok": True, "reuse": True,
                    "pickcode": resp.get("pickcode") or resp.get("pick_code") or "",
                    "message": "秒传成功", "sha1": sha1, "size": size,
                    "need_check": False}

        if resp.get("status") == 7:
            sign_key = resp.get("sign_key") or ""
            sign_check = resp.get("sign_check") or ""
            sign_val = self._calc_sign_val(path, sign_check)
            if not sign_val:
                return {"ok": False, "reuse": False, "pickcode": "",
                        "message": "二次校验失败：无法读取文件区间",
                        "sha1": sha1, "size": size, "need_check": True}
            payload["sign_key"] = sign_key
            payload["sign_val"] = sign_val
            resp = self.upload_init(payload)
            if resp.get("status") == 2:
                return {"ok": True, "reuse": True,
                        "pickcode": resp.get("pickcode") or resp.get("pick_code") or "",
                        "message": "秒传成功（二次校验）", "sha1": sha1,
                        "size": size, "need_check": True}
            return {"ok": False, "reuse": False, "pickcode": "",
                    "message": f"秒传失败: {resp.get('error') or resp.get('message') or resp.get('status')}",
                    "sha1": sha1, "size": size, "need_check": True}

        return {"ok": False, "reuse": False, "pickcode": "",
                "message": f"未命中秒传（status={resp.get('status')}），需真实上传",
                "sha1": sha1, "size": size, "need_check": False}
