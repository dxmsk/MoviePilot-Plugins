export function unwrapResponse(response) {
  let envelope = response
  for (let depth = 0; depth < 3 && envelope && typeof envelope.success !== 'boolean' && envelope.data; depth++) envelope = envelope.data
  if (!envelope || typeof envelope.success !== 'boolean') throw new Error('接口响应格式错误，请刷新后重试')
  if (!envelope.success) throw new Error(envelope.message || '操作失败')
  return envelope.data ?? {}
}

export function resolvePluginId(props = {}, api = {}, injectedId = '') {
  // Instance identity must win over the source plugin identity.
  return String(props.pluginId || api?.pluginId || api?.plugin_id || api?.instanceId || injectedId || props.sourcePluginId || api?.sourcePluginId || '').trim()
}

export function createClient(context) {
  async function request(method, endpoint, payload) {
    const { api, props, injectedId } = context()
    if (!api || typeof api[method] !== 'function') throw new Error('宿主认证 API 不可用，请重新打开插件')
    const id = resolvePluginId(props, api, injectedId)
    if (!id) throw new Error('缺少插件实例 ID，请从 MoviePilot 插件入口打开')
    let url = `plugin/${encodeURIComponent(id)}/${endpoint}`
    if (method === 'get' && payload) url += `?${new URLSearchParams(Object.entries(payload).filter(([, value]) => value !== undefined)).toString()}`
    return unwrapResponse(await (method === 'get' ? api.get(url) : api.post(url, payload)))
  }
  return { get: (path, params) => request('get', path, params), post: (path, data = {}) => request('post', path, data) }
}

export function createGeneration() {
  let generation = 0
  return { next: () => ++generation, current: ticket => ticket === generation, invalidate: () => ++generation }
}
export const clone = value => JSON.parse(JSON.stringify(value))
export const errorText = error => error?.message || '请求失败，请重试'
export const settingsKeys = ['cookie', 'user_agent', 'extensions', 'remote_dir', 'local_paths']
export function completeSettings(value) {
  return !!value && settingsKeys.every(key => Object.hasOwn(value, key)) && Array.isArray(value.local_paths) && settingsKeys.slice(0, 4).every(key => typeof value[key] === 'string')
}
export function normalizeSettings(value) {
  if (!completeSettings(value)) throw new Error('配置响应不完整，已禁止保存，避免覆盖原配置')
  return Object.fromEntries(settingsKeys.map(key => [key, clone(value[key])]))
}
export function sizeText(bytes) {
  if (!Number.isFinite(Number(bytes))) return '—'
  const size = Number(bytes)
  if (size < 1024) return `${size} B`
  const i = Math.min(Math.floor(Math.log(size) / Math.log(1024)), 4)
  return `${(size / 1024 ** i).toFixed(1)} ${['B', 'KB', 'MB', 'GB', 'TB'][i]}`
}
export function requestId() {
  return globalThis.crypto?.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const r = Math.floor(Math.random() * 16); return (c === 'x' ? r : (r & 3) | 8).toString(16) })
}
