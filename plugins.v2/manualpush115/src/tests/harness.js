import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRenderer, nextTick } from 'vue'
import { parse, compileScript, compileTemplate, compileStyle } from 'vue/compiler-sfc'

export const defer = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
export const settle = async () => { for (let i = 0; i < 16; i++) { await Promise.resolve(); await nextTick() } }
export const ok = data => ({ success: true, message: '', data })
export const config = () => ({ cookie: 'test-cookie-not-real', user_agent: 'test-UA', extensions: 'mkv,mp4', remote_dir: '/待整理', local_paths: ['/media/original'] })
export const listing = (path, entries = [], extra = {}) => ({ path, parent: path.slice(0, path.lastIndexOf('/')) || null, entries, total: entries.length, offset: 0, limit: 100, has_more: false, warnings: [], ...extra })
export const directory = path => ({ path, name: path.split('/').at(-1), is_dir: true, selectable: true })
export const remoteListing = (cid = '0', path = '/', parent_cid = null, extra = {}) => ({ cid, path, parent_cid, entries: [], offset: 0, limit: 100, has_more: false, ...extra })
export function fixture() {
  const f = { gets: [], posts: [], settings: config(), running: false, getOverride: null, postOverride: null }
  f.api = {
    get(url) {
      f.gets.push(url)
      if (f.getOverride) return f.getOverride(url)
      const parsed = new URL(url, 'https://mock/'), endpoint = parsed.pathname.split('/').at(-1)
      if (endpoint === 'status') return Promise.resolve(ok({ has_cookie: !!f.settings.cookie, running: f.running, local_paths: f.settings.local_paths, remote_dir: f.settings.remote_dir, job: { total: 5, processed: 2 }, history: [] }))
      if (endpoint === 'settings') return Promise.resolve(ok({ settings: structuredClone(f.settings), revision: 1 }))
      if (endpoint === 'roots') return Promise.resolve(ok({ roots: [{ name: 'media', path: '/media', source: 'docker' }], warnings: [] }))
      if (endpoint === 'remote') return Promise.resolve(ok(remoteListing(parsed.searchParams.get('cid'))))
      return Promise.resolve(ok(listing(parsed.searchParams.get('path'))))
    },
    post(url, body) {
      f.posts.push({ url, body: structuredClone(body) })
      if (f.postOverride) return f.postOverride(url, body)
      if (url.endsWith('/settings')) { f.settings = structuredClone(body); return Promise.resolve(ok({ settings: structuredClone(f.settings), revision: 2 })) }
      if (url.endsWith('/push')) { f.running = true; return Promise.resolve(ok({ job_id: 'job-1', accepted: body.paths.length })) }
      return Promise.resolve(ok({ message: '测试已保存配置成功' }))
    },
  }
  return f
}
const renderer = createRenderer({
  createElement: type => ({ type, children: [] }), createText: text => ({ text }), createComment: text => ({ text }),
  setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text },
  parentNode: node => node.parent, nextSibling: () => null, patchProp: () => {},
  insert(node, parent) { node.parent = parent; parent.children.push(node) },
  remove(node) { if (node.parent) node.parent.children = node.parent.children.filter(child => child !== node) },
})
export function mount(t, component, props = {}, documentHidden = false, provided = {}) {
  const originals = { setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout, document: globalThis.document }
  const timers = new Map(), listeners = new Map(); let id = 0
  globalThis.setTimeout = (fn, delay) => { timers.set(++id, { fn, delay }); return id }
  globalThis.clearTimeout = value => timers.delete(value)
  globalThis.document = { hidden: documentHidden, addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) }
  const events = {}
  const handlers = Object.fromEntries((component.emits || []).map(name => [`on${name[0].toUpperCase()}${name.slice(1)}`, (...args) => { (events[name] ||= []).push(args) }]))
  const app = renderer.createApp({ ...component, render: () => null }, { ...props, ...handlers })
  app.testEvents = events
  for (const [key, value] of Object.entries(provided)) app.provide(key, value)
  app.mount({ children: [] })
  t.after(() => { app.unmount(); Object.assign(globalThis, originals) })
  return { app, state: app._instance.setupState, timers, listeners }
}
export async function compileComponent(name) {
  const filename = new URL(`../components/${name}.vue`, import.meta.url)
  const source = await readFile(filename, 'utf8')
  const { descriptor, errors } = parse(source); assert.deepEqual(errors, [])
  const compiled = compileScript(descriptor, { id: `m115-${name}` })
  const template = compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: `m115-${name}`, compilerOptions: { bindingMetadata: compiled.bindings } }); assert.deepEqual(template.errors, [])
  const style = await readFile(new URL('../styles/panel.css', import.meta.url), 'utf8')
  assert.deepEqual(compileStyle({ source: style, filename: filename.pathname, id: `data-v-m115-${name}`, scoped: true }).errors, [])
  const script = compiled.content
    .replace(/import\s+\{([^}]+)\}\s+from ['"]vuetify\/components['"]/g, (_, names) => `const {${names}} = {}`)
    .replace(/import (\w+) from ['"].*?\.vue['"]/g, (_, name) => `const ${name} = {}`)
    .replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
    .replace(/from ['"]([^'"]+\.js)['"]/g, (_, path) => `from '${new URL(path, filename).href}'`)
  return { component: (await import(`data:text/javascript;base64,${Buffer.from(script).toString('base64')}`)).default, source, template }
}
