"""UI for ManualPush115: simple text input for paths, no file browser."""
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


def action(plugin_id, title, route, icon="mdi-refresh", method="post",
           color="primary", params=None):
    btn = node("VBtn", title, variant="tonal", color=color, size="small",
               **{"prepend-icon": icon, "class": "ma-1"})
    btn["events"] = {"click": {"api": "plugin/{}/{}".format(plugin_id, route),
                                "method": method, "params": params or {}}}
    return btn


def chip(status):
    colors = {"success": ("成功", "success"), "failed": ("失败", "error"),
              "running": ("秒传中", "primary")}
    label, color = colors.get(str(status), (str(status or ""), "secondary"))
    return node("VChip", label, color=color, variant="tonal", size="x-small")


def human_size(n):
    try:
        b = int(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return "{:.1f} {}".format(b, unit) if unit != "B" else "{} B".format(b)
        b /= 1024
    return "{:.1f} PB".format(b)


def render_page(snapshot, plugin_id):
    pid = plugin_id
    page = []

    # Header
    page.append(node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-cloud-upload-outline", color="primary", **{"class": "mr-2"}),
            node("span", "手动秒传 115"),
        ], **{"class": "d-flex align-center text-h6 font-weight-bold"}),
        node("VCardText",
             "输入本地路径（文件或文件夹）和 115 目标目录，点击秒传按钮即可。v{}".format(
                 snapshot.get("version", "")),
             **{"class": "pt-0 text-caption text-medium-emphasis"}),
        node("VCardText", content=[
            action(pid, "立即秒传", "push", "mdi-cloud-upload"),
            action(pid, "测试凭据", "test", "mdi-key", color="default"),
            action(pid, "刷新页面", "refresh", "mdi-refresh", method="get", color="default"),
        ], **{"class": "pt-0 d-flex flex-wrap"}),
    ], variant="outlined", **{"class": "rounded-lg mb-4"}))

    # Progress / status
    if snapshot.get("running"):
        page.append(node("VAlert", snapshot.get("progress") or "秒传中…",
                         type="info", variant="tonal", **{"class": "mb-3"}))
    elif snapshot.get("progress"):
        page.append(node("VAlert", snapshot["progress"],
                         type="success", variant="tonal", **{"class": "mb-3"}))
    if snapshot.get("last_error"):
        page.append(node("VAlert", snapshot["last_error"],
                         type="error", variant="tonal", **{"class": "mb-3"}))

    # Stats
    stats = snapshot.get("stats") or {}
    metrics = [
        ("success", "已秒传", "mdi-check-circle-outline", "success"),
        ("failed", "失败", "mdi-close-circle-outline", "error"),
        ("skipped", "跳过", "mdi-skip-next-circle-outline", "default"),
        ("total", "本次总计", "mdi-sigma", "primary"),
    ]
    if any(stats.get(k) for k, _, _, _ in metrics):
        page.append(node("VRow", content=[
            node("VCol", content=[node("VCard", content=[
                node("VCardText", content=[
                    node("div", str(stats.get(key, 0)),
                         **{"class": "text-h5 font-weight-bold"}),
                    node("div", title, **{"class": "text-caption text-medium-emphasis"}),
                ], **{"style": "position:relative;"}),
            ], variant="outlined", **{"class": "rounded-lg"})],
                cols=6, md=3) for key, title, _icon, _color in metrics
        ], dense=True, **{"class": "mb-3"}))

    # History
    hist = snapshot.get("history") or []
    hist_rows = []
    for row in hist[:50]:
        mobile = [node("div", content=[
            node("strong", row.get("name", ""),
                 style="flex:1;min-width:0;overflow-wrap:anywhere;"),
            chip(row.get("status")),
        ], style="display:flex;gap:8px;align-items:flex-start;")]
        if row.get("message"):
            mobile.append(node("div", row["message"],
                               style="font-size:12px;opacity:.7;overflow-wrap:anywhere;"))
        meta = []
        sz = human_size(row.get("size"))
        if sz:
            meta.append(sz)
        if row.get("remote_dir"):
            meta.append("→ " + row["remote_dir"])
        if row.get("time"):
            meta.append(row["time"])
        if meta:
            mobile.append(node("div", " · ".join(meta),
                               style="font-size:11px;opacity:.5;"))
        hist_rows.append(node("div", content=mobile,
                              style="padding:10px 0;border-bottom:1px solid rgba(128,128,128,.08);"))

    page.append(node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-history", **{"class": "mr-2"}),
            node("span", "秒传记录"),
            node("VChip", str(len(hist)), size="small", variant="tonal",
                 **{"class": "ml-2"}),
        ], **{"class": "d-flex align-center text-subtitle-1 font-weight-bold"}),
        node("div", content=hist_rows,
             style="max-height:400px;overflow-y:auto;padding:0 16px 8px;") if hist_rows else
        node("VCardText", "尚无秒传记录。在设置中填写 Cookie 和本地路径后点击「立即秒传」。",
             **{"class": "text-body-2 text-medium-emphasis py-5"}),
    ], variant="outlined", **{"class": "rounded-lg"}))

    # Footer
    page.append(node("div",
                     "默认目标：{} · Cookie：{}".format(
                         snapshot.get("remote_dir", "/"),
                         "已配置" if snapshot.get("has_cookie") else "未配置"),
                     **{"class": "text-caption text-medium-emphasis mt-3",
                        "style": "overflow-wrap:anywhere;"}))

    return page


