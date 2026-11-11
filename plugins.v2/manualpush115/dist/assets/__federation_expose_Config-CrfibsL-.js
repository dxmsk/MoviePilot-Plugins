import { importShared } from './__federation_fn_import-JrT3xvdd.js';

function unwrapResponse(response) {
  let envelope = response;
  for (let depth = 0; depth < 3 && envelope && typeof envelope.success !== 'boolean' && envelope.data; depth++) envelope = envelope.data;
  if (!envelope || typeof envelope.success !== 'boolean') throw new Error('接口响应格式错误，请刷新后重试')
  if (!envelope.success) throw new Error(envelope.message || '操作失败')
  return envelope.data ?? {}
}

function resolvePluginId(props = {}, api = {}, injectedId = '') {
  // Instance identity must win over the source plugin identity.
  return String(props.pluginId || api?.pluginId || api?.plugin_id || api?.instanceId || injectedId || props.sourcePluginId || api?.sourcePluginId || '').trim()
}

function createClient(context) {
  async function request(method, endpoint, payload) {
    const { api, props, injectedId } = context();
    if (!api || typeof api[method] !== 'function') throw new Error('宿主认证 API 不可用，请重新打开插件')
    const id = resolvePluginId(props, api, injectedId);
    if (!id) throw new Error('缺少插件实例 ID，请从 MoviePilot 插件入口打开')
    let url = `plugin/${encodeURIComponent(id)}/${endpoint}`;
    if (method === 'get' && payload) url += `?${new URLSearchParams(Object.entries(payload).filter(([, value]) => value !== undefined)).toString()}`;
    return unwrapResponse(await (method === 'get' ? api.get(url) : api.post(url, payload)))
  }
  return { get: (path, params) => request('get', path, params), post: (path, data = {}) => request('post', path, data) }
}

function createGeneration() {
  let generation = 0;
  return { next: () => ++generation, current: ticket => ticket === generation, invalidate: () => ++generation }
}
const clone = value => JSON.parse(JSON.stringify(value));
const errorText = error => error?.message || '请求失败，请重试';
const settingsKeys = ['cookie', 'user_agent', 'extensions', 'remote_dir', 'local_paths', 'failure_move_enabled', 'failure_move_dir', 'delete_on_success', 'failure_move_preserve_structure'];
function completeSettings(value) {
  return !!value && settingsKeys.slice(0, 5).every(key => Object.hasOwn(value, key)) && Array.isArray(value.local_paths) && settingsKeys.slice(0, 4).every(key => typeof value[key] === 'string')
}
function normalizeSettings(value) {
  if (!completeSettings(value)) throw new Error('配置响应不完整，已禁止保存，避免覆盖原配置')
  const merged = { failure_move_enabled: false, failure_move_dir: '', delete_on_success: false, failure_move_preserve_structure: true, ...value };
  for (const key of ['failure_move_enabled', 'delete_on_success', 'failure_move_preserve_structure']) {
    if (typeof merged[key] !== 'boolean') throw new Error('文件动作开关格式错误')
  }
  if (typeof merged.failure_move_dir !== 'string') throw new Error('失败目录格式错误')
  return Object.fromEntries(settingsKeys.map(key => [key, clone(merged[key])]))
}
function sizeText(bytes) {
  if (!Number.isFinite(Number(bytes))) return '—'
  const size = Number(bytes);
  if (size < 1024) return `${size} B`
  const i = Math.min(Math.floor(Math.log(size) / Math.log(1024)), 4);
  return `${(size / 1024 ** i).toFixed(1)} ${['B', 'KB', 'MB', 'GB', 'TB'][i]}`
}
function requestId() {
  return globalThis.crypto?.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const r = Math.floor(Math.random() * 16); return (c === 'x' ? r : (r & 3) | 8).toString(16) })
}

const {getCurrentInstance,inject,unref} = await importShared('vue');

