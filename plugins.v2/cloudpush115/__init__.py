"""115 网盘秒传 — MoviePilot V2/V3 兼容。"""
try:
    from app.plugins import _PluginBase
except ImportError:
    from app.sdk.plugins import _PluginBase  # type: ignore

try:
    from app.core.event import Event, eventmanager
except ImportError:
    from app.sdk.events import Event, eventmanager  # type: ignore

try:
    from app.schemas.types import EventType
except ImportError:
    from app.sdk.events import EventType  # type: ignore

from .runtime import RuntimeMixin
from .ui import UiMixin


def optional_event(name):
    event_type = getattr(EventType, name, None)
    return eventmanager.register(event_type) if event_type is not None else (lambda method: method)


class CloudPush115(RuntimeMixin, UiMixin, _PluginBase):
    plugin_name = "115网盘秒传"
    plugin_desc = "整理事件实时入队、115秒传、硬链接失败重试与成功清理、源目录保护。"
    plugin_icon = "clouddisk.png"
    plugin_version = "1.8.2"
    plugin_author = "Minis"
    author_url = "https://github.com/dxmsk/MoviePilot-Plugins"
    plugin_config_prefix = "cloudpush115_"
    plugin_order = 20
    auth_level = 1

    @optional_event('TransferComplete')
    def on_transfer_complete(self, event: Event):
        return self._on_transfer_complete(event)

    @optional_event('SubtitleTransferComplete')
    def on_subtitle_complete(self, event: Event):
        return self._on_transfer_complete(event)

    @optional_event('AudioTransferComplete')
    def on_audio_complete(self, event: Event):
        return self._on_transfer_complete(event)

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        return self._plugin_action(event)
