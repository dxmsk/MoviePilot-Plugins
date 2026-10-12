"""可视化 115 目录选择器的自包含 HTML 片段。

MoviePilot 插件页通过 `VHtml` 组件渲染本片段，片段内部直接调用插件 API：
  - GET /api/v1/plugin/__PREFIX__/browse?cid=<id>   列出子目录
选择后把路径写回配置项 remote_dir（通过 update_config 接口）。
"""

DIR_BROWSER_HTML = r"""
<div id="v115-dirbrowser" style="font-family:-apple-system,system-ui,sans-serif">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
    <span style="font-weight:600">📁 115 目录</span>
    <span id="v115-path" style="font-size:13px;color:#666;flex:1;word-break:break-all">/</span>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
    <button onclick="v115Go('0','/')" style="padding:5px 12px;border:1px solid #ccc;border-radius:6px;background:#fff;cursor:pointer">🏠 根目录</button>
    <button id="v115-up" onclick="v115Up()" style="padding:5px 12px;border:1px solid #ccc;border-radius:6px;background:#fff;cursor:pointer">⬆ 上级</button>
    <button id="v115-reload" onclick="v115Reload()" style="padding:5px 12px;border:1px solid #ccc;border-radius:6px;background:#fff;cursor:pointer">🔄 刷新</button>
    <button onclick="v115Pick()" style="padding:5px 12px;border:none;border-radius:6px;background:#1976d2;color:#fff;cursor:pointer">✅ 选择当前目录</button>
  </div>
  <div id="v115-list" style="border:1px solid #e0e0e0;border-radius:8px;max-height:320px;overflow:auto">
    <div style="padding:16px;color:#888">加载中…</div>
  </div>
  <div id="v115-msg" style="margin-top:8px;font-size:13px"></div>
</div>
<script>
(function(){
  var API = "/api/v1/plugin/__PREFIX__";
  var state = { cid: "0", path: "/", stack: [] };

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }

  window.v115Load = function(cid, path){
    var list = document.getElementById("v115-list");
    var msg  = document.getElementById("v115-msg");
    list.innerHTML = '<div style="padding:16px;color:#888">加载中…</div>';
    msg.textContent = "";
    fetch(API + "/browse?cid=" + encodeURIComponent(cid), {credentials:"include"})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(!d.success){
          list.innerHTML = '<div style="padding:16px;color:#c62828">' + esc(d.message||"加载失败") + '</div>';
          return;
        }
        state.cid = String(cid);
        state.path = path;
        document.getElementById("v115-path").textContent = path;
        var es = d.entries || [];
        if(!es.length){
          list.innerHTML = '<div style="padding:16px;color:#888">（此目录下没有子目录）</div>';
          return;
        }
        var html = "";
        es.forEach(function(e){
          html += '<div onclick="v115Enter(\'' + esc(e.cid) + '\',\'' +
                  esc((path==="/"?"":path) + "/" + e.name).replace(/'/g,"\\'") + '\')" ' +
                  'style="padding:9px 14px;border-bottom:1px solid #f0f0f0;cursor:pointer;display:flex;align-items:center;gap:8px">' +
                  '<span>📂</span><span style="flex:1">' + esc(e.name) + '</span>' +
                  '<span style="color:#999;font-size:12px">›</span></div>';
        });
        list.innerHTML = html;
      })
      .catch(function(e){
        list.innerHTML = '<div style="padding:16px;color:#c62828">请求失败: ' + esc(e) + '</div>';
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
