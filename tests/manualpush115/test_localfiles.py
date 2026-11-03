"""Standalone tests: importing localfiles must not import the MoviePilot host."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "plugins.v2/manualpush115/localfiles.py"
SPEC = importlib.util.spec_from_file_location("manual115_localfiles_test", MODULE_PATH)
lf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lf)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(lf, "time", SimpleNamespace(monotonic=lambda: 0.0))


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "媒体 根, &"
    season = root / "Show" / "Season 1"
    season.mkdir(parents=True)
    (root / "电影, 中文 &.MKV").write_bytes(b"movie")
    (root / "a.mp4").write_bytes(b"a")
    (root / "z.txt").write_text("sidecar")
    (root / ".hidden.mkv").write_bytes(b"hidden")
    (root / ".hidden-dir").mkdir()
    (root / ".hidden-dir" / "secret.mkv").write_bytes(b"secret")
    (season / "EP 01.mkv").write_bytes(b"episode")
    (season / "EP 02.srt").write_bytes(b"subtitle")
    return root


def discovery(config=None, **kwargs):
    args = dict(directory_helper=None, settings=None, mountinfo_path=None, mounts_path=None, fallback_paths=[])
    args.update(kwargs)
    return lf.discover_roots(config, **args)


def never_scandir(*args, **kwargs):
    raise AssertionError("root discovery/virtual root must not scandir")


def test_virtual_root_does_not_scan(tree, monkeypatch):
    monkeypatch.setattr(lf.os, "scandir", never_scandir)
    result = discovery({"local_paths": [str(tree), str(tree / "Show")]})
    assert result["warnings"] == []
    assert result["roots"] == [{"path": str(tree), "name": tree.name, "source": "saved"}]
    files = lf.LocalFiles(result["roots"])
    page = files.list()
    assert page["path"] == page["parent"] == ""
    assert page["total"] == 1 and not page["has_more"]
    assert page["entries"] == [{"path": str(tree), "name": tree.name, "is_dir": True,
                                "size": 0, "selectable": True}]
    assert files.search(query="媒体")["entries"] == page["entries"]


def test_list_one_layer_only(tree, monkeypatch):
    calls, real = [], os.scandir

    def scan(path):
        calls.append(path)
        assert path == str(tree)
        return real(path)

    monkeypatch.setattr(lf.os, "scandir", scan)
    page = lf.LocalFiles([tree]).list(str(tree))
    assert calls == [str(tree)]
    assert [e["name"] for e in page["entries"]] == ["Show", "a.mp4", "电影, 中文 &.MKV"]
    assert page["parent"] == "" and page["total"] == 3
    assert page["entries"][-1]["size"] == 5
    assert all(e["selectable"] for e in page["entries"])


def test_parent_and_pagination(tree):
    files = lf.LocalFiles([tree, tree / "Show"])
    assert len(files.roots) == 1
    assert files.list(tree)["parent"] == ""
    assert files.list(tree / "Show")["parent"] == str(tree)
    assert files.list(tree / "Show/Season 1")["parent"] == str(tree / "Show")
    first = files.list(tree, offset=0, limit=1)
    second = files.list(tree, offset=1, limit=1)
    assert first["total"] == second["total"] == 3
    assert first["has_more"] and second["has_more"]
    assert first["entries"][0]["name"] == "Show"
    assert second["entries"][0]["name"] == "a.mp4"
    assert files.list(tree, offset=99)["entries"] == []
    assert not files.list(tree, offset=99)["has_more"]


@pytest.mark.parametrize("offset,limit", [(-1, 1), (0, 0), (0, 1001), (True, 1), (0, "1")])
def test_bad_pagination_never_scans(tree, monkeypatch, offset, limit):
    files = lf.LocalFiles([tree])
    monkeypatch.setattr(lf.os, "scandir", never_scandir)
    with pytest.raises(ValueError):
        files.list(tree, offset, limit)
    with pytest.raises(ValueError):
        files.search(tree, "movie", offset=offset, limit=limit)


def test_extension_filter_explicit_files(tree):
    files = lf.LocalFiles([tree], extensions={".MKV"})
    assert [e["name"] for e in files.list(tree)["entries"]] == ["Show", "电影, 中文 &.MKV"]
    assert lf.LocalFiles([tree], extensions=set()).list(tree)["total"] == 1
    assert files.validate(tree / "z.txt", directory=False) == str(tree / "z.txt")
    assert files.collect([str(tree / "z.txt")]) == [{"path": str(tree / "z.txt"), "relative_dir": ""}]
    with pytest.raises(NotADirectoryError):
        files.list(tree / "a.mp4")
    with pytest.raises(IsADirectoryError):
        files.validate(tree, directory=False)


def test_prefix_similar_directory_is_not_allowed(tree):
    outside = tree.with_name(tree.name + "-outside")
    outside.mkdir()
    secret = outside / "secret.mkv"
    secret.write_bytes(b"not allowed")
    files = lf.LocalFiles([tree])
    for path in [outside, secret, "/", tree / "..", "relative.mkv", "", "bad\0path"]:
        with pytest.raises(ValueError):
            files.validate(path)
    with pytest.raises(ValueError):
        files.search(outside, "secret", recursive=True)
    with pytest.raises(ValueError):
        files.collect([str(secret)])
    with pytest.raises(FileNotFoundError):
        files.validate(tree / "missing")


def test_symlink_escape_loop_and_internal_link(tree, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.mkv").write_bytes(b"secret")
    (tree / "external").symlink_to(outside, target_is_directory=True)
    (tree / "loop").symlink_to(tree, target_is_directory=True)
    (tree / "internal").symlink_to(tree / "Show", target_is_directory=True)
    (tree / "linked.mkv").symlink_to(outside / "secret.mkv")
    files = lf.LocalFiles([tree, outside])
    for target in ["external", "external/secret.mkv", "loop", "loop/loop", "internal", "linked.mkv"]:
        with pytest.raises(ValueError):
            files.validate(tree / target)
        with pytest.raises(ValueError):
            files.collect([str(tree / target)])
    assert files.search(tree, "secret", recursive=True)["total"] == 0
    assert {e["name"] for e in files.list(tree)["entries"]} == {"Show", "a.mp4", "电影, 中文 &.MKV"}
    result = files.collect([str(tree)])
    assert len(result) == 4
    assert all("secret" not in e["path"] for e in result)


def test_special_file_rejected(tree):
    fifo = tree / "pipe.mkv"
    os.mkfifo(fifo)
    files = lf.LocalFiles([tree])
    with pytest.raises(ValueError):
        files.validate(fifo)
    with pytest.raises(ValueError):
        files.collect([str(fifo)])
    assert "pipe.mkv" not in [e["name"] for e in files.list(tree)["entries"]]


def test_directory_helper_storage_is_independent(tree, tmp_path, monkeypatch):
    download = tmp_path / "download"
    download.mkdir()
    remote = tmp_path / "remote"
    remote.mkdir()
    extra = tmp_path / "extra"
    extra.mkdir()

    class Helper:
        def get_dirs(self):
            return [dict(storage="local", download_path=download, library_storage="115", library_path=remote),
                    SimpleNamespace(storage="115", download_path=remote, library_storage="local", library_path=tree)]

        def get_local_download_dirs(self):
            return [SimpleNamespace(download_path=download), extra]

        def get_local_library_dirs(self):
            return [{"library_path": tree}, {"library_storage": "115", "library_path": remote}]

    monkeypatch.setattr(lf.os, "scandir", never_scandir)
    result = discovery(directory_helper=Helper())
    assert {r["path"] for r in result["roots"]} == {str(download), str(tree), str(extra)}
    assert not result["warnings"]
    assert next(r for r in result["roots"] if r["path"] == str(tree))["source"] == "moviepilot:library"


def escape_mount(path):
    return str(path).replace("\\", "\\134").replace(" ", "\\040").replace("\t", "\\011").replace("\n", "\\012")


def test_mountinfo_dest_escapes_system_and_file_mounts(tmp_path, monkeypatch):
    dest = tmp_path / "container 空格, &\t\n\\x"
    dest.mkdir()
    source = tmp_path / "host-private-source"
    source.mkdir()
    single = tmp_path / "resolv.conf"
    single.write_text("nameserver")
    table = tmp_path / "mountinfo"
    table.write_text(
        "1 0 0:1 / / rw - overlay overlay rw\n"
        "2 1 0:2 / /proc rw - proc proc rw\n"
        "3 1 0:3 / /sys rw - sysfs sysfs rw\n"
        "4 1 0:4 / /dev rw - tmpfs tmpfs rw\n"
        "5 1 0:5 / /etc rw - ext4 /dev/sda rw\n"
        "6 1 0:6 {} {} rw shared:10 - ext4 {} rw\n".format(escape_mount(source), escape_mount(dest), escape_mount(source))
        + "7 1 0:7 / {} rw - ext4 /host/resolv.conf rw\n".format(escape_mount(single))
        + "8 1 0:8 / /root rw - ext4 /dev/sda rw\n"
    )
    monkeypatch.setattr(lf.os, "scandir", never_scandir)
    result = discovery(mountinfo_path=table)
    assert result["roots"] == [{"path": str(dest), "name": dest.name, "source": "docker:mountinfo"}]
    assert str(source) not in [r["path"] for r in result["roots"]]
    assert not result["warnings"]


@pytest.mark.parametrize("mountinfo", ["missing", "malformed"])
def test_mounts_fallback(tree, tmp_path, mountinfo):
    table = tmp_path / "mountinfo"
    if mountinfo == "malformed":
        table.write_text("bad line\n1 - wrong\n")
    mounts = tmp_path / "mounts"
    mounts.write_text("overlay / overlay rw 0 0\n/host/source {} ext4 rw 0 0\n".format(escape_mount(tree)))
    result = discovery(mountinfo_path=table, mounts_path=mounts)
    assert [r["path"] for r in result["roots"]] == [str(tree)]
    assert result["roots"][0]["source"] == "docker:mounts"
    assert bool(result["warnings"]) == (mountinfo == "missing")


def test_common_fallback_only_when_no_roots_and_saved_file_parent(tree, tmp_path):
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    result = discovery({"local_paths": [tree / "a.mp4"]}, fallback_paths=[fallback])
    assert [r["path"] for r in result["roots"]] == [str(tree)]
    assert result["roots"][0]["source"] == "saved"
    result = discovery(fallback_paths=[fallback])
    assert result["roots"][0]["source"] == "fallback"
    assert discovery({"local_paths": ["/", "/etc", "/proc", "/root"]})["roots"] == []
    assert discovery({"local_paths": str(tree)})["roots"][0]["path"] == str(tree)


def test_discovery_error_warns_and_continues(tree):
    class Helper:
        def get_dirs(self):
            raise RuntimeError("no host db")

        def get_local_library_dirs(self):
            return [tree]

    result = discovery(directory_helper=Helper())
    assert [r["path"] for r in result["roots"]] == [str(tree)]
    assert "no host db" in result["warnings"][0]


@pytest.mark.parametrize("query", ["", " ", "\t", None])
def test_empty_search_never_scans(tree, monkeypatch, query):
    files = lf.LocalFiles([tree])
    monkeypatch.setattr(lf.os, "scandir", never_scandir)
    with pytest.raises(ValueError):
        files.search(query=query, recursive=True)


def test_search_explicit_recursion_filename_only_casefold(tree, monkeypatch):
    files = lf.LocalFiles([tree])
    real, calls = os.scandir, []

    def scan(path):
        calls.append(str(path))
        return real(path)

    monkeypatch.setattr(lf.os, "scandir", scan)
    assert files.search(tree, "EP")["entries"] == []
    assert calls == [str(tree)]
    calls.clear()
    result = files.search(query="eP", recursive=True)
    assert [e["name"] for e in result["entries"]] == ["EP 01.mkv", "EP 02.srt"]
    assert not result["truncated"] and result["message"] == "搜索完成"
    assert set(calls) == {str(tree), str(tree / "Show"), str(tree / "Show/Season 1")}
    assert files.search(tree, "媒体", recursive=True)["total"] == 0
    assert files.search(tree, "secret", recursive=True)["total"] == 0
    assert files.search(tree, "中文 &")["total"] == 1
    assert files.search(query="eP")["total"] == 0
    with pytest.raises(ValueError):
        files.search(query="ep", recursive="false")


def test_search_stable_sort_and_pagination(tree):
    files = lf.LocalFiles([tree])
    full = files.search(tree, "EP", recursive=True)
    first = files.search(tree, "EP", recursive=True, limit=1)
    second = files.search(tree, "EP", recursive=True, offset=1, limit=1)
    assert first["entries"] + second["entries"] == full["entries"]
    assert first["has_more"] and not second["has_more"]
    assert first["total"] == second["total"] == 2


def test_search_limits(tree):
    scan_limit = lf.LocalFiles([tree], max_scanned=2).search(tree, "absent", recursive=True)
    assert scan_limit["scanned"] == 2
    assert scan_limit["truncated"] and "扫描节点上限 2" in scan_limit["message"]
    match_limit = lf.LocalFiles([tree], max_matches=1).search(tree, "EP", recursive=True)
    assert match_limit["total"] == 1 and match_limit["truncated"]
    assert "匹配上限 1" in match_limit["message"]
    ticks = iter([0.0, 4.0, 5.0])
    timeout = lf.LocalFiles([tree], clock=lambda: next(ticks)).search(tree, "EP", recursive=True)
    assert timeout["scanned"] == 0 and timeout["truncated"]
    assert "时间上限 3.0" in timeout["message"]


def test_permission_list_reject_search_warn_collect_reject(tree, monkeypatch):
    blocked = tree / "Show"
    real = os.scandir

    def scan(path):
        if str(path) == str(blocked):
            raise PermissionError("permission denied: " + str(path))
        return real(path)

    monkeypatch.setattr(lf.os, "scandir", scan)
    files = lf.LocalFiles([tree])
    with pytest.raises(PermissionError):
        files.list(blocked)
    result = files.search(tree, "EP", recursive=True)
    assert result["truncated"] and result["warnings"]
    assert "permission denied" in result["warnings"][0]
    with pytest.raises(PermissionError):
        files.collect([str(tree)])


def test_unreadable_file_reject_even_when_process_is_root(tree):
    path = tree / "unreadable.mkv"
    path.write_bytes(b"x")
    path.chmod(0)
    try:
        files = lf.LocalFiles([tree])
        with pytest.raises(PermissionError):
            files.collect([str(path)])
        with pytest.raises(PermissionError):
            files.collect([str(tree)])
        assert files.search(tree, "unreadable")["warnings"]
        assert files.list(tree)["warnings"]
    finally:
        path.chmod(0o600)


def test_collect_structure_overlap_dedup_and_explicit_nonmedia(tree):
    files = lf.LocalFiles([tree])
    season = tree / "Show/Season 1"
    episode = season / "EP 01.mkv"
    result = files.collect([str(episode), str(season), str(tree / "Show"), str(tree / "Show"), str(tree / "z.txt")])
    by_path = {r["path"]: r["relative_dir"] for r in result}
    assert len(by_path) == len(result) == 3
    assert by_path[str(episode)] == "Show/Season 1"
    assert by_path[str(season / "EP 02.srt")] == "Show/Season 1"
    assert by_path[str(tree / "z.txt")] == ""
    assert files.collect([str(episode), str(episode)]) == [{"path": str(episode), "relative_dir": ""}]
    mixed = files.collect([str(tree), str(tree / "z.txt")])
    assert next(r for r in mixed if r["path"].endswith("z.txt"))["relative_dir"] == tree.name
    flat = files.collect([str(tree)], preserve_structure=False)
    assert len(flat) == 4 and all(r["relative_dir"] == "" for r in flat)
    with pytest.raises(ValueError, match="no matches"):
        files.collect([])


def test_collect_equal_names_from_different_locations_do_not_collide(tmp_path):
    root = tmp_path / "media"
    first = root / "one/Show"
    second = root / "two/Show"
    for folder in [first, second]:
        folder.mkdir(parents=True)
        (folder / "same.mkv").write_bytes(b"x")
    files = lf.LocalFiles([root])
    result = files.collect([str(second), str(first)])
    assert {r["relative_dir"] for r in result} == {"one/Show", "two/Show"}
    assert result == files.collect([str(first), str(second)])
    assert len({r["path"] for r in result}) == 2


def test_collect_limits_invalid_input_and_cancel(tree):
    files = lf.LocalFiles([tree], max_files=1)
    with pytest.raises(ValueError, match="超过上限 1"):
        files.collect([str(tree)])
    assert len(files.collect([str(tree / "a.mp4")])) == 1
    with pytest.raises(ValueError):
        files.collect(str(tree))
    with pytest.raises(FileNotFoundError):
        files.collect([str(tree / "a.mp4"), str(tree / "missing")])
    with pytest.raises(InterruptedError):
        files.collect([str(tree)], cancelled=lambda: True)
    count = 0

    def cancel_later():
        nonlocal count
        count += 1
        return count >= 5

    with pytest.raises(InterruptedError):
        lf.LocalFiles([tree]).collect([str(tree)], cancelled=cancel_later)


def test_collect_reads_metadata_only(tree, monkeypatch):
    files = lf.LocalFiles([tree])

    def no_open(*args, **kwargs):
        raise AssertionError("collect must never read file contents")

    monkeypatch.setattr("builtins.open", no_open)
    assert len(files.collect([str(tree)])) == 4


def test_replaced_directory_with_symlink_after_constructor(tree, tmp_path):
    allowed = tree / "Show"
    files = lf.LocalFiles([allowed])
    renamed = tree / "original"
    allowed.rename(renamed)
    allowed.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        files.list(allowed)
    with pytest.raises(ValueError):
        files.collect([str(allowed)])


def test_normalization_preserves_case_spaces_commas_ampersands(tree):
    files = lf.LocalFiles([tree])
    raw = str(tree) + "/./电影, 中文 &.MKV"
    assert files.validate(raw) == str(tree / "电影, 中文 &.MKV")
    assert files.collect([raw])[0]["path"] == str(tree / "电影, 中文 &.MKV")
    result = discovery({"local_paths": [str(tree / "电影, 中文 &.MKV")]})
    assert result["roots"][0]["path"] == str(tree)


@pytest.mark.parametrize("path", [None, False, 0])
def test_only_empty_string_means_virtual_root(tree, path):
    files = lf.LocalFiles([tree])
    with pytest.raises(ValueError):
        files.list(path)
    with pytest.raises(ValueError):
        files.search(path, "ep", recursive=True)


def test_mountinfo_success_does_not_read_legacy_mounts(tree, tmp_path):
    info = tmp_path / "mountinfo"
    info.write_text("1 0 0:1 / {} rw - ext4 /host/path rw\n".format(escape_mount(tree)))
    result = discovery(mountinfo_path=info, mounts_path=tmp_path / "missing-mounts")
    assert len(result["roots"]) == 1
    assert not result["warnings"]


def test_mount_sysfs_or_rootfs_at_nonstandard_dest_excluded(tree, tmp_path):
    info = tmp_path / "mountinfo"
    info.write_text("1 0 0:1 / {} rw - rootfs /source rw\n".format(escape_mount(tree)))
    assert discovery(mountinfo_path=info)["roots"] == []
    for path in ["/var/run", "/var/log", "/var/cache", "/var/lib/docker"]:
        assert not lf._reasonable(path)


def test_saved_paths_preserve_literal_newline_in_list(tmp_path):
    root = tmp_path / "space , &\nnext line"
    root.mkdir()
    assert discovery({"local_paths": [str(root)]})["roots"][0]["path"] == str(root)


def test_collect_deep_equal_names_disambiguates_prefix_conflicts(tmp_path):
    root = tmp_path / "media"
    selections = [root / "one/Show", root / "two/Show", root / "elsewhere/one"]
    for selection in selections:
        selection.mkdir(parents=True)
        (selection / "same.mkv").write_bytes(b"x")
    result = lf.LocalFiles([root]).collect([str(p) for p in selections])
    labels = [r["relative_dir"] for r in result]
    assert len(set(labels)) == 3
    assert all(not a.casefold().startswith(b.casefold() + "/") for a in labels for b in labels if a != b)


def test_collect_case_only_directory_names_do_not_collide(tmp_path):
    root = tmp_path / "media"
    selections = [root / "Show", root / "show"]
    for selection in selections:
        selection.mkdir(parents=True)
        (selection / "same.mkv").write_bytes(b"x")
    result = lf.LocalFiles([root]).collect([str(p) for p in selections])
    assert len(result) == 2
    assert len({r["relative_dir"].casefold() for r in result}) == 2


def test_collect_cancellation_checks_every_entry(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    for number in range(20):
        (root / (str(number) + ".txt")).write_text("ignored extension")
    count = 0

    def cancel():
        nonlocal count
        count += 1
        return count == 8

    with pytest.raises(InterruptedError):
        lf.LocalFiles([root]).collect([str(root)], cancelled=cancel)


@pytest.mark.parametrize("options", [{"max_scanned": 0}, {"max_matches": 0}, {"max_files": 0},
                                     {"search_timeout": 0}, {"search_timeout": float("nan")},
                                     {"search_timeout": float("inf")}, {"max_files": 1.2}])
def test_invalid_budgets(tree, options):
    with pytest.raises(ValueError):
        lf.LocalFiles([tree], **options)


def test_search_never_reads_past_node_budget(tree, monkeypatch):
    real = os.scandir
    fetched = 0

    class GuardedScan:
        def __init__(self, path):
            self.stream = real(path)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def __next__(self):
            nonlocal fetched
            fetched += 1
            assert fetched <= 2, "budget must be checked before scandir next()"
            return next(self.stream)

    monkeypatch.setattr(lf.os, "scandir", GuardedScan)
    result = lf.LocalFiles([tree], max_scanned=2).search(tree, "nothing", recursive=True)
    assert result["scanned"] == fetched == 2
    assert result["truncated"]


def test_default_production_budgets(tree):
    files = lf.LocalFiles([tree])
    assert (files.max_scanned, files.max_matches, files.search_timeout, files.max_files) == (10000, 500, 3.0, 100000)


def test_same_name_explicit_files_not_deduplicated_by_basename(tree):
    first = tree / "a.mp4"
    second = tree / "Show/a.mp4"
    second.write_bytes(b"other")
    result = lf.LocalFiles([tree]).collect([str(first), str(second)])
    assert len(result) == 2
    assert {r["path"] for r in result} == {str(first), str(second)}
    assert all(r["relative_dir"] == "" for r in result)


def test_settings_fallback_without_directory_helper(tree):
    result = discovery(settings=SimpleNamespace(DOWNLOAD_PATH=tree))
    assert result["roots"] == [{"path": str(tree), "name": tree.name, "source": "moviepilot:settings"}]
    assert not result["warnings"]


def test_directory_helper_import_failure_warns_without_sdk_import(tree, monkeypatch):
    import builtins
    real = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name != "app.sdk.services", "unverified V3 helper must not be imported"
        if name == "app.helper.directory":
            raise ImportError("host helper unavailable")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    result = discovery(directory_helper=lf._AUTO, settings={"DOWNLOAD_PATH": tree})
    assert result["roots"][0]["path"] == str(tree)
    assert "host helper unavailable" in result["warnings"][0]


def test_collect_directory_without_matches_is_not_success(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    files = lf.LocalFiles([root])
    with pytest.raises(ValueError, match="no matches"):
        files.collect([str(root)])
    (root / "readme.txt").write_text("not a default extension")
    with pytest.raises(ValueError, match="no matches"):
        files.collect([str(root)])
