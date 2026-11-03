"""手动秒传 115 — MoviePilot V2/V3 兼容插件入口。"""
try:
    from app.plugins import _PluginBase
except ImportError:
    from app.sdk.plugins import _PluginBase

from .runtime import RuntimeMixin
from .ui import UiMixin


class ManualPush115(RuntimeMixin, UiMixin, _PluginBase):
    plugin_name = "手动秒传115"
    plugin_desc = "浏览本地文件，勾选后一键 SHA1 秒传到 115 网盘，不自动扫描、不需要调度。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/upload.png"
    plugin_version = "1.6.0"
    plugin_author = "Minis"
    author_url = "https://github.com/dxmsk/MoviePilot-Plugins"
    plugin_config_prefix = "manualpush115_"
    plugin_order = 21
    auth_level = 1