const hostProps = {
  api: { type: Object, default: null },
  pluginId: { type: String, default: '' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
};

function useClient(props) {
  const injectedApi = inject('moviepilot:api', null);
  const legacyApi = inject('api', null);
  const injectedId = inject('moviepilot:pluginId', '');
  const instance = getCurrentInstance();
  function hostId() {
    const explicit = unref(injectedId);
    if (explicit) return explicit
    // Older V2 PluginConfigDialog/PluginDataDialog pass only api. Their
    // own plugin prop still contains the instance identity; do not fall
    // back to another installed plugin or the fixed source name.
    for (let parent = instance?.parent, level = 0; parent && level < 20; parent = parent.parent, level++) {
      const value = unref(parent.props?.plugin);
      if (value?.id) return String(value.id)
      if (parent.props?.pluginId) return String(parent.props.pluginId)
    }
    return ''
  }
  return createClient(() => ({ api: props.api || unref(injectedApi) || unref(legacyApi), props, injectedId: hostId() }))
}

const {computed: computed$1,ref: ref$1} = await importShared('vue');
function useSettings(client, initialConfig, embedded, emit) {
  const draft = ref$1({ cookie: '', user_agent: '', extensions: '', remote_dir: '/', local_paths: [], failure_move_enabled: false, failure_move_dir: '', delete_on_success: false, failure_move_preserve_structure: true });
  const saved = ref$1(null), loaded = ref$1(false), loading = ref$1(false), saving = ref$1(false), testing = ref$1(false);
  const error = ref$1(''), notice = ref$1(''), revision = ref$1(null);
  const gate = createGeneration();
  const dirty = computed$1(() => saved.value !== null && JSON.stringify(draft.value) !== JSON.stringify(saved.value));
  const canSave = computed$1(() => loaded.value && !loading.value && !saving.value && completeSettings(draft.value));
  function seed(config) {
    if (!completeSettings(config) || saved.value !== null) return false
    saved.value = normalizeSettings(config); draft.value = clone(saved.value); loaded.value = true; return true
  }
  seed(initialConfig);
  async function load() {
    const ticket = gate.next(); loading.value = true; error.value = ''; loaded.value = false;
    const before = JSON.stringify(draft.value);
    try {
      const data = await client.get('settings');
      if (!gate.current(ticket)) return
      const config = normalizeSettings(data.settings);
      if ((!saved.value || !dirty.value) && JSON.stringify(draft.value) === before) draft.value = clone(config);
      saved.value = clone(config); revision.value = data.revision; loaded.value = true;
    } catch (cause) { if (gate.current(ticket)) error.value = errorText(cause); }
    finally { if (gate.current(ticket)) loading.value = false; }
  }
  async function save() {
    if (!canSave.value) return
    const snapshot = normalizeSettings(draft.value);
    if (!embedded) { emit('save', snapshot); notice.value = '已交由宿主保存；以宿主保存结果为准'; return }
    saving.value = true; error.value = ''; notice.value = '';
    try {
      const data = await client.post('settings', snapshot);
      const config = normalizeSettings(data.settings);
      saved.value = clone(config); revision.value = data.revision;
      if (JSON.stringify(draft.value) === JSON.stringify(snapshot)) draft.value = clone(config);
      notice.value = '配置已保存'; emit('saved', clone(config)); emit('save', clone(config));
    } catch (cause) { error.value = errorText(cause); }
    finally { saving.value = false; }
  }
  async function testSaved() {
    if (testing.value || saving.value) return
    testing.value = true; notice.value = ''; error.value = '';
    try { const data = await client.post('test'); notice.value = data.message || '已保存配置连接测试成功'; }
    catch (cause) { error.value = errorText(cause); }
    finally { testing.value = false; }
  }
  function discard() { if (saved.value) draft.value = clone(saved.value); }
  return { draft, saved, loaded, loading, saving, testing, error, notice, revision, dirty, canSave, seed, load, save, testSaved, discard, dispose: () => gate.invalidate() }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,vModelDynamic:_vModelDynamic,withDirectives:_withDirectives,vModelCheckbox:_vModelCheckbox,vModelText:_vModelText,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = {
  class: "m115 m-page",
  "aria-label": "手动秒传115配置"
};
const _hoisted_2 = { class: "m-header" };
const _hoisted_3 = { class: "m-stack" };
const _hoisted_4 = ["disabled"];
const _hoisted_5 = { class: "m-card m-stack" };
const _hoisted_6 = ["type"];
const _hoisted_7 = { class: "m-check" };
const _hoisted_8 = { class: "m-card m-stack" };
const _hoisted_9 = { class: "m-card m-stack" };
const _hoisted_10 = { class: "m-check" };
const _hoisted_11 = { key: 0 };
const _hoisted_12 = { class: "m-check" };
const _hoisted_13 = { class: "m-check" };
const _hoisted_14 = { class: "m-row" };
const _hoisted_15 = { class: "m-muted" };
const _hoisted_16 = { class: "m115 m-dialog" };
const _hoisted_17 = { class: "m-row m-spacer" };

const {computed,onBeforeUnmount,onMounted,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: { ...hostProps, initialConfig: { type: Object, default: () => ({}) }, isEmbedded: { type: Boolean, default: false } },
  emits: ['save', 'saved', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const form = reactive(useSettings(useClient(props), props.initialConfig, props.isEmbedded, emit));
const showCookie = ref(false), leaveKind = ref('');
const rawPaths = ref(form.draft.local_paths.join('\n'));
const parsePaths = text => [...new Set(text.split('\n').map(path => path.trim()).filter(Boolean))];
const pathsText = computed({ get: () => rawPaths.value, set: value => { rawPaths.value = value; form.draft.local_paths = parsePaths(value); } });
watch(() => form.draft.local_paths, paths => { if (JSON.stringify(parsePaths(rawPaths.value)) !== JSON.stringify(paths)) rawPaths.value = paths.join('\n'); }, { deep: true, flush: 'sync' });
watch(() => props.initialConfig, config => { form.seed(config); }, { deep: true });
function requestLeave(kind) { if (form.saving || form.testing) return; if (form.dirty) leaveKind.value = kind; else emit(kind); }
function confirmLeave() { const kind = leaveKind.value; leaveKind.value = ''; form.discard(); emit(kind); }
function beforeUnload(event) { if (form.dirty || form.saving) { event.preventDefault(); event.returnValue = ''; } }
onMounted(() => { if (props.isEmbedded || !form.loaded) form.load(); if (typeof window !== 'undefined') window.addEventListener('beforeunload', beforeUnload); });
onBeforeUnmount(() => { form.dispose(); if (typeof window !== 'undefined') window.removeEventListener('beforeunload', beforeUnload); });

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("section", _hoisted_1, [
    _createElementVNode("header", _hoisted_2, [
      _cache[14] || (_cache[14] = _createElementVNode("div", null, [
        _createElementVNode("div", { class: "m-kicker" }, "MANUAL PUSH · SETTINGS"),
        _createElementVNode("h1", null, "连接与默认配置"),
        _createElementVNode("p", { class: "m-muted" }, "完整保留原配置。选择本地文件与秒传操作均在首页完成。")
      ], -1)),
      _createVNode(_component_VBtn, {
        variant: "text",
        disabled: form.saving || form.testing,
        onClick: _cache[0] || (_cache[0] = $event => (requestLeave('close')))
      }, {
        default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
          _createTextVNode("关闭", -1)
        ]))]),
        _: 1
      }, 8, ["disabled"])
    ]),
    _createElementVNode("div", _hoisted_3, [
      (form.error)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: "error",
            variant: "tonal",
            role: "alert"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(form.error), 1),
              (!form.loaded)
                ? (_openBlock(), _createBlock(_component_VBtn, {
                    key: 0,
                    variant: "text",
                    disabled: form.loading,
                    onClick: form.load
                  }, {
                    default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                      _createTextVNode("重新加载配置", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"]))
                : _createCommentVNode("", true)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (form.notice)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            type: "info",
            variant: "tonal",
            role: "status"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(form.notice), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (form.loading)
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 2,
            indeterminate: "",
            "aria-label": "加载完整配置"
          }))
        : _createCommentVNode("", true),
      (!form.loaded)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 3,
            type: "warning",
            variant: "tonal"
          }, {
            default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
              _createTextVNode("配置尚未成功载入，禁止保存，避免用空值覆盖 Cookie 等原配置。", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode("", true),
      _createElementVNode("fieldset", {
        disabled: !form.loaded || form.loading,
        class: "m-stack"
      }, [
        _createElementVNode("div", _hoisted_5, [
          _createElementVNode("div", null, [
            _cache[18] || (_cache[18] = _createElementVNode("label", {
              for: "m115-cookie",
              class: "m-label"
            }, "115 Cookie", -1)),
            _withDirectives(_createElementVNode("input", {
              id: "m115-cookie",
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.draft.cookie) = $event)),
              class: "m-input",
              type: showCookie.value ? 'text' : 'password',
              autocomplete: "off",
              spellcheck: "false",
              placeholder: "填入115登录 Cookie"
            }, null, 8, _hoisted_6), [
              [_vModelDynamic, form.draft.cookie]
            ]),
            _createElementVNode("label", _hoisted_7, [
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((showCookie).value = $event)),
                type: "checkbox"
              }, null, 512), [
                [_vModelCheckbox, showCookie.value]
              ]),
              _cache[17] || (_cache[17] = _createTextVNode("显示 Cookie（请勿截图分享）", -1))
            ]),
            _cache[19] || (_cache[19] = _createElementVNode("p", { class: "m-muted" }, "仅配置接口加载 Cookie，首页状态与历史不显示密钥。留空保存将清除 Cookie。", -1))
          ]),
          _createElementVNode("div", null, [
            _cache[20] || (_cache[20] = _createElementVNode("label", {
              for: "m115-ua",
              class: "m-label"
            }, "User-Agent", -1)),
            _withDirectives(_createElementVNode("textarea", {
              id: "m115-ua",
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.draft.user_agent) = $event)),
              class: "m-input",
              rows: "2",
              spellcheck: "false",
              placeholder: "可选，与取得 Cookie 的客户端一致"
            }, null, 512), [
              [_vModelText, form.draft.user_agent]
            ])
          ]),
          _createElementVNode("div", null, [
            _cache[21] || (_cache[21] = _createElementVNode("label", {
              for: "m115-ext",
              class: "m-label"
            }, "文件扩展名过滤", -1)),
            _withDirectives(_createElementVNode("input", {
              id: "m115-ext",
              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.draft.extensions) = $event)),
              class: "m-input",
              placeholder: "例如 mkv,mp4；留空使用默认媒体扩展名"
            }, null, 512), [
              [_vModelText, form.draft.extensions]
            ]),
            _cache[22] || (_cache[22] = _createElementVNode("p", { class: "m-muted" }, "留空使用默认媒体扩展列表；填 * 包含所有文件。保留原过滤规则；目录由后台收集，不在首页递归统计。", -1))
          ])
        ]),
        _createElementVNode("div", _hoisted_8, [
          _createElementVNode("div", null, [
            _cache[23] || (_cache[23] = _createElementVNode("label", {
              for: "m115-default-remote",
              class: "m-label"
            }, "默认115目标目录", -1)),
            _withDirectives(_createElementVNode("input", {
              id: "m115-default-remote",
              "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.draft.remote_dir) = $event)),
              class: "m-input",
              placeholder: "/"
            }, null, 512), [
              [_vModelText, form.draft.remote_dir]
            ]),
            _cache[24] || (_cache[24] = _createElementVNode("p", { class: "m-muted" }, "可保留或编辑原路径；首页可逐层选择真实115目录，无需手填。", -1))
          ]),
          _createElementVNode("div", null, [
            _cache[25] || (_cache[25] = _createElementVNode("label", {
              for: "m115-default-paths",
              class: "m-label"
            }, "默认本地路径（每行一项）", -1)),
            _withDirectives(_createElementVNode("textarea", {
              id: "m115-default-paths",
              "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((pathsText).value = $event)),
              class: "m-input",
              rows: "3",
              spellcheck: "false"
            }, null, 512), [
              [_vModelText, pathsText.value]
            ]),
            _cache[26] || (_cache[26] = _createElementVNode("p", { class: "m-muted" }, "兼容保留已有配置；推荐在首页选择文件／文件夹后点击“保存为默认”。", -1))
          ])
        ]),
        _createElementVNode("div", _hoisted_9, [
          _createElementVNode("div", null, [
            _createElementVNode("label", _hoisted_10, [
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.draft.failure_move_enabled) = $event)),
                type: "checkbox"
              }, null, 512), [
                [_vModelCheckbox, form.draft.failure_move_enabled]
              ]),
              _cache[27] || (_cache[27] = _createTextVNode("本次文件失败后移动至指定目录", -1))
            ]),
            _cache[28] || (_cache[28] = _createElementVNode("p", { class: "m-muted" }, "默认关闭。包括网络或登录错误（远端结果可能未知）；文件签名变化或归档异常时保留源文件。", -1))
          ]),
          (form.draft.failure_move_enabled)
            ? (_openBlock(), _createElementBlock("div", _hoisted_11, [
                _cache[30] || (_cache[30] = _createElementVNode("label", {
                  for: "m115-failure-dir",
                  class: "m-label"
                }, "失败文件目录", -1)),
                _withDirectives(_createElementVNode("input", {
                  id: "m115-failure-dir",
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.draft.failure_move_dir) = $event)),
                  class: "m-input",
                  placeholder: "/media/failed"
                }, null, 512), [
                  [_vModelText, form.draft.failure_move_dir]
                ]),
                _cache[31] || (_cache[31] = _createElementVNode("p", { class: "m-muted" }, "填写绝对路径；可使用相邻目录。开启后本次收集会排除失败目录内文件。", -1)),
                _createElementVNode("label", _hoisted_12, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.draft.failure_move_preserve_structure) = $event)),
                    type: "checkbox"
                  }, null, 512), [
                    [_vModelCheckbox, form.draft.failure_move_preserve_structure]
                  ]),
                  _cache[29] || (_cache[29] = _createTextVNode("保留原目录结构", -1))
                ])
              ]))
            : _createCommentVNode("", true),
          _createElementVNode("div", null, [
            _createElementVNode("label", _hoisted_13, [
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.draft.delete_on_success) = $event)),
                type: "checkbox"
              }, null, 512), [
                [_vModelCheckbox, form.draft.delete_on_success]
              ]),
              _cache[32] || (_cache[32] = _createTextVNode("秒传明确成功后删除原文件", -1))
            ]),
            _cache[33] || (_cache[33] = _createElementVNode("p", { class: "m-muted" }, "默认关闭。删除前会重新校验文件签名，文件变化时保留原文件。", -1))
          ])
        ])
      ], 8, _hoisted_4),
      _createElementVNode("div", _hoisted_14, [
        _createVNode(_component_VBtn, {
          color: "primary",
          loading: form.saving,
          disabled: !form.canSave,
          onClick: form.save
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(__props.isEmbedded ? '保存配置' : '保存至宿主'), 1)
          ]),
          _: 1
        }, 8, ["loading", "disabled", "onClick"]),
        _createVNode(_component_VBtn, {
          variant: "tonal",
          loading: form.testing,
          disabled: !form.loaded || form.saving,
          onClick: form.testSaved
        }, {
          default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
            _createTextVNode("测试已保存配置", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "disabled", "onClick"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          disabled: form.saving || form.testing,
          onClick: _cache[11] || (_cache[11] = $event => (requestLeave('switch')))
        }, {
          default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
            _createTextVNode("返回秒传首页", -1)
          ]))]),
          _: 1
        }, 8, ["disabled"]),
        _createElementVNode("span", _hoisted_15, _toDisplayString(form.dirty ? '有未保存更改' : '无未保存更改'), 1)
      ]),
      _cache[36] || (_cache[36] = _createElementVNode("p", { class: "m-muted" }, "连接测试只使用服务端已保存的 Cookie，不会提交当前未保存的输入。保存配置不会启动任务或创建调度。", -1))
    ]),
    _createVNode(_component_VDialog, {
      "model-value": !!leaveKind.value,
      persistent: "",
      "max-width": "460"
    }, {
      default: _withCtx(() => [
        _createElementVNode("section", _hoisted_16, [
          _cache[39] || (_cache[39] = _createElementVNode("h2", null, "保留未保存的输入？", -1)),
          _cache[40] || (_cache[40] = _createElementVNode("p", null, "离开会丢弃尚未保存的配置。", -1)),
          _createElementVNode("div", _hoisted_17, [
            _createVNode(_component_VBtn, {
              color: "primary",
              onClick: _cache[12] || (_cache[12] = $event => (leaveKind.value = ''))
            }, {
              default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                _createTextVNode("继续编辑", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: confirmLeave
            }, {
              default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                _createTextVNode("丢弃并离开", -1)
              ]))]),
              _: 1
            })
          ])
        ])
      ]),
      _: 1
    }, 8, ["model-value"])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-1454d3aa"]]);

export { _export_sfc as _, clone as a, createGeneration as c, Config as default, errorText as e, hostProps as h, normalizeSettings as n, requestId as r, sizeText as s, useClient as u };
