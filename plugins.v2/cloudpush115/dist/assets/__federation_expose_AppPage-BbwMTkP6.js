import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { W as Workbench } from './Workbench-Ce3-wtO_.js';

const {unref:_unref,openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const {inject} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  setup(__props) {

const api = inject('api');

return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(Workbench, { api: _unref(api) }, null, 8, ["api"]))
}
}

};

export { _sfc_main as default };
