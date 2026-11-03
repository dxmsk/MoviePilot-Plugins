<script setup>
import { computed, reactive, watch } from 'vue'
// VAlert/VBtn/VDialog/VProgressLinear are registered by the MoviePilot host.
import Config from './Config.vue'
import LocalPicker from './LocalPicker.vue'
import RemotePicker from './RemotePicker.vue'
import { hostProps, useClient } from '../composables/useClient.js'
import { useWorkbench } from '../composables/useWorkbench.js'
import { sizeText } from '../utils/api.js'
const props = defineProps({ ...hostProps, showClose: { type: Boolean, default: false } })
const emit = defineEmits(['action', 'save', 'switch', 'close'])
const vm = reactive(useWorkbench(useClient(props), emit))
const phase = computed(() => ({ collecting: '正在收集所选文件', hashing: '正在计算文件哈希', uploading: '正在秒传', running: '正在秒传', cancelling: '等待当前文件完成后停止', completed: '已完成', completed_with_errors: '已完成，部分文件失败', cancelled: '已停止', interrupted: '任务已中断', failed: '任务失败', idle: '就绪' }[vm.status.job?.phase] || vm.status.job?.phase || (vm.status.running ? '处理中' : '就绪')))
const statusLabel = value => ({ success: '成功', failed: '失败', skipped: '跳过', error: '失败' }[value] || value || '未知')
const localSummary = computed(() => vm.local.selected.length ? `已选 ${vm.local.selected.length} 项 · ${vm.local.selected[0]}` : '点击选择 MP 挂载目录中的文件／文件夹')
watch([() => vm.historyQuery, () => vm.historyFilter], () => { vm.historyPage = 1 })
// Embedded Config's switch is an internal return-to-home; forwarding it to
// Page's host would reopen the external Config screen instead of returning.
function configSwitch() { vm.settingsOpen = false }
</script>
<template>
  <section class="m115 m-page" aria-label="手动秒传115首页">
    <header class="m-header"><div><div class="m-kicker">MANUAL PUSH · 115</div><h1>手动秒传115</h1><p class="m-muted">本地文件，自由选择。手动补传，不自动调度。</p></div><div class="m-row"><VBtn variant="tonal" @click="vm.settingsOpen = true">设置</VBtn><VBtn variant="text" :loading="vm.loading" :disabled="vm.submitting" @click="vm.loadStatus">刷新</VBtn><VBtn v-if="showClose" variant="text" @click="emit('close')">关闭</VBtn></div></header>
    <div class="m-stack">
      <VAlert v-if="vm.error" type="error" variant="tonal" role="alert">{{ vm.error }}</VAlert>
      <VAlert v-if="vm.notice" type="info" variant="tonal" role="status">{{ vm.notice }}</VAlert>
      <VAlert v-if="vm.status.persist_error" type="error" variant="tonal" role="alert">持久化失败：{{ vm.status.persist_error }}</VAlert>
      <VAlert v-if="vm.status.message" type="info" variant="tonal">{{ vm.status.message }}</VAlert>
      <VAlert v-if="vm.loaded && !vm.status.has_cookie" type="warning" variant="tonal">尚未配置115 Cookie，保存后才能秒传。<VBtn variant="text" @click="vm.settingsOpen = true">打开设置</VBtn></VAlert>
      <section class="m-card">
        <div class="m-kicker">01 · LOCAL</div><h2>本地秒传路径</h2><p class="m-muted">仅列出 MP Docker 挂载根目录，子目录由你手动逐层进入。</p>
        <div class="m-picker m-spacer"><input class="m-input" :value="localSummary" readonly role="combobox" aria-label="本地路径下拉选择" :aria-expanded="vm.local.open" aria-haspopup="dialog" @click="vm.local.show" @keydown.enter.prevent="vm.local.show" @keydown.space.prevent="vm.local.show" @keydown.down.prevent="vm.local.show"></div>
        <div v-if="vm.local.selected.length" class="m-chips" aria-label="已选本地路径"><div v-for="path in vm.local.selected" :key="path" class="m-chip"><span>{{ path }}</span><button type="button" :aria-label="`移除 ${path}`" @click="vm.local.remove(path)">×</button></div></div>
        <p v-else class="m-muted m-spacer">尚未选择。支持单文件、整个文件夹与跨层多选。</p>
        <div class="m-row m-spacer"><VBtn variant="text" :disabled="!vm.local.selected.length" @click="vm.local.clear">清空选择</VBtn><VBtn variant="tonal" :loading="vm.savingSelection" :disabled="vm.savingSelection" @click="vm.saveSelection">保存为默认</VBtn><span class="m-muted">无需保存，选择后可直接秒传。</span></div>
      </section>
      <section class="m-card">
        <div class="m-kicker">02 · DESTINATION</div><h2>115目标目录</h2>
        <div class="m-picker m-spacer"><input class="m-input" :value="vm.remote.target.path" readonly role="combobox" aria-label="115目标目录下拉选择" :aria-expanded="vm.remote.open" aria-haspopup="dialog" @click="vm.remote.show" @keydown.enter.prevent="vm.remote.show" @keydown.space.prevent="vm.remote.show" @keydown.down.prevent="vm.remote.show"></div>
        <p class="m-muted">点击后读取真实115目录，逐层选择；保留默认路径也可直接提交。</p>
        <label class="m-check"><input v-model="vm.preserveStructure" type="checkbox">保留文件夹结构</label>
        <label class="m-check"><input v-model="vm.skipUnchanged" type="checkbox">跳过同账户／目标未变化的成功项</label>
        <p class="m-muted">默认手工补传，不因旧成功记录盲目跳过；秒传结果以115响应为准。</p>
        <div class="m-row m-spacer"><VBtn color="primary" size="large" :loading="vm.submitting" :disabled="!vm.canPush" @click="vm.push">{{ vm.status.running ? '任务运行中' : `开始秒传${vm.local.selected.length ? `（${vm.local.selected.length} 项）` : ''}` }}</VBtn><span v-if="vm.status.running" class="m-muted">可继续浏览与调整选择，当前任务使用提交时的快照。</span><span v-else-if="!vm.local.selected.length" class="m-muted">请先选择文件或文件夹</span></div>
      </section>
      <section class="m-card" aria-label="秒传任务进度">
        <div class="m-row"><div class="m-grow"><div class="m-kicker">03 · PROGRESS</div><h2>{{ phase }}</h2></div><VBtn v-if="vm.status.running" variant="tonal" color="warning" :loading="vm.cancelling" :disabled="vm.cancelRequested" @click="vm.cancel">{{ vm.cancelRequested ? '正在等待停止' : '停止任务' }}</VBtn></div>
        <VProgressLinear class="m-spacer" :model-value="vm.progress" :indeterminate="vm.status.running && !vm.status.job.total" height="7" rounded :aria-label="`任务进度 ${vm.progress}%`" />
        <p class="m-muted m-spacer">已处理 {{ vm.status.job.processed || 0 }} / {{ vm.status.job.total || 0 }} · 剩余 {{ vm.status.job.remaining ?? Math.max(0, (vm.status.job.total || 0) - (vm.status.job.processed || 0)) }}{{ vm.status.running && !vm.status.job.total ? ' · 后台收集中，不等待前端哈希' : '' }}</p>
        <div class="m-stats"><div class="m-stat"><strong>{{ vm.status.job.success || 0 }}</strong>成功</div><div class="m-stat"><strong>{{ vm.status.job.failed || 0 }}</strong>失败</div><div class="m-stat"><strong>{{ vm.status.job.skipped || 0 }}</strong>跳过</div><div class="m-stat"><strong>{{ vm.progress }}%</strong>进度</div></div>
        <p v-if="vm.status.job.current_file" class="m-path"><span class="m-muted">当前文件：</span>{{ vm.status.job.current_file }}</p>
        <p v-if="vm.status.job.message" class="m-path">{{ vm.status.job.message }}</p>
        <VAlert v-if="vm.status.job.persist_error" type="error" variant="tonal">{{ vm.status.job.persist_error }}</VAlert>
        <details v-if="vm.status.job.errors?.length"><summary>查看任务错误（{{ vm.status.job.errors.length }}）</summary><p v-for="(item, index) in vm.status.job.errors" :key="index" class="m-path">{{ typeof item === 'string' ? item : item.message || JSON.stringify(item) }}</p></details>
        <p class="m-muted">仅任务运行时每2秒刷新状态；页面隐藏时暂停。停止请求会等待当前文件完成。</p>
      </section>
      <section class="m-card" aria-label="秒传历史">
        <div class="m-row"><h2 class="m-grow">秒传历史</h2><span class="m-badge">{{ vm.filteredHistory.length }} 条</span></div>
        <div class="m-row m-spacer"><input v-model="vm.historyQuery" class="m-input m-grow" type="search" aria-label="筛选历史文件或路径" placeholder="筛选文件、路径或消息"><select v-model="vm.historyFilter" class="m-input" style="width: auto; max-width: 100%" aria-label="历史状态筛选"><option value="all">全部状态</option><option value="success">成功</option><option value="failed">失败</option><option value="skipped">跳过</option></select></div>
        <div class="m-history"><article v-for="(row, index) in vm.pagedHistory" :key="`${row.path}-${row.time}-${index}`"><div class="m-row"><strong class="m-grow m-name">{{ row.name || row.path }}</strong><span class="m-badge">{{ statusLabel(row.status) }}</span></div><p class="m-muted m-path">{{ row.path }} → {{ row.remote_dir }}</p><p class="m-muted">{{ sizeText(row.size) }} · {{ row.time || '—' }}</p><p v-if="row.message" class="m-path">{{ row.message }}</p></article></div>
        <p v-if="!vm.filteredHistory.length" class="m-muted m-spacer">没有匹配的历史记录。</p>
        <div v-if="vm.historyPages > 1" class="m-pager"><VBtn variant="text" :disabled="vm.historyPage <= 1" @click="vm.historyPage--">上一页</VBtn><span>{{ Math.min(vm.historyPage, vm.historyPages) }} / {{ vm.historyPages }}</span><VBtn variant="text" :disabled="vm.historyPage >= vm.historyPages" @click="vm.historyPage++">下一页</VBtn></div>
      </section>
      <p class="m-muted">ManualPush115 · {{ vm.status.version || '1.8.0' }} · 不触发任何自动调度</p>
    </div>
    <LocalPicker :picker="vm.local" /><RemotePicker :picker="vm.remote" />
    <VDialog v-model="vm.settingsOpen" max-width="850" persistent scrollable><div class="m-dialog" style="padding: 0"><Config v-if="vm.settingsOpen" :api="api" :plugin-id="pluginId" :source-plugin-id="sourcePluginId" :native-subscribe="nativeSubscribe" is-embedded @saved="vm.settingsSaved" @save="emit('save', $event)" @close="vm.settingsOpen = false" @switch="configSwitch" /></div></VDialog>
  </section>
</template>
<style scoped src="../styles/panel.css"></style>
