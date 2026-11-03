import test from 'node:test'
import assert from 'node:assert/strict'
import { compileComponent, config, defer, fixture, mount, ok, settle } from './harness.js'
const { component: Workbench, source } = await compileComponent('Workbench')
const props = f => ({ api: f.api, pluginId: 'copy-instance', sourcePluginId: 'source' })

test('actual legacy V2 parent plugin identity works when only api is passed', async t => {
  const f = fixture()
  const { state: { vm } } = mount(t, Workbench, { api: f.api }, false, { __parentPlugin: { id: 'legacy-copy' } })
  await settle()
  assert.equal(vm.loaded, true)
  assert.equal(f.gets[0], 'plugin/legacy-copy/status')
  await vm.local.show()
  assert.equal(f.gets.at(-1), 'plugin/legacy-copy/roots')
})

test('first load works hidden; idle performs no roots/remote/settings calls or polling', async t => {
  const f = fixture(); const { state: { vm }, timers } = mount(t, Workbench, props(f), true); await settle()
  assert.equal(vm.loaded, true); assert.equal(f.gets.length, 1); assert.match(f.gets[0], /^plugin\/copy-instance\/status$/)
  assert.equal(timers.size, 0); assert.deepEqual(vm.local.selected, config().local_paths)
})
test('injected API instance supports pages without explicit api prop', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, { sourcePluginId: 'source' }, false, { 'moviepilot:api': f.api, 'moviepilot:pluginId': 'injected-copy' })
  await settle(); assert.equal(vm.loaded, true); assert.match(f.gets[0], /^plugin\/injected-copy\/status$/)
})
test('empty selections/no Cookie/failed initial status cannot submit', async t => {
  const f = fixture(); f.settings.cookie = ''; const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  await vm.push(); assert.equal(f.posts.length, 0)
  f.settings.cookie = 'test'; await vm.loadStatus(); vm.local.clear(); await vm.push(); assert.equal(f.posts.length, 0)
  vm.local.toggle('/media/x'); f.getOverride = () => Promise.reject(new Error('offline')); await vm.loadStatus(); await vm.push(); assert.equal(f.posts.length, 0)
})
test('double-click lock, request UUID and immutable snapshots preserve later selections', async t => {
  const f = fixture(); const { state: { vm }, timers } = mount(t, Workbench, props(f)); await settle()
  const pending = defer(); f.postOverride = () => pending.promise
  vm.remote.target = { path: '/115/dest', cid: '123' }
  const first = vm.push(); await vm.push(); assert.equal(f.posts.length, 1)
  vm.local.toggle('/media/later'); vm.remote.target = { path: '/new', cid: '456' }
  assert.deepEqual(f.posts[0].body.paths, ['/media/original']); assert.equal(f.posts[0].body.remote_cid, '123'); assert.equal(f.posts[0].body.force, true); assert.equal(f.posts[0].body.preserve_structure, true)
  assert.match(f.posts[0].body.request_id, /^[0-9a-f-]{36}$/)
  f.running = true; pending.resolve(ok({ job_id: 'j', accepted: 1 })); await first; await settle()
  assert.deepEqual(vm.local.selected, ['/media/original', '/media/later']); assert.equal(vm.canPush, false); assert.ok(timers.size)
  await vm.push(); assert.equal(f.posts.length, 1)
})
test('skip unchanged explicitly maps force=false and cancel does not claim completion', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  vm.skipUnchanged = true; vm.preserveStructure = false; await vm.push()
  assert.equal(f.posts[0].body.force, false); assert.equal(f.posts[0].body.preserve_structure, false)
  await vm.cancel(); assert.equal(vm.status.running, true); assert.equal(vm.cancelRequested, true); assert.match(vm.notice, /等待当前文件/)
  await vm.cancel(); assert.equal(f.posts.filter(post => post.url.endsWith('/cancel')).length, 1)
})
test('save selection fetches full config, preserves credentials and later input', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  vm.local.clear(); vm.local.toggle('/media/sent'); vm.remote.target = { path: '/target', cid: null }
  const pending = defer(); f.postOverride = () => pending.promise
  const saving = vm.saveSelection(); await settle(); vm.local.toggle('/media/new')
  assert.deepEqual(f.posts[0].body, { ...config(), local_paths: ['/media/sent'], remote_dir: '/target' })
  pending.resolve(ok({ settings: f.posts[0].body, revision: 2 })); await saving
  assert.deepEqual(vm.local.selected, ['/media/sent', '/media/new'])
})
test('save selection never POSTs after a failed/incomplete settings GET', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  f.getOverride = () => Promise.reject(new Error('offline')); await vm.saveSelection(); assert.equal(f.posts.length, 0)
  f.getOverride = () => Promise.resolve(ok({ settings: { cookie: '' } })); await vm.saveSelection(); assert.equal(f.posts.length, 0)
})
test('running status polls at 2s, pauses hidden and tears down on unmount', async t => {
  const f = fixture(); f.running = true; const { state: { vm }, app, timers, listeners } = mount(t, Workbench, props(f)); await settle()
  assert.equal(timers.size, 1); assert.equal([...timers.values()][0].delay, 2000)
  globalThis.document.hidden = true; listeners.get('visibilitychange')(); assert.equal(timers.size, 0)
  const count = f.gets.length; vm.syncPolling(); assert.equal(f.gets.length, count)
  globalThis.document.hidden = false; listeners.get('visibilitychange')(); await settle(); assert.ok(f.gets.length > count)
  const callbacks = [...timers.values()].map(timer => timer.fn); app.unmount(); assert.equal(timers.size, 0); assert.equal(listeners.size, 0)
  const finalCount = f.gets.length; for (const fn of callbacks) fn(); await settle(); assert.equal(f.gets.length, finalCount)
})
test('stale status cannot overwrite a new status or later selection', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  const a = defer(), b = defer(); let i = 0; f.getOverride = () => (++i === 1 ? a.promise : b.promise)
  const one = vm.loadStatus(), two = vm.loadStatus(); vm.local.toggle('/media/touched')
  b.resolve(ok({ running: false, has_cookie: true, local_paths: ['/new'], remote_dir: '/new', history: [{ name: 'new' }] })); await two
  a.resolve(ok({ running: true, has_cookie: false, local_paths: ['/old'], history: [] })); await one
  assert.equal(vm.status.has_cookie, true); assert.equal(vm.status.history[0].name, 'new'); assert.ok(vm.local.selected.includes('/media/touched'))
})
test('history filtering clamps pages and embedded settings are present', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  vm.status.history = Array.from({ length: 45 }, (_, i) => ({ name: `file-${i}`, path: '/x', status: i ? 'success' : 'failed' }))
  vm.historyPage = 3; assert.equal(vm.pagedHistory.length, 5)
  vm.historyFilter = 'failed'; await settle(); assert.equal(vm.historyPage, 1); assert.equal(vm.pagedHistory.length, 1)
  assert.match(source, /<Config v-if="vm.settingsOpen"/); assert.match(source, /is-embedded/); assert.match(source, /@save="emit\('save'/)
})

test('ambiguous push failure requires status confirmation before retry', async t => {
  const f = fixture(); const { state: { vm } } = mount(t, Workbench, props(f)); await settle()
  f.postOverride = () => Promise.reject(new Error('connection reset')); await vm.push()
  assert.equal(vm.canPush, false); assert.match(vm.error, /刷新确认/); await vm.push(); assert.equal(f.posts.length, 1)
  f.running = true; await vm.loadStatus(); assert.equal(vm.canPush, false)
})
test('embedded Config return closes dialog without reopening external Config', async t => {
  const f = fixture(); const { state, app } = mount(t, Workbench, props(f)); await settle()
  state.vm.settingsOpen = true; state.configSwitch(); assert.equal(state.vm.settingsOpen, false); assert.equal(app.testEvents.switch, undefined)
})
