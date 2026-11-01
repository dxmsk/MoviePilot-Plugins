"""可视化 115 目录选择器的自包含 HTML 片段。

MoviePilot 插件页通过 `VHtml` 组件渲染本片段，片段内部直接调用插件 API：
  - GET /api/v1/plugin/__PREFIX__/browse?cid=<id>   列出子目录
选择后把路径写回配置项 remote_dir（通过 update_config 接口）。
"""

DIR_BROWSER_HTML = r"""
<div id="v115-dirbrowser" class="v115db">
  <div class="v115db-pathbar">
    <span class="v115db-pathic">📍</span>
    <span id="v115-path" class="v115db-path">/</span>
  </div>
  <div class="v115db-tools">
    <button onclick="v115Go('0','/')" class="v115db-btn">🏠 根目录</button>
    <button id="v115-up" onclick="v115Up()" class="v115db-btn">⬆ 上级</button>
    <button id="v115-reload" onclick="v115Reload()" class="v115db-btn">🔄 刷新</button>
    <button onclick="v115Pick()" class="v115db-btn v115db-btn-primary">✅ 选择当前目录</button>
  </div>
  <div id="v115-list" class="v115db-list">
    <div class="v115db-empty">加载中…</div>
  </div>
  <div id="v115-msg" class="v115db-msg"></div>
</div>
<style>
.v115db{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
.v115db-pathbar{display:flex;align-items:center;gap:8px;margin-bottom:10px;padding:8px 12px;border-radius:10px;
  background:linear-gradient(135deg,#eef4ff,#f3eefc);border:1px solid rgba(10,132,255,.15)}
.v115db-pathic{font-size:14px}
.v115db-path{font-size:13px;color:#445;flex:1;word-break:break-all;font-weight:500}
.v115db-tools{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.v115db-btn{padding:7px 14px;border:1px solid #dfe2f0;border-radius:9px;background:#fff;cursor:pointer;font-size:13px;
  color:#445;transition:all .15s;font-weight:500}
.v115db-btn:hover{border-color:#0a84ff;color:#0a84ff;box-shadow:0 2px 8px -3px rgba(10,132,255,.4)}
.v115db-btn-primary{border:none;color:#fff;background:linear-gradient(135deg,#0a84ff,#5e5ce6);
  box-shadow:0 5px 14px -5px rgba(94,92,230,.6)}
.v115db-btn-primary:hover{color:#fff;transform:translateY(-1px);box-shadow:0 8px 18px -5px rgba(94,92,230,.7)}
.v115db-list{border:1px solid #eceef5;border-radius:12px;max-height:340px;overflow:auto;background:#fff}
.v115db-list::-webkit-scrollbar{width:8px}
.v115db-list::-webkit-scrollbar-thumb{background:#d6d9ea;border-radius:8px}
.v115db-empty{padding:28px 16px;color:#99a;text-align:center;font-size:13px}
.v115db-item{padding:11px 16px;border-bottom:1px solid #f4f5fa;cursor:pointer;display:flex;align-items:center;gap:10px;
  transition:background .12s}
.v115db-item:last-child{border-bottom:none}
.v115db-item:hover{background:linear-gradient(90deg,rgba(10,132,255,.07),rgba(94,92,230,.04))}
.v115db-item .ic{font-size:18px}
.v115db-item .nm{flex:1;font-size:14px;color:#334;word-break:break-all}
.v115db-item .ar{color:#bbc;font-size:16px}
.v115db-msg{margin-top:10px;font-size:13px;line-height:1.6}
</style>
<script>
(function(){
  var API = "/api/v1/plugin/__PREFIX__";
  var state = { cid: "0", path: "/", stack: [] };

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }

  window.v115Load = function(cid, path){
    var list = document.getElementById("v115-list");
    var msg  = document.getElementById("v115-msg");
    list.innerHTML = '<div class="v115db-empty">加载中…</div>';
    msg.textContent = "";
    fetch(API + "/browse?cid=" + encodeURIComponent(cid), {credentials:"include"})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(!d.success){
          list.innerHTML = '<div class="v115db-empty" style="color:#e5484d">' + esc(d.message||"加载失败") + '</div>';
          return;
        }
        state.cid = String(cid);
        state.path = path;
        document.getElementById("v115-path").textContent = path;
        var es = d.entries || [];
        if(!es.length){
          list.innerHTML = '<div class="v115db-empty">（此目录下没有子目录）</div>';
          return;
        }
        var html = "";
        es.forEach(function(e){
          html += '<div class="v115db-item" onclick="v115Enter(\'' + esc(e.cid) + '\',\'' +
                  esc((path==="/"?"":path) + "/" + e.name).replace(/'/g,"\\'") + '\')">' +
                  '<span class="ic">📁</span><span class="nm">' + esc(e.name) + '</span>' +
                  '<span class="ar">›</span></div>';
        });
        list.innerHTML = html;
      })
      .catch(function(e){
        list.innerHTML = '<div class="v115db-empty" style="color:#e5484d">请求失败: ' + esc(e) + '</div>';
      });
  };

  window.v115Go = function(cid, path){
    state.stack = [];
    v115Load(cid, path);
  };
  window.v115Enter = function(cid, path){
    state.stack.push({cid: state.cid, path: state.path});
    v115Load(cid, path);
  };
  window.v115Up = function(){
    if(!state.stack.length){ v115Load("0", "/"); return; }
    var last = state.stack.pop();
    v115Load(last.cid, last.path);
  };
  window.v115Reload = function(){ v115Load(state.cid, state.path); };

  window.v115Pick = function(){
    var msg = document.getElementById("v115-msg");
    var dir = state.path === "/" ? "" : state.path;
    // 写回插件配置项 remote_dir
    var payload = { plugin_id:"__PREFIX__", config:{ remote_dir: dir } };
    fetch("/api/v1/plugin/config", {
      method:"POST", credentials:"include",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(d && (d.success === false)){
        msg.style.color = "#c62828";
        msg.textContent = "保存失败：" + (d.message||"") + " —— 也可手动复制该路径到配置框：" + dir;
      }else{
        msg.style.color = "#2e7d32";
        msg.textContent = "✅ 已选择：" + (dir||"/") + "（如未生效请点插件「保存」）";
      }
    })
    .catch(function(){
      msg.style.color = "#c62828";
      msg.textContent = "请手动把此路径填入「115 目标目录」：" + (dir||"/");
    });
  };

  // 初始化
  setTimeout(function(){ v115Load("0","/"); }, 100);
})();
</script>
"""
