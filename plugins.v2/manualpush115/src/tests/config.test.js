import test from 'node:test'
import assert from 'node:assert/strict'
import { compileComponent, config, defer, fixture, mount, ok, settle } from './harness.js'
const { component: Config, source } = await compileComponent('Config')

test('initial loading or failed GET cannot save an empty configuration', async t => {
  const f = fixture(), pending = defer(); f.getOverride = () => pending.promise
  const { state: { form } } = mount(t, Config, { api: f.api, pluginId: 'copy', isEmbedded: true })
  assert.equal(form.canSave, false); await form.save(); assert.equal(f.posts.length, 0)
  pending.reject(new Error('offline')); await settle()
  assert.equal(form.loaded, false); assert.equal(form.canSave, false); await form.save(); assert.equal(f.posts.length, 0)
  assert.match(form.error, /offline/)
})
test('standalone Config honors complete initialConfig and emits full save/switch/close', async t => {
  const f = fixture(); const { state, app } = mount(t, Config, { api: f.api, pluginId: 'copy', initialConfig: config() })
  await settle(); assert.equal(f.gets.length, 0)
  state.form.draft.user_agent = 'new agent'; await state.form.save()
  const saved = app.testEvents.save[0][0]
  assert.deepEqual(Object.keys(saved).sort(), Object.keys(config()).sort())
  assert.equal(saved.cookie, config().cookie); assert.equal(saved.user_agent, 'new agent'); assert.equal(f.posts.length, 0)
  state.requestLeave('switch'); assert.equal(state.leaveKind, 'switch'); state.confirmLeave(); assert.ok(app.testEvents.switch)
  state.requestLeave('close'); assert.ok(app.testEvents.close)
})
test('partial initialConfig must fetch full settings and never replaces them with defaults', async t => {
  const f = fixture(); const { state: { form } } = mount(t, Config, { api: f.api, pluginId: 'copy', initialConfig: { cookie: 'partial' } })
  await settle(); assert.deepEqual(form.draft, config()); assert.equal(form.loaded, true)
})
test('embedded Config saves all fields while preserving edits made in flight', async t => {
  const f = fixture(); const { state: { form }, app } = mount(t, Config, { api: f.api, pluginId: 'copy', isEmbedded: true }); await settle()
  form.draft.remote_dir = '/sent'; const pending = defer(); f.postOverride = () => pending.promise
  const saving = form.save(); assert.equal(form.saving, true)
  form.draft.remote_dir = '/typed-after-submit'; form.draft.cookie = 'new-unsaved-test-cookie'
  pending.resolve(ok({ settings: f.posts[0].body, revision: 2 })); await saving
  assert.equal(form.draft.remote_dir, '/typed-after-submit'); assert.equal(form.draft.cookie, 'new-unsaved-test-cookie'); assert.equal(form.dirty, true)
  assert.equal(form.saved.remote_dir, '/sent'); assert.equal(f.posts[0].body.cookie, config().cookie); assert.ok(app.testEvents.save); assert.ok(app.testEvents.saved)
})
test('failed refresh disables save but retains every unsaved field', async t => {
  const f = fixture(); const { state: { form } } = mount(t, Config, { api: f.api, pluginId: 'copy', isEmbedded: true }); await settle()
  form.draft.extensions = 'txt'; f.getOverride = () => Promise.reject(new Error('offline'))
  await form.load(); assert.equal(form.canSave, false); assert.equal(form.draft.extensions, 'txt')
  await form.save(); assert.equal(f.posts.length, 0)
  f.getOverride = null; await form.load(); assert.equal(form.canSave, true); assert.equal(form.draft.extensions, 'txt')
})
test('test uses saved server config; dirty Cookie never sent', async t => {
  const f = fixture(); const { state: { form } } = mount(t, Config, { api: f.api, pluginId: 'copy', isEmbedded: true }); await settle()
  form.draft.cookie = 'do-not-send'; await form.testSaved()
  assert.deepEqual(f.posts[0].body, {}); assert.match(f.posts[0].url, /\/test$/)
  assert.equal(f.gets.some(url => url.includes('/remote')), false)
})
test('dirty dismiss prompts before discard and paths remain a complete array', async t => {
  const f = fixture(); const { state, app } = mount(t, Config, { api: f.api, pluginId: 'copy', isEmbedded: true }); await settle()
  state.pathsText = '/a\n/b\n/a\n'; assert.deepEqual(state.form.draft.local_paths, ['/a', '/b'])
  state.requestLeave('close'); assert.equal(app.testEvents?.close, undefined); assert.equal(state.leaveKind, 'close')
  state.leaveKind = ''; assert.deepEqual(state.form.draft.local_paths, ['/a', '/b'])
  state.requestLeave('close'); state.confirmLeave(); assert.ok(app.testEvents.close)
  assert.match(source, /initialConfig/); assert.match(source, /\['save', 'saved', 'switch', 'close'\]/)
})

test('multi-line path input preserves trailing newline and subsequent typing', async t => {
  const f = fixture(); const { state } = mount(t, Config, { api: f.api, pluginId: 'copy', isEmbedded: true }); await settle()
  state.pathsText = '/one\n'; await settle(); assert.equal(state.pathsText, '/one\n')
  state.pathsText += '/two'; await settle(); assert.deepEqual(state.form.draft.local_paths, ['/one', '/two'])
})
