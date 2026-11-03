import json
import threading
from pathlib import Path
from types import SimpleNamespace
import pytest


def make(env, relative="a.mkv", data=b"content"):
    path = env.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def push(env, paths, **kwargs):
    answer = env.plugin.api_push({"paths": paths, **kwargs})
    assert answer["success"], answer
    return env.finish()


def test_configuration_load_is_pure_and_defaults_dont_require_network(env, monkeypatch):
    monkeypatch.setattr(env.plugin, "_make_client", lambda *_a: pytest.fail("settings invoked network"))
    snapshot = env.plugin.api_settings()
    assert snapshot["data"]["settings"]["remote_dir"] == "/待整理"
    assert env.plugin.api_roots()["data"]["roots"][0]["path"] == str(env.root)
    assert env.plugin.api_browse()["data"]["entries"][0]["path"] == str(env.root)


def test_legacy_local_paths_and_combobox_object_roundtrip_without_config_loss(env):
    file = make(env, "some, movie.mkv")
    env.plugin.init_plugin({"cookie": "UID=x;SEID=fixture", "local_paths": [file],
        "remote_dir": {"value": "/待整理"}, "future_key": {"keep": 1}})
    cfg = env.plugin.api_settings()["data"]["settings"]
    assert cfg["local_paths"] == [file]
    assert cfg["remote_dir"] == "/待整理"
    saved = env.plugin.api_save_settings(env.settings.SettingsPayload(**cfg))
    assert saved["success"] and env.plugin.saved["future_key"] == {"keep": 1}


def test_blank_search_does_not_scan_or_issue_network(env, monkeypatch):
    monkeypatch.setattr(env.plugin, "_files", lambda *_a: pytest.fail("blank search started scan"))
    answer = env.plugin.api_search("   ")
    assert answer["success"] is False


def test_browse_and_search_input_boundary(env, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    assert not env.plugin.api_browse(str(outside))["success"]
    assert not env.plugin.api_search("movie", str(outside), recursive=True)["success"]
    assert not env.plugin.api_push({"paths": [str(outside)]})["success"]


def test_explicit_single_file_is_received_in_json_payload(env):
    path = make(env)
    status = push(env, [path])
    assert status["job"]["success"] == 1
    assert status["job"]["phase"] == "completed"
    assert env.client.calls == [(path, 10)]
    assert env.client.targets == ["/待整理"]
    assert env.plugin.writes[-1]["history"][-1]["path"] == path


def test_selected_folder_preserves_hierarchy_and_overlapping_file_dedup(env):
    a = make(env, "Show/Season 1/a.mkv")
    b = make(env, "Show/Season 2/b.mkv")
    status = push(env, [str(env.root / "Show"), a])
    assert status["job"]["total"] == 2
    assert len(env.client.calls) == 2
    assert {r["remote_dir"] for r in status["history"]} == {"/待整理/Show/Season 1", "/待整理/Show/Season 2"}
    assert Path(a).exists() and Path(b).exists()


def test_new_manual_submission_does_not_blindly_skip_old_success(env):
    path = make(env)
    push(env, [path])
    push(env, [path])
    assert len(env.client.calls) == 2, "manual repair defaults to reattempt"
    status = push(env, [path], force=False)
    assert status["job"]["skipped"] == 1
    assert len(env.client.calls) == 2
    status = push(env, [path], force=False, remote_dir="/another-target")
    assert status["job"]["success"] == 1 and len(env.client.calls) == 3
    Path(path).write_bytes(b"updated file content")
    status = push(env, [path], force=False)
    assert status["job"]["success"] == 1 and len(env.client.calls) == 4


def test_success_is_not_inferred_from_arbitrary_truthy_strings(env):
    env.client.answer = {"ok": "false", "status": 1, "message": "not found"}
    status = push(env, [make(env)])
    assert status["job"]["failed"] == 1 and status["job"]["success"] == 0


def test_no_matching_files_is_error_not_zero_file_success(env):
    (env.root / "empty").mkdir()
    status = push(env, [str(env.root / "empty")])
    assert status["job"]["phase"] == "failed"
    assert "没有" in status["job"]["message"]
    assert not env.client.calls


def test_configuration_save_during_job_does_not_change_running_snapshot(env, monkeypatch):
    a, b = make(env), make(env, "b.mkv")
    entered, release = threading.Event(), threading.Event()
    def answer(_path):
        entered.set()
        assert release.wait(5)
        return {"ok": True}
    env.client.answer = answer
    resp = env.plugin.api_push({"paths": [a, b], "request_id": "run-1"})
    assert resp["success"] and entered.wait(5)
    try:
        env.plugin.init_plugin({"cookie": "UID=other", "remote_dir": "/new"})
        assert env.plugin._running
        duplicate = env.plugin.api_push({"paths": [a]})
        assert not duplicate["success"]
    finally:
        release.set()
    status = env.finish()
    assert len(env.client.calls) == 2
    assert env.client.targets == ["/待整理"]
    assert {row["remote_dir"] for row in status["history"]} == {"/待整理"}
    assert status["remote_dir"] == "/new"


def test_idempotent_submission_and_cancel_wait_for_current_file(env):
    a, b = make(env), make(env, "b.mkv")
    entered, release = threading.Event(), threading.Event()
    def answer(_path):
        entered.set()
        assert release.wait(5)
        return {"ok": True}
    env.client.answer = answer
    body = {"paths": [a, b], "request_id": "tap-one"}
    first = env.plugin.api_push(body)
    assert entered.wait(5)
    try:
        second = env.plugin.api_push(body)
        assert first["data"]["job_id"] == second["data"]["job_id"]
        assert env.plugin.api_cancel()["success"]
        assert env.plugin.api_status()["data"]["running"]
    finally:
        release.set()
    status = env.finish()
    assert status["job"]["phase"] == "cancelled"
    assert status["job"]["remaining"] == 1 and len(env.client.calls) == 1


def test_status_hides_credentials_and_copies_nested_history(env):
    push(env, [make(env)])
    snapshot = env.plugin.api_status()["data"]
    assert "SEID" not in json.dumps(snapshot) and "cookie" not in snapshot
    snapshot["history"][0]["signature"][0] = -100
    assert env.plugin._history[0]["signature"][0] >= 0


def test_per_file_success_persisted_before_next_transfer(env):
    paths = [make(env, f"{n}.mkv") for n in range(3)]
    counts = []
    def answer(_path):
        saved = env.plugin.data[env.plugin.STATE_KEY]
        counts.append(len(saved["history"]))
        return {"ok": True}
    env.client.answer = answer
    push(env, paths)
    assert counts == [0, 1, 2]


def test_fastapi_routes_accept_actual_json_and_query_fields(env):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    for route in env.plugin.get_api():
        app.add_api_route(route["path"], route["endpoint"], methods=route["methods"])
    with TestClient(app) as client:
        roots = client.get("/roots").json()
        assert roots["success"]
        assert client.get("/search", params={"query": ""}).json()["success"] is False
        answer = client.post("/push", json={"paths": [make(env)], "remote_dir": "/other", "force": True}).json()
        assert answer["success"], answer
        env.finish()
        assert env.client.targets == ["/other"]
        settings = client.get("/settings").json()["data"]["settings"]
        assert client.post("/settings", json=settings).json()["success"]
