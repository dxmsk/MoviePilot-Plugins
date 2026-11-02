"""Scanner/RetryQueue regressions; load by path, without MoviePilot imports."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[2] / "plugins.v2/cloudpush115/scanner.py"
SPEC = importlib.util.spec_from_file_location("cloudpush115_scanner_tested", SOURCE)
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)
MediaScanner, RetryQueue = scanner.MediaScanner, scanner.RetryQueue


class ScandirProbe:
    """Track laziness/cleanup and inject deterministic errors even when run as root."""
    def __init__(self, denied=(), bad_stat=(), broken=()):
        self.real = os.scandir
        self.denied, self.bad_stat, self.broken = map(set, (denied, bad_stat, broken))
        self.opened, self.closed, self.reads = [], [], []

    def __call__(self, path):
        path = os.fspath(path)
        if path in self.denied:
            raise PermissionError("directory denied")
        underlying, owner = self.real(path), self
        self.opened.append(path)

        class Handle:
            count = 0

            def __next__(self):
                if path in owner.broken and self.count:
                    raise PermissionError("iteration denied")
                entry = next(underlying)
                self.count += 1
                owner.reads.append(entry.path)

                def file_stat(*, follow_symlinks=True):
                    if entry.path in owner.bad_stat:
                        raise PermissionError("file stat denied")
                    return entry.stat(follow_symlinks=follow_symlinks)

                return SimpleNamespace(path=entry.path, stat=file_stat)

            def close(self):
                underlying.close()
                owner.closed.append(path)

        return Handle()


@pytest.fixture
def clock(monkeypatch):
    value = [100.0]
    monkeypatch.setattr(scanner.time, "time", lambda: value[0])
    return value


def test_default_extensions_remain_155():
    expected = ("mp4 mkv avi mov wmv flv ts m2ts iso rmvb webm mpg mpeg m4v vob 3gp "
                "strm srt ass ssa sub idx sup vtt mp3 flac aac m4a ape wav dts").split()
    assert scanner.DEFAULT_EXTENSIONS == expected
    assert MediaScanner([]).extensions == set(expected)


def test_overlap_roots_canonical_metadata_and_readonly(tmp_path, monkeypatch):
    root = tmp_path / "media"
    sub = root / "sub"
    sub.mkdir(parents=True)
    files = [root / "one.MKV", sub / "two.srt"]
    for path in files:
        path.write_bytes(b"unchanged")
    (root / "ignored.txt").write_text("not media")
    before = {str(p): p.stat() for p in files}
    monkeypatch.chdir(tmp_path)
    roots = ["media/sub", "media", "media/./sub", str(files[0]), "media", "", None]
    records = MediaScanner().iter_files(roots)
    assert isinstance(records, list)
    assert {r["path"] for r in records} == {str(p) for p in files}
    assert len(records) == 2
    for item in records:
        info = before[item["path"]]
        assert set(item) == {"path", "name", "size", "mtime", "mtime_ns", "inode"}
        assert item["name"] == Path(item["path"]).name
        assert item["size"] == info.st_size == 9
        assert item["mtime"] == info.st_mtime
        assert item["mtime_ns"] == info.st_mtime_ns
        assert item["inode"] == info.st_ino
        assert type(item["mtime"]) is float
        assert all(type(item[key]) is int for key in ("size", "mtime_ns", "inode"))
        assert Path(item["path"]).read_bytes() == b"unchanged"
        assert Path(item["path"]).stat().st_mtime_ns == info.st_mtime_ns


def test_extensions_single_file_and_modification_identity(tmp_path):
    file = tmp_path / "movie.MKV"
    file.write_bytes(b"one")
    scan = MediaScanner([" .MkV "])
    first = scan.iter_files([str(file)])[0]
    file.write_bytes(b"larger content")
    os.utime(file, ns=(first["mtime_ns"], first["mtime_ns"] + 1_000_000_000))
    second = scan.iter_files([str(file)])[0]
    assert first["path"] == second["path"]
    assert first["size"] != second["size"]
    assert first["mtime_ns"] != second["mtime_ns"]
    assert first["mtime"] != second["mtime"]
    replacement = tmp_path / "replacement"
    replacement.write_bytes(file.read_bytes())
    os.utime(replacement, ns=(second["mtime_ns"], second["mtime_ns"]))
    replacement.replace(file)
    third = scan.iter_files([str(file)])[0]
    assert third["size"] == second["size"]
    assert third["mtime_ns"] == second["mtime_ns"]
    assert third["inode"] != second["inode"]
    assert MediaScanner(["srt"]).iter_files([str(file)]) == []


def test_symlinks_cannot_escape_or_loop_but_explicit_roots_resolve(tmp_path):
    root, outside = tmp_path / "media", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    movie, secret = root / "movie.mkv", outside / "other.mkv"
    movie.touch()
    secret.touch()
    (root / "loop").symlink_to(root, target_is_directory=True)
    (root / "escape").symlink_to(outside, target_is_directory=True)
    (root / "escape.mkv").symlink_to(secret)
    (root / "broken.mkv").symlink_to(tmp_path / "missing")
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    records = MediaScanner().iter_files([str(root), str(alias)])
    assert [r["path"] for r in records] == [str(movie)]
    assert MediaScanner().iter_files([str(root / "escape.mkv")])[0]["path"] == str(secret)


def test_hardlink_paths_are_distinct(tmp_path):
    first, second = tmp_path / "a.mkv", tmp_path / "b.mkv"
    first.touch()
    os.link(first, second)
    records = MediaScanner().iter_files([str(tmp_path)])
    assert len(records) == 2
    assert records[0]["inode"] == records[1]["inode"]


def test_missing_roots_report_callback_and_default_logging(tmp_path, caplog):
    missing, valid = tmp_path / "missing", tmp_path / "ok.mkv"
    valid.touch()
    errors = []
    records = list(MediaScanner().walk_files([str(missing), str(valid)],
                                           on_error=lambda *args: errors.append(args)))
    assert [r["path"] for r in records] == [str(valid)]
    assert len(errors) == 1 and errors[0][0] == str(missing) and errors[0][1]
    assert MediaScanner().iter_files([str(missing)]) == []
    assert str(missing) in caplog.text


def test_permission_and_file_stat_errors_only_skip_affected_items(tmp_path, monkeypatch):
    denied = tmp_path / "denied"
    denied.mkdir()
    (denied / "private.mkv").touch()
    bad, good = tmp_path / "bad.mkv", tmp_path / "good.mkv"
    bad.touch()
    good.touch()
    probe = ScandirProbe(denied=[str(denied)], bad_stat=[str(bad)])
    monkeypatch.setattr(scanner.os, "scandir", probe)
    errors = []
    records = list(MediaScanner().walk_files([str(tmp_path)],
                                           on_error=lambda *args: errors.append(args)))
    assert [r["path"] for r in records] == [str(good)]
    assert {path for path, message in errors if message} == {str(denied), str(bad)}
    assert probe.closed == probe.opened


def test_directory_iterator_failure_is_reported_and_other_roots_continue(tmp_path, monkeypatch):
    root = tmp_path / "broken"
    root.mkdir()
    (root / "first.mkv").touch()
    other = tmp_path / "other.mkv"
    other.touch()
    probe = ScandirProbe(broken=[str(root)])
    monkeypatch.setattr(scanner.os, "scandir", probe)
    errors = []
    result = list(MediaScanner().walk_files([str(root), str(other)],
                                          on_error=lambda *args: errors.append(args)))
    assert len(result) == 2 and result[-1]["path"] == str(other)
    assert errors == [(str(root), "iteration denied")]
    assert probe.closed == probe.opened


def test_lazy_first_yield_and_generator_close(tmp_path, monkeypatch):
    for number in range(40):
        (tmp_path / f"{number}.mkv").touch()
    probe = ScandirProbe()
    monkeypatch.setattr(scanner.os, "scandir", probe)
    walk = MediaScanner().walk_files([str(tmp_path)])
    assert probe.opened == []
    assert next(walk)["name"].endswith(".mkv")
    assert len(probe.reads) == 1  # No list/scandir sort before first yield.
    walk.close()
    assert probe.closed == probe.opened


def test_cancel_in_deep_tree_before_any_media_yield(tmp_path, monkeypatch):
    leaf = tmp_path
    for _ in range(100):
        leaf /= "d"
        leaf.mkdir()
    (leaf / "movie.mkv").touch()
    probe = ScandirProbe()
    monkeypatch.setattr(scanner.os, "scandir", probe)
    checks = []

    def stop():
        checks.append(True)
        return len(checks) >= 25

    assert list(MediaScanner().walk_files([str(tmp_path)], stop=stop)) == []
    assert len(checks) == 25
    assert 1 < len(probe.opened) < 100
    assert probe.closed == list(reversed(probe.opened))
    probe.opened.clear()
    assert list(MediaScanner().walk_files([str(tmp_path)], stop=lambda: True)) == []
    assert probe.opened == []


def test_callback_failure_propagates_and_closes_handles(tmp_path, monkeypatch):
    bad = tmp_path / "bad.mkv"
    bad.touch()
    probe = ScandirProbe(bad_stat=[str(bad)])
    monkeypatch.setattr(scanner.os, "scandir", probe)

    def callback(path, message):
        raise RuntimeError("caller error")

    with pytest.raises(RuntimeError, match="caller error"):
        list(MediaScanner().walk_files([str(tmp_path)], on_error=callback))
    assert probe.closed == probe.opened


def test_retry_interval_boundary_and_reload_do_not_change_schedule(clock):
    queue = RetryQueue(retry_interval=3600, max_attempts=2)
    queue.add("/movie.mkv", "movie.mkv", 10, "/target", "initial failure")
    item = queue.get("/movie.mkv")
    assert item["attempts"] == 1 and item["status"] == "pending"
    assert item["next_retry"] == 3700
    assert queue.due(3699.999) == []
    assert queue.due("3700")[0]["attempts"] == 1
    assert queue.pending["/movie.mkv"] == item
    clock[0] = 500
    restored = RetryQueue(3600, 2, queue.to_list())
    assert restored.get("/movie.mkv")["next_retry"] == 3700
    assert restored.due() == []
    clock[0] = 3700
    restored.add("/movie.mkv", "renamed.mkv", 11, "/target", "retry failure")
    assert restored.get("/movie.mkv")["next_retry"] == 7300
    assert restored.get("/movie.mkv")["name"] == "renamed.mkv"
    assert restored.get("/movie.mkv")["size"] == 11


@pytest.mark.parametrize("limit", [1, 2, 5])
def test_exhaustion_is_after_initial_plus_n_retries_and_never_removed(clock, limit):
    queue = RetryQueue(60, limit)
    for failures in range(1, limit + 2):
        queue.add("/a.mkv", "a.mkv", 1, "/remote", f"failure {failures}")
        before = deepcopy(queue.pending)
        due = queue.due(clock[0] + 60)
        assert bool(due) == (failures <= limit)
        assert queue.get("/a.mkv")["attempts"] == failures
        assert queue.pending == before
        clock[0] += 60
    assert queue.due(10**12) == []
    assert len(queue) == 1 and "/a.mkv" in queue.pending
    exhausted = queue.to_list()[0]
    assert exhausted["status"] == "exhausted"
    assert exhausted["error"] == exhausted["last_error"] == f"failure {limit + 1}"
    assert "next_retry" in exhausted
    # Existing full-scan membership filtering must still see exhausted paths.
    assert [p for p in ["/a.mkv"] if p not in queue.pending] == []
    restored = RetryQueue(60, limit, queue.to_list())
    assert restored.due(10**12) == [] and len(restored) == 1
    restored.remove("/a.mkv")
    restored.remove("/missing")
    assert len(restored) == 0


def test_zero_limit_is_unlimited_including_stale_exhausted_status(clock):
    queue = RetryQueue(30, 0, [{"path": "/a", "attempts": 100, "status": "exhausted"}])
    assert queue.get("/a")["status"] == "pending"
    for _ in range(25):
        queue.add("/a", "a", 0, "/r", "failed")
        assert queue.due(clock[0] + 30)[0]["status"] == "pending"
    assert queue.get("/a")["attempts"] == 125


@pytest.mark.parametrize("status", ["busy", "suspended"])
def test_busy_suspended_retained_until_explicit_manual_retry(clock, status):
    queue = RetryQueue(60, 3)
    queue.add("/a", "a", 1, "/target", "busy", status=status, source="qb")
    queue.add("/a", "a", 1, "/target", "still busy")
    assert queue.get("/a")["status"] == status
    assert queue.due(10**9) == []
    assert queue.defer("/a", now=200)
    assert queue.get("/a")["status"] == status
    assert queue.retry_now("/a", reset_attempts=False)
    assert queue.due()[0]["attempts"] == 2
    assert queue.due()[0]["status"] == "pending"


def test_deep_copies_and_read_methods_never_write_status(clock):
    metadata = {"target": {"cid": "99", "parts": ["folder"]}}
    queue = RetryQueue(60, 1)
    queue.add("/a", "a", 1, "/remote", "failure", **metadata)
    metadata["target"]["parts"].append("outside")
    original = deepcopy(queue.pending)
    for item in (queue.get("/a"), queue.to_list()[0], queue.due(160)[0]):
        item["target"]["parts"].append("modified")
        item["status"] = "suspended"
    assert queue.pending == original
    # Derive exhaustion from attempts without repairing the live dict in a read.
    queue.pending["/a"]["attempts"] = 2
    original = deepcopy(queue.pending)
    assert queue.to_list()[0]["status"] == "exhausted"
    assert queue.get("/a")["status"] == "exhausted"
    assert queue.due(1000) == []
    assert queue.pending == original
    queue.max_attempts = 0
    assert queue.due(1000)[0]["status"] == "pending"
    assert queue.pending == original


def test_metadata_preserved_without_overriding_failure_count_or_interval(clock):
    queue = RetryQueue(120, 1)
    queue.add("/a", "a", 5, "/r", "first", source="qb", status="suspended",
              target={"cid": 42}, attempts=-10, next_retry=0, updated_at=0,
              last_error="cannot override")
    item = queue.get("/a")
    assert item["attempts"] == 1 and item["next_retry"] == 220
    assert item["updated_at"] == 100
    assert item["error"] == item["last_error"] == "first"
    queue.add("/a", "a", 8, "/r", "second", mtime_ns=123, inode=456)
    item = queue.get("/a")
    assert item["source"] == "qb" and item["target"] == {"cid": 42}
    assert item["mtime_ns"] == 123 and item["inode"] == 456
    assert item["status"] == "exhausted" and item["attempts"] == 2


def test_legacy_pending_bad_records_and_mapping_compatibility():
    legacy = {"path": "/old.mkv", "size": "1.5GB", "attempts": "2",
              "next_retry": "900.5", "last_error": "legacy", "remote_dir": "/keep",
              "extra": {"list": [1]}}
    queue = RetryQueue(60, 2, [None, [], "bad", {}, {"path": []}, {"path": {}},
                              {"path": " "}, {"path": "bad\x00path"}, legacy,
                              {"path": "/another", "attempts": "bad", "size": "?"}])
    legacy["extra"]["list"].append(2)
    assert set(queue.pending) == {"/old.mkv", "/another"}
    item = queue.get("/old.mkv")
    assert item["size"] == 1610612736
    assert item["next_retry"] == 900.5 and item["attempts"] == 2
    assert item["last_error"] == item["error"] == "legacy"
    assert item["source"] == "local" and item["remote_dir"] == "/keep"
    assert item["extra"] == {"list": [1]}
    assert queue.get("/another")["size"] == queue.get("/another")["attempts"] == 0
    mapped = RetryQueue(pending={"/mapped": {"size": "1 KiB"}, "/bad": None})
    assert mapped.get("/mapped")["path"] == "/mapped"
    assert mapped.get("/mapped")["size"] == 1024
    assert len(mapped) == 1
    assert len(RetryQueue(pending="broken top-level value")) == 0


@pytest.mark.parametrize("value, expected", [("12", 12), ("1.5 KB", 1536),
    ("2MiB", 2097152), ("3B", 3), ("?", 0), (None, 0), ({}, 0),
    ("9007199254740993", 9007199254740993),
    (-1, 0), (float("nan"), 0), (float("inf"), 0)])
def test_legacy_size_is_always_safe_integer(value, expected):
    queue = RetryQueue(pending=[{"path": "/a", "size": value}])
    assert queue.to_list()[0]["size"] == expected
    assert type(queue.to_list()[0]["size"]) is int


@pytest.mark.parametrize("bad", [None, "", "not an epoch", "nan", "inf", -1, [], {}])
def test_malformed_epochs_fallback_without_crashing_or_losing_valid_records(bad):
    queue = RetryQueue(60, pending=[
        {"path": "/a", "updated_at": "100", "next_retry": bad},
        {"path": "/b", "updated_at": bad, "next_retry": bad},
        {"path": "/valid", "next_retry": "500"},
    ])
    assert queue.get("/a")["next_retry"] == 160
    assert queue.get("/b")["next_retry"] == 0
    assert [i["path"] for i in queue.due(159)] == ["/b"]
    assert {i["path"] for i in queue.due(160)} == {"/a", "/b"}
    assert len(queue) == 3


def test_legacy_config_minimum_and_invalid_values():
    assert RetryQueue("120", "2").retry_interval == 120
    assert RetryQueue("120", "2").max_attempts == 2
    assert RetryQueue(1, -1).retry_interval == 30
    assert RetryQueue(1, -1).max_attempts == 0
    assert RetryQueue("bad", "bad").retry_interval == 600
    assert RetryQueue(None, None).max_attempts == 0


def test_defer_only_due_items_without_consuming_attempts_or_sliding_forever(clock):
    queue = RetryQueue(60, 1)
    queue.add("/a", "a", 1, "/target", "failure", source="qb", target={"cid": 7})
    before = deepcopy(queue.pending)
    assert not queue.defer("/a", now=159)
    assert queue.pending == before
    assert queue.defer("/a", error="client busy", now=159)
    assert queue.get("/a")["next_retry"] == 160
    assert queue.defer("/a", now=160)
    item = queue.get("/a")
    assert item["attempts"] == 1 and item["next_retry"] == 220
    assert item["error"] == item["last_error"] == "client busy"
    assert item["source"] == "qb" and item["target"] == {"cid": 7}
    before = deepcopy(queue.pending)
    assert not queue.defer("/a", now=180)
    assert not queue.defer("/a", error="client busy", now=219)
    assert queue.pending == before
    assert queue.due(219) == [] and len(queue.due(220)) == 1
    assert not queue.defer("/missing", now=1000)


def test_manual_requeue_resets_exhaustion_but_preserves_target_and_errors(clock):
    queue = RetryQueue(600, 1, [{"path": "/a", "attempts": 2, "remote_dir": "/keep",
                               "source": "qb", "target": {"cid": 77}, "last_error": "failed"}])
    before = deepcopy(queue.pending)
    assert not queue.retry_now("/a", reset_attempts=False)
    assert queue.pending == before
    assert queue.retry_now("/a")
    item = queue.due()[0]
    assert item["attempts"] == 0 and item["status"] == "pending"
    assert item["next_retry"] == clock[0]
    assert item["remote_dir"] == "/keep" and item["target"] == {"cid": 77}
    assert item["source"] == "qb" and item["error"] == "failed"
    queue.add("/a", "a", 1, "/keep", "failed again")
    assert queue.get("/a")["attempts"] == 1
    assert queue.due() == []
    assert not queue.retry_now("/missing") and queue.get("/missing") is None


def test_legacy_last_error_updates_are_visible_without_read_side_effects(clock):
    queue = RetryQueue()
    queue.add("/a", "a", 1, "/r", "previous")
    queue.pending["/a"]["last_error"] = "legacy caller updated"
    before = deepcopy(queue.pending)
    assert queue.to_list()[0]["error"] == "legacy caller updated"
    assert queue.pending == before
    error_only = RetryQueue(pending=[{"path": "/a", "error": "new format"}])
    assert error_only.get("/a")["last_error"] == "new format"


def test_root_stat_failure_and_invalid_path_report_and_continue(tmp_path, monkeypatch):
    bad, valid = tmp_path / "bad.mkv", tmp_path / "ok.mkv"
    valid.touch()
    real = os.stat

    def file_stat(path, *args, **kwargs):
        if os.fspath(path) == str(bad):
            raise PermissionError("root stat denied")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(scanner.os, "stat", file_stat)
    errors = []
    records = list(MediaScanner().walk_files([str(bad), "bad\x00path", str(valid)],
                                           on_error=lambda *args: errors.append(args)))
    assert [item["path"] for item in records] == [str(valid)]
    assert len(errors) == 2 and errors[0] == (str(bad), "root stat denied")


def test_cancellation_after_yield_never_visits_next_root(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "one.mkv").touch()
    (second / "two.mkv").touch()
    probe = ScandirProbe()
    monkeypatch.setattr(scanner.os, "scandir", probe)
    cancelled = [False]
    walk = MediaScanner().walk_files([str(first), str(second)], stop=lambda: cancelled[0])
    assert next(walk)["path"] == str(first / "one.mkv")
    cancelled[0] = True
    assert list(walk) == []
    assert probe.opened == probe.closed == [str(first)]


def test_invalid_add_and_read_time_values_are_safe(clock):
    queue = RetryQueue(60)
    for path in ("", " ", None, [], "bad\x00path"):
        with pytest.raises(ValueError):
            queue.add(path, "a", 0, "/r", "bad")
    queue.add("/a", "a", 0, "/r", "failure")
    assert queue.due("nan") == []  # Invalid now falls back to the wall clock.
    assert queue.defer("/a", now="160")
    assert queue.get("/a")["next_retry"] == 220
    assert queue.due(0) == []


def test_non_regular_root_is_not_opened_as_media(tmp_path):
    fifo = tmp_path / "not-a-file.mkv"
    os.mkfifo(fifo)
    assert MediaScanner().iter_files([str(fifo)]) == []


def test_unrepresentable_human_size_does_not_crash():
    queue = RetryQueue(pending=[{"path": "/a", "size": "9" * 400 + ".0GB"}])
    assert queue.get("/a")["size"] == 0


def test_uncopyable_and_later_corrupted_pending_items_are_isolated():
    class BadCopy:
        def __deepcopy__(self, memo):
            raise ValueError("corrupt metadata")

    queue = RetryQueue(pending=[{"path": "/bad", "meta": BadCopy()}, {"path": "/good"}])
    assert list(queue.pending) == ["/good"]
    queue.pending["/bad"] = None
    assert [item["path"] for item in queue.to_list()] == ["/good"]
    assert [item["path"] for item in queue.due(0)] == ["/good"]
