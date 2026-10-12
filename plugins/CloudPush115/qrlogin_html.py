"""扫码登录 115 的自包含 HTML 组件（路 A）。

流程：
  1. 点「生成二维码」→ 调 /qrlogin 拿到二维码 data URI；
  2. 显示二维码，每 2s 调 /qrstatus 轮询；
  3. status=confirmed 时提示用户复制 Cookie 到配置框。

由于 115 网页扫码后的 Cookie 只下发给 115 浏览器 App，
纯 HTTP 无法直接获取，故最后一步需用户手动复制（界面上给出明确指引）。
"""

QR_LOGIN_HTML = r"""
<div id="v115-qr" style="font-family:-apple-system,system-ui,sans-serif">
  <div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap">
    <div id="v115-qr-box" style="width:160px;height:160px;border:1px dashed #bbb;border-radius:8px;
         display:flex;align-items:center;justify-content:center;color:#999;font-size:13px;flex:0 0 auto">
      未生成
    </div>
    <div style="flex:1;min-width:180px">
      <button id="v115-qr-btn" onclick="v115QrStart()"
        style="padding:7px 16px;border:none;border-radius:6px;background:#1976d2;color:#fff;cursor:pointer">
        📱 生成二维码</button>
      <div id="v115-qr-status" style="margin-top:10px;font-size:13px;color:#555;line-height:1.6">
        点击生成二维码，然后用 115 App 扫码。
      </div>
      <div id="v115-qr-cookie" style="margin-top:10px;display:none">
        <div style="font-size:13px;color:#333;margin-bottom:6px">📋 已确认登录！请复制 Cookie 填入配置：</div>
        <div style="font-size:12px;color:#666;line-height:1.7">
          1. 电脑浏览器登录 <b>115.com</b> → F12 → Network → 刷新 → 点任一请求<br>
          2. 复制 Request Headers 里的整行 <b>Cookie</b><br>
          3. 粘贴到「115 网页 Cookie」输入框并保存
        </div>
      </div>
    </div>
  </div>
</div>
<script>
(function(){
  var API = "/api/v1/plugin/__PREFIX__";
  var timer = null, sess = null;
  var box   = document.getElementById("v115-qr-box");
  var msg   = document.getElementById("v115-qr-status");
  var ckBox = document.getElementById("v115-qr-cookie");

  window.v115QrStart = function(){
    if(timer){ clearInterval(timer); timer = null; }
    ckBox.style.display = "none";
    box.innerHTML = "生成中…";
    msg.textContent = "正在生成二维码…";
    fetch(API + "/qrlogin", {credentials:"include"})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(!d.success){ box.innerHTML = "失败"; msg.textContent = "❌ " + (d.message||""); return; }
        sess = d;
        box.innerHTML = '<img src="' + d.qrcode + '" style="width:100%;height:100%;object-fit:contain">';
        msg.textContent = "请用 115 App 扫描二维码（有效期约 2 分钟）";
        timer = setInterval(v115QrPoll, 2000);
      })
      .catch(function(e){ box.innerHTML = "失败"; msg.textContent = "❌ " + e; });
  };

  function v115QrPoll(){
    if(!sess){ return; }
    var url = API + "/qrstatus?uid=" + encodeURIComponent(sess.uid) +
              "&sign=" + encodeURIComponent(sess.sign) + "&time=" + sess.time;
    fetch(url, {credentials:"include"})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(!d.success){ return; }
        msg.textContent = d.message || "";
        if(d.status === "confirmed"){
          clearInterval(timer); timer = null;
          ckBox.style.display = "block";
        }else if(d.status === "expired"){
          clearInterval(timer); timer = null;
          box.innerHTML = "已过期";
        }
      })
      .catch(function(){});
  }

  // 鼠标悬停在生成的二维码容器上时不要自动触发
})();
</script>
"""
