"""顶部概览仪表盘的自包含 HTML 片段（视觉升级版）。

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
    <div class="v115-hero-ic">☁️</div>
    <div class="v115-hero-txt">
      <div class="v115-hero-t">115 网盘秒传</div>
      <div class="v115-hero-s">SHA1 秒传 · 只读原文件 · qBittorrent 下载完成即推送</div>
    </div>
    <div class="v115-badge v115-badge-__STATE_ON__">__STATE__</div>
  </div>

  <div class="v115-grid">
    <div class="v115-stat v115-g1">
      <div class="v115-stat-ic">🚀</div>
      <div class="v115-stat-body">
        <div class="v115-stat-num">__DONE__</div>
        <div class="v115-stat-lbl">已秒传文件</div>
      </div>
    </div>
    <div class="v115-stat v115-g2">
      <div class="v115-stat-ic">🔁</div>
      <div class="v115-stat-body">
        <div class="v115-stat-num">__RETRY__</div>
        <div class="v115-stat-lbl">待重试队列</div>
      </div>
    </div>
    <div class="v115-stat v115-g3">
      <div class="v115-stat-ic">🕐</div>
      <div class="v115-stat-body">
        <div class="v115-stat-num v115-stat-sm">__LASTRUN__</div>
        <div class="v115-stat-lbl">最近扫描</div>
      </div>
    </div>
    <div class="v115-stat v115-g4">
      <div class="v115-stat-ic">🔗</div>
      <div class="v115-stat-body">
        <div class="v115-stat-num v115-stat-sm">__QB__</div>
        <div class="v115-stat-lbl">qBittorrent 联动</div>
      </div>
    </div>
  </div>
</div>

<style>
.v115-dash{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;margin-bottom:4px}
.v115-hero{display:flex;align-items:center;gap:16px;padding:18px 22px;border-radius:18px;
  background:linear-gradient(135deg,#0a84ff 0%,#5e5ce6 55%,#bf5af2 100%);
  color:#fff;box-shadow:0 10px 30px -8px rgba(94,92,230,.55);position:relative;overflow:hidden}
.v115-hero::after{content:"";position:absolute;right:-40px;top:-60px;width:180px;height:180px;
  background:radial-gradient(circle,rgba(255,255,255,.22),transparent 70%);pointer-events:none}
.v115-hero-ic{font-size:40px;line-height:1;filter:drop-shadow(0 4px 8px rgba(0,0,0,.25))}
.v115-hero-txt{flex:1;min-width:0}
.v115-hero-t{font-size:20px;font-weight:700;letter-spacing:.5px}
.v115-hero-s{font-size:12.5px;opacity:.9;margin-top:3px;line-height:1.5}
.v115-badge{flex:0 0 auto;font-size:13px;font-weight:600;padding:7px 14px;border-radius:999px;
  background:rgba(255,255,255,.2);backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.35);white-space:nowrap}
.v115-badge-1{background:rgba(52,199,89,.95);box-shadow:0 0 0 3px rgba(52,199,89,.25)}
.v115-badge-0{background:rgba(255,159,10,.95);box-shadow:0 0 0 3px rgba(255,159,10,.25)}
.v115-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px}
@media(max-width:860px){.v115-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:480px){.v115-grid{grid-template-columns:1fr}}
.v115-stat{display:flex;align-items:center;gap:14px;padding:16px 18px;border-radius:16px;color:#fff;
  box-shadow:0 8px 22px -10px rgba(0,0,0,.4);transition:transform .18s ease,box-shadow .18s ease;position:relative;overflow:hidden}
.v115-stat:hover{transform:translateY(-3px);box-shadow:0 14px 30px -10px rgba(0,0,0,.5)}
.v115-stat::after{content:"";position:absolute;right:-20px;bottom:-30px;width:110px;height:110px;
  background:radial-gradient(circle,rgba(255,255,255,.18),transparent 70%)}
.v115-g1{background:linear-gradient(135deg,#34c759,#30b0c7)}
.v115-g2{background:linear-gradient(135deg,#ff9f0a,#ff375f)}
.v115-g3{background:linear-gradient(135deg,#5e5ce6,#0a84ff)}
.v115-g4{background:linear-gradient(135deg,#bf5af2,#ff2d92)}
.v115-stat-ic{font-size:30px;line-height:1;flex:0 0 auto;filter:drop-shadow(0 3px 6px rgba(0,0,0,.3))}
.v115-stat-body{min-width:0}
.v115-stat-num{font-size:26px;font-weight:800;line-height:1.1;text-shadow:0 2px 6px rgba(0,0,0,.2);word-break:break-all}
.v115-stat-sm{font-size:15px;font-weight:700}
.v115-stat-lbl{font-size:12px;opacity:.92;margin-top:4px;letter-spacing:.3px}
</style>
"""
