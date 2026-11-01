"""扫码登录 115 的自包含 HTML 组件（路 A）。

流程：
  1. 点「生成二维码」→ 调 /qrlogin 拿到二维码 data URI；
  2. 显示二维码，每 2s 调 /qrstatus 轮询；
  3. status=confirmed 时提示用户复制 Cookie 到配置框。

由于 115 网页扫码后的 Cookie 只下发给 115 浏览器 App，
纯 HTTP 无法直接获取，故最后一步需用户手动复制（界面上给出明确指引）。
"""

QR_LOGIN_HTML = r"""
<div id="v115-qr" class="v115qr">
  <div class="v115qr-row">
    <div id="v115-qr-box" class="v115qr-box">
      <span class="v115qr-ph">📷<br>未生成</span>
    </div>
    <div class="v115qr-side">
      <button id="v115-qr-btn" onclick="v115QrStart()" class="v115qr-btn">
        <span style="font-size:15px">📱</span> 生成二维码</button>
      <div id="v115-qr-status" class="v115qr-status">
        点击生成二维码，然后用 115 App 扫码。
      </div>
      <div id="v115-qr-cookie" class="v115qr-cookie" style="display:none">
        <div class="v115qr-ck-t">✅ 已确认登录！请复制 Cookie 填入配置：</div>
        <ol class="v115qr-ck-ol">
          <li>电脑浏览器登录 <b>115.com</b> → F12 → Network → 刷新 → 点任一请求</li>
          <li>复制 Request Headers 里的整行 <b>Cookie</b></li>
          <li>粘贴到「115 网页 Cookie」输入框并保存</li>
        </ol>
      </div>
    </div>
  </div>
</div>
<style>
.v115qr{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
.v115qr-row{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}
.v115qr-box{width:168px;height:168px;border-radius:16px;flex:0 0 auto;
  display:flex;align-items:center;justify-content:center;color:#9aa;font-size:13px;text-align:center;line-height:1.7;
  background:linear-gradient(135deg,#f5f7ff,#eef0fb);border:1.5px dashed #c3c7e8;box-shadow:inset 0 2px 10px rgba(94,92,230,.08)}
.v115qr-box img{width:100%;height:100%;object-fit:contain;border-radius:12px}
.v115qr-ph{font-size:30px}
.v115qr-side{flex:1;min-width:200px}
.v115qr-btn{padding:9px 20px;border:none;border-radius:10px;color:#fff;cursor:pointer;font-size:14px;font-weight:600;
  background:linear-gradient(135deg,#0a84ff,#5e5ce6);box-shadow:0 6px 16px -6px rgba(94,92,230,.6);transition:transform .15s,box-shadow .15s}
.v115qr-btn:hover{transform:translateY(-2px);box-shadow:0 10px 22px -6px rgba(94,92,230,.7)}
.v115qr-btn:active{transform:translateY(0)}
.v115qr-status{margin-top:12px;font-size:13px;color:#667;line-height:1.6}
.v115qr-cookie{margin-top:12px;padding:12px 14px;border-radius:12px;background:rgba(52,199,89,.08);border:1px solid rgba(52,199,89,.3)}
.v115qr-ck-t{font-size:13px;font-weight:600;color:#1a7f37;margin-bottom:8px}
.v115qr-ck-ol{margin:0;padding-left:20px;font-size:12.5px;color:#556;line-height:1.9}
.v115qr-ck-ol b{color:#0a84ff}
</style>
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
