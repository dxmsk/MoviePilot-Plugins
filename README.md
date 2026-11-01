# 115网盘秒传 插件（MoviePilot V2）

把 MoviePilot 媒体库（或任意本地路径）中的文件，用 **SHA1「秒传」** 的方式推送到 115 网盘。
不下载、不上传文件本体，**全程只读，绝不移动 / 修改 / 删除原始文件**。

---

## 🔑 两种登录方式（二选一）

插件支持两种 115 登录方式，在配置页「115 登录方式」下拉中选择：

### 方式 A：网页 Cookie（推荐，免申请）
从浏览器里复制 115 网页版的登录 Cookie 填进来即可，**无需申请开放平台应用**。

**获取方式 1 —— 扫码登录（插件内一键）**
打开插件页面 → 点「扫码登录」→ 用 115 App 扫码并确认 → 按提示复制 Cookie 填入。
（115 出于安全设计，网页扫码后的 Cookie 只下发给 115 浏览器 App，插件无法直接读取，
所以扫码后仍需手动复制一步 —— 这一步是 115 的限制，不是插件的问题。）

**获取方式 2 —— 浏览器复制**
1. 电脑浏览器登录 <https://115.com>；
2. `F12` → `Network`（网络）→ 刷新页面 → 点任意一个请求 → `Request Headers` → 复制整行 `Cookie:` 的内容；
3. 粘贴到插件配置「115 网页 Cookie」框。至少需包含 `UID` / `CID` / `SEID` 三项。

> **支持多种粘贴格式**（自动识别，无需手动整理）：
> - 请求头 / cURL：`UID=1; CID=2; SEID=3` 或 `Cookie: UID=1; ...`
> - EditThisCookie / Cookie-Editor 导出的 **JSON**
> - Chrome DevTools 的 **Tab 分隔**表格复制
> - Netscape `cookies.txt` 文件内容
> - 每行 `key=value`
>
> Cookie 有时效，若提示「Cookie 已失效」，重新复制一次即可。

### 方式 B：开放平台 access_token
1. 到 <https://open.115.com> 申请应用；
2. 走 OAuth 换取 `access_token`；
3. 填入插件配置「115 开放平台 access_token」。

> 两种方式都只用于调用 115 的秒传 / 目录接口，令牌仅保存在 MoviePilot 本地配置中。

---

## ✨ 功能特性

1. **可选路径秒传到 115 网盘**
   - 自定义一个或多个本地监控目录（媒体库），插件自动扫描其中的视频 / 字幕 / 音频文件并秒传。
   - 自定义 115 网盘目标目录，不存在会自动创建；也可在插件页面用「**浏览 115 目录**」**可视化点选**。
   - 可自定义处理的文件扩展名（留空则使用内置的视频/字幕/音频列表）。

2. **两种登录方式**
   - **网页 Cookie**（免申请）：支持插件内「扫码登录」生成二维码，以及多种 Cookie 文本格式自动解析。
   - **开放平台 access_token**：适合已在 open.115.com 申请应用的场景。

3. **秒传失败可自定义重试**
   - 自定义 **重试间隔**（秒）与 **最大重试次数**（0 = 无限）。
   - 失败文件进入重试队列，后台按间隔自动重试，直到成功或放弃。

4. **不动原始路径**
   - 插件对本地文件 **只读**（仅计算 SHA1 与读取校验区间），
     **绝不复制、移动、重命名或删除** 任何原始文件/目录。

---

## 📦 安装

1. 把本目录（`115cloudpush`）整体放到 MoviePilot 的插件目录，或打包成 zip 后在
   `设置 → 插件 → 安装插件` 上传。
2. 插件市场本地安装路径一般为：
   ```
   MoviePilot配置目录/plugins/
   ```
   确保目录结构为：
   ```
   plugins/115cloudpush/__init__.py
   plugins/115cloudpush/p115_client.py   # 开放平台模式
   plugins/115cloudpush/p115_web.py      # Cookie 模式
   plugins/115cloudpush/_crypto.py       # 加解密（纯标准库）
   plugins/115cloudpush/_vendor/aes.py   # 纯 Python AES
   plugins/115cloudpush/scanner.py
   ```
3. 重启 MoviePilot 或在插件页刷新，即可看到「115网盘秒传」插件。

> **零第三方依赖**：所有加解密（AES / RSA / LZ4）均为纯 Python 纯标准库实现，
> 无需 `pip install` 任何包，避免在 MoviePilot 容器里装不上依赖的问题。

---

## ⚙️ 配置说明

