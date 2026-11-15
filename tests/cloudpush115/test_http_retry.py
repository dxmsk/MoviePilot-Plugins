import importlib
import sys
import types
from urllib.error import HTTPError
from test_runtime import host


def test_http_retry_transient_503(host, monkeypatch):
    p = host.new({'cookie': 'UID=fixture'})
    web = importlib.import_module(type(p).__module__ + '.p115_web')
    client = web.P115WebClient('UID=fixture')
    class Headers:
        def get(self, key, default=''): return ''
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'ok'
    calls = []
    def opener(req, timeout=0):
        calls.append(req.full_url)
        if len(calls) < 3: raise HTTPError(req.full_url, 503, 'busy', Headers(), None)
        return Resp()
    monkeypatch.setattr(client._opener, 'open', opener)
    monkeypatch.setattr(web.time, 'sleep', lambda value: None)
    assert client._request('https://uplb.115.com/test') == b'ok'
    assert len(calls) == 3


def test_http_retry_non_transient_once(host, monkeypatch):
    p = host.new({'cookie': 'UID=fixture'})
    web = importlib.import_module(type(p).__module__ + '.p115_web')
    client = web.P115WebClient('UID=fixture')
    class Headers:
        def get(self, key, default=''): return ''
    calls = []
    def opener(req, timeout=0):
        calls.append(1); raise HTTPError(req.full_url, 401, 'auth', Headers(), None)
    monkeypatch.setattr(client._opener, 'open', opener)
    try: client._request('https://uplb.115.com/test')
    except web.P115WebError: pass
    assert len(calls) == 1
