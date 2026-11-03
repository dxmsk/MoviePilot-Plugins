import { getCurrentInstance, inject, unref } from 'vue'
import { createClient } from '../utils/api.js'

export const hostProps = {
  api: { type: Object, default: null },
  pluginId: { type: String, default: '' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
}

export function useClient(props) {
  const injectedApi = inject('moviepilot:api', null)
  const legacyApi = inject('api', null)
  const injectedId = inject('moviepilot:pluginId', '')
  const instance = getCurrentInstance()
  function hostId() {
    const explicit = unref(injectedId)
    if (explicit) return explicit
    // Older V2 PluginConfigDialog/PluginDataDialog pass only api. Their
    // own plugin prop still contains the instance identity; do not fall
    // back to another installed plugin or the fixed source name.
    for (let parent = instance?.parent, level = 0; parent && level < 20; parent = parent.parent, level++) {
      const value = unref(parent.props?.plugin)
      if (value?.id) return String(value.id)
      if (parent.props?.pluginId) return String(parent.props.pluginId)
    }
    return ''
  }
  return createClient(() => ({ api: props.api || unref(injectedApi) || unref(legacyApi), props, injectedId: hostId() }))
}