| 配置项 | 说明 |
| --- | --- |
| 启用插件 | 总开关 |
| 仅运行一次 | 保存后立即执行一次扫描，然后自动关闭该开关 |
| 发送通知 | 秒传完成后发送通知 |
| **115 登录方式** | `网页 Cookie` 或 `开放平台 access_token`，二选一 |
| 115 网页 Cookie | 方式 A 填这里（推荐，免申请） |
| 自定义 User-Agent | 可选，留空使用默认 115Browser UA |
| 115 开放平台 access_token | 方式 B 填这里 |
| 监控的本地目录 | 一个或多个本地目录，逗号分隔，如 `/media/电影,/media/电视剧` |
| 115 目标目录 | 如 `/媒体/电影`，留空 = 根目录。可在插件页面用「浏览 115 目录」可视化选择 |
| 处理的文件扩展名 | 逗号分隔，留空 = 内置视频/字幕/音频列表 |
| 扫描间隔（分钟） | 多久扫描一次新文件 |
| 秒传失败重试间隔（秒） | 单个文件失败后等待多久再试 |
| 最大重试次数 | 0 = 无限重试 |
| 未命中秒传也重试 | 开关。开启(默认)=服务器没有该文件时也按间隔重试；关闭=明确未命中时跳过。网络/校验类暂时性失败始终重试。 |

### 获取 115 开放平台 access_token

1. 打开 [115 开放平台](https://open.115.com/) 并登录。
2. 创建应用（类型不限，仅需上传能力），获取 `client_id` / `client_secret`。
3. 通过 OAuth 授权流程换取 `access_token`：
   ```
   POST https://passportapi.115.com/open/authCodeToToken
   ```
   或用 115 官方提供的授权工具获取令牌。
4. 把得到的 `access_token` 填入插件配置（**建议长期有效令牌**，过期后需重新获取）。

> 也可以使用第三方工具（如 p115client）扫码登录后导出 Open API 令牌。

---

## 🔧 工作原理（秒传协议）

本插件调用 115 官方 **开放平台** 接口，核心只有一步：

```
POST https://proapi.115.com/open/upload/init
Header: Authorization: Bearer <access_token>
Body:  file_name, file_size, fileid(文件的SHA1), target=U_1_<目录ID>, topupload=1
```

- 返回 `status == 2` → **秒传成功**（服务器已存在相同 SHA1 的文件，直接登记）。
- 返回 `status == 7` → 需要 **二次认证**：
  - 服务器给出 `sign_check`（形如 `2392148-2392298`，闭区间）。
  - 插件按区间读取本地文件对应字节，计算 **大写 SHA1** 作为 `sign_val`，连同 `sign_key` 再提交一次。
  - 返回 `status == 2` 即秒传成功。
- 返回 `status == 1` → 服务器没有该文件，需要真实上传（本插件不处理）。
  - 默认仍会按你设置的间隔重试（很多资源会在别处上传后才可秒传）；可在配置里关闭「未命中秒传也重试」。

**关键点**：整个过程 115 只校验文件的 SHA1，不需要上传文件内容，因此：
- 极快、零带宽占用；
- 本地文件只被 **读取**（算 SHA1、读校验区间），不改动任何数据。

### Cookie 模式（网页版接口）

选择 Cookie 登录时，插件走 115 网页版接口：

```
POST https://uplb.115.com/4.0/initupload.php
```

- 请求体为 `AES-128-CBC` 加密的 URL 编码表单，含 `sig` / `token`（防重放校验）；
- 响应为 `AES-128-CBC` 加密、外层再套 `LZ4` 块的 JSON；
- `sig` 由 `userkey` + `SHA1(userid+fileid+target+0)` 计算；
- `token` 由 `MD5(salt) + fileid+filesize+sign_key+sign_val+userid+t + MD5(userid) + appversion` 计算；
- 返回 `status == 2` / `7` / `1` 的含义与开放平台模式一致。

> 为做到 **零第三方依赖**，插件内置了纯 Python 实现的 AES、RSA、LZ4（`_crypto.py` + `_vendor/aes.py`），
> 已用 FIPS-197 标准向量与官方 p115cipher 实现逐字节比对通过。无需 `pip install`。


---

## 🤖 远程命令

| 命令 | 说明 |
| --- | --- |
| `/115push` | 立即执行一次扫描 |
| `/115status` | 查看插件状态与重试队列数量 |

---

## 🌐 API

所有 API 需 `Authorization: Bearer <MoviePilot令牌>`（`auth: bear`）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/v1/plugin/CloudPush115/scan` | 立即扫描并秒传 |
| GET | `/api/v1/plugin/CloudPush115/status` | 获取状态与重试队列 |
| GET/POST | `/api/v1/plugin/CloudPush115/test` | 测试凭据（Cookie 或 access_token）是否有效 |
| GET/POST | `/api/v1/plugin/CloudPush115/qrlogin` | 生成扫码登录二维码（返回 PNG） |
| GET/POST | `/api/v1/plugin/CloudPush115/qrstatus` | 轮询扫码状态 |
| GET/POST | `/api/v1/plugin/CloudPush115/browse` | 列出 115 网盘某目录下的子目录 |
| GET | `/api/v1/plugin/CloudPush115/dirbrowser` | 可视化目录选择器 HTML 组件 |

---

## ⚠️ 注意事项

- 秒传依赖 115 服务器上 **已存在相同 SHA1 的文件**；冷门资源可能未命中，属正常现象。
- 请确保 `access_token` 过期后及时更新，否则鉴权失败会中止本轮扫描。
- 扫描间隔不宜过短（建议 ≥ 10 分钟），避免频繁请求触发风控。
- 本插件 **不做真实上传**，只做秒传；如需真实上传请配合其它工具。
