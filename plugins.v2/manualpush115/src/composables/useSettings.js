import { computed, ref } from 'vue'
import { clone, completeSettings, createGeneration, errorText, normalizeSettings } from '../utils/api.js'
export function useSettings(client, initialConfig, embedded, emit) {
  const draft = ref({ cookie: '', user_agent: '', extensions: '', remote_dir: '/', local_paths: [] })
  const saved = ref(null), loaded = ref(false), loading = ref(false), saving = ref(false), testing = ref(false)
  const error = ref(''), notice = ref(''), revision = ref(null)
  const gate = createGeneration()
  const dirty = computed(() => saved.value !== null && JSON.stringify(draft.value) !== JSON.stringify(saved.value))
  const canSave = computed(() => loaded.value && !loading.value && !saving.value && completeSettings(draft.value))
  function seed(config) {
    if (!completeSettings(config) || saved.value !== null) return false
    saved.value = normalizeSettings(config); draft.value = clone(saved.value); loaded.value = true; return true
  }
  seed(initialConfig)
  async function load() {
    const ticket = gate.next(); loading.value = true; error.value = ''; loaded.value = false
    const before = JSON.stringify(draft.value)
    try {
      const data = await client.get('settings')
      if (!gate.current(ticket)) return
      const config = normalizeSettings(data.settings)
      if ((!saved.value || !dirty.value) && JSON.stringify(draft.value) === before) draft.value = clone(config)
      saved.value = clone(config); revision.value = data.revision; loaded.value = true
    } catch (cause) { if (gate.current(ticket)) error.value = errorText(cause) }
    finally { if (gate.current(ticket)) loading.value = false }
  }
  async function save() {
    if (!canSave.value) return
    const snapshot = normalizeSettings(draft.value)
    if (!embedded) { emit('save', snapshot); notice.value = '已交由宿主保存；以宿主保存结果为准'; return }
    saving.value = true; error.value = ''; notice.value = ''
    try {
      const data = await client.post('settings', snapshot)
      const config = normalizeSettings(data.settings)
      saved.value = clone(config); revision.value = data.revision
      if (JSON.stringify(draft.value) === JSON.stringify(snapshot)) draft.value = clone(config)
      notice.value = '配置已保存'; emit('saved', clone(config)); emit('save', clone(config))
    } catch (cause) { error.value = errorText(cause) }
    finally { saving.value = false }
  }
  async function testSaved() {
    if (testing.value || saving.value) return
    testing.value = true; notice.value = ''; error.value = ''
    try { const data = await client.post('test'); notice.value = data.message || '已保存配置连接测试成功' }
    catch (cause) { error.value = errorText(cause) }
    finally { testing.value = false }
  }
  function discard() { if (saved.value) draft.value = clone(saved.value) }
  return { draft, saved, loaded, loading, saving, testing, error, notice, revision, dirty, canSave, seed, load, save, testSaved, discard, dispose: () => gate.invalidate() }
}
