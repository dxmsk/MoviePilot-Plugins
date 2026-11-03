"""插件首页自刷新单页应用（视觉升级 + 移动端适配）。

通过 VHtml 渲染，内部直接调用插件 API：
  GET  /api/v1/plugin/__PREFIX__/status        实时统计 + 历史 + 重试队列
  POST /api/v1/plugin/__PREFIX__/scan          立即扫描并秒传
  GET  /api/v1/plugin/__PREFIX__/test          测试 115 凭据

占位符：__PREFIX__ 替换为 plugin_id。
"""

HOMEPAGE_HTML = r"""
<div id="v115app" class="v115app">
  <!-- Hero -->
  <div class="v115-hero">
    <div class="v115-hero-ic">☁️</div>
    <div class="v115-hero-txt">
      <div class="v115-hero-t">115 网盘秒传</div>
      <div class="v115-hero-s">SHA1 秒传 · 只读原文件 · qB 下载完成即推送</div>
    </div>
    <div id="v115-state" class="v115-badge v115-badge-0">· · ·</div>
  </div>

  <!-- 操作栏 -->
  <div class="v115-actions">
    <button id="v115-scan" onclick="v115Scan()" class="v115-act v115-act-primary">
      <span class="ic">🚀</span><span>立即扫描秒传</span></button>
    <button id="v115-test" onclick="v115Test()" class="v115-act">
      <span class="ic">🔑</span><span>测试凭据</span></button>
    <button onclick="v115Refresh()" class="v115-act">
      <span class="ic">🔄</span><span>刷新</span></button>
    <span id="v115-auto" class="v115-auto">自动刷新 5s</span>
  </div>
  <div id="v115-toast" class="v115-toast"></div>

  <!-- 统计卡 -->
  <div class="v115-grid">
    <div class="v115-stat v115-g1"><div class="v115-stat-ic">🚀</div>
      <div><div class="v115-stat-num" id="v115-done">0</div><div class="v115-stat-lbl">已秒传</div></div></div>
    <div class="v115-stat v115-g2"><div class="v115-stat-ic">🔁</div>
      <div><div class="v115-stat-num" id="v115-retry">0</div><div class="v115-stat-lbl">待重试</div></div></div>
    <div class="v115-stat v115-g3"><div class="v115-stat-ic">🕐</div>
      <div><div class="v115-stat-num v115-sm" id="v115-last">—</div><div class="v115-stat-lbl">最近扫描</div></div></div>
    <div class="v115-stat v115-g4"><div class="v115-stat-ic">⚡</div>
      <div><div class="v115-stat-num v115-sm" id="v115-run">空闲</div><div class="v115-stat-lbl">运行状态</div></div></div>
  </div>

  <!-- 待重试 -->
  <div id="v115-retrybox" class="v115-sect" style="display:none">
    <div class="v115-sect-h"><span class="ic">🔁</span>待重试队列<span id="v115-retrycnt" class="v115-chip">0</span></div>
    <div id="v115-retrylist" class="v115-list"></div>
  </div>

  <!-- 整理条目 -->
  <div class="v115-sect">
    <div class="v115-sect-h">
      <span class="ic">📋</span>整理条目
      <span id="v115-histcnt" class="v115-chip">0</span>
      <div class="v115-filter">
        <button class="v115-fbtn v115-fbtn-on" data-f="all" onclick="v115Filter('all',this)">全部</button>
        <button class="v115-fbtn" data-f="ok" onclick="v115Filter('ok',this)">成功</button>
        <button class="v115-fbtn" data-f="fail" onclick="v115Filter('fail',this)">失败</button>
      </div>
    </div>
    <div id="v115-histlist" class="v115-list">
      <div class="v115-empty">加载中…</div>
    </div>
  </div>
</div>
"""

