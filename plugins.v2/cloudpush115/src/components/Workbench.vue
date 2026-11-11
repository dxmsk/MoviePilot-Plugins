<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  initialTab: { type: String, default: 'history' },
  compact: { type: Boolean, default: false },
  showClose: { type: Boolean, default: false },
})
const emit = defineEmits(['action', 'close'])
const hostToast = inject('moviepilot:toast', null)
const loading = ref(true)
const error = ref('')
const scanning = ref(false)
const testing = ref(false)
const indexing = ref(false)
const retrying = ref(false)
const activeTab = ref(props.initialTab)
const lastSynced = ref(null)
const now = ref(Date.now())
let mounted = false, disposed = false, pollTimer = null, clockTimer = null

const pluginBase = 'plugin/CloudPush115'
const status = ref({
  enabled: false, running: false, phase: 'idle', version: '',
  done_count: 0, retry_count: 0, local_count: 0,
  stats: {}, history: [], retry_queue: [], local_queue: [], qb_queue: [], roots: [],
  last_run: null, last_error: null, storage_error: null, qb_error: null,
  has_cookie: false, remote_dir: '',
})

const phaseLabel = computed(() => ({
  indexing: '扫描本地文件', ready: '索引完成', uploading: '处理本地队列',
  retry: '处理重试队列', qb: '检查 qB 任务', idle: '空闲',
}[status.value.phase] || status.value.phase))

const statusMap = {
  success: { label: '秒传成功', color: 'success', icon: 'mdi-check-circle' },
  failed: { label: '失败', color: 'error', icon: 'mdi-close-circle' },
  skipped: { label: '跳过', color: 'default', icon: 'mdi-skip-next-circle' },
  retry: { label: '待重试', color: 'warning', icon: 'mdi-restart' },
  exhausted: { label: '重试已达上限', color: 'error', icon: 'mdi-alert-circle' },
  pending: { label: '待处理', color: 'info', icon: 'mdi-clock-outline' },
  processing: { label: '秒传中', color: 'primary', icon: 'mdi-cloud-upload' },
  uploading: { label: '秒传中', color: 'primary', icon: 'mdi-cloud-upload' },
  waiting: { label: '等待稳定', color: 'warning', icon: 'mdi-timer-sand' },
  blocked: { label: '暂不可处理', color: 'warning', icon: 'mdi-lock-outline' },
  ready: { label: '就绪', color: 'info', icon: 'mdi-checkbox-marked-circle-outline' },
  indexing: { label: '索引中', color: 'primary', icon: 'mdi-magnify' },
  error: { label: '读取失败', color: 'error', icon: 'mdi-alert' },
  legacy: { label: '旧版标记', color: 'default', icon: 'mdi-archive-outline' },
}
function chipProps(s) {
  const entry = statusMap[s] || { label: s || '未知', color: 'default', icon: 'mdi-help-circle' }
  return entry
}
const sourceMap = { local: '本地', qb: 'qB', retry: '本地重试', legacy: '历史记录' }
function sourceLabel(s) { return sourceMap[s] || s || '' }

function formatBytes(v) {
  const b = Number(v || 0); if (!b) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(b) / Math.log(1024)), units.length - 1)
  return `${(b / 1024 ** i).toFixed(i > 1 ? 1 : 0)} ${units[i]}`
}
function formatTime(v) {
  if (!v) return '—'
  const d = new Date(v); return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('zh-CN', { hour12: false })
}

// Search & filter per tab
const historySearch = ref(''); const historyFilter = ref('all'); const historyPage = ref(1); const historyPageSize = ref(20)
const retrySearch = ref(''); const retryPage = ref(1); const retryPageSize = ref(20)
const localSearch = ref(''); const localPage = ref(1); const localPageSize = ref(20)
const qbSearch = ref(''); const qbPage = ref(1); const qbPageSize = ref(20)

