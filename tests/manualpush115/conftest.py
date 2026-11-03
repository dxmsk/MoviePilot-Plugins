"""Offline MoviePilot contract: real modules, durable JSON, no network."""
import importlib.util
import json
import logging
import socket
import sys
import types
from copy import deepcopy
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2] / "plugins.v2" / "manualpush115"


@pytest.fixture
def env(monkeypatch, tmp_path):
    def mod(name, **attrs):
        value = types.ModuleType(name)
        value.__dict__.update(attrs)
        value.__path__ = []
        monkeypatch.setitem(sys.modules, name, value)
        return value

    class Base:
        def __init__(self):
            self.data = {}
            self.saved = {}
            self.writes = []
        def save_data(self, key, value):
            value = json.loads(json.dumps(value))
            self.data[key] = value
            self.writes.append(deepcopy(value))
        def get_data(self, key):
            return deepcopy(self.data.get(key))
        def update_config(self, value):
            self.saved = deepcopy(value)

    mod("app")
    mod("app.plugins", _PluginBase=Base)
    mod("app.log", logger=logging.getLogger("manual115-test"))
    name = "manual115_integration"
    for module_name in list(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            monkeypatch.delitem(sys.modules, module_name)
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, package)
    spec.loader.exec_module(package)
    runtime = sys.modules[name + ".runtime"]
    root = tmp_path / "MP mounted media"
    root.mkdir()
    roots = {"roots": [{"path": str(root), "name": root.name, "source": "test mount"}], "warnings": []}
    monkeypatch.setattr(runtime, "discover_roots", lambda cfg=None: deepcopy(roots))

    def no_network(*args, **kwargs):
        pytest.fail("Unexpected live network request")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)

    class Client:
        def __init__(self):
            self.calls, self.created, self.targets = [], [], []
            self.rows = {}
            self.answer = {"ok": True, "message": "秒传成功", "sha1": "local-test"}
        def get_dir_id_by_path(self, path):
            self.targets.append(path)
            return 10
        def find_dir(self, parent, name):
            return self.rows.get((parent, name))
        def make_dir(self, parent, name):
            cid = 100 + len(self.created)
            self.created.append((parent, name))
            self.rows[parent, name] = cid
            return cid
        def push_file(self, path, remote_dir_id):
            self.calls.append((str(path), remote_dir_id))
            return self.answer(path) if callable(self.answer) else dict(self.answer)
        def check_login(self):
            return {"state": True, "user_name": "local"}

    client = Client()
    plugin = package.ManualPush115()
    plugin.init_plugin({"cookie": "UID=123_A1;CID=fixture;SEID=fixture", "remote_dir": "/待整理"})
    monkeypatch.setattr(plugin, "_make_client", lambda cfg: client)
    def finish():
        worker = plugin._worker
        if worker:
            worker.join(5)
            assert not worker.is_alive(), "Background job failed to finish"
        return plugin.api_status()["data"]

    return types.SimpleNamespace(plugin=plugin, root=root, client=client, runtime=runtime,
        package=package, finish=finish, settings=sys.modules[name + ".settings"],
        remote=sys.modules[name + ".remotefiles"], client_module=sys.modules[name + ".p115_web"], roots=roots)
