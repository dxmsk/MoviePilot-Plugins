"""UI for ManualPush115: fully server-rendered VNode file browser."""
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


def action_btn(plugin_id, title, route, icon="mdi-refresh", method="post",
               color="primary", params=None, **extra):
    merged = {"variant": "tonal", "size": "small", "class": "ma-1"}
    if icon:
        merged["prepend-icon"] = icon
    merged.update(extra)
    btn = node("VBtn", title, color=color, **merged)
    btn["events"] = {"click": {"api": "plugin/{}/{}".format(plugin_id, route),
                                "method": method, "params": params or {}}}
    return btn


def chip(status):
    colors = {"success": ("成功", "success"), "failed": ("失败", "error")}
    label, color = colors.get(str(status), (str(status or ""), "secondary"))
    return node("VChip", label, color=color, variant="tonal", size="x-small")


def human_size(n) -> str:
    try:
        b = int(n)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
        b /= 1024
    return f"{b:.1f} PB"


def render_browser(plugin_id, browse_path, entries,
                   parent, selected, running,
                   progress, has_cookie, remote_dir,
                   history, version):
    pid = plugin_id
    page = []

    # Header
    page.append(node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-cloud-upload-outline", color="primary", **{"class": "mr-2"}),
            node("span", "手动秒传 115"),
            node("VChip", "秒传中…" if running else "空闲",
                 color="primary" if running else "default",
                 variant="tonal", size="small", **{"class": "ml-3"}),
        ], **{"class": "d-flex align-center text-h6 font-weight-bold"}),
        node("VCardText", f"选择文件或文件夹 → 点击秒传 · 目标：{remote_dir} · v{version}",
             **{"class": "pt-0 text-caption text-medium-emphasis"}),
    ], variant="outlined", **{"class": "rounded-lg mb-4"}))

    # Progress
    if running and progress:
        page.append(node("VAlert", progress, type="info", variant="tonal", **{"class": "mb-3"}))
    elif progress and not running:
        page.append(node("VAlert", progress, type="success", variant="tonal", **{"class": "mb-3"}))

    # Selected items + actions
    sel_count = len(selected)
    action_row = [
        action_btn(pid, f"🚀 秒传选中 ({sel_count})", "push", "mdi-cloud-upload",
                   color="primary" if sel_count and has_cookie and not running else "default",
                   disabled=not sel_count or not has_cookie or running,
                   params={"remote_dir": remote_dir}),
        action_btn(pid, "全选当前目录", "select", "mdi-checkbox-multiple-marked",
                   color="default", params={"action": "select_all_files"}),
        action_btn(pid, "清空选择", "clear", "mdi-close-circle-outline", color="warning"),
        action_btn(pid, "测试凭据", "test", "mdi-key", color="default"),
    ]
    page.append(node("div", content=action_row,
                     style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px;"))

    # Selected files summary
    if selected:
        sel_names = list(selected.values())[:8]
        sel_text = "、".join(item.get("name", "?") for item in sel_names)
        if len(selected) > 8:
            sel_text += f" 等共 {len(selected)} 项"
        page.append(node("VAlert", f"已选择：{sel_text}", type="info", variant="tonal",
                         density="compact", **{"class": "mb-3"}))

    # Breadcrumb navigation
    bread = []
    bread.append(action_btn(pid, "根目录", "navigate", "mdi-home", color="default",
                           params={"path": "/"}, variant="text", size="x-small"))
    if browse_path and browse_path != "/":
        parts = browse_path.split("/")
        acc = ""
        for part in parts:
            if not part:
                continue
            acc += "/" + part
            bread.append(node("span", " / ", style="opacity:.4;"))
            bread.append(action_btn(pid, part, "navigate", "", color="default",
                                   params={"path": acc}, variant="text", size="x-small"))
    page.append(node("div", content=bread,
                     style="display:flex;align-items:center;flex-wrap:wrap;gap:2px;padding:8px 4px;margin-bottom:8px;"))

    # File listing
    file_rows = []
    if parent is not None:
        row = action_btn(pid, "⬆️ 返回上级目录", "navigate", "mdi-arrow-up",
                        color="default", params={"path": parent},
                        variant="text", block=True, **{"class": "justify-start"})
        file_rows.append(row)

    for entry in entries:
        path = entry["path"]
        name = entry["name"]
        is_selected = path in selected

        if entry["is_dir"]:
            # Directory: click navigates into it, with a select toggle
            row_content = [
                action_btn(pid, "", "select", "mdi-checkbox-marked" if is_selected else "mdi-checkbox-blank-outline",
                          color="primary" if is_selected else "default",
                          params={"path": path, "action": "toggle"},
                          variant="text", size="x-small", **{"min-width": "36px"}),
                action_btn(pid, f"📁 {name}", "navigate", "",
                          color="primary", params={"path": path},
                          variant="text", size="small", **{"class": "justify-start font-weight-bold", "style": "flex:1;text-transform:none;letter-spacing:0;"}),
            ]
            file_rows.append(node("div", content=row_content,
                                  style="display:flex;align-items:center;gap:4px;padding:2px 0;border-bottom:1px solid rgba(128,128,128,.08);"))
        else:
            # File: click toggles selection
            size_text = entry.get("size_text") or human_size(entry.get("size"))
            row_content = [
                action_btn(pid, "", "select",
                          "mdi-checkbox-marked" if is_selected else "mdi-checkbox-blank-outline",
                          color="primary" if is_selected else "default",
                          params={"path": path, "action": "toggle"},
                          variant="text", size="x-small", **{"min-width": "36px"}),
                node("span", f"📄 {name}", style="flex:1;min-width:0;font-size:14px;overflow-wrap:anywhere;"),
                node("span", size_text, style="font-size:12px;opacity:.5;white-space:nowrap;margin-left:8px;"),
            ]
            file_rows.append(node("div", content=row_content,
                                  style="display:flex;align-items:center;gap:4px;padding:4px 0;border-bottom:1px solid rgba(128,128,128,.08);cursor:pointer;"))

    if not entries and browse_path == "/":
        file_rows.append(node("VCardText", "未检测到常用媒体目录。请检查容器挂载路径。",
                             **{"class": "text-body-2 text-medium-emphasis py-5"}))
    elif not entries:
        file_rows.append(node("VCardText", "目录为空或无符合条件的文件",
                             **{"class": "text-body-2 text-medium-emphasis py-5"}))

    page.append(node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-folder-open", **{"class": "mr-2"}),
            node("span", browse_path or "/"),
        ], **{"class": "d-flex align-center text-subtitle-1 font-weight-bold"}),
        node("div", content=file_rows, style="max-height:400px;overflow-y:auto;padding:0 16px 8px;"),
    ], variant="outlined", **{"class": "rounded-lg mb-4"}))

    # History
    hist_rows = []
    for row in (history or [])[:30]:
        status = row.get("status", "")
        mobile = [node("div", content=[
            node("strong", row.get("name", ""), style="flex:1;min-width:0;overflow-wrap:anywhere;"),
            chip(status),
        ], style="display:flex;gap:8px;align-items:flex-start;")]
        if row.get("message"):
            mobile.append(node("div", row["message"], style="font-size:12px;opacity:.7;overflow-wrap:anywhere;"))
        mobile.append(node("div", f"{human_size(row.get('size'))} · {row.get('time', '')}",
                          style="font-size:11px;opacity:.5;"))
        hist_rows.append(node("div", content=mobile,
                             style="padding:10px 0;border-bottom:1px solid rgba(128,128,128,.08);"))

    page.append(node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-history", **{"class": "mr-2"}),
            node("span", "秒传记录"),
            node("VChip", str(len(history or [])), size="small", variant="tonal", **{"class": "ml-2"}),
        ], **{"class": "d-flex align-center text-subtitle-1 font-weight-bold"}),
        node("div", content=hist_rows, style="max-height:320px;overflow-y:auto;padding:0 16px 8px;") if hist_rows else
        node("VCardText", "尚无秒传记录", **{"class": "text-body-2 text-medium-emphasis py-5"}),
    ], variant="outlined", **{"class": "rounded-lg mb-4"}))

    return page


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
        # type: () -> List[dict]
        import os
        try:
            self._ensure_init()
            path = getattr(self, "_browse_path", "/")
            entries = self._list_dir(path)
            parent = os.path.dirname(path) if path != "/" else None
            status = self.api_status()
            return render_browser(
                plugin_id=type(self).__name__,
                browse_path=path,
                entries=entries,
                parent=parent,
                selected=getattr(self, "_selected", {}),
                running=status.get("running", False),
                progress=status.get("progress", ""),
                has_cookie=status.get("has_cookie", False),
                remote_dir=status.get("remote_dir", "/"),
                history=status.get("history", []),
                version=status.get("version", ""),
            )
        except Exception as exc:
            return [node("VAlert", "页面渲染失败：{}。请保存设置后刷新页面。".format(exc),
                         type="error", variant="tonal")]

    def get_form(self):
        def field(key, label, component="VTextField", md=6, **props):
            return node("VCol", content=[node(component, model=key, label=label,
                        **{"density": "comfortable", "persistent-hint": True, **props})], cols=12, md=md)

        def row(*items):
            return node("VRow", content=list(items))

        content = [
            node("VCard", content=[
                node("VCardTitle", "115 网页 Cookie"),
                node("VCardText", "填写 115 网页 Cookie（包含 UID/CID/SEID）。本插件不自动扫描，仅手动秒传时使用。"),
            ], variant="tonal", color="primary", **{"class": "my-3 rounded-lg"}),
            row(field("cookie", "115 网页 Cookie", "VTextarea", 12, rows=3,
                      hint="从浏览器复制完整 Cookie")),
            row(field("remote_dir", "115 默认目标目录", placeholder="/媒体/电影",
                      hint="秒传时的默认网盘目标"),
                field("extensions", "限制文件扩展名（可选）", placeholder="mkv,mp4,srt",
                      hint="留空使用默认媒体扩展名列表")),
            row(field("user_agent", "115 User-Agent（可选）", md=12,
                      hint="留空使用内置 UA")),
        ]
        return [node("VForm", content=content)], deepcopy(DEFAULTS)
