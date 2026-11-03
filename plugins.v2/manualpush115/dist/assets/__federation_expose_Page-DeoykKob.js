import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { W as Workbench } from './Workbench-DNrZd_BY.js';
import { h as hostProps } from './__federation_expose_Config--inL-uro.js';

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');

const _sfc_main = {
  __name: 'Page',
  props: hostProps,
  emits: ['action', 'save', 'switch', 'close'],
  setup(__props) {




return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(Workbench, {
    api: _ctx.api,
    "plugin-id": _ctx.pluginId,
    "source-plugin-id": _ctx.sourcePluginId,
    "native-subscribe": _ctx.nativeSubscribe,
    "show-close": "",
    onAction: _cache[0] || (_cache[0] = $event => (_ctx.$emit('action', $event))),
    onSave: _cache[1] || (_cache[1] = $event => (_ctx.$emit('save', $event))),
    onSwitch: _cache[2] || (_cache[2] = $event => (_ctx.$emit('switch', $event))),
    onClose: _cache[3] || (_cache[3] = $event => (_ctx.$emit('close', $event)))
  }, null, 8, ["api", "plugin-id", "source-plugin-id", "native-subscribe"]))
}
}

};

export { _sfc_main as default };
