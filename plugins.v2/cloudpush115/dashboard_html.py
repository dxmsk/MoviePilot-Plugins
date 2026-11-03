"""顶部概览仪表盘的自包含 HTML 片段。

通过占位符注入运行时数据，由 get_page 用 VHtml 渲染：
  __STATE__   插件状态文案（已启用/未启用）
  __STATE_ON__  "1"/"0"
  __DONE__    已秒传数
  __RETRY__   待重试数
  __LASTRUN__ 最近扫描时间
  __QB__      qb 联动状态文案
  __QB_ON__   "1"/"0"
"""

DASHBOARD_HTML = r"""
<div class="v115-dash">
  <div class="v115-hero">
    <svg class="v115-hero-ic" viewBox="0 0 24 24" width="32" height="32"><path fill="currentColor" d="M19.35 10.04A7.49 7.49 0 0 0 12 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
    <div class="v115-hero-txt">
      <div class="v115-hero-t">115 网盘秒传</div>
      <div class="v115-hero-s">SHA1 秒传 · 只读原文件 · qB 下载完成即推送</div>
    </div>
    <div class="v115-badge v115-badge-__STATE_ON__">__STATE__</div>
  </div>
  <div class="v115-grid">
    <div class="v115-stat"><div class="v115-stat-body"><div class="v115-stat-num">__DONE__</div><div class="v115-stat-lbl">已秒传文件</div></div></div>
    <div class="v115-stat"><div class="v115-stat-body"><div class="v115-stat-num">__RETRY__</div><div class="v115-stat-lbl">待重试队列</div></div></div>
    <div class="v115-stat"><div class="v115-stat-body"><div class="v115-stat-num v115-stat-sm">__LASTRUN__</div><div class="v115-stat-lbl">最近扫描</div></div></div>
    <div class="v115-stat"><div class="v115-stat-body"><div class="v115-stat-num v115-stat-sm">__QB__</div><div class="v115-stat-lbl">qBittorrent 联动</div></div></div>
  </div>
</div>

<style>
.v115-dash{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;margin-bottom:4px}
.v115-hero{display:flex;align-items:center;gap:16px;padding:16px 20px;border-radius:14px;
  border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgb(var(--v-theme-on-surface,30,30,30))}
.v115-hero-ic{flex:0 0 auto;color:rgb(var(--v-theme-primary,109,74,255));opacity:.7}
.v115-hero-txt{flex:1;min-width:0}
.v115-hero-t{font-size:18px;font-weight:700}
.v115-hero-s{font-size:12px;opacity:.65;margin-top:2px}
.v115-badge{flex:0 0 auto;font-size:12px;font-weight:600;padding:5px 12px;border-radius:999px;white-space:nowrap}
.v115-badge-1{background:rgba(var(--v-theme-success,76,175,80),.15);color:rgb(var(--v-theme-success,76,175,80))}
.v115-badge-0{background:rgba(var(--v-theme-warning,255,152,0),.15);color:rgb(var(--v-theme-warning,255,152,0))}
.v115-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}
@media(max-width:860px){.v115-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:480px){.v115-grid{grid-template-columns:1fr}}
.v115-stat{padding:14px 16px;border-radius:14px;
  border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgb(var(--v-theme-on-surface,30,30,30))}
.v115-stat-body{min-width:0}
.v115-stat-num{font-size:24px;font-weight:800;line-height:1.2}
.v115-stat-sm{font-size:14px;font-weight:700}
.v115-stat-lbl{font-size:11.5px;opacity:.6;margin-top:3px}
</style>
"""
