"""MoviePilot V2 native UI. PageRender always supplies a default slot: use explicit
VTable rows / native cards, never a VDataTable driven solely through items props.
"""
from __future__ import annotations

from copy import deepcopy
from .config import DEFAULTS, human_size, stamp

STATUS = {"success": ("秒传成功", "success"), "failed": ("失败", "error"), "skipped": ("跳过", "secondary"),
          "retry": ("待重试", "warning"), "exhausted": ("重试已达上限", "error"), "pending": ("待处理", "info"),
          "processing": ("秒传中", "primary"), "uploading": ("秒传中", "primary"), "waiting": ("等待稳定", "warning"),
          "blocked": ("暂不可处理", "warning"), "ready": ("就绪", "info"), "indexing": ("索引中", "primary"),
          "error": ("读取失败", "error"), "legacy": ("旧版已处理标记", "secondary"), "info": ("记录", "secondary")}
SOURCES = {"local": "本地", "qb": "qB", "retry": "本地重试", "legacy": "历史记录"}


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
    label, color = STATUS.get(str(status), (str(status or "未运行"), "secondary"))
    return node("VChip", label, color=color, variant="tonal", size="small")


def action(plugin_id, title, route, icon="mdi-refresh", method="post", color="primary"):
    button = node("VBtn", title, variant="tonal", color=color, **{"prepend-icon": icon, "class": "ma-1", "size": "small"})
    button["events"] = {"click": {"api": f"plugin/{plugin_id}/{route}", "method": method, "params": {}}}
    return button


def section(title, icon, rows, columns, empty, total=None):
    """Explicit tbody + mobile cards: data survives PageRender's default slot."""
    total = len(rows) if total is None else total
    heading = node("VCardTitle", content=[node("VIcon", icon=icon, **{"class": "mr-2"}),
                   node("span", title), node("VChip", total, size="small", variant="tonal", **{"class": "ml-2"})],
                   **{"class": "d-flex align-center text-subtitle-1 font-weight-bold"})
    body = [heading]
    if rows:
        table_rows, cards = [], []
        for row in rows:
            cells = []
            for key, label in columns:
                value = row.get(key, "—")
                cell_children = [chip(row.get("status"))] if key == "status" else [node("span", value)]
                cells.append(node("td", content=cell_children,
                                  style="overflow-wrap:anywhere;word-break:break-word;max-width:360px;white-space:normal;padding:10px 12px;"))
            table_rows.append(node("tr", content=cells))
            main = row.get("name") or row.get("path") or "记录"
            mobile = [node("div", content=[node("strong", main, style="flex:1;min-width:0;overflow-wrap:anywhere;"),
                                           chip(row.get("status"))], style="display:flex;gap:8px;align-items:flex-start;")]
            for key, label in columns:
                if key in {"name", "status"} or row.get(key) in ("", None):
                    continue
                mobile.append(node("div", f"{label}：{row.get(key, '—')}",
                                   style="font-size:12px;line-height:1.7;overflow-wrap:anywhere;opacity:.85;"))
            cards.append(node("div", content=mobile, style="padding:12px;border-bottom:1px solid rgba(128,128,128,.15);"))
        table = node("VTable", content=[
            node("thead", content=[node("tr", content=[node("th", label, style="white-space:nowrap;padding:10px 12px;") for _, label in columns])]),
            node("tbody", content=table_rows),
        ], density="comfortable", **{"class": "d-none d-md-block", "height": min(390, 56 + len(rows) * 68), "fixed-header": True})
        body += [table, node("div", content=cards, **{"class": "d-md-none", "style": "max-height:420px;overflow:auto;overscroll-behavior:contain;"})]
        if total > len(rows):
            body.append(node("VCardText", f"共 {total} 条，本页展示最近/最先 {len(rows)} 条。状态接口支持 offset 分页。", **{"class": "text-caption"}))
    else:
        body.append(node("VCardText", empty, **{"class": "text-body-2 text-medium-emphasis py-5"}))
    return node("VCard", content=body, variant="outlined", **{"class": "rounded-lg mb-4", "style": "min-width:0;overflow:hidden;"})


