"""可视化服务器本地目录选择器（用于选监控路径）。

通过 VHtml 渲染，调用插件 API：
  GET /api/v1/plugin/__PREFIX__/localbrowse?path=<dir>
  GET /api/v1/plugin/__PREFIX__/addpath?path=<dir>
占位符 __PREFIX__ 替换为 plugin_id。
"""

LOCAL_BROWSER_HTML = r"""
<div id="v115lb" class="v115lb">
  <div class="v115lb-pathbar">
    <span class="v115lb-pathic">💻</span>
    <span id="v115lb-path" class="v115lb-path">选择要监控的本地目录</span>
  </div>
  <div class="v115lb-tools">
    <button onclick="v115lbRoot()" class="v115lb-btn">🖥 根目录</button>
    <button id="v115lb-up" onclick="v115lbUp()" class="v115lb-btn">⬆ 上级</button>
    <button onclick="v115lbReload()" class="v115lb-btn">🔄 刷新</button>
    <button onclick="v115lbAdd()" class="v115lb-btn v115lb-btn-primary">➕ 加入监控</button>
  </div>
  <div id="v115lb-list" class="v115lb-list"><div class="v115lb-empty">加载中…</div></div>
  <div id="v115lb-msg" class="v115lb-msg"></div>
</div>
<style>
.v115lb{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
.v115lb-pathbar{display:flex;align-items:center;gap:8px;margin-bottom:10px;padding:8px 12px;border-radius:10px;
  background:linear-gradient(135deg,#eafff1,#eef4ff);border:1px solid rgba(52,199,89,.2)}
.v115lb-pathic{font-size:14px}
.v115lb-path{font-size:13px;color:#2c5c3a;flex:1;word-break:break-all;font-weight:500}
.v115lb-tools{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.v115lb-btn{padding:7px 14px;border:1px solid #dfe8e2;border-radius:9px;background:#fff;cursor:pointer;font-size:13px;
  color:#445;transition:all .15s;font-weight:500}
.v115lb-btn:hover{border-color:#34c759;color:#1a7f37;box-shadow:0 2px 8px -3px rgba(52,199,89,.4)}
.v115lb-btn-primary{border:none;color:#fff;background:linear-gradient(135deg,#34c759,#30b0c7);
  box-shadow:0 5px 14px -5px rgba(52,199,89,.6)}
.v115lb-btn-primary:hover{color:#fff;transform:translateY(-1px)}
.v115lb-list{border:1px solid #eceef5;border-radius:12px;max-height:340px;overflow:auto;background:#fff}
.v115lb-list::-webkit-scrollbar{width:8px}
.v115lb-list::-webkit-scrollbar-thumb{background:#d6d9ea;border-radius:8px}
.v115lb-empty{padding:28px 16px;color:#99a;text-align:center;font-size:13px}
.v115lb-item{padding:11px 16px;border-bottom:1px solid #f4f5fa;cursor:pointer;display:flex;align-items:center;gap:10px;transition:background .12s}
.v115lb-item:last-child{border-bottom:none}
.v115lb-item:hover{background:linear-gradient(90deg,rgba(52,199,89,.07),rgba(48,176,199,.04))}
.v115lb-item .ic{font-size:18px}
.v115lb-item .nm{flex:1;font-size:14px;color:#334;word-break:break-all}
.v115lb-item .wt{font-size:11px;font-weight:700;color:#1a7f37;background:rgba(52,199,89,.14);padding:2px 8px;border-radius:999px}
.v115lb-item .ar{color:#bbc;font-size:16px}
.v115lb-msg{margin-top:10px;font-size:13px;line-height:1.6}
</style>
<script>
(function(){
  var API = "/api/v1/plugin/__PREFIX__";
  var state = { path:"", parent:"", is_root:true };
  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }

  window.v115lbLoad = function(path){
    var list=document.getElementById("v115lb-list"), msg=document.getElementById("v115lb-msg");
    list.innerHTML='<div class="v115lb-empty">加载中…</div>'; msg.textContent="";
    fetch(API+"/localbrowse?path="+encodeURIComponent(path||""),{credentials:"include"})
      .then(function(r){return r.json();})
      .then(function(d){
        if(!d.success){ list.innerHTML='<div class="v115lb-empty" style="color:#e5484d">'+esc(d.message||"加载失败")+'</div>'; return; }
        state.path=d.path; state.parent=d.parent; state.is_root=d.is_root;
        document.getElementById("v115lb-path").textContent = d.is_root ? "选择要监控的本地目录（常见根目录）" : d.path;
        var es=d.entries||[];
        if(!es.length){ list.innerHTML='<div class="v115lb-empty">（没有可进入的子目录）</div>'; return; }
        list.innerHTML = es.map(function(e){
          var wt = e.watched ? '<span class="wt">已监控</span>' : '';
          return '<div class="v115lb-item" onclick="v115lbEnter(\''+esc(e.path).replace(/'/g,"\\'")+'\')">'+
            '<span class="ic">📁</span><span class="nm">'+esc(d.is_root?e.path:e.name)+'</span>'+
            wt+'<span class="ar">›</span></div>';
        }).join("");
      })
      .catch(function(e){ list.innerHTML='<div class="v115lb-empty" style="color:#e5484d">请求失败: '+esc(e)+'</div>'; });
  };
  window.v115lbRoot  = function(){ v115lbLoad(""); };
  window.v115lbEnter = function(p){ v115lbLoad(p); };
  window.v115lbUp    = function(){ if(state.is_root||!state.parent){ v115lbLoad(""); } else { v115lbLoad(state.parent); } };
  window.v115lbReload= function(){ v115lbLoad(state.is_root?"":state.path); };
  window.v115lbAdd   = function(){
    var msg=document.getElementById("v115lb-msg");
    if(state.is_root||!state.path){ msg.style.color="#e5a000"; msg.textContent="请先进入一个具体目录，再点「加入监控」"; return; }
    msg.style.color="#0a6bd6"; msg.textContent="正在加入…";
    fetch(API+"/addpath?path="+encodeURIComponent(state.path),{credentials:"include"})
      .then(function(r){return r.json();})
      .then(function(d){
        if(d.success){ msg.style.color="#1a7f37"; msg.textContent="✅ "+(d.message||"已加入")+"（当前监控: "+((d.paths||[]).join(" , "))+"）"; }
        else { msg.style.color="#e5484d"; msg.textContent="❌ "+(d.message||"加入失败"); }
      })
      .catch(function(e){ msg.style.color="#e5484d"; msg.textContent="请求失败: "+esc(e); });
  };
  setTimeout(function(){ v115lbLoad(""); }, 150);
})();
</script>
"""
