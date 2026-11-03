import threading
from copy import deepcopy
import pytest


def make(env, filename="a.mkv", content=b"media"):
    path = env.root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def test_explicit_empty_paths_does_not_upload_legacy_default(env):
    path = make(env)
    cfg = env.plugin.api_settings()["data"]["settings"]
    cfg["local_paths"] = [path]
    env.plugin.init_plugin(cfg)
    assert not env.plugin.api_push({"paths": []})["success"]
    assert not env.client.calls


def test_wildcard_extension_keeps_unusual_file_visible_and_collectable(env):
    path = make(env, "example.xyz")
    cfg = env.plugin.api_settings()["data"]["settings"]
    cfg["extensions"] = "*"
    env.plugin.init_plugin(cfg)
    page = env.plugin.api_browse(str(env.root))["data"]
    assert page["entries"][0]["path"] == path
    assert env.plugin.api_push({"paths": [str(env.root)]})["success"]
    assert env.finish()["job"]["success"] == 1


def test_restarted_incomplete_job_is_marked_interrupted_without_auto_resume(env):
    saved = {"history": [{"name": "old", "status": "success"}],
             "job": {"id": "previous", "phase": "running", "total": 4, "processed": 1, "remaining": 3}}
    other = env.package.ManualPush115()
    other.data[other.STATE_KEY] = saved
    other.init_plugin({})
    data = other.api_status()["data"]
    assert data["job"]["phase"] == "interrupted"
    assert not data["running"] and data["history"][0]["name"] == "old"
    assert other.get_service() == []


def test_network_or_auth_failure_keeps_unprocessed_count_and_history(env):
    paths = [make(env, f"{n:02d}.mkv") for n in range(12)]
    env.client.answer = {"ok": False, "message": "未命中秒传"}
    assert env.plugin.api_push({"paths": paths})["success"]
    data = env.finish()
    assert data["job"]["phase"] == "failed"
    assert data["job"]["failed"] == 10 and data["job"]["remaining"] == 2
    assert len(data["history"]) == 10 and not data["running"]


def test_file_changed_after_success_response_is_not_marked_done(env):
    path = make(env)
    def answer(file):
        file.write_bytes(b"changed by downloader")
        return {"ok": True}
    env.client.answer = answer
    assert env.plugin.api_push({"paths": [path]})["success"]
    status = env.finish()
    assert status["job"]["failed"] == 1 and status["job"]["success"] == 0


def test_config_errors_do_not_replace_previous_values(env, monkeypatch):
    original = env.plugin.api_settings()["data"]["settings"]
    def fail(*_a):
        raise OSError("temporary storage unavailable")
    monkeypatch.setattr(env.plugin, "update_config", fail)
    changed = {**original, "remote_dir": "/next"}
    answer = env.plugin.api_save_settings(changed)
    assert not answer["success"]
    assert env.plugin.api_settings()["data"]["settings"] == original


def test_duplicate_request_id_cannot_silently_change_selected_files(env):
    a, b = make(env), make(env, "b.mkv")
    assert env.plugin.api_push({"paths": [a], "request_id": "once"})["success"]
    env.finish()
    answer = env.plugin.api_push({"paths": [b], "request_id": "once"})
    assert not answer["success"]
    assert len(env.client.calls) == 1


def test_form_and_status_never_call_remote_directory_listing(env, monkeypatch):
    monkeypatch.setattr(env.plugin, "_make_client", lambda *_a: pytest.fail("unexpected remote lookup"))
    fields, default = env.plugin.get_form()
    assert fields and default["local_paths"] == []
    assert env.plugin.api_status()["success"]
    assert env.plugin.get_render_mode() == ("vue", "dist/assets")


def test_new_account_and_same_local_file_not_skipped(env):
    path = make(env)
    assert env.plugin.api_push({"paths": [path], "force": False})["success"]
    env.finish()
    cfg = env.plugin.api_settings()["data"]["settings"]
    env.plugin.init_plugin({**cfg, "cookie": "UID=999_A;CID=fixture;SEID=fixture"})
    assert env.plugin.api_push({"paths": [path], "force": False})["success"]
    status = env.finish()
    assert status["job"]["success"] == 1 and len(env.client.calls) == 2


def test_partial_settings_save_cannot_clear_unsubmitted_cookie(env):
    previous = env.plugin.api_settings()["data"]["settings"]
    response = env.plugin.api_save_settings({"remote_dir": "/changed-only"})
    assert response["success"]
    current = env.plugin.api_settings()["data"]["settings"]
    assert current["cookie"] == previous["cookie"]
    assert current["remote_dir"] == "/changed-only"


def test_explicit_selected_filename_spaces_and_newlines_are_preserved(env):
    path = make(env, " movie, & file.mkv ")
    assert env.plugin.api_push({"paths": [path]})["success"]
    status = env.finish()
    assert status["job"]["success"] == 1
    assert env.client.calls[0][0] == path
