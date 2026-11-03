import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config, { _ as _export_sfc, s as sizeText, c as createGeneration, e as errorText, n as normalizeSettings, a as clone, r as requestId, h as hostProps, u as useClient } from './__federation_expose_Config--inL-uro.js';

const {createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$2,vModelText:_vModelText$1,withDirectives:_withDirectives$1,vModelCheckbox:_vModelCheckbox$1,createBlock:_createBlock$2,withModifiers:_withModifiers$1,unref:_unref$1} = await importShared('vue');


const _hoisted_1$2 = {
  class: "m115 m-dialog",
  "aria-label": "本地逐层目录选择"
};
const _hoisted_2$2 = { class: "m-header" };
const _hoisted_3$2 = {
  class: "m-breadcrumbs",
  "aria-label": "本地目录面包屑"
};
const _hoisted_4$2 = ["onClick"];
const _hoisted_5$2 = {
  key: 0,
  class: "m-toolbar"
};
const _hoisted_6$2 = { class: "m-path m-muted" };
const _hoisted_7$2 = { class: "m-row" };
const _hoisted_8$2 = { class: "m-check" };
const _hoisted_9$2 = {
  key: 0,
  class: "m-list"
};
const _hoisted_10$2 = { class: "m-check" };
const _hoisted_11$1 = ["checked", "aria-label", "onChange"];
const _hoisted_12$1 = { class: "m-grow" };
const _hoisted_13$1 = ["onClick"];
const _hoisted_14$1 = { class: "m-name" };
const _hoisted_15$1 = { class: "m-muted m-path" };
const _hoisted_16$1 = {
  key: 0,
  class: "m-muted m-spacer"
};
const _hoisted_17$1 = {
  key: 0,
  class: "m-muted m-spacer"
};
const _hoisted_18$1 = { class: "m-list" };
const _hoisted_19$1 = { class: "m-check" };
const _hoisted_20$1 = ["checked", "disabled", "aria-label", "onChange"];
const _hoisted_21$1 = { class: "m-grow" };
const _hoisted_22$1 = ["onClick"];
const _hoisted_23$1 = { class: "m-name" };
const _hoisted_24$1 = {
  key: 1,
  class: "m-name"
};
const _hoisted_25$1 = { class: "m-muted m-path" };
const _hoisted_26$1 = {
  key: 2,
  class: "m-muted m-spacer"
};
const _hoisted_27$1 = { class: "m-pager" };
const _hoisted_28$1 = { class: "m-muted" };
const _hoisted_29$1 = { class: "m-muted m-spacer" };