HOMEPAGE_HTML += r"""
<style>
.v115app{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;color:rgb(var(--v-theme-on-surface,44,44,58))}
.v115-hero{display:flex;align-items:center;gap:16px;padding:16px 20px;border-radius:14px;
  border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgb(var(--v-theme-on-surface,44,44,58))}
.v115-hero-ic{font-size:28px;line-height:1;color:rgb(var(--v-theme-primary,109,74,255));opacity:.7}
.v115-hero-txt{flex:1;min-width:0}
.v115-hero-t{font-size:18px;font-weight:700}
.v115-hero-s{font-size:12px;opacity:.6;margin-top:2px}
.v115-badge{flex:0 0 auto;font-size:12px;font-weight:600;padding:5px 12px;border-radius:999px;white-space:nowrap}
.v115-badge-1{background:rgba(var(--v-theme-success,76,175,80),.15);color:rgb(var(--v-theme-success,76,175,80))}
.v115-badge-0{background:rgba(var(--v-theme-warning,255,152,0),.15);color:rgb(var(--v-theme-warning,255,152,0))}

.v115-actions{display:flex;gap:10px;align-items:center;margin-top:14px;flex-wrap:wrap}
.v115-act{display:inline-flex;align-items:center;gap:7px;padding:9px 16px;border-radius:11px;cursor:pointer;
  font-size:13.5px;font-weight:600;border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgb(var(--v-theme-on-surface,44,44,58));transition:all .15s}
.v115-act .ic{font-size:15px}
.v115-act:hover{border-color:rgb(var(--v-theme-primary,109,74,255));color:rgb(var(--v-theme-primary,109,74,255))}
.v115-act:disabled{opacity:.55;cursor:not-allowed}
.v115-act-primary{border-color:rgb(var(--v-theme-primary,109,74,255));color:rgb(var(--v-theme-primary,109,74,255));font-weight:700}
.v115-auto{font-size:11.5px;color:#99a;margin-left:auto}
.v115-toast{margin-top:10px;font-size:13px;line-height:1.5;display:none;padding:10px 14px;border-radius:10px}
.v115-toast.ok{display:block;background:rgba(var(--v-theme-success,76,175,80),.1);color:rgb(var(--v-theme-success,76,175,80));border:1px solid rgba(var(--v-theme-success,76,175,80),.3)}
.v115-toast.err{display:block;background:rgba(var(--v-theme-error,244,67,54),.1);color:rgb(var(--v-theme-error,244,67,54));border:1px solid rgba(var(--v-theme-error,244,67,54),.3)}
.v115-toast.info{display:block;background:rgba(var(--v-theme-info,33,150,243),.1);color:rgb(var(--v-theme-info,33,150,243));border:1px solid rgba(var(--v-theme-info,33,150,243),.3)}

.v115-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}
@media(max-width:860px){.v115-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:430px){.v115-grid{grid-template-columns:repeat(2,1fr);gap:10px}}
.v115-stat{display:flex;align-items:center;gap:12px;padding:15px 16px;border-radius:14px;
  border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgb(var(--v-theme-on-surface,44,44,58))}
.v115-g1,.v115-g2,.v115-g3,.v115-g4{}
.v115-stat-ic{font-size:22px;line-height:1;flex:0 0 auto;opacity:.6}
.v115-stat-num{font-size:22px;font-weight:800;line-height:1.2}
.v115-sm{font-size:14px;font-weight:700}
.v115-stat-lbl{font-size:11.5px;opacity:.92;margin-top:3px}

.v115-sect{margin-top:18px;border-radius:14px;padding:4px 0 8px;
  border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255))}
.v115-sect-h{display:flex;align-items:center;gap:8px;padding:14px 18px 10px;font-size:15px;font-weight:700;color:rgb(var(--v-theme-on-surface,44,44,58))}
.v115-sect-h .ic{font-size:17px;opacity:.6}
.v115-chip{font-size:12px;font-weight:700;color:rgb(var(--v-theme-primary,109,74,255));background:rgba(var(--v-theme-primary,109,74,255),.1);
  padding:2px 10px;border-radius:999px}
.v115-filter{margin-left:auto;display:flex;gap:6px}
.v115-fbtn{font-size:12px;padding:4px 12px;border-radius:999px;border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgba(var(--v-theme-on-surface,44,44,58),.7);cursor:pointer;font-weight:600;transition:all .12s}
.v115-fbtn-on{background:rgb(var(--v-theme-primary,109,74,255));color:#fff;border-color:transparent}

.v115-list{padding:0 10px}
.v115-empty{padding:28px 16px;text-align:center;color:#9aa;font-size:13px}
.v115-card{display:flex;align-items:center;gap:12px;padding:12px 12px;border-radius:12px;margin:6px 2px;
  background:rgb(var(--v-theme-surface,255,255,255));border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));transition:background .12s}
.v115-card:hover{background:rgba(var(--v-theme-primary,109,74,255),.04)}
.v115-card .emo{font-size:20px;flex:0 0 auto;opacity:.6}
.v115-card .mid{flex:1;min-width:0}
.v115-card .nm{font-size:14px;font-weight:600;color:rgb(var(--v-theme-on-surface,44,44,58));white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.v115-card .meta{font-size:11.5px;color:rgba(var(--v-theme-on-surface,44,44,58),.55);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.v115-card .right{flex:0 0 auto;text-align:right}
.v115-card .tag{font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap}
.v115-tag-ok{color:rgb(var(--v-theme-success,76,175,80));background:rgba(var(--v-theme-success,76,175,80),.12)}
.v115-tag-fail{color:rgb(var(--v-theme-error,244,67,54));background:rgba(var(--v-theme-error,244,67,54),.12)}
.v115-card .tm{font-size:11px;color:rgba(var(--v-theme-on-surface,44,44,58),.4);margin-top:4px}
@media(max-width:430px){
  .v115-hero-t{font-size:17px}.v115-act{flex:1;justify-content:center}
  .v115-auto{width:100%;text-align:right;margin-top:2px}
  .v115-card .meta{white-space:normal}
}
</style>
"""

