import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,mergeProps:_mergeProps,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "cloud115__header" };
const _hoisted_2 = { class: "cloud115__identity" };
const _hoisted_3 = { class: "cloud115__actions" };
const _hoisted_4 = {
  key: 4,
  class: "cloud115__loading"
};
const _hoisted_5 = { class: "operation-actions" };
const _hoisted_6 = { class: "operation-hint" };
const _hoisted_7 = { class: "stats" };
const _hoisted_8 = { class: "list-filters" };
const _hoisted_9 = { class: "cell-name" };
const _hoisted_10 = { class: "empty-table" };
const _hoisted_11 = { class: "mobile-cards d-md-none" };
const _hoisted_12 = { class: "mobile-card__head" };
const _hoisted_13 = { key: 0 };
const _hoisted_14 = { key: 1 };
const _hoisted_15 = { class: "mobile-card__foot" };
const _hoisted_16 = {
  key: 0,
  class: "empty-table"
};
const _hoisted_17 = { class: "list-filters" };
const _hoisted_18 = { class: "cell-name" };
const _hoisted_19 = { class: "mobile-cards d-md-none" };
const _hoisted_20 = { class: "mobile-card__head" };
const _hoisted_21 = { key: 0 };
const _hoisted_22 = {
  key: 0,
  class: "empty-table"
};
const _hoisted_23 = { class: "list-filters" };
const _hoisted_24 = { class: "cell-name" };
const _hoisted_25 = { class: "empty-table" };
const _hoisted_26 = { class: "mobile-cards d-md-none" };
const _hoisted_27 = { class: "mobile-card__head" };
const _hoisted_28 = { key: 0 };
const _hoisted_29 = {
  key: 0,
  class: "empty-table"
};
const _hoisted_30 = { class: "list-filters" };
const _hoisted_31 = { class: "cell-name" };
const _hoisted_32 = { class: "mobile-cards d-md-none" };
const _hoisted_33 = { class: "mobile-card__head" };
const _hoisted_34 = { key: 0 };
const _hoisted_35 = {
  key: 0,
  class: "empty-table"
};
const _hoisted_36 = { class: "mobile-cards d-md-none" };
const _hoisted_37 = { class: "mobile-card__head" };
const _hoisted_38 = {
  key: 0,
  class: "empty-table"
};
const _hoisted_39 = { class: "cloud115__footer" };

const {computed,inject,onBeforeUnmount,onMounted,ref,watch} = await importShared('vue');


const pluginBase = 'plugin/CloudPush115';

const _sfc_main = {
  __name: 'Workbench',
  props: {
  api: { type: Object, default: () => ({}) },
  initialTab: { type: String, default: 'history' },
  compact: { type: Boolean, default: false },
  showClose: { type: Boolean, default: false },
},
  emits: ['action', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const hostToast = inject('moviepilot:toast', null);
const loading = ref(true);
const error = ref('');
const scanning = ref(false);
const testing = ref(false);
const indexing = ref(false);
const retrying = ref(false);
const activeTab = ref(props.initialTab);
const lastSynced = ref(null);
const now = ref(Date.now());
let disposed = false, pollTimer = null, clockTimer = null;

const status = ref({
  enabled: false, running: false, phase: 'idle', version: '',
  done_count: 0, retry_count: 0, local_count: 0,
  stats: {}, history: [], retry_queue: [], local_queue: [], qb_queue: [], roots: [],
  last_run: null, last_error: null, storage_error: null, qb_error: null,
  has_cookie: false, remote_dir: '',
});

const phaseLabel = computed(() => ({
  indexing: '扫描本地文件', ready: '索引完成', uploading: '处理本地队列',
  retry: '处理重试队列', qb: '检查 qB 任务', idle: '空闲',
}[status.value.phase] || status.value.phase));

const statusMap = {
  success: { label: '秒传成功', color: 'success', icon: 'mdi-check-circle' },
  failed: { label: '失败', color: 'error', icon: 'mdi-close-circle' },
  skipped: { label: '跳过', color: 'default', icon: 'mdi-skip-next-circle' },
  retry: { label: '待重试', color: 'warning', icon: 'mdi-restart' },
  exhausted: { label: '重试已达上限', color: 'error', icon: 'mdi-alert-circle' },
  pending: { label: '待处理', color: 'info', icon: 'mdi-clock-outline' },
  processing: { label: '秒传中', color: 'primary', icon: 'mdi-cloud-upload' },
  uploading: { label: '秒传中', color: 'primary', icon: 'mdi-cloud-upload' },
  waiting: { label: '等待稳定', color: 'warning', icon: 'mdi-timer-sand' },
  blocked: { label: '暂不可处理', color: 'warning', icon: 'mdi-lock-outline' },
  ready: { label: '就绪', color: 'info', icon: 'mdi-checkbox-marked-circle-outline' },
  indexing: { label: '索引中', color: 'primary', icon: 'mdi-magnify' },
  error: { label: '读取失败', color: 'error', icon: 'mdi-alert' },
  legacy: { label: '旧版标记', color: 'default', icon: 'mdi-archive-outline' },
};
function chipProps(s) {
  const entry = statusMap[s] || { label: s || '未知', color: 'default', icon: 'mdi-help-circle' };
  return entry
}
const sourceMap = { local: '本地', qb: 'qB', retry: '本地重试', legacy: '历史记录' };
function sourceLabel(s) { return sourceMap[s] || s || '' }

function formatBytes(v) {
  const b = Number(v || 0); if (!b) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(b) / Math.log(1024)), units.length - 1);
  return `${(b / 1024 ** i).toFixed(i > 1 ? 1 : 0)} ${units[i]}`
}
function formatTime(v) {
  if (!v) return '—'
  const d = new Date(v); return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('zh-CN', { hour12: false })
}

