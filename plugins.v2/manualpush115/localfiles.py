"""Read-only local file selection; no MoviePilot imports until root discovery.

Empty path is a virtual root, never '/'. Browsing never reads child directories.
Explicitly selected regular files bypass extension filtering (including sidecars).
A validated path is not an open file handle: jobs should revalidate before upload.
"""
from __future__ import annotations

import os
import re
import stat
import time
from collections.abc import Mapping

DEFAULT_EXTENSIONS = frozenset({
    "mkv", "mp4", "avi", "ts", "rmvb", "wmv", "flv", "mov", "m4v",
    "srt", "ass", "ssa", "sub", "sup", "idx", "mp3", "flac", "aac",
    "wav", "m4a", "ogg", "wma", "nfo", "jpg", "jpeg", "png",
})
_AUTO = object()
_SYSTEM_TREES = ("/proc", "/sys", "/dev", "/run", "/etc", "/usr", "/bin",
                 "/sbin", "/lib", "/lib64", "/boot", "/root", "/var/run",
                 "/var/lock", "/var/cache", "/var/log", "/var/lib/docker",
                 "/var/lib/containerd")
_SYSTEM_ROOTS = {"/", "/tmp", "/var", "/opt"}
_SYSTEM_FS = {"rootfs", "overlay", "proc", "sysfs", "devtmpfs", "devpts",
              "tmpfs", "cgroup", "cgroup2", "securityfs", "pstore", "debugfs",
              "tracefs", "mqueue", "hugetlbfs", "fusectl", "autofs", "ramfs"}
_FALLBACKS = ("/media", "/mnt", "/downloads", "/data", "/volume1",
              "/movie", "/tv", "/music", "/video", "/nas")


def _under(path, root):
    return os.path.commonpath((path, root)) == root


def _absolute(path):
    try:
        value = os.fspath(path)
    except TypeError as exc:
        raise ValueError("路径必须为绝对路径字符串") from exc
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError("路径不能为空或包含 NUL")
    if not os.path.isabs(value) or ".." in value.split("/"):
        raise ValueError("路径必须为绝对路径，且不能包含 '..'")
    return os.path.normpath(value)


def _canonical(path):
    value = _absolute(path)
    # Reject every symlink component, not just the last component. This also
    # rejects links between two otherwise allowed roots and symlink loops.
    current = "/"
    for part in value.split("/"):
        if part:
            current = os.path.join(current, part)
            if stat.S_ISLNK(os.lstat(current).st_mode):
                raise ValueError("不允许符号链接路径：{}".format(value))
    return os.path.realpath(value)


def _reasonable(path):
    return path not in _SYSTEM_ROOTS and not any(_under(path, p) for p in _SYSTEM_TREES)


def _readable(path, info):
    directory = stat.S_ISDIR(info.st_mode)
    if not directory and not stat.S_ISREG(info.st_mode):
        raise ValueError("仅支持目录和常规文件：{}".format(path))
    mask = os.R_OK | (os.X_OK if directory else 0)
    if (not info.st_mode & 0o444 or (directory and not info.st_mode & 0o111)
            or not os.access(path, mask)):
        raise PermissionError("路径不可读或不可进入：{}".format(path))


def _prune(roots):
    result = []
    for root in sorted(roots, key=lambda r: (r["path"].count("/"), r["path"].casefold(), r["path"])):
        if not any(_under(root["path"], old["path"]) for old in result):
            result.append(root)
    return sorted(result, key=lambda r: (r["path"].casefold(), r["path"]))


def _field(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


def _local(value):
    return str(getattr(value, "value", value)).strip().casefold() == "local"


def _items(value):
    if value is None:
        return []
    if isinstance(value, (str, os.PathLike, Mapping)) or not hasattr(value, "__iter__"):
        return [value]
    return value


def _unescape(value):
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)


