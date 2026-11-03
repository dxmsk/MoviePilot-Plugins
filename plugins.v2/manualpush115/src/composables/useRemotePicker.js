import { ref } from 'vue'
import { createGeneration, errorText } from '../utils/api.js'
export function useRemotePicker(client) {
  const open = ref(false), loading = ref(false), error = ref(''), result = ref(null)
  const target = ref({ path: '/', cid: null }), touched = ref(false), pendingCid = ref('0')
  const gate = createGeneration(), previousOffsets = ref([])
  async function load(cid = '0', offset = 0, paging = false) {
    const ticket = gate.next()
    if (!paging) previousOffsets.value = []
    pendingCid.value = String(cid); loading.value = true; error.value = ''; result.value = null
    try {
      const data = await client.get('remote', { cid, offset, limit: 100 })
      if (!gate.current(ticket)) return
      if (!Array.isArray(data.entries) || data.cid == null || typeof data.path !== 'string') throw new Error('115 目录响应无效')
      result.value = data
    } catch (cause) { if (gate.current(ticket)) error.value = errorText(cause) }
    finally { if (gate.current(ticket)) loading.value = false }
  }
  function show() { open.value = true; return load(target.value.cid ?? '0') }
  function choose() {
    if (loading.value || error.value || !result.value) return false
    target.value = { path: result.value.path, cid: String(result.value.cid) }
    touched.value = true; open.value = false; return true
  }
  function up() { if (result.value?.parent_cid != null && String(result.value.cid) !== '0') return load(result.value.parent_cid) }
  function page(offset) { if (!loading.value && result.value) return load(result.value.cid, Math.max(0, offset), true) }
  function nextPage() {
    if (loading.value || !result.value?.has_more) return
    const { offset = 0, limit = 100, next_offset } = result.value
    previousOffsets.value.push(offset)
    return page(next_offset ?? offset + limit)
  }
  function previousPage() {
    if (loading.value || !result.value || !previousOffsets.value.length) return
    return page(previousOffsets.value.pop())
  }
  function invalidate() { gate.invalidate(); result.value = null; target.value.cid = null; loading.value = false; open.value = false }
  function dispose() { gate.invalidate() }
  return { open, loading, error, result, target, touched, pendingCid, previousOffsets, load, show, choose, up, page, nextPage, previousPage, invalidate, dispose }
}
