"""Federation pages include both the manual browser and complete settings UI."""
from copy import deepcopy
from .settings import DEFAULTS


def node(component, text=None, content=None, **props):
    result = {"component": component}
    if text is not None:
        result["text"] = str(text)
    if content is not None:
        result["content"] = content
    if props:
        result["props"] = props
    return result


class UiMixin:
    @staticmethod
    def get_render_mode():
        # src/components/Config.vue is a full settings form, not a placeholder.
        return "vue", "dist/assets"

    def get_form(self):
        """Fallback/default schema; no filesystem walk or 115 network request."""
        fields = [
            node("VAlert", "本地文件选择、逐层浏览和搜索均位于插件首页；这里只配置凭据与默认值。", type="info", variant="tonal"),
            node("VTextarea", model="cookie", label="115 网页 Cookie", rows=3, autocomplete="off"),
            node("VTextField", model="remote_dir", label="默认115目标目录", hint="在首页也可点击选择网盘真实目录"),
            node("VTextField", model="extensions", label="目录内扩展名过滤", hint="留空为媒体默认值，* 表示所有文件"),
            node("VTextField", model="user_agent", label="User-Agent（可选）"),
        ]
        return [node("VForm", content=fields)], deepcopy(DEFAULTS)

    def get_page(self):
        # Only old/non-federation hosts reach this; no v-html or embedded scripts.
        return [node("VAlert", "文件浏览首页使用官方 Vue 联邦组件。更新插件后重新打开详情页；设置入口仍保留。",
                     type="info", variant="tonal")]
