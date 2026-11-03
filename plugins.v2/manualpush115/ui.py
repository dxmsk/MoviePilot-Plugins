"""UI for ManualPush115: Vuetify native page + native form."""
from __future__ import annotations
from copy import deepcopy


def node(component, text=None, content=None, **props):
    item = {"component": component}
    if text is not None:
        item["text"] = str(text)
    if content is not None:
        item["content"] = content
    if props:
        item["props"] = props
    return item


def chip(status):
    colors = {"success": ("秒传成功", "success"), "failed": ("失败", "error")}
    label, color = colors.get(str(status), (str(status or ""), "secondary"))
    return node("VChip", label, color=color, variant="tonal", size="small")


def render_page(snapshot: dict, plugin_id: str):
    history = snapshot.get("history") or []
    header = node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-cloud-upload", color="primary", **{"class": "mr-2"}),
            node("span", "手动秒传 115"),
        ], **{"class": "d-flex align-center text-h6 font-weight-bold"}),
        node("VCardText", f"选择文件一键秒传 · v{snapshot.get('version', '')}", **{"class": "pt-0 text-caption text-medium-emphasis"}),
    ], variant="outlined", **{"class": "rounded-lg mb-4"})

    rows, cards = [], []
    for row in history[:50]:
        cells = []
        for key in ("name", "status", "size_text", "message", "remote_dir", "time"):
            val = row.get(key, "—")
            if key == "status":
                cells.append(node("td", content=[chip(val)], style="padding:10px 12px;"))
            elif key == "size_text":
                cells.append(node("td", _human_size(row.get("size")), style="padding:10px 12px;"))
            else:
                cells.append(node("td", str(val), style="overflow-wrap:anywhere;max-width:300px;padding:10px 12px;"))
        rows.append(node("tr", content=cells))
        mobile = [node("div", content=[
            node("strong", row.get("name", ""), style="flex:1;min-width:0;overflow-wrap:anywhere;"),
            chip(row.get("status")),
        ], style="display:flex;gap:8px;align-items:flex-start;")]
        if row.get("message"):
            mobile.append(node("div", row["message"], style="font-size:12px;opacity:.85;overflow-wrap:anywhere;"))
        mobile.append(node("div", f"{_human_size(row.get('size'))} · {row.get('time', '')}", style="font-size:11px;opacity:.6;"))
        cards.append(node("div", content=mobile, style="padding:12px;border-bottom:1px solid rgba(128,128,128,.15);"))

    columns = [("name", "文件"), ("status", "结果"), ("size_text", "大小"),
               ("message", "详情"), ("remote_dir", "目标"), ("time", "时间")]
    history_section = node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-history", **{"class": "mr-2"}),
            node("span", "秒传记录"),
            node("VChip", len(history), size="small", variant="tonal", **{"class": "ml-2"}),
        ], **{"class": "d-flex align-center text-subtitle-1 font-weight-bold"}),
        node("VTable", content=[
            node("thead", content=[node("tr", content=[node("th", label, style="white-space:nowrap;padding:10px 12px;") for _, label in columns])]),
            node("tbody", content=rows),
        ], density="comfortable", **{"class": "d-none d-md-block", "height": min(390, 56 + len(rows) * 60), "fixed-header": True}) if rows else node("span"),
        node("div", content=cards, **{"class": "d-md-none", "style": "max-height:420px;overflow:auto;"}) if cards else node("span"),
        node("VCardText", "尚无秒传记录。在设置中填写 Cookie，然后使用 API 或 CLI 发起手动秒传。",
             **{"class": "text-body-2 text-medium-emphasis py-5"}) if not rows else node("span"),
    ], variant="outlined", **{"class": "rounded-lg mb-4"})

    return [header, history_section,
            node("div", f"目标目录：{snapshot.get('remote_dir', '/')} · 运行状态：{snapshot.get('progress') or '空闲'}",
                 **{"class": "text-caption text-medium-emphasis", "style": "overflow-wrap:anywhere;"})]


def _human_size(n) -> str:
    try:
        b = int(n)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
        b /= 1024
    return f"{b:.1f} PB"


DEFAULTS = {
    "cookie": "",
    "user_agent": "",
    "remote_dir": "/",
    "extensions": "",
}


class UiMixin:
    @staticmethod
    def get_render_mode():
        return "vuetify", None

    def get_page(self):
        from .browser_html import BROWSER_HTML
        html = BROWSER_HTML.replace("__PREFIX__", type(self).__name__)
        return [{"component": "div", "html": html}]

    def get_form(self):
        def field(key, label, component="VTextField", md=6, **props):
            return node("VCol", content=[node(component, model=key, label=label,
                        **{"density": "comfortable", "persistent-hint": True, **props})], cols=12, md=md)

        def row(*items):
            return node("VRow", content=list(items))

        content = [
            node("VCard", content=[
                node("VCardTitle", "🔐 115 网页 Cookie"),
                node("VCardText", "填写 115 网页 Cookie（包含 UID/CID/SEID）。不会自动扫描，仅手动秒传时使用。"),
            ], variant="tonal", color="primary", **{"class": "my-3 rounded-lg"}),
            row(field("cookie", "115 网页 Cookie", "VTextarea", 12, rows=3,
                      hint="从浏览器复制完整 Cookie")),
            row(field("remote_dir", "115 默认目标目录", placeholder="/媒体/电影",
                      hint="秒传时的默认网盘目标；每次秒传也可单独指定"),
                field("extensions", "限制文件扩展名（可选）", placeholder="mkv,mp4,srt",
                      hint="留空不限制；多个用逗号分隔")),
            row(field("user_agent", "115 User-Agent（可选）", md=12,
                      hint="留空使用内置 UA")),
        ]
        return [node("VForm", content=content)], deepcopy(DEFAULTS)
