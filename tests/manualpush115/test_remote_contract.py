import json
import urllib.parse
import pytest


def test_client_list_call_constructs_real_url_with_params(env, monkeypatch):
    client = env.client_module.P115WebClient("UID=1;CID=fixture;SEID=fixture")
    urls = []
    def request(url, **kwargs):
        urls.append(url)
        return b'{"state":true,"data":[]}'
    monkeypatch.setattr(client, "_request", request)
    assert client.browse(0)["entries"] == []
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(urls[0]).query)["cid"] == ["0"]


def test_remote_selector_fetches_only_requested_layer_and_maps_parent(env):
    calls = []
    class Remote:
        def _get_json(self, url, params, **kwargs):
            calls.append(params)
            return {"state": True, "count": 2,
                "path": [{"cid": "0", "name": "文件"}, {"cid": "10", "name": "我的 影视"}],
                "data": [{"cid": "12", "n": "电视剧", "sha": ""},
                         {"fid": "99", "cid": "10", "n": "movie.mkv", "sha": "abcdef"}]}
    result = env.remote.browse_remote(Remote(), "10", 0, 100)
    assert result["path"] == "/我的 影视" and result["parent_cid"] == "0"
    assert result["entries"] == [{"cid": "12", "name": "电视剧", "path": "/我的 影视/电视剧"}]
    assert len(calls) == 1 and calls[0]["cid"] == "10"
    assert result["has_more"] is False


def test_remote_pagination_counts_files_too_without_mislabelling_page_as_empty(env):
    class Remote:
        def _get_json(self, *a, **kw):
            return {"state": True, "count": 5, "path": [],
                    "data": [{"fid": "1", "n": "x", "sha": "yes"}, {"fid": "2", "sha": "yes"}]}
    result = env.remote.browse_remote(Remote(), "0", 0, 2)
    assert result["entries"] == [] and result["has_more"] is True and result["next_offset"] == 2


def test_remote_failure_and_missing_path_not_reported_as_root_success(env):
    class Remote:
        def _get_json(self, *args, **kwargs):
            return {"state": False, "code": 990002, "message": "Cookie expired"}
    with pytest.raises(env.client_module.P115AuthError):
        env.remote.browse_remote(Remote())
    Remote._get_json = lambda *_a, **_kw: {"state": True, "data": []}
    with pytest.raises(env.client_module.P115WebError, match="未返回"):
        env.remote.browse_remote(Remote(), "20")


def test_missing_cookie_directory_api_does_not_access_remote(env, monkeypatch):
    env.plugin.init_plugin({})
    monkeypatch.setattr(env.plugin, "_make_client", lambda *_a: pytest.fail("network"))
    answer = env.plugin.api_remote()
    assert not answer["success"] and "Cookie" in answer["message"]


def test_remote_error_does_not_echo_credential_or_token(env, monkeypatch):
    def fail(*_):
        raise ValueError("request failed https://webapi.115.com/files?token=secret CID=fixture SEID=fixture")
    monkeypatch.setattr(env.plugin, "_make_client", fail)
    answer = env.plugin.api_remote()
    assert not answer["success"]
    assert "token=secret" not in answer["message"] and "SEID=fixture" not in answer["message"]
