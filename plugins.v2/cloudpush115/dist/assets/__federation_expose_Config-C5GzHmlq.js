import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { W as Workbench } from './Workbench-D2srnewj.js';

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const {onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: Object, default: () => ({}) },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['layout', 'close'],
  setup(__props, { emit: __emit }) {


const emit = __emit;
onMounted(() => emit('layout', { maxWidth: '86rem' }));

return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(Workbench, {
    api: __props.api,
    compact: "",
    "show-close": "",
    "initial-tab": "settings",
    onClose: _cache[0] || (_cache[0] = $event => (_ctx.$emit('close')))
  }, null, 8, ["api"]))
}
}

};

export { _sfc_main as default };