def discover_roots(config=None, *, directory_helper=_AUTO, settings=_AUTO,
                   mountinfo_path="/proc/self/mountinfo", mounts_path="/proc/mounts",
                   fallback_paths=None):
    """Discover only configured/mounted roots, using stat but never scandir.

    Keyword dependencies are optional test seams. directory_helper=None and
    settings=None disable host imports; mount paths may be None. Config contributes local_paths
    (saved directories or parents of saved files). Commas are NEVER separators.
    """
    roots, warnings = [], []

    def add(value, source, saved=False):
        if not value:
            return
        try:
            path = _canonical(value)
            info = os.stat(path)
            if saved and stat.S_ISREG(info.st_mode):
                path = os.path.dirname(path)
                info = os.stat(path)
            if not _reasonable(path) or not stat.S_ISDIR(info.st_mode):
                return
            _readable(path, info)
            roots.append({"path": path, "name": os.path.basename(path), "source": source})
        except (OSError, ValueError, TypeError) as exc:
            warnings.append("{}：{}".format(source, exc))

    if directory_helper is _AUTO:
        try:
            from app.helper.directory import DirectoryHelper
            directory_helper = DirectoryHelper()
        except Exception as exc:
            warnings.append("DirectoryHelper 不可用：{}".format(exc))
            directory_helper = None
    for method, only in (("get_dirs", None), ("get_local_download_dirs", "download"),
                         ("get_local_library_dirs", "library")):
        fn = getattr(directory_helper, method, None)
        if fn is None:
            continue
        try:
            for item in _items(fn()):
                if isinstance(item, (str, os.PathLike)):
                    add(item, "moviepilot:" + (only or "directory"))
                    continue
                for kind, storage in (("download", "storage"), ("library", "library_storage")):
                    if only is not None and only != kind:
                        continue
                    # Local helper methods guarantee local storage when the
                    # field is absent; get_dirs must explicitly mark it local.
                    default = "local" if only else None
                    if _local(_field(item, storage, default)):
                        add(_field(item, kind + "_path"), "moviepilot:" + kind)
                if _field(item, "path") and _local(_field(item, "storage", "local")):
                    add(_field(item, "path"), "moviepilot:directory")
        except Exception as exc:
            warnings.append("DirectoryHelper.{}：{}".format(method, exc))

    if not roots:
        if settings is _AUTO:
            try:
                from app.core.config import settings
            except Exception as exc:
                warnings.append("MoviePilot settings 不可用：{}".format(exc))
                settings = None
        if settings is not None:
            for key in ("LIBRARY_PATH", "DOWNLOAD_PATH", "MEDIA_PATH",
                        "TRANSFER_PATH", "library_path", "download_path"):
                for value in _items(_field(settings, key)):
                    add(value, "moviepilot:settings")

    parsed = False
    for filename, is_info in ((mountinfo_path, True), (mounts_path, False)):
        if not filename or (not is_info and parsed):
            continue
        try:
            with open(filename, encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    fields = line.split()
                    if is_info:
                        if "-" not in fields:
                            continue
                        split = fields.index("-")
                        if split < 6 or len(fields) < split + 4:
                            continue
                        dest, fs = fields[4], fields[split + 1]
                    else:
                        if len(fields) < 3:
                            continue
                        dest, fs = fields[1], fields[2]
                    parsed = True
                    if fs not in _SYSTEM_FS:
                        # Only mount destination; never host source or fs root.
                        add(_unescape(dest), "docker:mountinfo" if is_info else "docker:mounts")
        except OSError as exc:
            warnings.append("挂载表读取失败 {}：{}".format(filename, exc))

    saved_paths = _field(config or {}, "local_paths", [])
    # Only a scalar legacy value is newline-separated. Lists preserve literal
    # filenames exactly (including newline characters decoded from mountinfo).
    if isinstance(saved_paths, str):
        saved_paths = [p for p in saved_paths.splitlines() if p]
    for saved in _items(saved_paths):
        add(saved, "saved", saved=True)
    if not roots:
        for path in (_FALLBACKS if fallback_paths is None else fallback_paths):
            # Missing fallback paths are normal, not user-facing errors.
            if os.path.isdir(path):
                add(path, "fallback")
    return {"roots": _prune(roots), "warnings": warnings}


class LocalFiles:
    """Allowlisted, read-only browser and bounded filename search.

    None extensions uses media/sidecar defaults; an empty set shows directories
    only. Explicit collect(file) accepts any regular file. Pagination limit is
    1..1000. Search limits are constructor-injectable for deterministic tests.
    """

    def __init__(self, roots, extensions=None, *, max_scanned=10000,
                 max_matches=500, search_timeout=3.0, max_files=100000, clock=None):
        checked = []
        for root in roots:
            raw = _field(root, "path") if isinstance(root, Mapping) else root
            path = _canonical(raw)
            if not _reasonable(path):
                raise ValueError("不允许系统目录作为文件根：{}".format(path))
            info = os.stat(path)
            if not stat.S_ISDIR(info.st_mode):
                raise NotADirectoryError(path)
            _readable(path, info)
            checked.append({"path": path, "name": _field(root, "name") or os.path.basename(path),
                            "source": _field(root, "source", "configured")})
        self.roots = _prune(checked)
        self.extensions = {str(e).casefold().lstrip(".") for e in
                           (DEFAULT_EXTENSIONS if extensions is None else extensions)}
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1
               for v in (max_scanned, max_matches, max_files)):
            raise ValueError("扫描数量限制必须为正整数")
        if (isinstance(search_timeout, bool) or not isinstance(search_timeout, (int, float))
                or not 0 < search_timeout < float("inf")):
            raise ValueError("扫描时间限制必须为有限正数")
        self.max_scanned, self.max_matches = max_scanned, max_matches
        self.search_timeout, self.max_files = search_timeout, max_files
        self.clock = clock or time.monotonic

    def validate(self, path, directory=None):
        """Return a canonical allowed path; reject symlinks/special/unreadable files."""
        if directory is not None and not isinstance(directory, bool):
            raise ValueError("directory 必须是布尔值或 None")
        lexical = _absolute(path)
        if not any(_under(lexical, r["path"]) for r in self.roots):
            raise ValueError("路径不在允许的根目录下：{}".format(lexical))
        canonical = _canonical(lexical)
        if not any(_under(canonical, r["path"]) for r in self.roots):
            raise ValueError("路径解析后越出根目录：{}".format(lexical))
        info = os.stat(canonical)
        _readable(canonical, info)
        if directory is True and not stat.S_ISDIR(info.st_mode):
            raise NotADirectoryError(canonical)
        if directory is False and not stat.S_ISREG(info.st_mode):
            raise IsADirectoryError(canonical)
        return canonical

    def _parent(self, path):
        if not path or any(path == r["path"] for r in self.roots):
            return ""
        parent = os.path.dirname(path)
        return parent if any(_under(parent, r["path"]) for r in self.roots) else ""

    @staticmethod
    def _page(path, entries, offset, limit, warnings):
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset 必须是非负整数")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit 必须为 1..1000")
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].casefold(), e["name"], e["path"]))
        return {"path": path, "entries": entries[offset:offset + limit], "total": len(entries),
                "offset": offset, "limit": limit, "has_more": offset + limit < len(entries),
                "truncated": False, "warnings": warnings}

    @staticmethod
    def _warn(warnings, error):
        if len(warnings) < 100:
            warnings.append(str(error))
        elif len(warnings) == 100:
            warnings.append("更多权限/路径错误已省略")

    def _root_entries(self):
        return [{"path": r["path"], "name": r["name"], "is_dir": True,
                 "size": 0, "selectable": True} for r in self.roots]

    def _entry(self, entry):
        if entry.name.startswith(".") or entry.is_symlink():
            return None
        info = entry.stat(follow_symlinks=False)
        is_dir = stat.S_ISDIR(info.st_mode)
        if not is_dir and (not stat.S_ISREG(info.st_mode)
                           or os.path.splitext(entry.name)[1][1:].casefold() not in self.extensions):
            return None
        path = self.validate(entry.path)
        return {"path": path, "name": entry.name, "is_dir": is_dir,
                "size": 0 if is_dir else info.st_size, "selectable": True}

    def list(self, path="", offset=0, limit=100):
        # Validate pagination before touching the filesystem.
        self._page("", [], offset, limit, [])
        warnings, entries = [], []
        if path == "":
            canonical, entries = "", self._root_entries()
        else:
            canonical = self.validate(path, directory=True)
            with os.scandir(canonical) as stream:
                for item in stream:
                    try:
                        entry = self._entry(item)
                        if entry:
                            entries.append(entry)
                    except (OSError, ValueError) as exc:
                        self._warn(warnings, exc)
        result = self._page(canonical, entries, offset, limit, warnings)
        result["parent"] = self._parent(canonical)
        result["truncated"] = bool(warnings)
        return result

    def search(self, path="", query="", recursive=False, offset=0, limit=100):
        """Search filenames only. Empty virtual root never implies recursion.

        Limits are cooperative metadata-operation budgets: one blocked OS call
        cannot be interrupted. total is the matches retained, NOT an estimated
        full-tree count; truncated/message disclose every early stop. Sorting
        is stable for the retained set, without reading beyond the node cap.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("搜索词不能为空；不会执行无条件递归扫描")
        if not isinstance(recursive, bool):
            raise ValueError("recursive 必须是布尔值")
        self._page("", [], offset, limit, [])
        canonical = "" if path == "" else self.validate(path, directory=True)
        needle = query.casefold()
        entries, warnings, reasons = [], [], []
        scanned, deadline = 0, self.clock() + self.search_timeout

        def budget():
            if reasons:
                return True
            if scanned >= self.max_scanned:
                reasons.append("达到扫描节点上限 {}".format(self.max_scanned))
            elif len(entries) >= self.max_matches:
                reasons.append("达到匹配上限 {}".format(self.max_matches))
            elif self.clock() >= deadline:
                reasons.append("达到搜索时间上限 {} 秒".format(self.search_timeout))
            return bool(reasons)

        if not canonical and not recursive:
            for entry in self._root_entries():
                if budget():
                    break
                scanned += 1
                if needle in entry["name"].casefold():
                    entries.append(entry)
        else:
            pending = [canonical] if canonical else [r["path"] for r in reversed(self.roots)]
            seen = set()
            while pending and not budget():
                current = pending.pop()
                children = []
                try:
                    self.validate(current, directory=True)
                    info = os.stat(current)
                    identity = (info.st_dev, info.st_ino)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    with os.scandir(current) as stream:
                        while not budget():
                            try:
                                item = next(stream)
                            except StopIteration:
                                break
                            scanned += 1
                            try:
                                entry = self._entry(item)
                                if not entry:
                                    continue
                                if needle in entry["name"].casefold():
                                    entries.append(entry)
                                if recursive and entry["is_dir"]:
                                    children.append(entry["path"])
                            except (OSError, ValueError) as exc:
                                self._warn(warnings, exc)
                    pending.extend(sorted(children, reverse=True))
                except (OSError, ValueError) as exc:
                    self._warn(warnings, exc)
        # Even when the last matching entry hits the cap, conservatively state
        # the bound; a bounded response must never advertise exhaustive results.
        if not reasons:
            budget()
        if warnings:
            reasons.append("部分目录或条目不可读取，见 warnings")
        result = self._page(canonical, entries, offset, limit, warnings)
        result.update(parent=self._parent(canonical), scanned=scanned,
                      truncated=bool(reasons),
                      message=("结果不完整：" + "；".join(reasons)) if reasons else "搜索完成")
        return result

    @staticmethod
    def _selection_labels(directories):
        # Preserve basename normally. If two independent selections have the
        # same basename, include just enough ancestor names to disambiguate.
        parts = {path: path.strip("/").split("/") for path in directories}
        depth = {path: 1 for path in directories}
        while True:
            labels = {p: "/".join(parts[p][-depth[p]:]) for p in directories}
            conflicts = set()
            ordered = sorted(labels)
            for index, first in enumerate(ordered):
                a = labels[first].casefold()
                for second in ordered[index + 1:]:
                    b = labels[second].casefold()
                    if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                        conflicts.update((first, second))
            if not conflicts:
                return labels
            changed = False
            for path in conflicts:
                if depth[path] < len(parts[path]):
                    depth[path] += 1
                    changed = True
            if not changed:
                # Distinct POSIX selections differing only by case need
                # distinct namespaces even on case-insensitive remote storage.
                # Use unique leading folders so no label is another's prefix.
                for index, path in enumerate(sorted(directories), 1):
                    labels[path] = "selection-{:04d}/{}".format(index, parts[path][-1])
                return labels

    def collect(self, paths, preserve_structure=True, cancelled=None):
        """Strict background-only collection; never read contents or calculate hashes.

        Explicit invalid/unreadable inputs, unreadable directories and matching
        unreadable files raise; there is no partial-success return. Hidden/
        symlink descendants are skipped. Explicit regular files (including
        hidden/non-media) are accepted. Deduplication uses canonical paths,
        never basenames. Separate directory selections receive unique prefixes;
        standalone files always have relative_dir='', so the uploader owns any
        same-filename policy. preserve_structure=False deliberately flattens.
        """
        if not isinstance(paths, (list, tuple)):
            raise ValueError("paths 必须为路径列表")
        if not isinstance(preserve_structure, bool):
            raise ValueError("preserve_structure 必须为布尔值")

        def check_cancel():
            if cancelled is not None and cancelled():
                raise InterruptedError("文件收集已取消")

        directories, explicit = [], set()
        for raw in paths:
            check_cancel()
            path = self.validate(raw)
            if os.path.isdir(path):
                directories.append({"path": path})
            else:
                explicit.add(path)
        directories = [r["path"] for r in _prune(directories)]
        labels = self._selection_labels(directories) if preserve_structure else {}
        collected = {}

        def include(path, selected=None):
            if path in collected:
                return
            check_cancel()
            self.validate(path, directory=False)
            if len(collected) >= self.max_files:
                raise ValueError("文件收集超过上限 {}，请缩小选择范围".format(self.max_files))
            relative = ""
            if preserve_structure and selected is not None:
                subdir = os.path.relpath(os.path.dirname(path), selected)
                relative = labels[selected] if subdir == "." else labels[selected] + "/" + subdir
            collected[path] = {"path": path, "relative_dir": relative}

        for selected in directories:
            pending, seen = [selected], set()
            while pending:
                check_cancel()
                current = self.validate(pending.pop(), directory=True)
                info = os.stat(current)
                identity = (info.st_dev, info.st_ino)
                if identity in seen:
                    continue
                seen.add(identity)
                children = []
                with os.scandir(current) as stream:
                    for item in stream:
                        check_cancel()
                        if item.name.startswith(".") or item.is_symlink():
                            continue
                        info = item.stat(follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            children.append(self.validate(item.path, directory=True))
                        elif stat.S_ISREG(info.st_mode):
                            if (os.path.splitext(item.name)[1][1:].casefold() in self.extensions
                                    or item.path in explicit):
                                include(item.path, selected)
                pending.extend(sorted(children, reverse=True))
        for path in sorted(explicit):
            check_cancel()
            owner = next((d for d in directories if _under(path, d)), None)
            include(path, owner)
        check_cancel()
        if not collected:
            raise ValueError("没有匹配的可上传文件（no matches），请检查选择及扩展名")
        return sorted(collected.values(), key=lambda x: (x["relative_dir"].casefold(),
                                                         x["relative_dir"], x["path"]))
