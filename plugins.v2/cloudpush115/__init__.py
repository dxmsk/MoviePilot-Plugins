"""115 网盘秒传 — MoviePilot V2 native pages and durable work queues."""
from app.plugins import _PluginBase
from app.core.event import Event, eventmanager
from app.schemas.types import EventType

from .runtime import RuntimeMixin
from .ui import UiMixin


class CloudPush115(RuntimeMixin, UiMixin, _PluginBase):
    plugin_name = "115网盘秒传"
    plugin_desc = "本地文件SHA1秒传115；网页Cookie、手填目录、可见文件队列、失败重试和qB完成联动。"
    plugin_icon = "clouddisk.png"
    plugin_version = "1.6.4"
    plugin_author = "Minis"
    author_url = "https://github.com/dxmsk/MoviePilot-Plugins"
    plugin_config_prefix = "cloudpush115_"
    plugin_order = 20
    auth_level = 1

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        return self._plugin_action(event)