HOMEPAGE_HTML += r"""
<script>
(function(){
  var API = "/api/v1/plugin/__PREFIX__";
  var timer = null, filterMode = "all", lastData = null;

  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }
  function fsize(b){ b=Number(b)||0; if(b<1024)return b+" B";
    var u=["KB","MB","GB","TB"],i=-1; do{b/=1024;i++;}while(b>=1024&&i<3);
    return b.toFixed(b<10?1:0)+" "+u[i]; }
  function isOk(r){ r=String(r||""); return (r.indexOf("成功")>=0)||(r.indexOf("秒传")>=0&&r.indexOf("失败")<0); }
  function toast(cls,msg){ var t=document.getElementById("v115-toast");
    t.className="v115-toast "+cls; t.textContent=msg;
    if(cls!=="info"){ setTimeout(function(){ t.className="v115-toast"; },6000); } }

  function g(id){ return document.getElementById(id); }

  function render(d){
    lastData = d;
    var on = !!d.enabled;
    var st = g("v115-state");
    st.className = "v115-badge v115-badge-"+(on?"1":"0");
    st.textContent = on ? "已启用" : "未启用";
    g("v115-done").textContent  = d.done_count || 0;
    g("v115-retry").textContent = d.retry_count || 0;
    g("v115-last").textContent  = d.last_run || "尚未运行";
    g("v115-run").textContent   = d.running ? "扫描中…" : "空闲";
    g("v115-scan").disabled = !!d.running;

    // 待重试
    var rq = d.retry_queue || [];
    g("v115-retrycnt").textContent = rq.length;
    g("v115-retrybox").style.display = rq.length ? "block" : "none";
    if(rq.length){
      g("v115-retrylist").innerHTML = rq.slice(0,30).map(function(it){
        return '<div class="v115-card"><span class="emo">🔁</span>'+
          '<div class="mid"><div class="nm">'+esc(it.name)+'</div>'+
          '<div class="meta">'+esc(String(it.last_error||"等待重试").slice(0,80))+'</div></div>'+
          '<div class="right"><span class="tag v115-tag-fail">第 '+(it.attempts||0)+' 次</span></div></div>';
      }).join("");
    }

    // 历史
    var h = (d.history||[]).slice().reverse();
    var shown = h.filter(function(x){
      if(filterMode==="all") return true;
      var ok = isOk(x.result);
      return filterMode==="ok" ? ok : !ok;
    });
    g("v115-histcnt").textContent = h.length;
    var list = g("v115-histlist");
    if(!shown.length){
      list.innerHTML = '<div class="v115-empty">'+(h.length?"没有符合筛选的条目":"还没有整理记录，点上面「立即扫描秒传」试试")+'</div>';
    }else{
      list.innerHTML = shown.slice(0,100).map(function(x){
        var ok = isOk(x.result);
        return '<div class="v115-card"><span class="emo">'+(ok?"✅":"⚠️")+'</span>'+
          '<div class="mid"><div class="nm">'+esc(x.name)+'</div>'+
          '<div class="meta">'+esc(x.path||"")+'</div></div>'+
          '<div class="right"><span class="tag '+(ok?"v115-tag-ok":"v115-tag-fail")+'">'+
          esc(x.result||(ok?"成功":"失败"))+'</span>'+
          '<div class="tm">'+esc(x.size!=null?fsize(x.size):"")+(x.time?" · "+esc(x.time):"")+'</div></div></div>';
      }).join("");
    }
  }

  window.v115Refresh = function(){
    fetch(API+"/status",{credentials:"include"})
      .then(function(r){return r.json();})
      .then(render)
      .catch(function(e){ toast("err","状态获取失败: "+e); });
  };
  window.v115Filter = function(mode,btn){
    filterMode = mode;
    document.querySelectorAll(".v115-fbtn").forEach(function(b){ b.classList.remove("v115-fbtn-on"); });
    btn.classList.add("v115-fbtn-on");
    if(lastData) render(lastData);
  };
  window.v115Scan = function(){
    var b=g("v115-scan"); b.disabled=true;
    toast("info","已触发扫描，正在秒传…结果会在下方自动刷新");
    fetch(API+"/scan",{method:"POST",credentials:"include"})
      .then(function(r){return r.json();})
      .then(function(d){
        toast(d.success?"info":"err", d.message||(d.success?"已触发":"触发失败"));
        setTimeout(v115Refresh,1500);
      })
      .catch(function(e){ toast("err","触发失败: "+e); b.disabled=false; });
  };
  window.v115Test = function(){
    var b=g("v115-test"); b.disabled=true;
    toast("info","正在测试 115 登录凭据…");
    fetch(API+"/test",{credentials:"include"})
      .then(function(r){return r.json();})
      .then(function(d){ toast(d.success?"ok":"err", (d.success?"✅ ":"❌ ")+(d.message||"")); b.disabled=false; })
      .catch(function(e){ toast("err","测试失败: "+e); b.disabled=false; });
  };

  v115Refresh();
  timer = setInterval(v115Refresh, 5000);
})();
</script>
"""
