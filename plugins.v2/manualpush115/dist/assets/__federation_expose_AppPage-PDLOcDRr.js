import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { W as Workbench } from './Workbench-BrX1lFzk.js';
import Config, { h as hostProps } from './__federation_expose_Config-CrfibsL-.js';

const {openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');

const _sfc_main = {
  __name: 'AppPage',
  props: { ...hostProps, navKey: { type: String, default: 'main' }, initialConfig: { type: Object, default: () => ({}) } },
  emits: ['action', 'save', 'switch', 'close'],
  setup(__props) {




return (_ctx, _cache) => {
  return (__props.navKey === 'settings')
    ? (_openBlock(), _createBlock(Config, {
        key: 0,
        api: _ctx.api,
        "plugin-id": _ctx.pluginId,
        "source-plugin-id": _ctx.sourcePluginId,
        "initial-config": __props.initialConfig,
        "is-embedded": "",
        onSave: _cache[0] || (_cache[0] = $event => (_ctx.$emit('save', $event))),
        onSwitch: _cache[1] || (_cache[1] = $event => (_ctx.$emit('switch', $event))),
        onClose: _cache[2] || (_cache[2] = $event => (_ctx.$emit('close', $event)))
      }, null, 8, ["api", "plugin-id", "source-plugin-id", "initial-config"]))
    : (_openBlock(), _createBlock(Workbench, {
        key: 1,
        api: _ctx.api,
        "plugin-id": _ctx.pluginId,
        "source-plugin-id": _ctx.sourcePluginId,
        "native-subscribe": _ctx.nativeSubscribe,
        onAction: _cache[3] || (_cache[3] = $event => (_ctx.$emit('action', $event))),
        onSave: _cache[4] || (_cache[4] = $event => (_ctx.$emit('save', $event))),
        onSwitch: _cache[5] || (_cache[5] = $event => (_ctx.$emit('switch', $event))),
        onClose: _cache[6] || (_cache[6] = $event => (_ctx.$emit('close', $event)))
      }, null, 8, ["api", "plugin-id", "source-plugin-id", "native-subscribe"]))
}
}

};

export { _sfc_main as default };
