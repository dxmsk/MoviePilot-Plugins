"""Configuration normalization and non-secret state helpers for CloudPush115."""
from __future__ import annotations
from __future__ import annotations

import hashlib
import os
import re
from copy import deepcopy
from datetime import datetime
from typing import Any

DEFAULTS = {
    "enabled": False, "onlyonce": False, "notify": False,
    "cookie": "", "user_agent": "", "watch_paths": "", "remote_dir": "/",
    "extensions": "", "scan_interval": 60, "retry_interval": 600,
    "max_attempts": 0, "retry_notfound": True,
    "qb_enabled": False, "qb_host": "", "qb_username": "admin", "qb_password": "",
    "qb_done_tag": "已整理", "qb_interval": 5, "qb_settle": 0, "qb_path_mappings": "",
    "failure_move_enabled": False, "failure_move_dir": "", "failure_move_on": "exhausted",
    "failure_move_preserve_structure": True, "delete_on_success": False,
}
OBSOLETE = {"access_token", "login_mode", "local_browse_path", "remote_browse_cid",
            "remote_browse_path", "watch_paths_display", "remote_dir_display"}


def flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "none"}
    return bool(value)


def integer(value: Any, default: int = 0, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (ValueError, TypeError, OverflowError):
        try:
            return max(minimum, int(float(value)))
        except (ValueError, TypeError, OverflowError):
            return default


def split_paths(value: Any) -> list[str]:
    if isinstance(value, (tuple, list, set)):
        parts = [str(x).strip() for x in value if x is not None]
    else:
        parts = re.split(r"[,，\r\n]+", str(value or ""))
    return list(dict.fromkeys(os.path.normpath(x.strip()) for x in parts if x.strip()))


def normalize_config(value: Any) -> dict:
    original = value if isinstance(value, dict) else {}
    config = {**DEFAULTS, **deepcopy(original)}
    for key in OBSOLETE:
        config.pop(key, None)
    for key in ("enabled", "onlyonce", "notify", "retry_notfound", "qb_enabled"):
        config[key] = flag(config.get(key))
    for key in ("scan_interval", "retry_interval", "max_attempts", "qb_interval", "qb_settle"):
        minimum = {"scan_interval": 1, "retry_interval": 30, "qb_interval": 3}.get(key, 0)
        config[key] = integer(config.get(key), DEFAULTS[key], minimum)
    for key in ("cookie", "user_agent", "remote_dir", "extensions", "qb_host", "qb_username",
                "qb_password", "qb_done_tag", "qb_path_mappings"):
        config[key] = str(config.get(key) or "").strip()
    config["qb_done_tag"] = config["qb_done_tag"] or "已整理"
    config["watch_paths"] = "\n".join(split_paths(config.get("watch_paths")))
    config["remote_dir"] = remote_path(config.get("remote_dir"))
    from .fileactions import validate_directory, contains
    for key in ('failure_move_enabled', 'delete_on_success', 'failure_move_preserve_structure'):
        config[key] = flag(config[key])
    config['failure_move_dir'] = validate_directory(config['failure_move_dir'])
    if config['failure_move_on'] not in {'each_failure', 'exhausted'}:
        raise ValueError('失败移动策略必须为 each_failure 或 exhausted')
    if config['failure_move_enabled']:
        if not config['failure_move_dir']:
            raise ValueError('启用失败移动时必须设置失败目录')
        if any(contains(root, config['failure_move_dir']) for root in split_paths(config['watch_paths'])):
            raise ValueError('失败目录不能位于监控目录内，避免循环扫描')
        if config['failure_move_on'] == 'exhausted' and config['max_attempts'] == 0:
            raise ValueError('无限重试请选每次失败移动，或设置有限重试次数')
    return config


def remote_path(path: Any) -> str:
    return "/" + "/".join(x for x in str(path or "").split("/") if x and x != ".")


def account_scope(config: dict) -> str:
    # UID user number is stable across Cookie renewal. Never expose Cookie material.
    raw = str(config.get("cookie") or "")
    uid = re.search(r"(?:^|[;\s])UID=([^;\s]+)", raw, re.I)
    identity = uid.group(1).split("_")[0] if uid else raw
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def task_key(path: str, target: str, scope: str) -> str:
    return hashlib.sha256((scope + "\0" + target + "\0" + path).encode()).hexdigest()


def stamp(value: Any = None) -> str:
    try:
        return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S") if value else ""
    except (ValueError, TypeError, OverflowError, OSError):
        return ""


def byte_size(value: Any) -> int:
    if isinstance(value, (float, int)):
        return integer(value)
    text = str(value or "").strip().upper()
    if text.isdecimal():
        return integer(text)
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KMGTPE]?I?B)?", text)
    if not match:
        return 0
    unit = (match.group(2) or "B").replace("I", "")
    return integer(float(match.group(1)) * 1024 ** ["B", "KB", "MB", "GB", "TB", "PB", "EB"].index(unit))


def human_size(value: Any) -> str:
    n = byte_size(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if n < 1024 or unit == "PB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return "0 B"


def signature(item: dict) -> list[int]:
    return [integer(item.get("size")), integer(item.get("mtime_ns")), integer(item.get("inode"))]


def clean_message(value: Any, config: dict) -> str:
    message = str(value or "")
    for key in ("cookie", "qb_password"):
        secret = str(config.get(key) or "")
        if secret:
            message = message.replace(secret, "[已隐藏凭据]")
    return message[:2000]


def normalize_history(rows: Any) -> list[dict]:
    result = []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        row = deepcopy(row)
        label = str(row.get("result", ""))
        if label == "qB状态":  # Polling diagnostics are not transfer outcomes.
            continue
        state = row.get("status")
        if not state:
            state = "skipped" if "跳过" in label else ("failed" if "失败" in label else ("success" if "成功" in label else "info"))
        row.update(status=state, size=byte_size(row.get("size_bytes", row.get("size"))),
                   message=str(row.get("message", "")), source=str(row.get("source") or "legacy"))
        row.setdefault("id", "legacy-" + hashlib.sha256((str(index) + str(row)).encode()).hexdigest()[:20])
        row.setdefault("name", os.path.basename(str(row.get("path") or "")))
        for key in ("id", "name", "path", "status", "result", "message", "source", "remote_dir", "time"):
            row[key] = str(row.get(key) or "")
        result.append(row)
    return result[-500:]