DEFAULTS = {
    "cookie": "",
    "user_agent": "",
    "remote_dir": "/",
    "local_paths": "",
    "extensions": "",
}


class UiMixin:
    @staticmethod
    def get_render_mode():
        return "vuetify", None

    def get_page(self):
        try:
            self._ensure_init()
            status = self.api_status()
            return render_page(status, type(self).__name__)
        except Exception as exc:
            return [node("VAlert",
                         "页面渲染失败：{}。请保存设置后刷新。".format(exc),
                         type="error", variant="tonal")]

    def get_form(self):
        self._ensure_init()

        # Dynamic local mount points
        local_options = self._scan_local_options()

        # Real 115 directories from Cookie (or fallback if no cookie)
        remote_options = self._scan_remote_options()
        # Filter out None entries from error fallback
        remote_options = [r for r in remote_options if r is not None]

        def field(key, label, component="VTextField", md=6, **props):
            return node("VCol", content=[node(component, model=key, label=label,
                        **{"density": "comfortable", "persistent-hint": True,
                           **props})], cols=12, md=md)

        def row(*items):
            return node("VRow", content=list(items))

        def heading(title, description, color="primary"):
            return node("VCard", content=[
                node("VCardTitle", title),
                node("VCardText", description),
            ], variant="tonal", color=color, **{"class": "my-3 rounded-lg"})

        content = [
            heading("115 网页 Cookie",
                    "填写 115 网页 Cookie（包含 UID/CID/SEID）。本插件不自动扫描，仅手动秒传时使用。"),
            row(field("cookie", "115 网页 Cookie", "VTextarea", 12, rows=3,
                      hint="从浏览器复制完整 Cookie")),

            heading("秒传路径",
                    "点击下拉选择本地文件夹（可多选），文件夹会递归秒传所有媒体文件。"
                    "115 目标目录可从下拉选择或手动输入。", "info"),
            row(field("local_paths", "本地文件/文件夹（点击选择，可多选）",
                      "VSelect", 12,
                      items=local_options,
                      multiple=True, chips=True, closable_chips=True, clearable=True,
                      hint="列出 MP 容器内的挂载目录及其子目录；选择后保存设置再点秒传。")),
            row(field("remote_dir", "115 目标目录（可选择网盘真实目录或手动输入）",
                      "VCombobox",
                      items=remote_options,
                      clearable=True,
                      placeholder="/媒体/电影",
                      hint="网盘目标路径，不存在时自动创建；留空或 / 为根目录"),
                field("extensions", "限制扩展名（可选）",
                      placeholder="mkv,mp4,srt",
                      hint="留空使用默认媒体扩展名列表；多个用逗号分隔")),

            heading("其他", "高级选项，一般不需要修改。", "default"),
            row(field("user_agent", "115 User-Agent（可选）", md=12,
                      hint="留空使用内置 UA")),
        ]
        return [node("VForm", content=content)], deepcopy(DEFAULTS)
