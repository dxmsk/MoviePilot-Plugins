"""Read one real 115 directory at a time; never enumerate the whole drive on form load."""
from __future__ import annotations
import posixpath
from .p115_web import P115WebError, P115AuthError, WEBAPI


def browse_remote(client, cid="0", offset=0, limit=100):
    cid = str(cid or "0")
    if not cid.isdecimal():
        raise ValueError("115 目录 ID 无效")
    offset, limit = max(0, int(offset)), max(1, min(200, int(limit)))
    raw = client._get_json(f"{WEBAPI}/files", {
        "aid": 1, "cid": cid, "offset": offset, "limit": limit,
        "show_dir": 1, "o": "file_name", "asc": 1,
    }, timeout=15)
    if raw.get("state") is not True and raw.get("state") != 1:
        message = raw.get("error") or raw.get("message") or "读取网盘目录失败"
        error = P115AuthError if raw.get("code") in (40101017, 40101001, 990002) else P115WebError
        raise error(str(message))
    ancestors = raw.get("path") or []
    parts = []
    for ancestor in ancestors:
        if not isinstance(ancestor, dict):
            continue
        aid = str(ancestor.get("cid", ancestor.get("id", "0")))
        name = str(ancestor.get("name") or ancestor.get("n") or "").strip("/")
        if aid != "0" and name:
            parts.append(name)
    current_path = "/" + "/".join(parts)
    if cid != "0" and not parts:
        raise P115WebError("115 未返回当前目录路径，请返回根目录重新选择")
    parent = str(ancestors[-2].get("cid", ancestors[-2].get("id", "0"))) if len(ancestors) > 1 else "0"
    entries = []
    rows = raw.get("data") or []
    for row in rows:
        if not isinstance(row, dict) or row.get("sha") or not row.get("cid"):
            continue
        name = str(row.get("n") or row.get("fn") or "")
        if not name or "/" in name or name in (".", ".."):
            continue
        entries.append({"cid": str(row["cid"]), "name": name,
                        "path": posixpath.join(current_path, name)})
    try:
        total = int(raw.get("count"))
        has_more = offset + len(rows) < total
    except (TypeError, ValueError):
        total = None
        has_more = len(rows) >= limit
    return {"cid": cid, "path": current_path, "parent_cid": parent,
            "entries": entries, "offset": offset, "limit": limit,
            "next_offset": offset + len(rows), "total": total, "has_more": has_more}