def render_page(snapshot: dict, plugin_id: str, include_actions: bool = True):
    data = deepcopy(snapshot)
    stats = data["stats"]
    phase = {"indexing": "扫描本地文件", "ready": "索引完成", "uploading": "处理本地队列", "retry": "处理重试队列", "qb": "检查qB任务", "idle": "空闲"}.get(data["phase"], data["phase"])
    header = node("VCard", content=[
        node("VCardTitle", content=[
            node("VIcon", icon="mdi-cloud-upload", color="primary", **{"class": "mr-2"}),
            node("span", "115 网盘秒传"),
        ], **{"class": "d-flex align-center text-h6 font-weight-bold"}),
        node("VCardText", f"{phase} · v{data['version']} · 快照 {data['snapshot_at']}", **{"class": "pt-0 text-caption text-medium-emphasis"}),
        node("VCardText", content=[
            action(plugin_id, "刷新显示", "refresh", method="get", icon="mdi-refresh"),
            action(plugin_id, "扫描并秒传", "scan", "mdi-cloud-upload"),
            action(plugin_id, "刷新本地队列", "index", "mdi-folder-search"),
            action(plugin_id, "重试失败文件", "retry", "mdi-restart", color="warning"),
        ], **{"class": "pt-0 d-flex flex-wrap"}),
    ], variant="outlined", **{"class": "rounded-lg mb-4"})
    if not include_actions:
        header["content"][-1] = node("VCardText", "此仪表盘由MoviePilot定时刷新；扫描和重试操作请在插件详情页执行。", **{"class": "pt-0 text-caption"})
    metrics = [("success", "已秒传", "mdi-check-circle-outline", "success"),
               ("local", "本地待处理", "mdi-folder-open-outline", "info"),
               ("retry", "待重试", "mdi-restart", "warning"),
               ("qb", "qB 任务", "mdi-download-network-outline", "primary"),
               ("indexed", "已索引", "mdi-file-document-multiple-outline", "info"),
               ("roots", "监控路径", "mdi-folder-multiple-outline", "secondary")]
    page = [header, node("VRow", content=[node("VCol", content=[node("VCard", content=[
        node("VCardText", content=[
            node("div", content=[
                node("div", stats[key], **{"class": "text-h5 font-weight-bold"}),
                node("div", title, **{"class": "text-caption text-medium-emphasis"}),
            ]),
            node("VIcon", icon=icon, color=color, **{"style": "position:absolute;top:16px;right:16px;opacity:.6;"}),
        ], **{"style": "position:relative;"})
    ], variant="outlined", **{"class": "rounded-lg"})], cols=6, md=2) for key, title, icon, color in metrics], dense=True, **{"class": "mb-3"})]
    for text in (data.get("storage_error"), data.get("qb_error"), data.get("last_error")):
        if text:
            page.append(node("VAlert", text, type="warning", variant="tonal", **{"class": "mb-3", "style": "overflow-wrap:anywhere;"}))
    for row in data["history"]:
        row["size_text"] = human_size(row.get("size"))
        row["source_text"] = SOURCES.get(row.get("source"), row.get("source", ""))
    for row in data["retry_queue"] + data["local_queue"]:
        row["size_text"] = human_size(row.get("size"))
        row["source_text"] = SOURCES.get(row.get("source"), "本地")
    for row in data["qb_queue"]:
        row["ready_text"] = f"{row.get('ready', 0)}/{row.get('total', 0)}"
    page += [
        section("整理条目", "mdi-history", data["history"], [("name", "文件"), ("status", "结果"), ("size_text", "大小"), ("message", "详情"), ("path", "源路径"), ("remote_dir", "目标目录"), ("source_text", "来源"), ("time", "时间")],
                "尚无秒传结果。成功、失败和跳过记录将在这里保留；qB等待状态独立列在下方。", stats["history"]),
        section("待重试队列", "mdi-restart", data["retry_queue"], [("name", "文件"), ("status", "状态"), ("attempts", "已失败次数"), ("message", "原因"), ("next_retry_text", "下次重试"), ("remote_dir", "原目标目录"), ("source_text", "来源")],
                "当前没有待重试文件。重试达到上限的项目仍会保留并标明原因。", stats["retry"]),
        section("本地待处理队列", "mdi-folder-play", data["local_queue"], [("name", "文件"), ("status", "状态"), ("size_text", "大小"), ("path", "本地路径"), ("message", "说明")],
                ("本地队列为空。上次索引：" + data["last_index"] if data["last_index"] else "尚未完成本地索引。填写手动路径后，点击「刷新本地队列」可只读发现文件。"), stats["local"]),
        section("qB 联动任务", "mdi-download-network", data["qb_queue"], [("name", "种子"), ("status", "状态"), ("ready_text", "就绪文件"), ("path", "MP内路径"), ("message", "诊断")],
                "未发现待处理qB任务，或未启用qB联动。任务等待文件稳定时也会显示，不会冒充成功记录。", stats["qb"]),
        section("本地监控路径", "mdi-folder-multiple", data["roots"], [("path", "容器内路径"), ("status", "索引状态"), ("file_count", "媒体文件数"), ("message", "说明")],
                "尚未配置或索引本地路径。目录仍使用手动填写，不再构建目录树。"),
    ]
    if data.get("legacy_processed"):
        page.append(section("旧版已处理文件（原明细缺失）", "mdi-archive-outline", data["legacy_processed"],
                            [("name", "文件"), ("path", "原路径"), ("status", "记录类型"), ("message", "说明")], "", stats.get("legacy")))
    page.append(node("div", f"最近本地秒传：{data['last_scan'] or '尚未执行'} · 最近qB检查：{data['last_qb'] or '尚未执行'} · 115目标：{data['remote_dir']}", **{"class": "text-caption text-medium-emphasis", "style": "overflow-wrap:anywhere;"}))
    return page