const _sfc_main$2 = {
  __name: 'LocalPicker',
  props: { picker: { type: Object, required: true } },
  setup(__props) {

// VAlert/VBtn/VDialog/VProgressLinear are registered by the MoviePilot host.


return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VProgressLinear = _resolveComponent$2("VProgressLinear");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createBlock$2(_component_VDialog, {
    modelValue: __props.picker.open,
    "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((__props.picker.open) = $event)),
    "max-width": "820",
    scrollable: ""
  }, {
    default: _withCtx$2(() => [
      _createElementVNode$2("section", _hoisted_1$2, [
        _createElementVNode$2("header", _hoisted_2$2, [
          _cache[9] || (_cache[9] = _createElementVNode$2("div", null, [
            _createElementVNode$2("div", { class: "m-kicker" }, "LOCAL · MP MOUNTS"),
            _createElementVNode$2("h2", null, "选择本地文件与文件夹")
          ], -1)),
          _createVNode$2(_component_VBtn, {
            variant: "text",
            onClick: _cache[0] || (_cache[0] = $event => (__props.picker.open = false))
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2("完成（" + _toDisplayString$2(__props.picker.selected.length) + "）", 1)
            ]),
            _: 1
          })
        ]),
        _cache[24] || (_cache[24] = _createElementVNode$2("p", { class: "m-muted" }, "只显示 MoviePilot Docker 挂载根目录。点击目录名称进入一层；勾选不会展开目录。", -1)),
        _createElementVNode$2("nav", _hoisted_3$2, [
          _createElementVNode$2("button", {
            type: "button",
            onClick: _cache[1] || (_cache[1] = (...args) => (__props.picker.showRoots && __props.picker.showRoots(...args)))
          }, "挂载根目录"),
          (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.picker.crumbs, (crumb) => {
            return (_openBlock$2(), _createElementBlock$2("button", {
              key: crumb.path,
              type: "button",
              onClick: $event => (__props.picker.enter(crumb.path))
            }, _toDisplayString$2(crumb.name), 9, _hoisted_4$2))
          }), 128))
        ]),
        (__props.picker.path)
          ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_5$2, [
              _createVNode$2(_component_VBtn, {
                variant: "text",
                disabled: __props.picker.loading || !__props.picker.result,
                onClick: __props.picker.up
              }, {
                default: _withCtx$2(() => [...(_cache[10] || (_cache[10] = [
                  _createTextVNode$2("返回上级", -1)
                ]))]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              _createVNode$2(_component_VBtn, {
                color: "primary",
                variant: "tonal",
                disabled: __props.picker.loading || !!__props.picker.error || !__props.picker.result,
                onClick: __props.picker.selectCurrent
              }, {
                default: _withCtx$2(() => [...(_cache[11] || (_cache[11] = [
                  _createTextVNode$2("选当前文件夹", -1)
                ]))]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              _createElementVNode$2("span", _hoisted_6$2, _toDisplayString$2(__props.picker.path), 1)
            ]))
          : _createCommentVNode$2("", true),
        (__props.picker.path)
          ? (_openBlock$2(), _createElementBlock$2("form", {
              key: 1,
              class: "m-card m-spacer",
              onSubmit: _cache[5] || (_cache[5] = _withModifiers$1((...args) => (__props.picker.search && __props.picker.search(...args)), ["prevent"]))
            }, [
              _cache[15] || (_cache[15] = _createElementVNode$2("label", {
                for: "m115-search",
                class: "m-label"
              }, "本地文件搜索", -1)),
              _createElementVNode$2("div", _hoisted_7$2, [
                _withDirectives$1(_createElementVNode$2("input", {
                  id: "m115-search",
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((__props.picker.query) = $event)),
                  class: "m-input m-grow",
                  placeholder: "文件或文件夹名称（非正则）",
                  type: "search"
                }, null, 512), [
                  [_vModelText$1, __props.picker.query]
                ]),
                _createVNode$2(_component_VBtn, {
                  type: "submit",
                  color: "primary",
                  disabled: __props.picker.loading || !__props.picker.query.trim()
                }, {
                  default: _withCtx$2(() => [...(_cache[12] || (_cache[12] = [
                    _createTextVNode$2("搜索", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]),
              _createElementVNode$2("label", _hoisted_8$2, [
                _withDirectives$1(_createElementVNode$2("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((__props.picker.recursive) = $event)),
                  type: "checkbox"
                }, null, 512), [
                  [_vModelCheckbox$1, __props.picker.recursive]
                ]),
                _cache[13] || (_cache[13] = _createTextVNode$2("包括子目录", -1))
              ]),
              _cache[16] || (_cache[16] = _createElementVNode$2("p", { class: "m-muted" }, "默认只搜当前层。输入文字或勾选不发请求，仅点击“搜索”或按回车执行；包含子目录可能耗时。", -1)),
              (__props.picker.mode === 'search')
                ? (_openBlock$2(), _createBlock$2(_component_VBtn, {
                    key: 0,
                    variant: "text",
                    onClick: _cache[4] || (_cache[4] = $event => (__props.picker.enter(__props.picker.path)))
                  }, {
                    default: _withCtx$2(() => [...(_cache[14] || (_cache[14] = [
                      _createTextVNode$2("退出搜索，浏览当前目录", -1)
                    ]))]),
                    _: 1
                  }))
                : _createCommentVNode$2("", true)
            ], 32))
          : _createCommentVNode$2("", true),
        (__props.picker.loading)
          ? (_openBlock$2(), _createBlock$2(_component_VProgressLinear, {
              key: 2,
              class: "m-spacer",
              indeterminate: "",
              "aria-label": "读取本地当前层"
            }))
          : _createCommentVNode$2("", true),
        (__props.picker.error)
          ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
              key: 3,
              class: "m-spacer",
              type: "error",
              variant: "tonal",
              role: "alert"
            }, {
              default: _withCtx$2(() => [
                _createTextVNode$2(_toDisplayString$2(__props.picker.error), 1),
                _createVNode$2(_component_VBtn, {
                  variant: "text",
                  disabled: __props.picker.loading,
                  onClick: __props.picker.retry
                }, {
                  default: _withCtx$2(() => [...(_cache[17] || (_cache[17] = [
                    _createTextVNode$2("重试当前请求", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "onClick"])
              ]),
              _: 1
            }))
          : _createCommentVNode$2("", true),
        (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.picker.warnings, (warning) => {
          return (_openBlock$2(), _createBlock$2(_component_VAlert, {
            key: warning,
            class: "m-spacer",
            type: "warning",
            variant: "tonal"
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2(_toDisplayString$2(warning), 1)
            ]),
            _: 2
          }, 1024))
        }), 128)),
        (!__props.picker.loading && !__props.picker.error)
          ? (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 4 }, [
              (__props.picker.mode === 'roots')
                ? (_openBlock$2(), _createElementBlock$2("ul", _hoisted_9$2, [
                    (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.picker.roots, (root) => {
                      return (_openBlock$2(), _createElementBlock$2("li", {
                        key: root.path,
                        class: "m-entry"
                      }, [
                        _createElementVNode$2("label", _hoisted_10$2, [
                          _createElementVNode$2("input", {
                            type: "checkbox",
                            checked: __props.picker.selected.includes(root.path),
                            "aria-label": `选择目录 ${root.path}`,
                            onChange: $event => (__props.picker.toggle(root.path))
                          }, null, 40, _hoisted_11$1)
                        ]),
                        _createElementVNode$2("div", _hoisted_12$1, [
                          _createElementVNode$2("button", {
                            type: "button",
                            class: "m-entry-action",
                            onClick: $event => (__props.picker.enter(root.path))
                          }, [
                            _createElementVNode$2("strong", _hoisted_14$1, "▸ " + _toDisplayString$2(root.name || root.path), 1),
                            _createElementVNode$2("div", _hoisted_15$1, _toDisplayString$2(root.path), 1)
                          ], 8, _hoisted_13$1)
                        ]),
                        _createVNode$2(_component_VBtn, {
                          variant: "text",
                          onClick: $event => (__props.picker.enter(root.path))
                        }, {
                          default: _withCtx$2(() => [...(_cache[18] || (_cache[18] = [
                            _createTextVNode$2("进入", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]))
                    }), 128)),
                    (!__props.picker.roots.length)
                      ? (_openBlock$2(), _createElementBlock$2("li", _hoisted_16$1, "没有可用的 MP Docker 挂载根目录，请检查挂载设置。"))
                      : _createCommentVNode$2("", true)
                  ]))
                : (__props.picker.result)
                  ? (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 1 }, [
                      (__props.picker.mode === 'search')
                        ? (_openBlock$2(), _createElementBlock$2("p", _hoisted_17$1, "搜索结果 · " + _toDisplayString$2(__props.picker.searchSpec?.recursive ? '包括子目录' : '仅当前层') + " · 已扫描 " + _toDisplayString$2(__props.picker.result.scanned ?? '—') + " 项 " + _toDisplayString$2(__props.picker.result.message || ''), 1))
                        : _createCommentVNode$2("", true),
                      (__props.picker.result.truncated)
                        ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                            key: 1,
                            type: "warning",
                            variant: "tonal",
                            class: "m-spacer"
                          }, {
                            default: _withCtx$2(() => [...(_cache[19] || (_cache[19] = [
                              _createTextVNode$2("搜索／列表已达服务端上限，结果可能不完整。请缩小目录或关键词。", -1)
                            ]))]),
                            _: 1
                          }))
                        : _createCommentVNode$2("", true),
                      _createElementVNode$2("ul", _hoisted_18$1, [
                        (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.picker.result.entries, (entry) => {
                          return (_openBlock$2(), _createElementBlock$2("li", {
                            key: entry.path,
                            class: "m-entry"
                          }, [
                            _createElementVNode$2("label", _hoisted_19$1, [
                              _createElementVNode$2("input", {
                                type: "checkbox",
                                checked: __props.picker.selected.includes(entry.path),
                                disabled: entry.selectable === false,
                                "aria-label": `选择 ${entry.path}`,
                                onChange: $event => (__props.picker.toggle(entry.path))
                              }, null, 40, _hoisted_20$1)
                            ]),
                            _createElementVNode$2("div", _hoisted_21$1, [
                              (entry.is_dir)
                                ? (_openBlock$2(), _createElementBlock$2("button", {
                                    key: 0,
                                    type: "button",
                                    class: "m-entry-action",
                                    onClick: $event => (__props.picker.enter(entry.path))
                                  }, [
                                    _createElementVNode$2("strong", _hoisted_23$1, "▸ " + _toDisplayString$2(entry.name), 1)
                                  ], 8, _hoisted_22$1))
                                : (_openBlock$2(), _createElementBlock$2("strong", _hoisted_24$1, _toDisplayString$2(entry.name), 1)),
                              _createElementVNode$2("div", _hoisted_25$1, _toDisplayString$2(__props.picker.mode === 'search' ? entry.path : entry.is_dir ? '文件夹' : _unref$1(sizeText)(entry.size)) + _toDisplayString$2(entry.selectable === false ? ' · 不可选择' : ''), 1)
                            ]),
                            (__props.picker.mode === 'search')
                              ? (_openBlock$2(), _createBlock$2(_component_VBtn, {
                                  key: 0,
                                  variant: "text",
                                  onClick: $event => (__props.picker.locate(entry))
                                }, {
                                  default: _withCtx$2(() => [...(_cache[20] || (_cache[20] = [
                                    _createTextVNode$2("定位", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["onClick"]))
                              : (entry.is_dir)
                                ? (_openBlock$2(), _createBlock$2(_component_VBtn, {
                                    key: 1,
                                    variant: "text",
                                    onClick: $event => (__props.picker.enter(entry.path))
                                  }, {
                                    default: _withCtx$2(() => [...(_cache[21] || (_cache[21] = [
                                      _createTextVNode$2("进入", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"]))
                                : _createCommentVNode$2("", true)
                          ]))
                        }), 128))
                      ]),
                      (!__props.picker.result.entries.length)
                        ? (_openBlock$2(), _createElementBlock$2("p", _hoisted_26$1, _toDisplayString$2(__props.picker.mode === 'search' ? '未找到匹配项，试试其他关键词或包括子目录。' : '此目录为空。'), 1))
                        : _createCommentVNode$2("", true),
                      _createElementVNode$2("div", _hoisted_27$1, [
                        _createVNode$2(_component_VBtn, {
                          variant: "text",
                          disabled: !__props.picker.result.offset,
                          onClick: _cache[6] || (_cache[6] = $event => (__props.picker.page(__props.picker.result.offset - 100)))
                        }, {
                          default: _withCtx$2(() => [...(_cache[22] || (_cache[22] = [
                            _createTextVNode$2("上一页", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"]),
                        _createElementVNode$2("span", _hoisted_28$1, "第 " + _toDisplayString$2(Math.floor((__props.picker.result.offset || 0) / 100) + 1) + " 页 · " + _toDisplayString$2(__props.picker.result.total ?? '—') + " 项", 1),
                        _createVNode$2(_component_VBtn, {
                          variant: "text",
                          disabled: !__props.picker.result.has_more,
                          onClick: _cache[7] || (_cache[7] = $event => (__props.picker.page(__props.picker.result.offset + 100)))
                        }, {
                          default: _withCtx$2(() => [...(_cache[23] || (_cache[23] = [
                            _createTextVNode$2("下一页", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"])
                      ])
                    ], 64))
                  : _createCommentVNode$2("", true)
            ], 64))
          : _createCommentVNode$2("", true),
        _createElementVNode$2("p", _hoisted_29$1, "已选 " + _toDisplayString$2(__props.picker.selected.length) + " 个路径，跨层与翻页保留；可回首页移除。", 1)
      ])
    ]),
    _: 1
  }, 8, ["modelValue"]))
}
}

};
const LocalPicker = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-2bbc1aa2"]]);

const {createElementVNode:_createElementVNode$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createVNode:_createVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,toDisplayString:_toDisplayString$1,renderList:_renderList$1,Fragment:_Fragment$1,createElementBlock:_createElementBlock$1} = await importShared('vue');


const _hoisted_1$1 = {
  class: "m115 m-dialog",
  "aria-label": "115目标目录选择"
};
const _hoisted_2$1 = { class: "m-header" };
const _hoisted_3$1 = { class: "m-toolbar" };
const _hoisted_4$1 = { class: "m-path m-spacer" };
const _hoisted_5$1 = { class: "m-list" };
const _hoisted_6$1 = ["onClick"];
const _hoisted_7$1 = { class: "m-name" };
const _hoisted_8$1 = {
  key: 0,
  class: "m-muted m-spacer"
};
const _hoisted_9$1 = { class: "m-pager" };
const _hoisted_10$1 = { class: "m-muted" };


const _sfc_main$1 = {
  __name: 'RemotePicker',
  props: { picker: { type: Object, required: true } },
  setup(__props) {

// VAlert/VBtn/VDialog/VProgressLinear are registered by the MoviePilot host.


return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VProgressLinear = _resolveComponent$1("VProgressLinear");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VDialog, {
    modelValue: __props.picker.open,
    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((__props.picker.open) = $event)),
    "max-width": "700",
    scrollable: ""
  }, {
    default: _withCtx$1(() => [
      _createElementVNode$1("section", _hoisted_1$1, [
        _createElementVNode$1("header", _hoisted_2$1, [
          _cache[5] || (_cache[5] = _createElementVNode$1("div", null, [
            _createElementVNode$1("div", { class: "m-kicker" }, "115 · DESTINATION"),
            _createElementVNode$1("h2", null, "选择115目标目录")
          ], -1)),
          _createVNode$1(_component_VBtn, {
            variant: "text",
            onClick: _cache[0] || (_cache[0] = $event => (__props.picker.open = false))
          }, {
            default: _withCtx$1(() => [...(_cache[4] || (_cache[4] = [
              _createTextVNode$1("关闭", -1)
            ]))]),
            _: 1
          })
        ]),
        _cache[14] || (_cache[14] = _createElementVNode$1("p", { class: "m-muted" }, "按层读取真实目录，不自动遍历网盘。进入文件夹后点击“选当前目录”。", -1)),
        _createElementVNode$1("div", _hoisted_3$1, [
          _createVNode$1(_component_VBtn, {
            variant: "text",
            onClick: _cache[1] || (_cache[1] = $event => (__props.picker.load('0')))
          }, {
            default: _withCtx$1(() => [...(_cache[6] || (_cache[6] = [
              _createTextVNode$1("115根目录", -1)
            ]))]),
            _: 1
          }),
          _createVNode$1(_component_VBtn, {
            variant: "text",
            disabled: __props.picker.loading || !__props.picker.result || String(__props.picker.result.cid) === '0' || __props.picker.result.parent_cid == null,
            onClick: __props.picker.up
          }, {
            default: _withCtx$1(() => [...(_cache[7] || (_cache[7] = [
              _createTextVNode$1("返回上级", -1)
            ]))]),
            _: 1
          }, 8, ["disabled", "onClick"])
        ]),
        (__props.picker.loading)
          ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
              key: 0,
              indeterminate: "",
              "aria-label": "读取115当前层"
            }))
          : _createCommentVNode$1("", true),
        (__props.picker.error)
          ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
              key: 1,
              type: "error",
              variant: "tonal",
              role: "alert"
            }, {
              default: _withCtx$1(() => [
                _createTextVNode$1(_toDisplayString$1(__props.picker.error), 1),
                _cache[9] || (_cache[9] = _createElementVNode$1("p", null, "此目录未加载成功，不能选择。可能已删除或 Cookie 失效；可返回根目录重试。", -1)),
                _createVNode$1(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[2] || (_cache[2] = $event => (__props.picker.load(__props.picker.pendingCid)))
                }, {
                  default: _withCtx$1(() => [...(_cache[8] || (_cache[8] = [
                    _createTextVNode$1("重试", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }))
          : _createCommentVNode$1("", true),
        (__props.picker.result && !__props.picker.loading && !__props.picker.error)
          ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 2 }, [
              _createElementVNode$1("p", _hoisted_4$1, [
                _createElementVNode$1("strong", null, _toDisplayString$1(__props.picker.result.path), 1)
              ]),
              _createElementVNode$1("ul", _hoisted_5$1, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(__props.picker.result.entries, (entry) => {
                  return (_openBlock$1(), _createElementBlock$1("li", {
                    key: entry.cid,
                    class: "m-entry"
                  }, [
                    _createElementVNode$1("button", {
                      type: "button",
                      class: "m-entry-action m-grow",
                      onClick: $event => (__props.picker.load(entry.cid))
                    }, [
                      _createElementVNode$1("span", _hoisted_7$1, "▸ " + _toDisplayString$1(entry.name), 1)
                    ], 8, _hoisted_6$1),
                    _createVNode$1(_component_VBtn, {
                      variant: "text",
                      onClick: $event => (__props.picker.load(entry.cid))
                    }, {
                      default: _withCtx$1(() => [...(_cache[10] || (_cache[10] = [
                        _createTextVNode$1("进入", -1)
                      ]))]),
                      _: 1
                    }, 8, ["onClick"])
                  ]))
                }), 128))
              ]),
              (!__props.picker.result.entries.length)
                ? (_openBlock$1(), _createElementBlock$1("p", _hoisted_8$1, "当前目录没有子文件夹，仍可选为目标。"))
                : _createCommentVNode$1("", true),
              _createElementVNode$1("div", _hoisted_9$1, [
                _createVNode$1(_component_VBtn, {
                  variant: "text",
                  disabled: !__props.picker.previousOffsets.length,
                  onClick: __props.picker.previousPage
                }, {
                  default: _withCtx$1(() => [...(_cache[11] || (_cache[11] = [
                    _createTextVNode$1("上一页", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "onClick"]),
                _createElementVNode$1("span", _hoisted_10$1, "第 " + _toDisplayString$1(__props.picker.previousOffsets.length + 1) + " 页", 1),
                _createVNode$1(_component_VBtn, {
                  variant: "text",
                  disabled: !__props.picker.result.has_more,
                  onClick: __props.picker.nextPage
                }, {
                  default: _withCtx$1(() => [...(_cache[12] || (_cache[12] = [
                    _createTextVNode$1("下一页", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "onClick"])
              ])
            ], 64))
          : _createCommentVNode$1("", true),
        _createVNode$1(_component_VBtn, {
          color: "primary",
          class: "m-spacer",
          disabled: __props.picker.loading || !!__props.picker.error || !__props.picker.result,
          onClick: __props.picker.choose
        }, {
          default: _withCtx$1(() => [...(_cache[13] || (_cache[13] = [
            _createTextVNode$1("选当前目录", -1)
          ]))]),
          _: 1
        }, 8, ["disabled", "onClick"])
      ])
    ]),
    _: 1
  }, 8, ["modelValue"]))
}
}

};
const RemotePicker = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-436c09f2"]]);

const {computed: computed$2,ref: ref$2} = await importShared('vue');

function useLocalPicker(client) {
  const open = ref$2(false), loading = ref$2(false), error = ref$2(''), warnings = ref$2([]);
  const roots = ref$2([]), path = ref$2(''), result = ref$2(null), mode = ref$2('roots');
  const query = ref$2(''), recursive = ref$2(false), searchSpec = ref$2(null);
  const selected = ref$2([]), selectionTouched = ref$2(false);
  const gate = createGeneration();
  const crumbs = computed$2(() => {
    const root = [...roots.value].sort((a, b) => b.path.length - a.path.length).find(root => path.value === root.path || path.value.startsWith(root.path.replace(/\/$/, '') + '/'));
    if (!root) return []
    const items = [{ name: root.name || root.path, path: root.path }];
    let current = root.path.replace(/\/$/, '');
    for (const name of path.value.slice(current.length).split('/').filter(Boolean)) { current += `/${name}`; items.push({ name, path: current }); }
    return items
  });
  async function fetchView(type, target = '', offset = 0, spec = null) {
    const ticket = gate.next();
    mode.value = type; path.value = target; result.value = null;
    loading.value = true; error.value = ''; warnings.value = [];
    try {
      const data = await client.get(type === 'roots' ? 'roots' : type === 'search' ? 'search' : 'browse', type === 'roots' ? undefined : { path: target, offset, limit: 100, ...(type === 'search' ? spec : {}) });
      if (!gate.current(ticket)) return
      if (type === 'roots') {
        if (!Array.isArray(data.roots)) throw new Error('挂载根目录响应无效')
        roots.value = data.roots;
      } else {
        if (!Array.isArray(data.entries) || typeof data.path !== 'string') throw new Error('本地目录响应无效')
        result.value = data; path.value = data.path;
      }
      warnings.value = data.warnings || [];
    } catch (cause) { if (gate.current(ticket)) error.value = errorText(cause); }
    finally { if (gate.current(ticket)) loading.value = false; }
  }
  function showRoots() { searchSpec.value = null; return fetchView('roots') }
  function enter(target) { searchSpec.value = null; return fetchView('browse', target) }
  async function show() { open.value = true; return showRoots() }
  function search() {
    if (!query.value.trim()) { error.value = '请输入搜索关键词'; return }
    if (!path.value) { error.value = '请先进入一个 MP 挂载目录'; return }
    searchSpec.value = { query: query.value.trim(), recursive: recursive.value };
    return fetchView('search', path.value, 0, searchSpec.value)
  }
  function page(offset) {
    if (loading.value || !result.value) return
    return fetchView(mode.value, path.value, Math.max(0, offset), searchSpec.value)
  }
  function retry() { return fetchView(mode.value, path.value, 0, searchSpec.value) }
  function toggle(target) {
    selectionTouched.value = true;
    selected.value = selected.value.includes(target) ? selected.value.filter(item => item !== target) : [...selected.value, target];
  }
  function selectCurrent() {
    if (loading.value || error.value || !result.value || !path.value) return
    if (!selected.value.includes(path.value)) toggle(path.value);
  }
  function remove(target) { selectionTouched.value = true; selected.value = selected.value.filter(item => item !== target); }
  function clear() { selectionTouched.value = true; selected.value = []; }
  function locate(entry) { return enter(entry.path.slice(0, entry.path.lastIndexOf('/')) || '/') }
  function up() { return result.value?.parent ? enter(result.value.parent) : showRoots() }
  function dispose() { gate.invalidate(); }
  return { open, loading, error, warnings, roots, path, result, mode, query, recursive, searchSpec, selected, selectionTouched, crumbs, show, showRoots, enter, search, page, retry, toggle, remove, clear, selectCurrent, locate, up, dispose }
}

const {ref: ref$1} = await importShared('vue');
function useRemotePicker(client) {
  const open = ref$1(false), loading = ref$1(false), error = ref$1(''), result = ref$1(null);
  const target = ref$1({ path: '/', cid: null }), touched = ref$1(false), pendingCid = ref$1('0');
  const gate = createGeneration(), previousOffsets = ref$1([]);
  async function load(cid = '0', offset = 0, paging = false) {
    const ticket = gate.next();
    if (!paging) previousOffsets.value = [];
    pendingCid.value = String(cid); loading.value = true; error.value = ''; result.value = null;
    try {
      const data = await client.get('remote', { cid, offset, limit: 100 });
      if (!gate.current(ticket)) return
      if (!Array.isArray(data.entries) || data.cid == null || typeof data.path !== 'string') throw new Error('115 目录响应无效')
      result.value = data;
    } catch (cause) { if (gate.current(ticket)) error.value = errorText(cause); }
    finally { if (gate.current(ticket)) loading.value = false; }
  }
  function show() { open.value = true; return load(target.value.cid ?? '0') }
  function choose() {
    if (loading.value || error.value || !result.value) return false
    target.value = { path: result.value.path, cid: String(result.value.cid) };
    touched.value = true; open.value = false; return true
  }
  function up() { if (result.value?.parent_cid != null && String(result.value.cid) !== '0') return load(result.value.parent_cid) }
  function page(offset) { if (!loading.value && result.value) return load(result.value.cid, Math.max(0, offset), true) }
  function nextPage() {
    if (loading.value || !result.value?.has_more) return
    const { offset = 0, limit = 100, next_offset } = result.value;
    previousOffsets.value.push(offset);
    return page(next_offset ?? offset + limit)
  }
  function previousPage() {
    if (loading.value || !result.value || !previousOffsets.value.length) return
    return page(previousOffsets.value.pop())
  }
  function invalidate() { gate.invalidate(); result.value = null; target.value.cid = null; loading.value = false; open.value = false; }
  function dispose() { gate.invalidate(); }
  return { open, loading, error, result, target, touched, pendingCid, previousOffsets, load, show, choose, up, page, nextPage, previousPage, invalidate, dispose }
}

const {computed: computed$1,onActivated,onBeforeUnmount,onDeactivated,onMounted,ref} = await importShared('vue');

function useWorkbench(client, emit) {
  const local = useLocalPicker(client), remote = useRemotePicker(client);
  const status = ref({ has_cookie: false, running: false, job: {}, history: [] });
  const loaded = ref(false), loading = ref(false), error = ref(''), notice = ref('');
  const submitting = ref(false), cancelling = ref(false), cancelRequested = ref(false), savingSelection = ref(false);
  const settingsOpen = ref(false), preserveStructure = ref(true), skipUnchanged = ref(false);
  const historyQuery = ref(''), historyFilter = ref('all'), historyPage = ref(1);
  const statusGate = createGeneration();
  let timer = null, disposed = false, active = true;
  const canPush = computed$1(() => loaded.value && status.value.has_cookie && local.selected.value.length > 0 && !status.value.running && !submitting.value);
  const progress = computed$1(() => status.value.job?.total > 0 ? Math.min(100, Math.round((status.value.job.processed || 0) / status.value.job.total * 100)) : 0);
  const filteredHistory = computed$1(() => (status.value.history || []).filter(row => (historyFilter.value === 'all' || row.status === historyFilter.value) && (!historyQuery.value.trim() || `${row.name} ${row.path} ${row.message}`.toLowerCase().includes(historyQuery.value.trim().toLowerCase()))));
  const historyPages = computed$1(() => Math.max(1, Math.ceil(filteredHistory.value.length / 20)));
  const pagedHistory = computed$1(() => { const page = Math.min(historyPage.value, historyPages.value); return filteredHistory.value.slice((page - 1) * 20, page * 20) });
  function stopPolling() { if (timer !== null) clearTimeout(timer); timer = null; }
  function visible() { return active && !disposed && (typeof document === 'undefined' || !document.hidden) }
  function syncPolling() {
    stopPolling();
    if (status.value.running && visible()) timer = setTimeout(() => { timer = null; if (visible()) loadStatus(); }, 2000);
  }
  async function loadStatus() {
    if (disposed) return
    stopPolling();
    const ticket = statusGate.next(); loading.value = true; error.value = '';
    try {
      const data = await client.get('status');
      if (!statusGate.current(ticket) || disposed) return
      if (typeof data.running !== 'boolean' || typeof data.has_cookie !== 'boolean') throw new Error('状态响应不完整')
      status.value = { ...data, job: data.job || {}, history: data.history || [] }; loaded.value = true;
      if (!local.selectionTouched.value) local.selected.value = [...new Set(data.local_paths || [])];
      if (!remote.touched.value) remote.target.value = { path: data.remote_dir || '/', cid: null };
      if (!data.running) cancelRequested.value = false;
    } catch (cause) { if (statusGate.current(ticket) && !disposed) { error.value = errorText(cause); loaded.value = false; } }
    finally { if (statusGate.current(ticket) && !disposed) { loading.value = false; syncPolling(); } }
  }
  async function push() {
    if (!canPush.value) return
    submitting.value = true; error.value = ''; notice.value = ''; statusGate.invalidate(); stopPolling();
    const target = clone(remote.target.value);
    const body = { paths: [...local.selected.value], remote_dir: target.path || '/', force: !skipUnchanged.value, preserve_structure: preserveStructure.value, request_id: requestId(), ...(target.cid != null ? { remote_cid: target.cid } : {}) };
    try {
      const data = await client.post('push', body);
      status.value.running = true; cancelRequested.value = false;
      status.value.job = { id: data.job_id, phase: 'collecting', total: 0, processed: 0 };
      notice.value = `任务已受理（${data.accepted ?? body.paths.length} 个所选路径），后台收集文件后秒传。`;
      emit('action'); await loadStatus();
    } catch (cause) {
      // A transport error may occur after acceptance. Require status confirmation
      // before allowing another submission rather than risk a duplicate job.
      error.value = `${errorText(cause)}；请刷新确认任务状态后重试。`; loaded.value = false; syncPolling();
    }
    finally { submitting.value = false; loading.value = false; }
  }
  async function cancel() {
    if (!status.value.running || cancelling.value || cancelRequested.value) return
    cancelling.value = true; error.value = '';
    try { await client.post('cancel'); cancelRequested.value = true; notice.value = '已请求停止，等待当前文件完成；后台仍可能运行。'; }
    catch (cause) { error.value = errorText(cause); }
    finally { cancelling.value = false; }
  }
  async function saveSelection() {
    if (savingSelection.value) return
    savingSelection.value = true; error.value = ''; notice.value = '';
    const paths = [...local.selected.value], target = remote.target.value.path || '/';
    try {
      const latest = await client.get('settings');
      const config = normalizeSettings(latest.settings);
      const data = await client.post('settings', { ...config, local_paths: paths, remote_dir: target });
      normalizeSettings(data.settings);
      notice.value = '已将本次选择保存为默认路径，不影响后续选择；无需保存也能直接秒传。';
    } catch (cause) { error.value = errorText(cause); }
    finally { savingSelection.value = false; }
  }
  function settingsSaved(config) {
    remote.invalidate();
    if (!remote.touched.value) remote.target.value.path = config.remote_dir || '/';
    loadStatus();
  }
  function visibilityChanged() { if (visible() && status.value.running) loadStatus(); else stopPolling(); }
  onMounted(() => {
    // Initial load must work in an initially hidden iOS WebView too.
    loadStatus();
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', visibilityChanged);
  });
  onActivated(() => { active = true; syncPolling(); });
  onDeactivated(() => { active = false; stopPolling(); });
  onBeforeUnmount(() => {
    disposed = true; stopPolling(); statusGate.invalidate(); local.dispose(); remote.dispose();
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', visibilityChanged);
  });
  return { local, remote, status, loaded, loading, error, notice, submitting, cancelling, cancelRequested, savingSelection, settingsOpen, preserveStructure, skipUnchanged, canPush, progress, historyQuery, historyFilter, historyPage, historyPages, filteredHistory, pagedHistory, loadStatus, push, cancel, saveSelection, settingsSaved, syncPolling, visibilityChanged }
}

const {createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,withModifiers:_withModifiers,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives,vModelText:_vModelText,vModelSelect:_vModelSelect,unref:_unref} = await importShared('vue');


const _hoisted_1 = {
  class: "m115 m-page",
  "aria-label": "手动秒传115首页"
};
const _hoisted_2 = { class: "m-header" };
const _hoisted_3 = { class: "m-row" };
const _hoisted_4 = { class: "m-stack" };
const _hoisted_5 = { class: "m-card" };
const _hoisted_6 = { class: "m-picker m-spacer" };
const _hoisted_7 = ["value", "aria-expanded"];
const _hoisted_8 = {
  key: 0,
  class: "m-chips",
  "aria-label": "已选本地路径"
};
const _hoisted_9 = ["aria-label", "onClick"];
const _hoisted_10 = {
  key: 1,
  class: "m-muted m-spacer"
};
const _hoisted_11 = { class: "m-row m-spacer" };
const _hoisted_12 = { class: "m-card" };
const _hoisted_13 = { class: "m-picker m-spacer" };
const _hoisted_14 = ["value", "aria-expanded"];
const _hoisted_15 = { class: "m-check" };
const _hoisted_16 = { class: "m-check" };
const _hoisted_17 = { class: "m-row m-spacer" };
const _hoisted_18 = {
  key: 0,
  class: "m-muted"
};
const _hoisted_19 = {
  key: 1,
  class: "m-muted"
};
const _hoisted_20 = {
  class: "m-card",
  "aria-label": "秒传任务进度"
};
const _hoisted_21 = { class: "m-row" };
const _hoisted_22 = { class: "m-grow" };
const _hoisted_23 = { class: "m-muted m-spacer" };
const _hoisted_24 = { class: "m-stats" };
const _hoisted_25 = { class: "m-stat" };
const _hoisted_26 = { class: "m-stat" };
const _hoisted_27 = { class: "m-stat" };
const _hoisted_28 = { class: "m-stat" };
const _hoisted_29 = {
  key: 0,
  class: "m-path"
};
const _hoisted_30 = {
  key: 1,
  class: "m-path"
};
const _hoisted_31 = { key: 3 };
const _hoisted_32 = {
  class: "m-card",
  "aria-label": "秒传历史"
};
const _hoisted_33 = { class: "m-row" };
const _hoisted_34 = { class: "m-badge" };
const _hoisted_35 = { class: "m-row m-spacer" };
const _hoisted_36 = { class: "m-history" };
const _hoisted_37 = { class: "m-row" };
const _hoisted_38 = { class: "m-grow m-name" };
const _hoisted_39 = { class: "m-badge" };
const _hoisted_40 = { class: "m-muted m-path" };
const _hoisted_41 = { class: "m-muted" };
const _hoisted_42 = {
  key: 0,
  class: "m-path"
};
const _hoisted_43 = {
  key: 0,
  class: "m-muted m-spacer"
};
const _hoisted_44 = {
  key: 1,
  class: "m-pager"
};
const _hoisted_45 = { class: "m-muted" };
const _hoisted_46 = {
  class: "m-dialog",
  style: {"padding":"0"}
};

const {computed,reactive,watch} = await importShared('vue');

const _sfc_main = {
  __name: 'Workbench',
  props: { ...hostProps, showClose: { type: Boolean, default: false } },
  emits: ['action', 'save', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const vm = reactive(useWorkbench(useClient(props), emit));
const phase = computed(() => ({ collecting: '正在收集所选文件', hashing: '正在计算文件哈希', uploading: '正在秒传', running: '正在秒传', cancelling: '等待当前文件完成后停止', completed: '已完成', completed_with_errors: '已完成，部分文件失败', cancelled: '已停止', interrupted: '任务已中断', failed: '任务失败', idle: '就绪' }[vm.status.job?.phase] || vm.status.job?.phase || (vm.status.running ? '处理中' : '就绪')));
const statusLabel = value => ({ success: '成功', failed: '失败', skipped: '跳过', error: '失败' }[value] || value || '未知');
const localSummary = computed(() => vm.local.selected.length ? `已选 ${vm.local.selected.length} 项 · ${vm.local.selected[0]}` : '点击选择 MP 挂载目录中的文件／文件夹');
watch([() => vm.historyQuery, () => vm.historyFilter], () => { vm.historyPage = 1; });
// Embedded Config's switch is an internal return-to-home; forwarding it to
// Page's host would reopen the external Config screen instead of returning.
function configSwitch() { vm.settingsOpen = false; }

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("section", _hoisted_1, [
    _createElementVNode("header", _hoisted_2, [
      _cache[23] || (_cache[23] = _createElementVNode("div", null, [
        _createElementVNode("div", { class: "m-kicker" }, "MANUAL PUSH · 115"),
        _createElementVNode("h1", null, "手动秒传115"),
        _createElementVNode("p", { class: "m-muted" }, "本地文件，自由选择。手动补传，不自动调度。")
      ], -1)),
      _createElementVNode("div", _hoisted_3, [
        _createVNode(_component_VBtn, {
          variant: "tonal",
          onClick: _cache[0] || (_cache[0] = $event => (vm.settingsOpen = true))
        }, {
          default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
            _createTextVNode("设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          variant: "text",
          loading: vm.loading,
          disabled: vm.submitting,
          onClick: vm.loadStatus
        }, {
          default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "disabled", "onClick"]),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 0,
              variant: "text",
              onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                _createTextVNode("关闭", -1)
              ]))]),
              _: 1
            }))
          : _createCommentVNode("", true)
      ])
    ]),
    _createElementVNode("div", _hoisted_4, [
      (vm.error)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: "error",
            variant: "tonal",
            role: "alert"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(vm.error), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (vm.notice)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            type: "info",
            variant: "tonal",
            role: "status"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(vm.notice), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (vm.status.persist_error)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 2,
            type: "error",
            variant: "tonal",
            role: "alert"
          }, {
            default: _withCtx(() => [
              _createTextVNode("持久化失败：" + _toDisplayString(vm.status.persist_error), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (vm.status.message)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 3,
            type: "info",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(vm.status.message), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (vm.loaded && !vm.status.has_cookie)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 4,
            type: "warning",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _cache[25] || (_cache[25] = _createTextVNode("尚未配置115 Cookie，保存后才能秒传。", -1)),
              _createVNode(_component_VBtn, {
                variant: "text",
                onClick: _cache[2] || (_cache[2] = $event => (vm.settingsOpen = true))
              }, {
                default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                  _createTextVNode("打开设置", -1)
                ]))]),
                _: 1
              })
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      _createElementVNode("section", _hoisted_5, [
        _cache[29] || (_cache[29] = _createElementVNode("div", { class: "m-kicker" }, "01 · LOCAL", -1)),
        _cache[30] || (_cache[30] = _createElementVNode("h2", null, "本地秒传路径", -1)),
        _cache[31] || (_cache[31] = _createElementVNode("p", { class: "m-muted" }, "仅列出 MP Docker 挂载根目录，子目录由你手动逐层进入。", -1)),
        _createElementVNode("div", _hoisted_6, [
          _createElementVNode("input", {
            class: "m-input",
            value: localSummary.value,
            readonly: "",
            role: "combobox",
            "aria-label": "本地路径下拉选择",
            "aria-expanded": vm.local.open,
            "aria-haspopup": "dialog",
            onClick: _cache[3] || (_cache[3] = (...args) => (vm.local.show && vm.local.show(...args))),
            onKeydown: [
              _cache[4] || (_cache[4] = _withKeys(_withModifiers((...args) => (vm.local.show && vm.local.show(...args)), ["prevent"]), ["enter"])),
              _cache[5] || (_cache[5] = _withKeys(_withModifiers((...args) => (vm.local.show && vm.local.show(...args)), ["prevent"]), ["space"])),
              _cache[6] || (_cache[6] = _withKeys(_withModifiers((...args) => (vm.local.show && vm.local.show(...args)), ["prevent"]), ["down"]))
            ]
          }, null, 40, _hoisted_7)
        ]),
        (vm.local.selected.length)
          ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(vm.local.selected, (path) => {
                return (_openBlock(), _createElementBlock("div", {
                  key: path,
                  class: "m-chip"
                }, [
                  _createElementVNode("span", null, _toDisplayString(path), 1),
                  _createElementVNode("button", {
                    type: "button",
                    "aria-label": `移除 ${path}`,
                    onClick: $event => (vm.local.remove(path))
                  }, "×", 8, _hoisted_9)
                ]))
              }), 128))
            ]))
          : (_openBlock(), _createElementBlock("p", _hoisted_10, "尚未选择。支持单文件、整个文件夹与跨层多选。")),
        _createElementVNode("div", _hoisted_11, [
          _createVNode(_component_VBtn, {
            variant: "text",
            disabled: !vm.local.selected.length,
            onClick: vm.local.clear
          }, {
            default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
              _createTextVNode("清空选择", -1)
            ]))]),
            _: 1
          }, 8, ["disabled", "onClick"]),
          _createVNode(_component_VBtn, {
            variant: "tonal",
            loading: vm.savingSelection,
            disabled: vm.savingSelection,
            onClick: vm.saveSelection
          }, {
            default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
              _createTextVNode("保存为默认", -1)
            ]))]),
            _: 1
          }, 8, ["loading", "disabled", "onClick"]),
          _cache[28] || (_cache[28] = _createElementVNode("span", { class: "m-muted" }, "无需保存，选择后可直接秒传。", -1))
        ])
      ]),
      _createElementVNode("section", _hoisted_12, [
        _cache[34] || (_cache[34] = _createElementVNode("div", { class: "m-kicker" }, "02 · DESTINATION", -1)),
        _cache[35] || (_cache[35] = _createElementVNode("h2", null, "115目标目录", -1)),
        _createElementVNode("div", _hoisted_13, [
          _createElementVNode("input", {
            class: "m-input",
            value: vm.remote.target.path,
            readonly: "",
            role: "combobox",
            "aria-label": "115目标目录下拉选择",
            "aria-expanded": vm.remote.open,
            "aria-haspopup": "dialog",
            onClick: _cache[7] || (_cache[7] = (...args) => (vm.remote.show && vm.remote.show(...args))),
            onKeydown: [
              _cache[8] || (_cache[8] = _withKeys(_withModifiers((...args) => (vm.remote.show && vm.remote.show(...args)), ["prevent"]), ["enter"])),
              _cache[9] || (_cache[9] = _withKeys(_withModifiers((...args) => (vm.remote.show && vm.remote.show(...args)), ["prevent"]), ["space"])),
              _cache[10] || (_cache[10] = _withKeys(_withModifiers((...args) => (vm.remote.show && vm.remote.show(...args)), ["prevent"]), ["down"]))
            ]
          }, null, 40, _hoisted_14)
        ]),
        _cache[36] || (_cache[36] = _createElementVNode("p", { class: "m-muted" }, "点击后读取真实115目录，逐层选择；保留默认路径也可直接提交。", -1)),
        _createElementVNode("label", _hoisted_15, [
          _withDirectives(_createElementVNode("input", {
            "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((vm.preserveStructure) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox, vm.preserveStructure]
          ]),
          _cache[32] || (_cache[32] = _createTextVNode("保留文件夹结构", -1))
        ]),
        _createElementVNode("label", _hoisted_16, [
          _withDirectives(_createElementVNode("input", {
            "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((vm.skipUnchanged) = $event)),
            type: "checkbox"
          }, null, 512), [
            [_vModelCheckbox, vm.skipUnchanged]
          ]),
          _cache[33] || (_cache[33] = _createTextVNode("跳过同账户／目标未变化的成功项", -1))
        ]),
        _cache[37] || (_cache[37] = _createElementVNode("p", { class: "m-muted" }, "默认手工补传，不因旧成功记录盲目跳过；秒传结果以115响应为准。", -1)),
        _createElementVNode("div", _hoisted_17, [
          _createVNode(_component_VBtn, {
            color: "primary",
            size: "large",
            loading: vm.submitting,
            disabled: !vm.canPush,
            onClick: vm.push
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(vm.status.running ? '任务运行中' : `开始秒传${vm.local.selected.length ? `（${vm.local.selected.length} 项）` : ''}`), 1)
            ]),
            _: 1
          }, 8, ["loading", "disabled", "onClick"]),
          (vm.status.running)
            ? (_openBlock(), _createElementBlock("span", _hoisted_18, "可继续浏览与调整选择，当前任务使用提交时的快照。"))
            : (!vm.local.selected.length)
              ? (_openBlock(), _createElementBlock("span", _hoisted_19, "请先选择文件或文件夹"))
              : _createCommentVNode("", true)
        ])
      ]),
      _createElementVNode("section", _hoisted_20, [
        _createElementVNode("div", _hoisted_21, [
          _createElementVNode("div", _hoisted_22, [
            _cache[38] || (_cache[38] = _createElementVNode("div", { class: "m-kicker" }, "03 · PROGRESS", -1)),
            _createElementVNode("h2", null, _toDisplayString(phase.value), 1)
          ]),
          (vm.status.running)
            ? (_openBlock(), _createBlock(_component_VBtn, {
                key: 0,
                variant: "tonal",
                color: "warning",
                loading: vm.cancelling,
                disabled: vm.cancelRequested,
                onClick: vm.cancel
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(vm.cancelRequested ? '正在等待停止' : '停止任务'), 1)
                ]),
                _: 1
              }, 8, ["loading", "disabled", "onClick"]))
            : _createCommentVNode("", true)
        ]),
        _createVNode(_component_VProgressLinear, {
          class: "m-spacer",
          "model-value": vm.progress,
          indeterminate: vm.status.running && !vm.status.job.total,
          height: "7",
          rounded: "",
          "aria-label": `任务进度 ${vm.progress}%`
        }, null, 8, ["model-value", "indeterminate", "aria-label"]),
        _createElementVNode("p", _hoisted_23, "已处理 " + _toDisplayString(vm.status.job.processed || 0) + " / " + _toDisplayString(vm.status.job.total || 0) + " · 剩余 " + _toDisplayString(vm.status.job.remaining ?? Math.max(0, (vm.status.job.total || 0) - (vm.status.job.processed || 0))) + _toDisplayString(vm.status.running && !vm.status.job.total ? ' · 后台收集中，不等待前端哈希' : ''), 1),
        _createElementVNode("div", _hoisted_24, [
          _createElementVNode("div", _hoisted_25, [
            _createElementVNode("strong", null, _toDisplayString(vm.status.job.success || 0), 1),
            _cache[39] || (_cache[39] = _createTextVNode("成功", -1))
          ]),
          _createElementVNode("div", _hoisted_26, [
            _createElementVNode("strong", null, _toDisplayString(vm.status.job.failed || 0), 1),
            _cache[40] || (_cache[40] = _createTextVNode("失败", -1))
          ]),
          _createElementVNode("div", _hoisted_27, [
            _createElementVNode("strong", null, _toDisplayString(vm.status.job.skipped || 0), 1),
            _cache[41] || (_cache[41] = _createTextVNode("跳过", -1))
          ]),
          _createElementVNode("div", _hoisted_28, [
            _createElementVNode("strong", null, _toDisplayString(vm.progress) + "%", 1),
            _cache[42] || (_cache[42] = _createTextVNode("进度", -1))
          ])
        ]),
        (vm.status.job.current_file)
          ? (_openBlock(), _createElementBlock("p", _hoisted_29, [
              _cache[43] || (_cache[43] = _createElementVNode("span", { class: "m-muted" }, "当前文件：", -1)),
              _createTextVNode(_toDisplayString(vm.status.job.current_file), 1)
            ]))
          : _createCommentVNode("", true),
        (vm.status.job.message)
          ? (_openBlock(), _createElementBlock("p", _hoisted_30, _toDisplayString(vm.status.job.message), 1))
          : _createCommentVNode("", true),
        (vm.status.job.persist_error)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 2,
              type: "error",
              variant: "tonal"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(vm.status.job.persist_error), 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (vm.status.job.errors?.length)
          ? (_openBlock(), _createElementBlock("details", _hoisted_31, [
              _createElementVNode("summary", null, "查看任务错误（" + _toDisplayString(vm.status.job.errors.length) + "）", 1),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(vm.status.job.errors, (item, index) => {
                return (_openBlock(), _createElementBlock("p", {
                  key: index,
                  class: "m-path"
                }, _toDisplayString(typeof item === 'string' ? item : item.message || JSON.stringify(item)), 1))
              }), 128))
            ]))
          : _createCommentVNode("", true),
        _cache[44] || (_cache[44] = _createElementVNode("p", { class: "m-muted" }, "仅任务运行时每2秒刷新状态；页面隐藏时暂停。停止请求会等待当前文件完成。", -1))
      ]),
      _createElementVNode("section", _hoisted_32, [
        _createElementVNode("div", _hoisted_33, [
          _cache[45] || (_cache[45] = _createElementVNode("h2", { class: "m-grow" }, "秒传历史", -1)),
          _createElementVNode("span", _hoisted_34, _toDisplayString(vm.filteredHistory.length) + " 条", 1)
        ]),
        _createElementVNode("div", _hoisted_35, [
          _withDirectives(_createElementVNode("input", {
            "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((vm.historyQuery) = $event)),
            class: "m-input m-grow",
            type: "search",
            "aria-label": "筛选历史文件或路径",
            placeholder: "筛选文件、路径或消息"
          }, null, 512), [
            [_vModelText, vm.historyQuery]
          ]),
          _withDirectives(_createElementVNode("select", {
            "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((vm.historyFilter) = $event)),
            class: "m-input",
            style: {"width":"auto","max-width":"100%"},
            "aria-label": "历史状态筛选"
          }, [...(_cache[46] || (_cache[46] = [
            _createElementVNode("option", { value: "all" }, "全部状态", -1),
            _createElementVNode("option", { value: "success" }, "成功", -1),
            _createElementVNode("option", { value: "failed" }, "失败", -1),
            _createElementVNode("option", { value: "skipped" }, "跳过", -1)
          ]))], 512), [
            [_vModelSelect, vm.historyFilter]
          ])
        ]),
        _createElementVNode("div", _hoisted_36, [
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(vm.pagedHistory, (row, index) => {
            return (_openBlock(), _createElementBlock("article", {
              key: `${row.path}-${row.time}-${index}`
            }, [
              _createElementVNode("div", _hoisted_37, [
                _createElementVNode("strong", _hoisted_38, _toDisplayString(row.name || row.path), 1),
                _createElementVNode("span", _hoisted_39, _toDisplayString(statusLabel(row.status)), 1)
              ]),
              _createElementVNode("p", _hoisted_40, _toDisplayString(row.path) + " → " + _toDisplayString(row.remote_dir), 1),
              _createElementVNode("p", _hoisted_41, _toDisplayString(_unref(sizeText)(row.size)) + " · " + _toDisplayString(row.time || '—'), 1),
              (row.message)
                ? (_openBlock(), _createElementBlock("p", _hoisted_42, _toDisplayString(row.message), 1))
                : _createCommentVNode("", true)
            ]))
          }), 128))
        ]),
        (!vm.filteredHistory.length)
          ? (_openBlock(), _createElementBlock("p", _hoisted_43, "没有匹配的历史记录。"))
          : _createCommentVNode("", true),
        (vm.historyPages > 1)
          ? (_openBlock(), _createElementBlock("div", _hoisted_44, [
              _createVNode(_component_VBtn, {
                variant: "text",
                disabled: vm.historyPage <= 1,
                onClick: _cache[15] || (_cache[15] = $event => (vm.historyPage--))
              }, {
                default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                  _createTextVNode("上一页", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createElementVNode("span", null, _toDisplayString(Math.min(vm.historyPage, vm.historyPages)) + " / " + _toDisplayString(vm.historyPages), 1),
              _createVNode(_component_VBtn, {
                variant: "text",
                disabled: vm.historyPage >= vm.historyPages,
                onClick: _cache[16] || (_cache[16] = $event => (vm.historyPage++))
              }, {
                default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                  _createTextVNode("下一页", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"])
            ]))
          : _createCommentVNode("", true)
      ]),
      _createElementVNode("p", _hoisted_45, "ManualPush115 · " + _toDisplayString(vm.status.version || '1.8.0') + " · 不触发任何自动调度", 1)
    ]),
    _createVNode(LocalPicker, {
      picker: vm.local
    }, null, 8, ["picker"]),
    _createVNode(RemotePicker, {
      picker: vm.remote
    }, null, 8, ["picker"]),
    _createVNode(_component_VDialog, {
      modelValue: vm.settingsOpen,
      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((vm.settingsOpen) = $event)),
      "max-width": "850",
      persistent: "",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createElementVNode("div", _hoisted_46, [
          (vm.settingsOpen)
            ? (_openBlock(), _createBlock(Config, {
                key: 0,
                api: _ctx.api,
                "plugin-id": _ctx.pluginId,
                "source-plugin-id": _ctx.sourcePluginId,
                "native-subscribe": _ctx.nativeSubscribe,
                "is-embedded": "",
                onSaved: vm.settingsSaved,
                onSave: _cache[17] || (_cache[17] = $event => (emit('save', $event))),
                onClose: _cache[18] || (_cache[18] = $event => (vm.settingsOpen = false)),
                onSwitch: configSwitch
              }, null, 8, ["api", "plugin-id", "source-plugin-id", "native-subscribe", "onSaved"]))
            : _createCommentVNode("", true)
        ])
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const Workbench = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-15814e2f"]]);

export { Workbench as W };