const historyFilterOptions = computed(() => {
  const outcomes = new Set((status.value.history || []).map(r => r.status))
  return [{ title: '全部结果', value: 'all' }, ...Array.from(outcomes).filter(Boolean).map(s => ({ title: chipProps(s).label, value: s }))]
})
function filterList(list, search, filterKey, filterValue) {
  return (list || []).filter(row => {
    const q = search.trim().toLocaleLowerCase()
    const textMatch = !q || [row.name, row.path, row.message, row.remote_dir].filter(Boolean).join(' ').toLocaleLowerCase().includes(q)
    const statusMatch = filterValue === 'all' || row[filterKey] === filterValue
    return textMatch && statusMatch
  })
}
function paginate(list, page, size) {
  const start = (page - 1) * size
  return { items: list.slice(start, start + size), pages: Math.max(1, Math.ceil(list.length / size)), total: list.length }
}

const filteredHistory = computed(() => filterList(status.value.history, historySearch.value, 'status', historyFilter.value))
const pagedHistory = computed(() => paginate(filteredHistory.value, historyPage.value, historyPageSize.value))
const filteredRetry = computed(() => filterList(status.value.retry_queue, retrySearch.value, 'status', 'all'))
const pagedRetry = computed(() => paginate(filteredRetry.value, retryPage.value, retryPageSize.value))
const filteredLocal = computed(() => filterList(status.value.local_queue, localSearch.value, 'status', 'all'))
const pagedLocal = computed(() => paginate(filteredLocal.value, localPage.value, localPageSize.value))
const filteredQb = computed(() => filterList(status.value.qb_queue, qbSearch.value, 'status', 'all'))
const pagedQb = computed(() => paginate(filteredQb.value, qbPage.value, qbPageSize.value))

watch([historySearch, historyFilter], () => { historyPage.value = 1 })
watch(retrySearch, () => { retryPage.value = 1 })
watch(localSearch, () => { localPage.value = 1 })
watch(qbSearch, () => { qbPage.value = 1 })

function notify(text, kind = 'success') {
  if (typeof hostToast?.[kind] === 'function') hostToast[kind](text)
  else if (kind === 'error') error.value = text
}

async function loadStatus() {
  try {
    const response = await props.api.get(`${pluginBase}/status`)
    const data = response?.data ?? response
    if (disposed) return
    Object.assign(status.value, data)
    scanning.value = Boolean(data.running)
    error.value = ''
    lastSynced.value = new Date().toISOString()
  } catch (err) {
    if (!disposed) error.value = err?.message || '加载状态失败'
  } finally {
    if (!disposed) loading.value = false
  }
}