class UiMixin:
    @staticmethod
    def get_render_mode():
        return "vuetify", None

    def get_page(self):
        return render_page(self._snapshot(limit=100), type(self).__name__)

    def get_dashboard_meta(self):
        return [{"key": "main", "name": "115秒传主面板"}]

    def get_dashboard(self, key: str = "main", **kwargs):
        if key not in (None, "", "main"):
            return None
        return ({"cols": 12, "md": 12},
                {"title": "115网盘秒传", "subtitle": "整理记录 · 重试队列 · 本地队列 · qB诊断", "refresh": 10, "border": False},
                render_page(self._snapshot(limit=50), type(self).__name__, include_actions=False))

    def get_form(self):
        """Keep manual fields and original groups. Constructing a form performs no IO."""
        def field(key, label, component="VTextField", md=6, **props):
            return node("VCol", content=[node(component, model=key, label=label,
                        **{"density": "comfortable", "persistent-hint": True, **props})], cols=12, md=md)

        def row(*items):
            return node("VRow", content=list(items))

        def heading(title, description, color="primary"):
            return node("VCard", content=[node("VCardTitle", title), node("VCardText", description)],
                        variant="tonal", color=color, **{"class": "my-3 rounded-lg"})

        content = [
            row(field("enabled", "启用定时扫描", "VSwitch", 4), field("onlyonce", "保存后立即运行一次", "VSwitch", 4),
                field("notify", "发送完成通知", "VSwitch", 4)),
            heading("文件副作用（默认关闭）", "失败移动和成功删除都默认关闭；开启前确认路径和文件安全策略。", "warning"),
            row(field("failure_move_on", "失败移动时机", "VSelect", 12,
                      items=[{"title": "每次失败（首次归档，后续在新路径重试）", "value": "each_failure"},
                             {"title": "达到重试上限后（需设置有限次数）", "value": "exhausted"}],
                      hint="网络／登录错误也算失败，远端结果可能未知；文件变化则保留。qB按文件失败次数判断。")),
            row(field("failure_move_enabled", "启用失败文件移动", "VSwitch", 4),
                field("failure_move_dir", "失败文件目录", md=8, placeholder="/media/failed",
                      hint="不能位于监控目录内，避免循环扫描")),
            row(field("failure_move_preserve_structure", "失败移动保留原目录结构", "VSwitch", 6),
                field("delete_on_success", "秒传明确成功后删除原文件", "VSwitch", 6,
                      hint="删除／移动会影响qB做种；删除前复核签名，变化则保留")),
            heading("🔐 115 网页 Cookie 登录", "只用115网页Cookie；目录由下方手动填写。保存设置不会遍历目录或请求网盘。"),
            row(field("cookie", "115 网页 Cookie", "VTextarea", 12, rows=3,
                      hint="填写包含 UID / CID / SEID 的 Cookie；请勿填开放平台令牌。")),
            row(field("watch_paths", "本地监控目录", "VTextarea", 6, rows=2,
                      placeholder="/media/电影\n/media/电视剧", hint="MP容器内绝对路径；多个目录用换行或逗号分隔。"),
                field("remote_dir", "115 目标目录", placeholder="/媒体/电影",
                      hint="留空或 / 为网盘根目录；目标不存在时创建，失败时不自动改传根目录。")),
            heading("⚙️ 扫描与重试", "启用后立即扫描一次，之后按间隔执行；失败文件保留原目标目录，达到重试上限也不会消失。"),
            row(field("extensions", "处理的文件扩展名", md=12, placeholder="mkv,mp4,srt,ass",
                      hint="留空使用视频、字幕、音频默认列表；默认保留源文件。")),
            row(field("scan_interval", "扫描间隔（分钟）", md=4, type="number", min=1),
                field("retry_interval", "失败重试间隔（秒）", md=4, type="number", min=30),
                field("max_attempts", "最大重试次数（0为不限）", md=4, type="number", min=0)),
            row(field("retry_notfound", "115明确未命中也重试", "VSwitch", 12,
                      hint="关闭时只跳过status=1；网络错误和未知返回不会被当成未命中。")),
            heading("🧲 qBittorrent 下载完成联动（可选）", "所有选中的媒体文件稳定且秒传成功后才标记已整理。等待原因直接显示在主页。", "info"),
            row(field("qb_enabled", "启用qB联动", "VSwitch", 4),
                field("qb_host", "qB地址（留空自动读MP下载器）", md=8, placeholder="http://qbittorrent:8080")),
            row(field("qb_username", "qB用户名", md=4), field("qb_password", "qB密码", md=4, type="password"),
                field("qb_done_tag", "全部成功后添加的标签", md=4, hint="默认：已整理")),
            row(field("qb_interval", "qB检查间隔（秒）", type="number", min=3),
                field("qb_settle", "文件稳定等待（秒）", type="number", min=0, hint="按完整秒数等待，0为不额外等待。")),
            row(field("qb_path_mappings", "qB → MP 路径映射（可选）", "VTextarea", 12, rows=2,
                      placeholder="/downloads=>/media/downloads", hint="两个容器的路径不同才填写；每行一条qB前缀=>MP前缀，不自动猜路径。")),
            row(field("user_agent", "115 User-Agent（可选）", md=12, hint="留空保留内置网页UA。")),
        ]
        return [node("VForm", content=content)], deepcopy(DEFAULTS)