// Search & filter per tab
const historySearch = ref(''); const historyFilter = ref('all'); const historyPage = ref(1); const historyPageSize = ref(20);
const retrySearch = ref(''); const retryPage = ref(1); const retryPageSize = ref(20);
const localSearch = ref(''); const localPage = ref(1); const localPageSize = ref(20);
const qbSearch = ref(''); const qbPage = ref(1); const qbPageSize = ref(20);

const historyFilterOptions = computed(() => {
  const outcomes = new Set((status.value.history || []).map(r => r.status));
  return [{ title: '全部结果', value: 'all' }, ...Array.from(outcomes).filter(Boolean).map(s => ({ title: chipProps(s).label, value: s }))]
});
function filterList(list, search, filterKey, filterValue) {
  return (list || []).filter(row => {
    const q = search.trim().toLocaleLowerCase();
    const textMatch = !q || [row.name, row.path, row.message, row.remote_dir].filter(Boolean).join(' ').toLocaleLowerCase().includes(q);
    const statusMatch = filterValue === 'all' || row[filterKey] === filterValue;
    return textMatch && statusMatch
  })
}
function paginate(list, page, size) {
  const start = (page - 1) * size;
  return { items: list.slice(start, start + size), pages: Math.max(1, Math.ceil(list.length / size)), total: list.length }
}

const filteredHistory = computed(() => filterList(status.value.history, historySearch.value, 'status', historyFilter.value));
const pagedHistory = computed(() => paginate(filteredHistory.value, historyPage.value, historyPageSize.value));
const filteredRetry = computed(() => filterList(status.value.retry_queue, retrySearch.value, 'status', 'all'));
const pagedRetry = computed(() => paginate(filteredRetry.value, retryPage.value, retryPageSize.value));
const filteredLocal = computed(() => filterList(status.value.local_queue, localSearch.value, 'status', 'all'));
const pagedLocal = computed(() => paginate(filteredLocal.value, localPage.value, localPageSize.value));
const filteredQb = computed(() => filterList(status.value.qb_queue, qbSearch.value, 'status', 'all'));
const pagedQb = computed(() => paginate(filteredQb.value, qbPage.value, qbPageSize.value));

watch([historySearch, historyFilter], () => { historyPage.value = 1; });
watch(retrySearch, () => { retryPage.value = 1; });
watch(localSearch, () => { localPage.value = 1; });
watch(qbSearch, () => { qbPage.value = 1; });

function notify(text, kind = 'success') {
  if (typeof hostToast?.[kind] === 'function') hostToast[kind](text);
  else if (kind === 'error') error.value = text;
}

async function loadStatus() {
  try {
    const response = await props.api.get(`${pluginBase}/status`);
    const data = response?.data ?? response;
    if (disposed) return
    Object.assign(status.value, data);
    scanning.value = Boolean(data.running);
    error.value = '';
    lastSynced.value = new Date().toISOString();
  } catch (err) {
    if (!disposed) error.value = err?.message || '加载状态失败';
  } finally {
    if (!disposed) loading.value = false;
  }
}

