import { inject, unref } from 'vue'
import { createClient } from '../utils/api.js'
export const hostProps = {
  api: { type: Object, default: null },
  pluginId: { type: String, default: '' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
}
export function useClient(props) {
  const injectedApi = inject('moviepilot:api', null)
  const injectedId = inject('moviepilot:pluginId', '')
  return createClient(() => ({ api: props.api || unref(injectedApi), props, injectedId: unref(injectedId) }))
}