async function runOperation(operation, loadingRef) {
  loadingRef.value = true
  try {
    const response = await props.api.post(`${pluginBase}/${operation}`)
    const data = response?.data ?? response
    notify(data?.message || '操作已提交')
    setTimeout(loadStatus, 1500)
    setTimeout(loadStatus, 4000)
  } catch (err) {
    notify(err?.message || '操作失败', 'error')
  } finally {
    loadingRef.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = globalThis.setInterval(() => { if (!disposed && !globalThis.document?.hidden) loadStatus() }, 5000)
}
function stopPolling() { if (pollTimer !== null) { globalThis.clearInterval(pollTimer); pollTimer = null } }

onMounted(() => {
  mounted = true
  loadStatus()
  startPolling()
  clockTimer = globalThis.setInterval(() => { now.value = Date.now() }, 30000)
  globalThis.document?.addEventListener('visibilitychange', onVisibility)
  if (globalThis.document?.hidden) loadStatus()
})
onBeforeUnmount(() => {
  disposed = true; mounted = false; stopPolling()
  if (clockTimer !== null) globalThis.clearInterval(clockTimer)
  globalThis.document?.removeEventListener('visibilitychange', onVisibility)
})
function onVisibility() {
  if (globalThis.document?.hidden) { stopPolling() } else { loadStatus(); startPolling() }
}
</script>

<template>
  <div class="cloud115" :class="{ 'cloud115--compact': compact }">
    <header class="cloud115__header">
      <div class="cloud115__identity">
        <VIcon icon="mdi-cloud-upload" color="primary" size="30" />
        <div><h1>115 网盘秒传</h1><p>SHA1 秒传 · 默认保留原文件 · qB 下载完成即推送</p></div>
      </div>
      <div class="cloud115__actions">
        <VChip :color="status.enabled ? 'success' : 'default'" size="small" variant="tonal">{{ status.enabled ? '已启用' : '未启用' }}</VChip>
        <VChip v-if="status.running" color="primary" size="small" variant="tonal" prepend-icon="mdi-loading mdi-spin">{{ phaseLabel }}</VChip>
        <VChip v-else size="small" variant="tonal">{{ phaseLabel }}</VChip>
        <VTooltip text="刷新"><template #activator="{ props: tip }"><VBtn v-bind="tip" icon="mdi-refresh" variant="text" :loading="loading" @click="loadStatus" /></template></VTooltip>
        <VTooltip v-if="showClose" text="关闭"><template #activator="{ props: tip }"><VBtn v-bind="tip" icon="mdi-close" variant="text" @click="$emit('close')" /></template></VTooltip>
      </div>
    </header>

    <VAlert v-if="error" type="error" variant="tonal" closable @click:close="error = ''">{{ error }}</VAlert>
    <VAlert v-if="status.storage_error" type="warning" variant="tonal">存储错误：{{ status.storage_error }}</VAlert>
    <VAlert v-if="status.qb_error" type="warning" variant="tonal">qB 连接：{{ status.qb_error }}</VAlert>
    <VAlert v-if="status.last_error" type="warning" variant="tonal">{{ status.last_error }}</VAlert>

    <div v-if="loading && !status.version" class="cloud115__loading"><VSkeletonLoader type="list-item-three-line, article" /></div>
    <template v-else>
      <!-- 操作栏 -->
      <div class="operation-actions">
        <VBtn color="primary" variant="flat" prepend-icon="mdi-cloud-upload" :loading="scanning" :disabled="scanning || !status.has_cookie" @click="runOperation('scan', scanning)">扫描秒传</VBtn>
        <VBtn variant="tonal" prepend-icon="mdi-folder-search" :loading="indexing" :disabled="scanning" @click="runOperation('index', indexing)">刷新本地队列</VBtn>
        <VBtn variant="tonal" prepend-icon="mdi-restart" :loading="retrying" :disabled="scanning" color="warning" @click="runOperation('retry', retrying)">重试失败文件</VBtn>
        <VBtn variant="tonal" prepend-icon="mdi-key" :loading="testing" @click="runOperation('test', testing)">测试凭据</VBtn>
      </div>
      <p class="operation-hint">{{ !status.has_cookie ? '未配置 115 Cookie，请在设置中填写后保存。' : scanning ? '正在' + phaseLabel + '…' : '最近扫描：' + (status.last_run || '尚未运行') + ' · 最近同步 ' + formatTime(lastSynced) }}</p>

      <!-- 统计卡 -->
      <div class="stats">
        <VSheet class="stat app-surface-static"><span>已秒传</span><strong>{{ status.done_count || 0 }}</strong><VIcon icon="mdi-check-circle-outline" color="success" /></VSheet>
        <VSheet class="stat app-surface-static"><span>待重试</span><strong>{{ status.retry_count || 0 }}</strong><VIcon icon="mdi-restart" color="warning" /></VSheet>
        <VSheet class="stat app-surface-static"><span>本地待处理</span><strong>{{ status.local_count || 0 }}</strong><VIcon icon="mdi-folder-open-outline" color="info" /></VSheet>
        <VSheet class="stat app-surface-static"><span>qB 任务</span><strong>{{ status.stats?.qb || 0 }}</strong><VIcon icon="mdi-download-network-outline" color="primary" /></VSheet>
        <VSheet class="stat app-surface-static"><span>已索引</span><strong>{{ status.stats?.indexed || 0 }}</strong><VIcon icon="mdi-file-document-multiple-outline" color="info" /></VSheet>
        <VSheet class="stat app-surface-static"><span>监控路径</span><strong>{{ status.stats?.roots || 0 }}</strong><VIcon icon="mdi-folder-multiple-outline" color="default" /></VSheet>
      </div>

      <!-- Tabs -->
      <VTabs v-model="activeTab" class="cloud115-tabs" show-arrows>
        <VTab value="history" prepend-icon="mdi-history">整理记录 <VChip size="x-small" variant="tonal" class="ml-1">{{ status.stats?.history || 0 }}</VChip></VTab>
        <VTab value="retry" prepend-icon="mdi-restart">待重试 <VChip size="x-small" variant="tonal" class="ml-1">{{ status.stats?.retry || 0 }}</VChip></VTab>
        <VTab value="local" prepend-icon="mdi-folder-open">本地队列 <VChip size="x-small" variant="tonal" class="ml-1">{{ status.stats?.local || 0 }}</VChip></VTab>
        <VTab value="qb" prepend-icon="mdi-download-network">qB 任务 <VChip size="x-small" variant="tonal" class="ml-1">{{ status.stats?.qb || 0 }}</VChip></VTab>
        <VTab value="roots" prepend-icon="mdi-folder-multiple">监控路径</VTab>
      </VTabs>

      <VWindow v-model="activeTab" class="cloud115-window">
        <!-- 整理记录 -->
        <VWindowItem value="history">
          <div class="list-filters">
            <VTextField v-model="historySearch" label="搜索文件名 / 路径" prepend-inner-icon="mdi-magnify" clearable hide-details density="compact" />
            <VSelect v-model="historyFilter" :items="historyFilterOptions" label="结果" hide-details density="compact" style="max-width:160px" />
          </div>
          <VDataTable :headers="[{title:'文件',key:'name',sortable:false},{title:'结果',key:'status',sortable:false,width:110},{title:'大小',key:'size',sortable:false,width:90},{title:'详情',key:'message',sortable:false},{title:'来源',key:'source',sortable:false,width:80},{title:'时间',key:'time',sortable:false,width:160}]" :items="pagedHistory.items" :loading="loading" density="comfortable" class="data-table d-none d-md-block" hide-default-footer>
            <template #item.name="{ item }"><div class="cell-name">{{ item.name }}<small>{{ item.path }}</small></div></template>
            <template #item.status="{ item }"><VChip :color="chipProps(item.status).color" size="small" variant="tonal">{{ chipProps(item.status).label }}</VChip></template>
            <template #item.size="{ item }">{{ formatBytes(item.size) }}</template>
            <template #item.source="{ item }">{{ sourceLabel(item.source) }}</template>
            <template #item.time="{ item }">{{ formatTime(item.time) }}</template>
            <template #no-data><div class="empty-table">{{ historySearch || historyFilter !== 'all' ? '没有符合筛选的记录' : '尚无整理记录' }}</div></template>
          </VDataTable>
          <!-- 手机卡片 -->
          <div class="mobile-cards d-md-none">
            <div v-for="row in pagedHistory.items" :key="row.path + row.time" class="mobile-card">
              <div class="mobile-card__head"><strong>{{ row.name }}</strong><VChip :color="chipProps(row.status).color" size="x-small" variant="tonal">{{ chipProps(row.status).label }}</VChip></div>
              <small v-if="row.path">{{ row.path }}</small>
              <small v-if="row.message">{{ row.message }}</small>
              <div class="mobile-card__foot"><span>{{ formatBytes(row.size) }}</span><span>{{ sourceLabel(row.source) }}</span><span>{{ formatTime(row.time) }}</span></div>
            </div>
            <div v-if="!pagedHistory.items.length" class="empty-table">{{ historySearch || historyFilter !== 'all' ? '没有符合筛选的记录' : '尚无整理记录' }}</div>
          </div>
          <VPagination v-if="pagedHistory.pages > 1" v-model="historyPage" :length="pagedHistory.pages" density="compact" class="mt-2" />
        </VWindowItem>

        <!-- 待重试 -->
        <VWindowItem value="retry">
          <div class="list-filters"><VTextField v-model="retrySearch" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details density="compact" /></div>
          <VDataTable :headers="[{title:'文件',key:'name',sortable:false},{title:'状态',key:'status',sortable:false,width:120},{title:'已失败',key:'attempts',sortable:false,width:80},{title:'原因',key:'message',sortable:false},{title:'下次重试',key:'next_retry_text',sortable:false,width:140}]" :items="pagedRetry.items" density="comfortable" class="data-table d-none d-md-block" hide-default-footer>
            <template #item.name="{ item }"><div class="cell-name">{{ item.name }}<small>{{ item.remote_dir }}</small></div></template>
            <template #item.status="{ item }"><VChip :color="chipProps(item.status).color" size="small" variant="tonal">{{ chipProps(item.status).label }}</VChip></template>
            <template #no-data><div class="empty-table">当前没有待重试文件</div></template>
          </VDataTable>
          <div class="mobile-cards d-md-none">
            <div v-for="row in pagedRetry.items" :key="row.path" class="mobile-card">
              <div class="mobile-card__head"><strong>{{ row.name }}</strong><VChip :color="chipProps(row.status).color" size="x-small" variant="tonal">{{ chipProps(row.status).label }}</VChip></div>
              <small>第 {{ row.attempts || 0 }} 次 · {{ row.message }}</small>
              <small v-if="row.next_retry_text">下次重试：{{ row.next_retry_text }}</small>
            </div>
            <div v-if="!pagedRetry.items.length" class="empty-table">当前没有待重试文件</div>
          </div>
          <VPagination v-if="pagedRetry.pages > 1" v-model="retryPage" :length="pagedRetry.pages" density="compact" class="mt-2" />
        </VWindowItem>

        <!-- 本地队列 -->
        <VWindowItem value="local">
          <div class="list-filters"><VTextField v-model="localSearch" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details density="compact" /></div>
          <VDataTable :headers="[{title:'文件',key:'name',sortable:false},{title:'状态',key:'status',sortable:false,width:110},{title:'大小',key:'size',sortable:false,width:90},{title:'路径',key:'path',sortable:false},{title:'说明',key:'message',sortable:false}]" :items="pagedLocal.items" density="comfortable" class="data-table d-none d-md-block" hide-default-footer>
            <template #item.name="{ item }"><div class="cell-name">{{ item.name }}</div></template>
            <template #item.status="{ item }"><VChip :color="chipProps(item.status).color" size="small" variant="tonal">{{ chipProps(item.status).label }}</VChip></template>
            <template #item.size="{ item }">{{ formatBytes(item.size) }}</template>
            <template #no-data><div class="empty-table">{{ status.last_index ? '本地队列为空' : '尚未完成本地索引' }}</div></template>
          </VDataTable>
          <div class="mobile-cards d-md-none">
            <div v-for="row in pagedLocal.items" :key="row.path" class="mobile-card">
              <div class="mobile-card__head"><strong>{{ row.name }}</strong><VChip :color="chipProps(row.status).color" size="x-small" variant="tonal">{{ chipProps(row.status).label }}</VChip></div>
              <small>{{ formatBytes(row.size) }} · {{ row.path }}</small>
              <small v-if="row.message">{{ row.message }}</small>
            </div>
            <div v-if="!pagedLocal.items.length" class="empty-table">{{ status.last_index ? '本地队列为空' : '尚未完成本地索引' }}</div>
          </div>
          <VPagination v-if="pagedLocal.pages > 1" v-model="localPage" :length="pagedLocal.pages" density="compact" class="mt-2" />
        </VWindowItem>

        <!-- qB 任务 -->
        <VWindowItem value="qb">
          <div class="list-filters"><VTextField v-model="qbSearch" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details density="compact" /></div>
          <VDataTable :headers="[{title:'种子',key:'name',sortable:false},{title:'状态',key:'status',sortable:false,width:110},{title:'就绪文件',key:'ready',sortable:false,width:90},{title:'路径',key:'path',sortable:false},{title:'诊断',key:'message',sortable:false}]" :items="pagedQb.items" density="comfortable" class="data-table d-none d-md-block" hide-default-footer>
            <template #item.name="{ item }"><div class="cell-name">{{ item.name }}</div></template>
            <template #item.status="{ item }"><VChip :color="chipProps(item.status).color" size="small" variant="tonal">{{ chipProps(item.status).label }}</VChip></template>
            <template #item.ready="{ item }">{{ item.ready || 0 }}/{{ item.total || 0 }}</template>
            <template #no-data><div class="empty-table">未发现待处理 qB 任务</div></template>
          </VDataTable>
          <div class="mobile-cards d-md-none">
            <div v-for="row in pagedQb.items" :key="row.path || row.name" class="mobile-card">
              <div class="mobile-card__head"><strong>{{ row.name }}</strong><VChip :color="chipProps(row.status).color" size="x-small" variant="tonal">{{ chipProps(row.status).label }}</VChip></div>
              <small>就绪 {{ row.ready || 0 }}/{{ row.total || 0 }} · {{ row.path }}</small>
              <small v-if="row.message">{{ row.message }}</small>
            </div>
            <div v-if="!pagedQb.items.length" class="empty-table">未发现待处理 qB 任务</div>
          </div>
          <VPagination v-if="pagedQb.pages > 1" v-model="qbPage" :length="pagedQb.pages" density="compact" class="mt-2" />
        </VWindowItem>

        <!-- 监控路径 -->
        <VWindowItem value="roots">
          <VDataTable :headers="[{title:'路径',key:'path',sortable:false},{title:'索引状态',key:'status',sortable:false,width:110},{title:'媒体文件数',key:'file_count',sortable:false,width:110},{title:'说明',key:'message',sortable:false}]" :items="status.roots || []" density="comfortable" class="data-table d-none d-md-block" hide-default-footer>
            <template #item.status="{ item }"><VChip :color="chipProps(item.status).color" size="small" variant="tonal">{{ chipProps(item.status).label }}</VChip></template>
            <template #no-data><div class="empty-table">尚未配置或索引本地路径</div></template>
          </VDataTable>
          <div class="mobile-cards d-md-none">
            <div v-for="row in (status.roots || [])" :key="row.path" class="mobile-card">
              <div class="mobile-card__head"><strong>{{ row.path }}</strong><VChip :color="chipProps(row.status).color" size="x-small" variant="tonal">{{ chipProps(row.status).label }}</VChip></div>
              <small>{{ row.file_count || 0 }} 个媒体文件 · {{ row.message || '' }}</small>
            </div>
            <div v-if="!(status.roots || []).length" class="empty-table">尚未配置或索引本地路径</div>
          </div>
        </VWindowItem>
      </VWindow>

      <div class="cloud115__footer">
        最近本地秒传：{{ status.last_scan || '尚未执行' }} · 最近 qB 检查：{{ status.last_qb || '尚未执行' }} · 115 目标：{{ status.remote_dir || '/' }} · v{{ status.version }}
      </div>
    </template>
  </div>
</template>

<style scoped>
.cloud115 { display: flex; flex-direction: column; gap: 16px; min-inline-size: 0; padding: 16px; }
.cloud115--compact { padding: 20px; }
.cloud115__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.cloud115__identity { display: flex; align-items: center; gap: 12px; min-inline-size: 0; }
.cloud115__identity h1 { margin: 0; font-size: 1.25rem; line-height: 1.35; letter-spacing: 0; }
.cloud115__identity p { margin: 2px 0 0; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: .85rem; }
.cloud115__actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cloud115__loading { min-block-size: 24rem; }
.operation-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.operation-hint { color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: .82rem; margin: 0; }
.stats { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.stat { position: relative; display: flex; flex-direction: column; gap: 4px; min-block-size: 96px; padding: 16px; border: var(--app-surface-border); border-radius: var(--app-surface-radius); }
.stat span { color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: .82rem; }
.stat strong { font-size: 1.4rem; }
.stat > :deep(.v-icon) { position: absolute; inset: 16px 16px auto auto; }
.cloud115-tabs { max-inline-size: 100%; }
.cloud115-window { padding-block-start: 16px; }
.list-filters { display: flex; gap: 10px; margin-block-end: 12px; }
.data-table { background: transparent; }
.cell-name { display: flex; flex-direction: column; max-inline-size: 30rem; }
.cell-name strong, .cell-name small { overflow-wrap: anywhere; }
.cell-name small { color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: .78rem; }
.mobile-cards { display: flex; flex-direction: column; gap: 8px; }
.mobile-card { padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: var(--app-control-radius, 10px); }
.mobile-card__head { display: flex; align-items: flex-start; gap: 8px; }
.mobile-card__head strong { flex: 1; min-inline-size: 0; overflow-wrap: anywhere; font-size: .9rem; }
.mobile-card small { display: block; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: .78rem; margin-top: 4px; overflow-wrap: anywhere; }
.mobile-card__foot { display: flex; gap: 12px; margin-top: 6px; font-size: .75rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.empty-table { padding: 28px 12px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); text-align: center; }
.cloud115__footer { color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: .78rem; overflow-wrap: anywhere; }
@media (max-width: 1199px) { .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 699px) {
  .cloud115 { padding: 12px; }
  .cloud115__identity p { display: none; }
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .operation-actions { flex-direction: column; }
  .list-filters { flex-direction: column; }
}
</style>
