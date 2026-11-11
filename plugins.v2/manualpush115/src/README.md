# ManualPush115 1.9.0 联邦前端

## 构建与测试

环境：Node 22、pnpm 9.15.9。工作树在 iOS `/var/minis/workspace` 上不能创建 symlink，因此安装／测试／构建必须复制到 `/tmp`。不要在共享 node_modules 的 symlink 上运行 install。

```sh
mkdir -p /tmp/manual115-ui-clean
cp -R plugins.v2/manualpush115/src /tmp/manual115-ui-clean/
cp plugins.v2/manualpush115/{package.json,pnpm-lock.yaml,vite.config.js,index.html} /tmp/manual115-ui-clean/
cd /tmp/manual115-ui-clean
pnpm install --frozen-lockfile
pnpm test
pnpm build
pnpm test:build
```

若使用已验证且同锁版本的依赖，可跳过 install：

```sh
ln -s /tmp/brushflowtracker-build/node_modules /tmp/manual115-ui-clean/node_modules
cd /tmp/manual115-ui-clean
pnpm test
pnpm build
pnpm test:build
```

`node:test` 测试不需要浏览器、不连接用户服务：使用模拟 API、Vue compiler-sfc 编译、Vue 自定义 renderer 挂载 script setup，验证状态／事件及生命周期。测试覆盖错误响应、实例ID、配置失败禁保存、完整初始配置、保存后续输入保护、本地逐层请求、显式搜索、跨页选择、代次隔离、115游标翻页、任务快照／重复点击、取消、可见性轮询和卸载。

## 宿主合同

暴露 `./Page`、`./Config`、`./AppPage`。均接收 `api`、`pluginId`、`sourcePluginId`、`nativeSubscribe`；API实例ID优先于源插件ID，缺失ID明确报错而不是写死 ManualPush115。也支持可选 `moviepilot:api` 与 `moviepilot:pluginId` 注入；认证仍由宿主负责，不自行读取令牌。

Config 接收完整 `initialConfig`，提供 `save`／`switch`／`close`；初始配置缺字段时必须成功 GET settings 后才允许保存。独立 Config 默认通过宿主 `save` 保存；首页对话框使用 `isEmbedded`，直接 POST settings，成功发 `saved` 和 `save`。打开首页不会加载 Cookie；仅打开配置或保存首页默认选择时取完整 settings。`test` 只测试已保存值，不提交草稿 Cookie。

本地与115选择器各有独立请求代次。roots／browse／search 不预取下层，勾选目录绝不展开。搜索只显式触发，分页沿用上次提交的 query/recursive 快照。115 `next_offset` 用于跳过接口内未展示的文件；上一页保存游标栈。根目录 `parent_cid='0'` 不再向自身返回。

上传仅 POST 快照，不在 UI 计算 hash；`force=true`、`preserve_structure=true` 默认开启。结构保留由后端定义为所选目录 basename + 子层。运行中只轮询 status（2秒），页面隐藏／失活／卸载停止计时；初始隐藏 WebView 仍执行首次载入。

`settings` 原有必需字段：cookie、user_agent、extensions、remote_dir、local_paths。新增 failure_move_enabled、failure_move_dir、delete_on_success、failure_move_preserve_structure；旧五字段配置以关闭动作和保留结构默认值迁移，保存时包含全部九字段。首页只显示已保存策略，修改在设置页完成。所有接口使用 `{success,message,data}`（兼容 Axios 的外层 data）。状态支持 collecting/running/cancelling/completed/completed_with_errors/failed/cancelled/interrupted，并展示 message/errors/persist_error。

## 样式边界

Vuetify组件由 MoviePilot 宿主全局注册（VBtn/VDialog/VAlert/VProgressLinear），模板直接复用；不直导 `vuetify/components`，避免重复打包Vuetify运行时。Vue、Vuetify 联邦 shared 均 `generate:false`。不要添加 `vuetify/styles` shared 条目：originjs 即使 generate:false 仍提前构建该CSS入口，产生332KB全局style chunk。当前从源头不导入／不共享这个样式入口，不使用 `.v-`／`.mdi-` 选择器过滤，不引入全局字体图标；业务CSS全部 scoped。

列表触控44px、窄屏换行、长路径断行。发布包含完整 `dist` 及后端接口。测试旧V2时除了 API、instance props 注入，还模拟其父级 `plugin.id`（官方旧版对话框仅传 api）来定位实例。新版优先使用显式实例 props。生产包不包含本地模拟服务器或测试文件路径。
