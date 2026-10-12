"""
115 扫码登录辅助模块（方案 A：扫码 + 手动粘贴 Cookie）。

背景
----
115 网页版扫码登录的「确认后换取 Cookie」这一步，是在 115 浏览器 App 内的
原生桥（browserInterface / bridge）里完成的，协议未公开。纯 HTTP 客户端
无论如何都无法直接拿到 Set-Cookie（会返回 40101017 老乡验证失败）。

因此本模块提供「半自动」方案：
  1. 向后端申请二维码 token，用 qrcode 库渲染成 PNG（base64 内嵌，前端直接显示）；
  2. 前端轮询状态接口，实时识别「等待扫码 / 已扫码待确认 / 已确认 / 已过期」；
  3. 用户手机确认后，模块提示「请从 115 App / 浏览器复制 Cookie 粘贴到配置」。

Cookie 的解析交给 p115_web.parse_cookie_string 完成（支持多种格式）。
"""

from __future__ import annotations

import base64
import io
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

QR_API = "https://qrcodeapi.115.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 状态码（来自 115 官方 login-api.js + 实测）
STATUS_WAITING = "waiting"     # 90038 请扫描二维码
STATUS_SCANNED = "scanned"     # 90039 已扫码，请在手机上确认
STATUS_CONFIRMED = "confirmed"  # 90040 / state=true 已确认
STATUS_EXPIRED = "expired"     # 90033 / 90034 二维码已过期
STATUS_CANCELED = "canceled"   # 90041 已取消


class QrLoginError(Exception):
    pass


def _get_json(url: str, params: Optional[dict] = None, timeout: int = 15) -> dict:
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": DEFAULT_UA})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_qrcode_token(timeout: int = 15) -> Dict[str, Any]:
    """申请二维码 token，返回 {uid, time, sign, qrcode, url}。"""
    data = _get_json(f"{QR_API}/api/1.0/web/1.0/token", timeout=timeout)
    if not data.get("state") or not data.get("data"):
        raise QrLoginError(f"获取二维码失败：{data.get('message') or data}")
    d = data["data"]
    return {
        "uid": d["uid"],
        "time": d["time"],
        "sign": d["sign"],
        "qrcode": d.get("qrcode", ""),
        # 用 115 官方扫码协议 URL（115 App 可识别）
        "url": d.get("qrcode") or f"https://115.com/scan/dg-{d['uid']}",
    }


def make_qr_png_base64(content: str, box_size: int = 6, border: int = 2) -> str:
    """把内容渲染成二维码 PNG，返回 data URI（可直接用于 <img src>）。"""
    try:
        import qrcode  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise QrLoginError(
            "缺少 qrcode 库，请在容器内执行：pip install qrcode"
        ) from e
    img = qrcode.make(content, box_size=box_size, border=border)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def poll_status(uid: str, sign: str, timestamp: int, timeout: int = 10) -> Dict[str, Any]:
    """
    轮询扫码状态。
    返回 {"status": waiting/scanned/confirmed/expired/canceled, "raw": {...}}
    """
    data = _get_json(
        f"{QR_API}/api/1.0/web/1.0/status/",
        {"uid": uid, "time": timestamp, "sign": sign},
        timeout=timeout,
    )
    code = data.get("code")
    if data.get("state") is True:
        # 已确认：data 里通常带 user_id / user_name
        return {"status": STATUS_CONFIRMED, "raw": data}
    if code == 90038:
        return {"status": STATUS_WAITING, "raw": data}
    if code in (90039, 90037):
        return {"status": STATUS_SCANNED, "raw": data}
    if code in (90033, 90034):
        return {"status": STATUS_EXPIRED, "raw": data}
    if code == 90041:
        return {"status": STATUS_CANCELED, "raw": data}
    # 其它未知：按未确认处理，保留原始信息
    return {"status": STATUS_WAITING, "raw": data,
            "message": data.get("message")}


def new_session() -> Dict[str, Any]:
    """创建一次扫码会话：返回 token 信息 + 二维码 data URI。"""
    tok = get_qrcode_token()
    png = make_qr_png_base64(tok["url"])
    return {
        "uid": tok["uid"],
        "time": tok["time"],
        "sign": tok["sign"],
        "url": tok["url"],
        "qrcode_png": png,
        "created_at": int(time.time()),
    }
