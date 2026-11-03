import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
import { clone, createGeneration, errorText, normalizeSettings, requestId } from '../utils/api.js'
import { useLocalPicker } from './useLocalPicker.js'
import { useRemotePicker } from './useRemotePicker.js'

export function useWorkbench(client, emit) {
  const local = useLocalPicker(client), remote = useRemotePicker(client)
  const status = ref({ has_cookie: false, running: false, job: {}, history: [] })
  const loaded = ref(false), loading = ref(false), error = ref(''), notice = ref('')
  const submitting = ref(false), cancelling = ref(false), cancelRequested = ref(false), savingSelection = ref(false)
  const settingsOpen = ref(false), preserveStructure = ref(true), skipUnchanged = ref(false)
  const historyQuery = ref(''), historyFilter = ref('all'), historyPage = ref(1)
  const statusGate = createGeneration()
  let timer = null, disposed = false, active = true
  const canPush = computed(() => loaded.value && status.value.has_cookie && local.selected.value.length > 0 && !status.value.running && !submitting.value)
  const progress = computed(() => status.value.job?.total > 0 ? Math.min(100, Math.round((status.value.job.processed || 0) / status.value.job.total * 100)) : 0)
  const filteredHistory = computed(() => (status.value.history || []).filter(row => (historyFilter.value === 'all' || row.status === historyFilter.value) && (!historyQuery.value.trim() || `${row.name} ${row.path} ${row.message}`.toLowerCase().includes(historyQuery.value.trim().toLowerCase()))))
  const historyPages = computed(() => Math.max(1, Math.ceil(filteredHistory.value.length / 20)))
  const pagedHistory = computed(() => { const page = Math.min(historyPage.value, historyPages.value); return filteredHistory.value.slice((page - 1) * 20, page * 20) })
  function stopPolling() { if (timer !== null) clearTimeout(timer); timer = null }
  function visible() { return active && !disposed && (typeof document === 'undefined' || !document.hidden) }
  function syncPolling() {
    stopPolling()
    if (status.value.running && visible()) timer = setTimeout(() => { timer = null; if (visible()) loadStatus() }, 2000)
  }
  async function loadStatus() {
    if (disposed) return
    stopPolling()
    const ticket = statusGate.next(); loading.value = true; error.value = ''
    try {
      const data = await client.get('status')
      if (!statusGate.current(ticket) || disposed) return
      if (typeof data.running !== 'boolean' || typeof data.has_cookie !== 'boolean') throw new Error('状态响应不完整')
      status.value = { ...data, job: data.job || {}, history: data.history || [] }; loaded.value = true
      if (!local.selectionTouched.value) local.selected.value = [...new Set(data.local_paths || [])]
      if (!remote.touched.value) remote.target.value = { path: data.remote_dir || '/', cid: null }
      if (!data.running) cancelRequested.value = false
    } catch (cause) { if (statusGate.current(ticket) && !disposed) { error.value = errorText(cause); loaded.value = false } }
    finally { if (statusGate.current(ticket) && !disposed) { loading.value = false; syncPolling() } }
  }
  async function push() {
    if (!canPush.value) return
    submitting.value = true; error.value = ''; notice.value = ''; statusGate.invalidate(); stopPolling()
    const target = clone(remote.target.value)
    const body = { paths: [...local.selected.value], remote_dir: target.path || '/', force: !skipUnchanged.value, preserve_structure: preserveStructure.value, request_id: requestId(), ...(target.cid != null ? { remote_cid: target.cid } : {}) }
    try {
      const data = await client.post('push', body)
      status.value.running = true; cancelRequested.value = false
      status.value.job = { id: data.job_id, phase: 'collecting', total: 0, processed: 0 }
      notice.value = `任务已受理（${data.accepted ?? body.paths.length} 个所选路径），后台收集文件后秒传。`
      emit('action'); await loadStatus()
    } catch (cause) {
      // A transport error may occur after acceptance. Require status confirmation
      // before allowing another submission rather than risk a duplicate job.
      error.value = `${errorText(cause)}；请刷新确认任务状态后重试。`; loaded.value = false; syncPolling()
    }
    finally { submitting.value = false; loading.value = false }
  }
  async function cancel() {
    if (!status.value.running || cancelling.value || cancelRequested.value) return
    cancelling.value = true; error.value = ''
    try { await client.post('cancel'); cancelRequested.value = true; notice.value = '已请求停止，等待当前文件完成；后台仍可能运行。' }
    catch (cause) { error.value = errorText(cause) }
    finally { cancelling.value = false }
  }
  async function saveSelection() {
    if (savingSelection.value) return
    savingSelection.value = true; error.value = ''; notice.value = ''
    const paths = [...local.selected.value], target = remote.target.value.path || '/'
    try {
      const latest = await client.get('settings')
      const config = normalizeSettings(latest.settings)
      const data = await client.post('settings', { ...config, local_paths: paths, remote_dir: target })
      normalizeSettings(data.settings)
      notice.value = '已将本次选择保存为默认路径，不影响后续选择；无需保存也能直接秒传。'
    } catch (cause) { error.value = errorText(cause) }
    finally { savingSelection.value = false }
  }
  function settingsSaved(config) {
    remote.invalidate()
    if (!remote.touched.value) remote.target.value.path = config.remote_dir || '/'
    loadStatus()
  }
  function visibilityChanged() { if (visible() && status.value.running) loadStatus(); else stopPolling() }
  onMounted(() => {
    // Initial load must work in an initially hidden iOS WebView too.
    loadStatus()
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', visibilityChanged)
  })
  onActivated(() => { active = true; syncPolling() })
  onDeactivated(() => { active = false; stopPolling() })
  onBeforeUnmount(() => {
    disposed = true; stopPolling(); statusGate.invalidate(); local.dispose(); remote.dispose()
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', visibilityChanged)
  })
  return { local, remote, status, loaded, loading, error, notice, submitting, cancelling, cancelRequested, savingSelection, settingsOpen, preserveStructure, skipUnchanged, canPush, progress, historyQuery, historyFilter, historyPage, historyPages, filteredHistory, pagedHistory, loadStatus, push, cancel, saveSelection, settingsSaved, syncPolling, visibilityChanged }
}
