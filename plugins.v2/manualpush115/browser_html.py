"""自包含的文件浏览器和秒传操作 HTML，通过 VHtml 在 get_page 中渲染。

占位符 __PREFIX__ 替换为 plugin_id。
"""

BROWSER_HTML = r"""
<div id="mp115app" class="mp115">
  <!-- Header -->
  <div class="mp115-header">
    <div class="mp115-title">
      <svg viewBox="0 0 24 24" width="28" height="28" style="color:rgb(var(--v-theme-primary,109,74,255));opacity:.7;flex:0 0 auto"><path fill="currentColor" d="M19.35 10.04A7.49 7.49 0 0 0 12 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
      <div>
        <div class="mp115-title-main">手动秒传 115</div>
        <div class="mp115-title-sub">浏览本地文件 → 勾选 → 一键秒传</div>
      </div>
    </div>
    <div class="mp115-status">
      <span id="mp115-state" class="mp115-badge">空闲</span>
      <button onclick="mp115Test()" class="mp115-btn mp115-btn-sm" id="mp115-testbtn">测试凭据</button>
    </div>
  </div>

  <!-- Toast -->
  <div id="mp115-toast" class="mp115-toast"></div>

  <!-- 目标目录 -->
  <div class="mp115-target">
    <label>115 目标目录</label>
    <input id="mp115-remote" type="text" value="/" placeholder="/媒体/电影" />
  </div>

  <!-- 文件浏览器 -->
  <div class="mp115-browser">
    <div class="mp115-breadcrumb" id="mp115-bread">/</div>
    <div class="mp115-toolbar">
      <button onclick="mp115SelectAll()" class="mp115-btn mp115-btn-sm">全选文件</button>
      <button onclick="mp115DeselectAll()" class="mp115-btn mp115-btn-sm">取消全选</button>
      <span class="mp115-sel-count">已选 <strong id="mp115-selcnt">0</strong> 项</span>
      <button onclick="mp115Push()" class="mp115-btn mp115-btn-primary" id="mp115-pushbtn">
        🚀 秒传选中文件
      </button>
    </div>
    <div id="mp115-filelist" class="mp115-filelist">
      <div class="mp115-empty">点击左侧目录开始浏览</div>
    </div>
  </div>

  <!-- 进度 -->
  <div id="mp115-progress" class="mp115-progress" style="display:none">
    <div class="mp115-progress-bar"><div id="mp115-pbar" class="mp115-pbar-fill"></div></div>
    <div id="mp115-ptext" class="mp115-ptext">准备中…</div>
  </div>

  <!-- 历史 -->
  <div class="mp115-section">
    <div class="mp115-section-h">
      <span>📋</span> 秒传记录
      <span id="mp115-histcnt" class="mp115-chip">0</span>
    </div>
    <div id="mp115-histlist" class="mp115-list">
      <div class="mp115-empty">尚无记录</div>
    </div>
  </div>
</div>

<style>
.mp115{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;color:rgb(var(--v-theme-on-surface,44,44,58))}
.mp115-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.mp115-title{display:flex;align-items:center;gap:12px}
.mp115-title-main{font-size:18px;font-weight:700}
.mp115-title-sub{font-size:12px;opacity:.6;margin-top:2px}
.mp115-status{display:flex;align-items:center;gap:8px}
.mp115-badge{font-size:12px;font-weight:600;padding:4px 12px;border-radius:999px;
  background:rgba(var(--v-theme-success,76,175,80),.15);color:rgb(var(--v-theme-success,76,175,80))}
.mp115-badge.busy{background:rgba(var(--v-theme-primary,109,74,255),.15);color:rgb(var(--v-theme-primary,109,74,255))}
.mp115-toast{display:none;padding:10px 14px;border-radius:10px;font-size:13px;margin-bottom:12px}
.mp115-toast.ok{display:block;background:rgba(var(--v-theme-success,76,175,80),.1);color:rgb(var(--v-theme-success,76,175,80));border:1px solid rgba(var(--v-theme-success,76,175,80),.3)}
.mp115-toast.err{display:block;background:rgba(var(--v-theme-error,244,67,54),.1);color:rgb(var(--v-theme-error,244,67,54));border:1px solid rgba(var(--v-theme-error,244,67,54),.3)}
.mp115-toast.info{display:block;background:rgba(var(--v-theme-info,33,150,243),.1);color:rgb(var(--v-theme-info,33,150,243));border:1px solid rgba(var(--v-theme-info,33,150,243),.3)}

.mp115-target{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.mp115-target label{font-size:13px;font-weight:600;white-space:nowrap}
.mp115-target input{flex:1;padding:8px 12px;border-radius:10px;font-size:14px;
  border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:inherit;outline:none}
.mp115-target input:focus{border-color:rgb(var(--v-theme-primary,109,74,255))}

.mp115-browser{border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  border-radius:14px;background:rgb(var(--v-theme-surface,255,255,255));overflow:hidden;margin-bottom:16px}
.mp115-breadcrumb{padding:12px 16px;font-size:13px;font-weight:600;border-bottom:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.08));overflow-wrap:anywhere}
.mp115-breadcrumb a{color:rgb(var(--v-theme-primary,109,74,255));text-decoration:none;cursor:pointer}
.mp115-breadcrumb a:hover{text-decoration:underline}
.mp115-toolbar{display:flex;align-items:center;gap:8px;padding:8px 16px;border-bottom:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.08));flex-wrap:wrap}
.mp115-sel-count{font-size:12px;opacity:.7;margin-left:auto}
.mp115-btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:10px;cursor:pointer;
  font-size:13px;font-weight:600;border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  background:rgb(var(--v-theme-surface,255,255,255));color:rgb(var(--v-theme-on-surface,44,44,58));transition:all .12s}
.mp115-btn:hover{border-color:rgb(var(--v-theme-primary,109,74,255));color:rgb(var(--v-theme-primary,109,74,255))}
.mp115-btn:disabled{opacity:.5;cursor:not-allowed}
.mp115-btn-sm{padding:5px 10px;font-size:12px}
.mp115-btn-primary{border-color:rgb(var(--v-theme-primary,109,74,255));color:rgb(var(--v-theme-primary,109,74,255));font-weight:700}

.mp115-filelist{max-height:420px;overflow-y:auto;overscroll-behavior:contain}
.mp115-row{display:flex;align-items:center;gap:10px;padding:9px 16px;cursor:pointer;transition:background .1s;border-bottom:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.05))}
.mp115-row:hover{background:rgba(var(--v-theme-primary,109,74,255),.04)}
.mp115-row input[type=checkbox]{width:16px;height:16px;accent-color:rgb(var(--v-theme-primary,109,74,255));flex:0 0 auto}
.mp115-row .ic{font-size:18px;flex:0 0 auto;opacity:.6}
.mp115-row .nm{flex:1;min-width:0;font-size:14px;overflow-wrap:anywhere}
.mp115-row .nm.dir{font-weight:600;color:rgb(var(--v-theme-primary,109,74,255));cursor:pointer}
.mp115-row .sz{font-size:12px;opacity:.55;white-space:nowrap}
.mp115-empty{padding:28px;text-align:center;font-size:13px;opacity:.5}

.mp115-progress{margin-bottom:16px}
.mp115-progress-bar{height:6px;border-radius:3px;background:rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.15));overflow:hidden}
.mp115-pbar-fill{height:100%;border-radius:3px;background:rgb(var(--v-theme-primary,109,74,255));transition:width .3s;width:0%}
.mp115-ptext{font-size:12px;opacity:.7;margin-top:4px}

.mp115-section{margin-top:16px;border:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.12));
  border-radius:14px;background:rgb(var(--v-theme-surface,255,255,255));overflow:hidden}
.mp115-section-h{display:flex;align-items:center;gap:8px;padding:12px 16px;font-size:15px;font-weight:700;border-bottom:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.08))}
.mp115-chip{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;
  background:rgba(var(--v-theme-primary,109,74,255),.1);color:rgb(var(--v-theme-primary,109,74,255))}
.mp115-list{max-height:360px;overflow-y:auto}
.mp115-hist{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid rgba(var(--v-border-color,200,200,200),var(--v-border-opacity,.05))}
.mp115-hist .mid{flex:1;min-width:0}
.mp115-hist .fnm{font-size:14px;font-weight:600;overflow-wrap:anywhere}
.mp115-hist .meta{font-size:11.5px;opacity:.55;margin-top:2px;overflow-wrap:anywhere}
.mp115-hist .tag{font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;flex:0 0 auto}
.mp115-tag-ok{color:rgb(var(--v-theme-success,76,175,80));background:rgba(var(--v-theme-success,76,175,80),.12)}
.mp115-tag-fail{color:rgb(var(--v-theme-error,244,67,54));background:rgba(var(--v-theme-error,244,67,54),.12)}
@media(max-width:600px){
  .mp115-title-sub{display:none}
  .mp115-toolbar{gap:6px}
  .mp115-sel-count{width:100%;margin-left:0}
}
</style>

<script>
(function(){
  var API="/api/v1/plugin/__PREFIX__";
  var selected={}, currentPath="/", entries=[], pollTimer=null;

  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]})}
  function fsize(b){b=Number(b)||0;if(b<1024)return b+" B";var u=["KB","MB","GB","TB"],i=-1;do{b/=1024;i++}while(b>=1024&&i<3);return b.toFixed(b<10?1:0)+" "+u[i]}
  function toast(cls,msg){var t=document.getElementById("mp115-toast");t.className="mp115-toast "+cls;t.textContent=msg;if(cls!=="info")setTimeout(function(){t.className="mp115-toast"},6000)}
  function g(id){return document.getElementById(id)}

  function browse(path){
    fetch(API+"/browse?path="+encodeURIComponent(path||"/"),{credentials:"include"})
    .then(function(r){return r.json()})
    .then(function(d){
      if(!d.success){toast("err",d.message||"浏览失败");return}
      currentPath=d.path;entries=d.entries||[];
      // Breadcrumb
      var parts=d.path.split("/").filter(Boolean);
      var bc='<a onclick="mp115Browse(\'/\')">根目录</a>';
      var acc="";
      parts.forEach(function(p){acc+="/"+p;bc+=' / <a onclick="mp115Browse(\''+esc(acc)+'\')">'+esc(p)+'</a>'});
      g("mp115-bread").innerHTML=bc;
      // File list
      var html="";
      if(d.parent!==null&&d.parent!==undefined){
        html+='<div class="mp115-row" onclick="mp115Browse(\''+esc(d.parent)+'\')"><span class="ic">⬆️</span><span class="nm dir">返回上级</span></div>';
      }
      entries.forEach(function(e,i){
        if(e.is_dir){
          html+='<div class="mp115-row">';
          html+='<input type="checkbox" data-path="'+esc(e.path)+'" data-dir="1" onchange="mp115Toggle(this)" '+(selected[e.path]?'checked':'')+'/>';
          html+='<span class="ic" onclick="mp115Browse(\''+esc(e.path)+'\')">📁</span>';
          html+='<span class="nm dir" onclick="mp115Browse(\''+esc(e.path)+'\')">'+esc(e.name)+'</span></div>';
        }else{
          html+='<div class="mp115-row">';
          html+='<input type="checkbox" data-path="'+esc(e.path)+'" onchange="mp115Toggle(this)" '+(selected[e.path]?'checked':'')+'/>';
          html+='<span class="ic">📄</span>';
          html+='<span class="nm">'+esc(e.name)+'</span>';
          html+='<span class="sz">'+fsize(e.size)+'</span></div>';
        }
      });
      if(!entries.length) html='<div class="mp115-empty">目录为空或无符合条件的文件</div>';
      g("mp115-filelist").innerHTML=html;
      updateCount();
    })
    .catch(function(e){toast("err","浏览失败: "+e)});
  }
  window.mp115Browse=browse;

  window.mp115Toggle=function(cb){
    var path=cb.getAttribute("data-path");
    if(cb.checked) selected[path]=true; else delete selected[path];
    updateCount();
  };

  window.mp115SelectAll=function(){
    entries.forEach(function(e){selected[e.path]=true});
    document.querySelectorAll("#mp115-filelist input[type=checkbox]").forEach(function(cb){cb.checked=true});
    updateCount();
  };
  window.mp115DeselectAll=function(){
    entries.forEach(function(e){delete selected[e.path]});
    document.querySelectorAll("#mp115-filelist input[type=checkbox]").forEach(function(cb){cb.checked=false});
    updateCount();
  };

  function updateCount(){
    g("mp115-selcnt").textContent=Object.keys(selected).length;
  }

  window.mp115Push=function(){
    var paths=Object.keys(selected);
    if(!paths.length){toast("err","请先勾选要秒传的文件或文件夹");return}
    var remote=g("mp115-remote").value.trim()||"/";
    g("mp115-pushbtn").disabled=true;
    g("mp115-progress").style.display="block";
    g("mp115-pbar").style.width="0%";
    g("mp115-ptext").textContent="提交中…";
    toast("info","正在提交 "+paths.length+" 项到 "+remote);
    fetch(API+"/push",{method:"POST",credentials:"include",
      headers:{"content-type":"application/json"},
      body:JSON.stringify({paths:paths,remote_dir:remote})})
    .then(function(r){return r.json()})
    .then(function(d){
      if(d.success){
        toast("info",d.message||"已开始");
        selected={};updateCount();
        browse(currentPath);
        startPoll();
      }else{
        toast("err",d.message||"提交失败");
        g("mp115-pushbtn").disabled=false;
        g("mp115-progress").style.display="none";
      }
    })
    .catch(function(e){toast("err","请求失败: "+e);g("mp115-pushbtn").disabled=false});
  };

  function startPoll(){
    stopPoll();
    pollTimer=setInterval(function(){
      fetch(API+"/status",{credentials:"include"})
      .then(function(r){return r.json()})
      .then(function(d){
        var badge=g("mp115-state");
        if(d.running){
          badge.className="mp115-badge busy";badge.textContent="秒传中";
          var prog=d.progress||"";
          g("mp115-ptext").textContent=prog;
          var m=prog.match(/^(\d+)\/(\d+)/);
          if(m)g("mp115-pbar").style.width=Math.round(parseInt(m[1])/parseInt(m[2])*100)+"%";
        }else{
          badge.className="mp115-badge";badge.textContent="空闲";
          g("mp115-pushbtn").disabled=false;
          if(d.progress)g("mp115-ptext").textContent=d.progress;
          g("mp115-pbar").style.width="100%";
          stopPoll();
          setTimeout(function(){g("mp115-progress").style.display="none"},3000);
        }
        renderHistory(d.history||[]);
      });
    },2000);
  }
  function stopPoll(){if(pollTimer){clearInterval(pollTimer);pollTimer=null}}

  function renderHistory(h){
    g("mp115-histcnt").textContent=h.length;
    if(!h.length){g("mp115-histlist").innerHTML='<div class="mp115-empty">尚无记录</div>';return}
    g("mp115-histlist").innerHTML=h.slice(0,100).map(function(x){
      var ok=x.status==="success";
      return '<div class="mp115-hist"><div class="mid"><div class="fnm">'+esc(x.name)+'</div>'+
        '<div class="meta">'+esc(x.path||"")+(x.size?" · "+fsize(x.size):"")+" · "+esc(x.time||"")+'</div>'+
        (x.message?'<div class="meta">'+esc(x.message)+'</div>':"")+
        '</div><span class="tag '+(ok?"mp115-tag-ok":"mp115-tag-fail")+'">'+(ok?"成功":"失败")+'</span></div>'
    }).join("");
  }

  window.mp115Test=function(){
    g("mp115-testbtn").disabled=true;
    toast("info","正在测试 115 凭据…");
    fetch(API+"/test",{method:"POST",credentials:"include"})
    .then(function(r){return r.json()})
    .then(function(d){toast(d.success?"ok":"err",d.message||"");g("mp115-testbtn").disabled=false})
    .catch(function(e){toast("err","测试失败: "+e);g("mp115-testbtn").disabled=false});
  };

  // Init
  fetch(API+"/status",{credentials:"include"}).then(function(r){return r.json()}).then(function(d){
    g("mp115-remote").value=d.remote_dir||"/";
    if(d.running){g("mp115-state").className="mp115-badge busy";g("mp115-state").textContent="秒传中";startPoll()}
    renderHistory(d.history||[]);
  });
  browse("/");
})();
</script>
"""
