import { computed, ref } from 'vue'
import { createGeneration, errorText } from '../utils/api.js'

export function useLocalPicker(client) {
  const open = ref(false), loading = ref(false), error = ref(''), warnings = ref([])
  const roots = ref([]), path = ref(''), result = ref(null), mode = ref('roots')
  const query = ref(''), recursive = ref(false), searchSpec = ref(null)
  const selected = ref([]), selectionTouched = ref(false)
  const gate = createGeneration()
  const crumbs = computed(() => {
    const root = [...roots.value].sort((a, b) => b.path.length - a.path.length).find(root => path.value === root.path || path.value.startsWith(root.path.replace(/\/$/, '') + '/'))
    if (!root) return []
    const items = [{ name: root.name || root.path, path: root.path }]
    let current = root.path.replace(/\/$/, '')
    for (const name of path.value.slice(current.length).split('/').filter(Boolean)) { current += `/${name}`; items.push({ name, path: current }) }
    return items
  })
  async function fetchView(type, target = '', offset = 0, spec = null) {
    const ticket = gate.next()
    mode.value = type; path.value = target; result.value = null
    loading.value = true; error.value = ''; warnings.value = []
    try {
      const data = await client.get(type === 'roots' ? 'roots' : type === 'search' ? 'search' : 'browse', type === 'roots' ? undefined : { path: target, offset, limit: 100, ...(type === 'search' ? spec : {}) })
      if (!gate.current(ticket)) return
      if (type === 'roots') {
        if (!Array.isArray(data.roots)) throw new Error('挂载根目录响应无效')
        roots.value = data.roots
      } else {
        if (!Array.isArray(data.entries) || typeof data.path !== 'string') throw new Error('本地目录响应无效')
        result.value = data; path.value = data.path
      }
      warnings.value = data.warnings || []
    } catch (cause) { if (gate.current(ticket)) error.value = errorText(cause) }
    finally { if (gate.current(ticket)) loading.value = false }
  }
  function showRoots() { searchSpec.value = null; return fetchView('roots') }
  function enter(target) { searchSpec.value = null; return fetchView('browse', target) }
  async function show() { open.value = true; return showRoots() }
  function search() {
    if (!query.value.trim()) { error.value = '请输入搜索关键词'; return }
    if (!path.value) { error.value = '请先进入一个 MP 挂载目录'; return }
    searchSpec.value = { query: query.value.trim(), recursive: recursive.value }
    return fetchView('search', path.value, 0, searchSpec.value)
  }
  function page(offset) {
    if (loading.value || !result.value) return
    return fetchView(mode.value, path.value, Math.max(0, offset), searchSpec.value)
  }
  function retry() { return fetchView(mode.value, path.value, 0, searchSpec.value) }
  function toggle(target) {
    selectionTouched.value = true
    selected.value = selected.value.includes(target) ? selected.value.filter(item => item !== target) : [...selected.value, target]
  }
  function selectCurrent() {
    if (loading.value || error.value || !result.value || !path.value) return
    if (!selected.value.includes(path.value)) toggle(path.value)
  }
  function remove(target) { selectionTouched.value = true; selected.value = selected.value.filter(item => item !== target) }
  function clear() { selectionTouched.value = true; selected.value = [] }
  function locate(entry) { return enter(entry.path.slice(0, entry.path.lastIndexOf('/')) || '/') }
  function up() { return result.value?.parent ? enter(result.value.parent) : showRoots() }
  function dispose() { gate.invalidate() }
  return { open, loading, error, warnings, roots, path, result, mode, query, recursive, searchSpec, selected, selectionTouched, crumbs, show, showRoots, enter, search, page, retry, toggle, remove, clear, selectCurrent, locate, up, dispose }
}
