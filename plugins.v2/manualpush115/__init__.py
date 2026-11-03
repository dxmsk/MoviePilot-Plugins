"""手动秒传 115 — MoviePilot V2 插件入口。"""
from app.plugins import _PluginBase

from .runtime import RuntimeMixin
from .ui import UiMixin


class ManualPush115(RuntimeMixin, UiMixin, _PluginBase):
    plugin_name = "手动秒传115"
    plugin_desc = "选择本地文件一键 SHA1 秒传到 115 网盘，不自动扫描、不需要调度。"
    plugin_icon = "clouddisk.png"
    plugin_version = "1.0.0"
    plugin_author = "Minis"
    author_url = "https://github.com/dxmsk/MoviePilot-Plugins"
    plugin_config_prefix = "manualpush115_"
    plugin_order = 21
    auth_level = 1
