"""ManualPush115 configuration and request contracts (MoviePilot V2)."""
from __future__ import annotations

import posixpath
from copy import deepcopy
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

DEFAULTS = {"cookie": "", "user_agent": "", "extensions": "", "remote_dir": "/", "local_paths": [],
            "failure_move_enabled": False, "failure_move_dir": "", "delete_on_success": False,
            "failure_move_preserve_structure": True}
DEFAULT_EXTS = {"mkv", "mp4", "avi", "ts", "rmvb", "wmv", "flv", "mov", "m4v", "m2ts",
                "srt", "ass", "ssa", "sub", "sup", "idx", "mp3", "flac", "aac", "wav", "m4a",
                "ogg", "wma", "nfo", "jpg", "jpeg", "png"}


def paths_list(value):
    # A comma is a valid Unix filename, not a separator for explicit lists.
    if isinstance(value, str):
        value = [entry.strip() for entry in value.splitlines() if entry.strip()]
    if not isinstance(value, (list, tuple)):
        return []
    paths = []
    for entry in value:
        if isinstance(entry, dict):
            entry = entry.get("value") or entry.get("path") or ""
        # A selected filesystem path is literal; do not trim spaces/newlines
        # from a real filename received as an explicit list value.
        if isinstance(entry, str) and entry and entry not in paths:
            paths.append(entry)
    return paths


def remote_path(value):
    if isinstance(value, dict):
        value = value.get("value") or value.get("path") or "/"
    path = str(value or "/").strip()
    if "\x00" in path or any(part == ".." for part in path.split("/")):
        raise ValueError("115 目标目录格式无效")
    return posixpath.normpath("/" + path.lstrip("/"))


def flag(value):
    if isinstance(value, str):
        if value.lower().strip() in {'false', '0', 'off', 'no', ''}:
            return False
        if value.lower().strip() in {'true', '1', 'on', 'yes'}:
            return True
        raise ValueError('文件动作开关必须是布尔值')
    if not isinstance(value, (bool, int)) or value not in (False, True):
        raise ValueError('文件动作开关必须是布尔值')
    return bool(value)


def normalize_config(raw):
    raw = raw if isinstance(raw, dict) else {}
    cfg = deepcopy(raw)
    cfg.update(cookie=str(raw.get("cookie") or "").strip(),
               user_agent=str(raw.get("user_agent") or "").strip(),
               extensions=str(raw.get("extensions") or "").strip(),
               remote_dir=remote_path(raw.get("remote_dir")),
               local_paths=paths_list(raw.get("local_paths")),
               failure_move_enabled=flag(raw.get("failure_move_enabled", False)),
               failure_move_dir=str(raw.get("failure_move_dir") or "").strip(),
               delete_on_success=flag(raw.get("delete_on_success", False)),
               failure_move_preserve_structure=flag(raw.get("failure_move_preserve_structure", True)))
    from .fileactions import validate_directory
    cfg['failure_move_dir'] = validate_directory(cfg['failure_move_dir'])
    if cfg['failure_move_enabled'] and not cfg['failure_move_dir']:
        raise ValueError('启用失败移动时必须设置失败目录')
    return cfg


def allowed_extensions(cfg):
    raw = str(cfg.get("extensions") or "").strip()
    if raw == "*":
        return {"*"}
    return {word.lower().lstrip(".") for word in raw.replace(",", " ").split()} if raw else set(DEFAULT_EXTS)


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    cookie: str = ""
    user_agent: str = ""
    extensions: str = ""
    remote_dir: str = "/"
    local_paths: list[str] = Field(default_factory=list)
    failure_move_enabled: bool = False
    failure_move_dir: str = ""
    delete_on_success: bool = False
    failure_move_preserve_structure: bool = True


class PushPayload(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=1000)
    remote_dir: Optional[str] = None
    remote_cid: Optional[str] = None
    force: bool = True
    preserve_structure: bool = True
    request_id: Optional[str] = Field(default=None, max_length=100)