async function runOperation(operation, loadingRef) {
  loadingRef.value = true;
  try {
    const response = await props.api.post(`${pluginBase}/${operation}`);
    const data = response?.data ?? response;
    notify(data?.message || '操作已提交');
    setTimeout(loadStatus, 1500);
    setTimeout(loadStatus, 4000);
  } catch (err) {
    notify(err?.message || '操作失败', 'error');
  } finally {
    loadingRef.value = false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = globalThis.setInterval(() => { if (!disposed && !globalThis.document?.hidden) loadStatus(); }, 5000);
}
function stopPolling() { if (pollTimer !== null) { globalThis.clearInterval(pollTimer); pollTimer = null; } }

onMounted(() => {
  loadStatus();
  startPolling();
  clockTimer = globalThis.setInterval(() => { now.value = Date.now(); }, 30000);
  globalThis.document?.addEventListener('visibilitychange', onVisibility);
  if (globalThis.document?.hidden) loadStatus();
});
onBeforeUnmount(() => {
  disposed = true; stopPolling();
  if (clockTimer !== null) globalThis.clearInterval(clockTimer);
  globalThis.document?.removeEventListener('visibilitychange', onVisibility);
});
function onVisibility() {
  if (globalThis.document?.hidden) { stopPolling(); } else { loadStatus(); startPolling(); }
}

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VSheet = _resolveComponent("VSheet");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VDataTable = _resolveComponent("VDataTable");
  const _component_VPagination = _resolveComponent("VPagination");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VWindow = _resolveComponent("VWindow");

  return (_openBlock(), _createElementBlock("div", {
    class: _normalizeClass(["cloud115", { 'cloud115--compact': __props.compact }])
  }, [
    _createElementVNode("header", _hoisted_1, [
      _createElementVNode("div", _hoisted_2, [
        _createVNode(_component_VIcon, {
          icon: "mdi-cloud-upload",
          color: "primary",
          size: "30"
        }),
        _cache[17] || (_cache[17] = _createElementVNode("div", null, [
          _createElementVNode("h1", null, "115 网盘秒传"),
          _createElementVNode("p", null, "SHA1 秒传 · 只读原文件 · qB 下载完成即推送")
        ], -1))
      ]),
      _createElementVNode("div", _hoisted_3, [
        _createVNode(_component_VChip, {
          color: status.value.enabled ? 'success' : 'default',
          size: "small",
          variant: "tonal"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(status.value.enabled ? '已启用' : '未启用'), 1)
          ]),
          _: 1
        }, 8, ["color"]),
        (status.value.running)
          ? (_openBlock(), _createBlock(_component_VChip, {
              key: 0,
              color: "primary",
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-loading mdi-spin"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(phaseLabel.value), 1)
              ]),
              _: 1
            }))
          : (_openBlock(), _createBlock(_component_VChip, {
              key: 1,
              size: "small",
              variant: "tonal"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(phaseLabel.value), 1)
              ]),
              _: 1
            })),
        _createVNode(_component_VTooltip, { text: "刷新" }, {
          activator: _withCtx(({ props: tip }) => [
            _createVNode(_component_VBtn, _mergeProps(tip, {
              icon: "mdi-refresh",
              variant: "text",
              loading: loading.value,
              onClick: loadStatus
            }), null, 16, ["loading"])
          ]),
          _: 1
        }),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VTooltip, {
              key: 2,
              text: "关闭"
            }, {
              activator: _withCtx(({ props: tip }) => [
                _createVNode(_component_VBtn, _mergeProps(tip, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('close')))
                }), null, 16)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true)
      ])
    ]),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "error",
          variant: "tonal",
          closable: "",
          "onClick:close": _cache[1] || (_cache[1] = $event => (error.value = ''))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (status.value.storage_error)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "warning",
          variant: "tonal"
        }, {
          default: _withCtx(() => [
            _createTextVNode("存储错误：" + _toDisplayString(status.value.storage_error), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (status.value.qb_error)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 2,
          type: "warning",
          variant: "tonal"
        }, {
          default: _withCtx(() => [
            _createTextVNode("qB 连接：" + _toDisplayString(status.value.qb_error), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (status.value.last_error)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 3,
          type: "warning",
          variant: "tonal"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(status.value.last_error), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (loading.value && !status.value.version)
      ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
          _createVNode(_component_VSkeletonLoader, { type: "list-item-three-line, article" })
        ]))
      : (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
          _createElementVNode("div", _hoisted_5, [
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-cloud-upload",
              loading: scanning.value,
              disabled: scanning.value || !status.value.has_cookie,
              onClick: _cache[2] || (_cache[2] = $event => (runOperation('scan', scanning.value)))
            }, {
              default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                _createTextVNode("扫描秒传", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"]),
            _createVNode(_component_VBtn, {
              variant: "tonal",
              "prepend-icon": "mdi-folder-search",
              loading: indexing.value,
              disabled: scanning.value,
              onClick: _cache[3] || (_cache[3] = $event => (runOperation('index', indexing.value)))
            }, {
              default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                _createTextVNode("刷新本地队列", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"]),
            _createVNode(_component_VBtn, {
              variant: "tonal",
              "prepend-icon": "mdi-restart",
              loading: retrying.value,
              disabled: scanning.value,
              color: "warning",
              onClick: _cache[4] || (_cache[4] = $event => (runOperation('retry', retrying.value)))
            }, {
              default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                _createTextVNode("重试失败文件", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"]),
            _createVNode(_component_VBtn, {
              variant: "tonal",
              "prepend-icon": "mdi-key",
              loading: testing.value,
              onClick: _cache[5] || (_cache[5] = $event => (runOperation('test', testing.value)))
            }, {
              default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                _createTextVNode("测试凭据", -1)
              ]))]),
              _: 1
            }, 8, ["loading"])
          ]),
          _createElementVNode("p", _hoisted_6, _toDisplayString(!status.value.has_cookie ? '未配置 115 Cookie，请在设置中填写后保存。' : scanning.value ? '正在' + phaseLabel.value + '…' : '最近扫描：' + (status.value.last_run || '尚未运行') + ' · 最近同步 ' + formatTime(lastSynced.value)), 1),
          _createElementVNode("div", _hoisted_7, [
            _createVNode(_component_VSheet, { class: "stat app-surface-static" }, {
              default: _withCtx(() => [
                _cache[22] || (_cache[22] = _createElementVNode("span", null, "已秒传", -1)),
                _createElementVNode("strong", null, _toDisplayString(status.value.done_count || 0), 1),
                _createVNode(_component_VIcon, {
                  icon: "mdi-check-circle-outline",
                  color: "success"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VSheet, { class: "stat app-surface-static" }, {
              default: _withCtx(() => [
                _cache[23] || (_cache[23] = _createElementVNode("span", null, "待重试", -1)),
                _createElementVNode("strong", null, _toDisplayString(status.value.retry_count || 0), 1),
                _createVNode(_component_VIcon, {
                  icon: "mdi-restart",
                  color: "warning"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VSheet, { class: "stat app-surface-static" }, {
              default: _withCtx(() => [
                _cache[24] || (_cache[24] = _createElementVNode("span", null, "本地待处理", -1)),
                _createElementVNode("strong", null, _toDisplayString(status.value.local_count || 0), 1),
                _createVNode(_component_VIcon, {
                  icon: "mdi-folder-open-outline",
                  color: "info"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VSheet, { class: "stat app-surface-static" }, {
              default: _withCtx(() => [
                _cache[25] || (_cache[25] = _createElementVNode("span", null, "qB 任务", -1)),
                _createElementVNode("strong", null, _toDisplayString(status.value.stats?.qb || 0), 1),
                _createVNode(_component_VIcon, {
                  icon: "mdi-download-network-outline",
                  color: "primary"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VSheet, { class: "stat app-surface-static" }, {
              default: _withCtx(() => [
                _cache[26] || (_cache[26] = _createElementVNode("span", null, "已索引", -1)),
                _createElementVNode("strong", null, _toDisplayString(status.value.stats?.indexed || 0), 1),
                _createVNode(_component_VIcon, {
                  icon: "mdi-file-document-multiple-outline",
                  color: "info"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VSheet, { class: "stat app-surface-static" }, {
              default: _withCtx(() => [
                _cache[27] || (_cache[27] = _createElementVNode("span", null, "监控路径", -1)),
                _createElementVNode("strong", null, _toDisplayString(status.value.stats?.roots || 0), 1),
                _createVNode(_component_VIcon, {
                  icon: "mdi-folder-multiple-outline",
                  color: "default"
                })
              ]),
              _: 1
            })
          ]),
          _createVNode(_component_VTabs, {
            modelValue: activeTab.value,
            "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((activeTab).value = $event)),
            class: "cloud115-tabs",
            "show-arrows": ""
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VTab, {
                value: "history",
                "prepend-icon": "mdi-history"
              }, {
                default: _withCtx(() => [
                  _cache[28] || (_cache[28] = _createTextVNode("整理记录 ", -1)),
                  _createVNode(_component_VChip, {
                    size: "x-small",
                    variant: "tonal",
                    class: "ml-1"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(status.value.stats?.history || 0), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VTab, {
                value: "retry",
                "prepend-icon": "mdi-restart"
              }, {
                default: _withCtx(() => [
                  _cache[29] || (_cache[29] = _createTextVNode("待重试 ", -1)),
                  _createVNode(_component_VChip, {
                    size: "x-small",
                    variant: "tonal",
                    class: "ml-1"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(status.value.stats?.retry || 0), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VTab, {
                value: "local",
                "prepend-icon": "mdi-folder-open"
              }, {
                default: _withCtx(() => [
                  _cache[30] || (_cache[30] = _createTextVNode("本地队列 ", -1)),
                  _createVNode(_component_VChip, {
                    size: "x-small",
                    variant: "tonal",
                    class: "ml-1"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(status.value.stats?.local || 0), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VTab, {
                value: "qb",
                "prepend-icon": "mdi-download-network"
              }, {
                default: _withCtx(() => [
                  _cache[31] || (_cache[31] = _createTextVNode("qB 任务 ", -1)),
                  _createVNode(_component_VChip, {
                    size: "x-small",
                    variant: "tonal",
                    class: "ml-1"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(status.value.stats?.qb || 0), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VTab, {
                value: "roots",
                "prepend-icon": "mdi-folder-multiple"
              }, {
                default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                  _createTextVNode("监控路径", -1)
                ]))]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"]),
          _createVNode(_component_VWindow, {
            modelValue: activeTab.value,
            "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((activeTab).value = $event)),
            class: "cloud115-window"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VWindowItem, { value: "history" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_8, [
                    _createVNode(_component_VTextField, {
                      modelValue: historySearch.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((historySearch).value = $event)),
                      label: "搜索文件名 / 路径",
                      "prepend-inner-icon": "mdi-magnify",
                      clearable: "",
                      "hide-details": "",
                      density: "compact"
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: historyFilter.value,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((historyFilter).value = $event)),
                      items: historyFilterOptions.value,
                      label: "结果",
                      "hide-details": "",
                      density: "compact",
                      style: {"max-width":"160px"}
                    }, null, 8, ["modelValue", "items"])
                  ]),
                  _createVNode(_component_VDataTable, {
                    headers: [{title:'文件',key:'name',sortable:false},{title:'结果',key:'status',sortable:false,width:110},{title:'大小',key:'size',sortable:false,width:90},{title:'详情',key:'message',sortable:false},{title:'来源',key:'source',sortable:false,width:80},{title:'时间',key:'time',sortable:false,width:160}],
                    items: pagedHistory.value.items,
                    loading: loading.value,
                    density: "comfortable",
                    class: "data-table d-none d-md-block",
                    "hide-default-footer": ""
                  }, {
                    "item.name": _withCtx(({ item }) => [
                      _createElementVNode("div", _hoisted_9, [
                        _createTextVNode(_toDisplayString(item.name), 1),
                        _createElementVNode("small", null, _toDisplayString(item.path), 1)
                      ])
                    ]),
                    "item.status": _withCtx(({ item }) => [
                      _createVNode(_component_VChip, {
                        color: chipProps(item.status).color,
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(chipProps(item.status).label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    "item.size": _withCtx(({ item }) => [
                      _createTextVNode(_toDisplayString(formatBytes(item.size)), 1)
                    ]),
                    "item.source": _withCtx(({ item }) => [
                      _createTextVNode(_toDisplayString(sourceLabel(item.source)), 1)
                    ]),
                    "item.time": _withCtx(({ item }) => [
                      _createTextVNode(_toDisplayString(formatTime(item.time)), 1)
                    ]),
                    "no-data": _withCtx(() => [
                      _createElementVNode("div", _hoisted_10, _toDisplayString(historySearch.value || historyFilter.value !== 'all' ? '没有符合筛选的记录' : '尚无整理记录'), 1)
                    ]),
                    _: 1
                  }, 8, ["items", "loading"]),
                  _createElementVNode("div", _hoisted_11, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedHistory.value.items, (row) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: row.path + row.time,
                        class: "mobile-card"
                      }, [
                        _createElementVNode("div", _hoisted_12, [
                          _createElementVNode("strong", null, _toDisplayString(row.name), 1),
                          _createVNode(_component_VChip, {
                            color: chipProps(row.status).color,
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(chipProps(row.status).label), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        (row.path)
                          ? (_openBlock(), _createElementBlock("small", _hoisted_13, _toDisplayString(row.path), 1))
                          : _createCommentVNode("", true),
                        (row.message)
                          ? (_openBlock(), _createElementBlock("small", _hoisted_14, _toDisplayString(row.message), 1))
                          : _createCommentVNode("", true),
                        _createElementVNode("div", _hoisted_15, [
                          _createElementVNode("span", null, _toDisplayString(formatBytes(row.size)), 1),
                          _createElementVNode("span", null, _toDisplayString(sourceLabel(row.source)), 1),
                          _createElementVNode("span", null, _toDisplayString(formatTime(row.time)), 1)
                        ])
                      ]))
                    }), 128)),
                    (!pagedHistory.value.items.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_16, _toDisplayString(historySearch.value || historyFilter.value !== 'all' ? '没有符合筛选的记录' : '尚无整理记录'), 1))
                      : _createCommentVNode("", true)
                  ]),
                  (pagedHistory.value.pages > 1)
                    ? (_openBlock(), _createBlock(_component_VPagination, {
                        key: 0,
                        modelValue: historyPage.value,
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((historyPage).value = $event)),
                        length: pagedHistory.value.pages,
                        density: "compact",
                        class: "mt-2"
                      }, null, 8, ["modelValue", "length"]))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "retry" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_17, [
                    _createVNode(_component_VTextField, {
                      modelValue: retrySearch.value,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((retrySearch).value = $event)),
                      label: "搜索",
                      "prepend-inner-icon": "mdi-magnify",
                      clearable: "",
                      "hide-details": "",
                      density: "compact"
                    }, null, 8, ["modelValue"])
                  ]),
                  _createVNode(_component_VDataTable, {
                    headers: [{title:'文件',key:'name',sortable:false},{title:'状态',key:'status',sortable:false,width:120},{title:'已失败',key:'attempts',sortable:false,width:80},{title:'原因',key:'message',sortable:false},{title:'下次重试',key:'next_retry_text',sortable:false,width:140}],
                    items: pagedRetry.value.items,
                    density: "comfortable",
                    class: "data-table d-none d-md-block",
                    "hide-default-footer": ""
                  }, {
                    "item.name": _withCtx(({ item }) => [
                      _createElementVNode("div", _hoisted_18, [
                        _createTextVNode(_toDisplayString(item.name), 1),
                        _createElementVNode("small", null, _toDisplayString(item.remote_dir), 1)
                      ])
                    ]),
                    "item.status": _withCtx(({ item }) => [
                      _createVNode(_component_VChip, {
                        color: chipProps(item.status).color,
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(chipProps(item.status).label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    "no-data": _withCtx(() => [...(_cache[33] || (_cache[33] = [
                      _createElementVNode("div", { class: "empty-table" }, "当前没有待重试文件", -1)
                    ]))]),
                    _: 1
                  }, 8, ["items"]),
                  _createElementVNode("div", _hoisted_19, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedRetry.value.items, (row) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: row.path,
                        class: "mobile-card"
                      }, [
                        _createElementVNode("div", _hoisted_20, [
                          _createElementVNode("strong", null, _toDisplayString(row.name), 1),
                          _createVNode(_component_VChip, {
                            color: chipProps(row.status).color,
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(chipProps(row.status).label), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("small", null, "第 " + _toDisplayString(row.attempts || 0) + " 次 · " + _toDisplayString(row.message), 1),
                        (row.next_retry_text)
                          ? (_openBlock(), _createElementBlock("small", _hoisted_21, "下次重试：" + _toDisplayString(row.next_retry_text), 1))
                          : _createCommentVNode("", true)
                      ]))
                    }), 128)),
                    (!pagedRetry.value.items.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_22, "当前没有待重试文件"))
                      : _createCommentVNode("", true)
                  ]),
                  (pagedRetry.value.pages > 1)
                    ? (_openBlock(), _createBlock(_component_VPagination, {
                        key: 0,
                        modelValue: retryPage.value,
                        "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((retryPage).value = $event)),
                        length: pagedRetry.value.pages,
                        density: "compact",
                        class: "mt-2"
                      }, null, 8, ["modelValue", "length"]))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "local" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_23, [
                    _createVNode(_component_VTextField, {
                      modelValue: localSearch.value,
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((localSearch).value = $event)),
                      label: "搜索",
                      "prepend-inner-icon": "mdi-magnify",
                      clearable: "",
                      "hide-details": "",
                      density: "compact"
                    }, null, 8, ["modelValue"])
                  ]),
                  _createVNode(_component_VDataTable, {
                    headers: [{title:'文件',key:'name',sortable:false},{title:'状态',key:'status',sortable:false,width:110},{title:'大小',key:'size',sortable:false,width:90},{title:'路径',key:'path',sortable:false},{title:'说明',key:'message',sortable:false}],
                    items: pagedLocal.value.items,
                    density: "comfortable",
                    class: "data-table d-none d-md-block",
                    "hide-default-footer": ""
                  }, {
                    "item.name": _withCtx(({ item }) => [
                      _createElementVNode("div", _hoisted_24, _toDisplayString(item.name), 1)
                    ]),
                    "item.status": _withCtx(({ item }) => [
                      _createVNode(_component_VChip, {
                        color: chipProps(item.status).color,
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(chipProps(item.status).label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    "item.size": _withCtx(({ item }) => [
                      _createTextVNode(_toDisplayString(formatBytes(item.size)), 1)
                    ]),
                    "no-data": _withCtx(() => [
                      _createElementVNode("div", _hoisted_25, _toDisplayString(status.value.last_index ? '本地队列为空' : '尚未完成本地索引'), 1)
                    ]),
                    _: 1
                  }, 8, ["items"]),
                  _createElementVNode("div", _hoisted_26, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedLocal.value.items, (row) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: row.path,
                        class: "mobile-card"
                      }, [
                        _createElementVNode("div", _hoisted_27, [
                          _createElementVNode("strong", null, _toDisplayString(row.name), 1),
                          _createVNode(_component_VChip, {
                            color: chipProps(row.status).color,
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(chipProps(row.status).label), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("small", null, _toDisplayString(formatBytes(row.size)) + " · " + _toDisplayString(row.path), 1),
                        (row.message)
                          ? (_openBlock(), _createElementBlock("small", _hoisted_28, _toDisplayString(row.message), 1))
                          : _createCommentVNode("", true)
                      ]))
                    }), 128)),
                    (!pagedLocal.value.items.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_29, _toDisplayString(status.value.last_index ? '本地队列为空' : '尚未完成本地索引'), 1))
                      : _createCommentVNode("", true)
                  ]),
                  (pagedLocal.value.pages > 1)
                    ? (_openBlock(), _createBlock(_component_VPagination, {
                        key: 0,
                        modelValue: localPage.value,
                        "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((localPage).value = $event)),
                        length: pagedLocal.value.pages,
                        density: "compact",
                        class: "mt-2"
                      }, null, 8, ["modelValue", "length"]))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "qb" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_30, [
                    _createVNode(_component_VTextField, {
                      modelValue: qbSearch.value,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((qbSearch).value = $event)),
                      label: "搜索",
                      "prepend-inner-icon": "mdi-magnify",
                      clearable: "",
                      "hide-details": "",
                      density: "compact"
                    }, null, 8, ["modelValue"])
                  ]),
                  _createVNode(_component_VDataTable, {
                    headers: [{title:'种子',key:'name',sortable:false},{title:'状态',key:'status',sortable:false,width:110},{title:'就绪文件',key:'ready',sortable:false,width:90},{title:'路径',key:'path',sortable:false},{title:'诊断',key:'message',sortable:false}],
                    items: pagedQb.value.items,
                    density: "comfortable",
                    class: "data-table d-none d-md-block",
                    "hide-default-footer": ""
                  }, {
                    "item.name": _withCtx(({ item }) => [
                      _createElementVNode("div", _hoisted_31, _toDisplayString(item.name), 1)
                    ]),
                    "item.status": _withCtx(({ item }) => [
                      _createVNode(_component_VChip, {
                        color: chipProps(item.status).color,
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(chipProps(item.status).label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    "item.ready": _withCtx(({ item }) => [
                      _createTextVNode(_toDisplayString(item.ready || 0) + "/" + _toDisplayString(item.total || 0), 1)
                    ]),
                    "no-data": _withCtx(() => [...(_cache[34] || (_cache[34] = [
                      _createElementVNode("div", { class: "empty-table" }, "未发现待处理 qB 任务", -1)
                    ]))]),
                    _: 1
                  }, 8, ["items"]),
                  _createElementVNode("div", _hoisted_32, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedQb.value.items, (row) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: row.path || row.name,
                        class: "mobile-card"
                      }, [
                        _createElementVNode("div", _hoisted_33, [
                          _createElementVNode("strong", null, _toDisplayString(row.name), 1),
                          _createVNode(_component_VChip, {
                            color: chipProps(row.status).color,
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(chipProps(row.status).label), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("small", null, "就绪 " + _toDisplayString(row.ready || 0) + "/" + _toDisplayString(row.total || 0) + " · " + _toDisplayString(row.path), 1),
                        (row.message)
                          ? (_openBlock(), _createElementBlock("small", _hoisted_34, _toDisplayString(row.message), 1))
                          : _createCommentVNode("", true)
                      ]))
                    }), 128)),
                    (!pagedQb.value.items.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_35, "未发现待处理 qB 任务"))
                      : _createCommentVNode("", true)
                  ]),
                  (pagedQb.value.pages > 1)
                    ? (_openBlock(), _createBlock(_component_VPagination, {
                        key: 0,
                        modelValue: qbPage.value,
                        "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((qbPage).value = $event)),
                        length: pagedQb.value.pages,
                        density: "compact",
                        class: "mt-2"
                      }, null, 8, ["modelValue", "length"]))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "roots" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VDataTable, {
                    headers: [{title:'路径',key:'path',sortable:false},{title:'索引状态',key:'status',sortable:false,width:110},{title:'媒体文件数',key:'file_count',sortable:false,width:110},{title:'说明',key:'message',sortable:false}],
                    items: status.value.roots || [],
                    density: "comfortable",
                    class: "data-table d-none d-md-block",
                    "hide-default-footer": ""
                  }, {
                    "item.status": _withCtx(({ item }) => [
                      _createVNode(_component_VChip, {
                        color: chipProps(item.status).color,
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(chipProps(item.status).label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    "no-data": _withCtx(() => [...(_cache[35] || (_cache[35] = [
                      _createElementVNode("div", { class: "empty-table" }, "尚未配置或索引本地路径", -1)
                    ]))]),
                    _: 1
                  }, 8, ["items"]),
                  _createElementVNode("div", _hoisted_36, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((status.value.roots || []), (row) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: row.path,
                        class: "mobile-card"
                      }, [
                        _createElementVNode("div", _hoisted_37, [
                          _createElementVNode("strong", null, _toDisplayString(row.path), 1),
                          _createVNode(_component_VChip, {
                            color: chipProps(row.status).color,
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(chipProps(row.status).label), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("small", null, _toDisplayString(row.file_count || 0) + " 个媒体文件 · " + _toDisplayString(row.message || ''), 1)
                      ]))
                    }), 128)),
                    (!(status.value.roots || []).length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_38, "尚未配置或索引本地路径"))
                      : _createCommentVNode("", true)
                  ])
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"]),
          _createElementVNode("div", _hoisted_39, " 最近本地秒传：" + _toDisplayString(status.value.last_scan || '尚未执行') + " · 最近 qB 检查：" + _toDisplayString(status.value.last_qb || '尚未执行') + " · 115 目标：" + _toDisplayString(status.value.remote_dir || '/') + " · v" + _toDisplayString(status.value.version), 1)
        ], 64))
  ], 2))
}
}

};
const Workbench = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-5595d9cb"]]);

export { Workbench as W };
