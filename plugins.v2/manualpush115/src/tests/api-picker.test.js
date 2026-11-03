import test from 'node:test'
import assert from 'node:assert/strict'
import { createClient, createGeneration, normalizeSettings, resolvePluginId, unwrapResponse } from '../utils/api.js'
import { useLocalPicker } from '../composables/useLocalPicker.js'
import { useRemotePicker } from '../composables/useRemotePicker.js'
import { config, defer, directory, fixture, listing, ok, remoteListing } from './harness.js'
const clientFor = f => createClient(() => ({ api: f.api, props: { pluginId: 'instance-115' } }))

test('normalizes direct/Axios envelopes, rejects unsuccessful or malformed responses', () => {
  assert.deepEqual(unwrapResponse(ok({ value: 1 })), { value: 1 })
  assert.deepEqual(unwrapResponse({ data: ok({ value: 2 }), status: 200 }), { value: 2 })
  assert.throws(() => unwrapResponse({ data: { success: false, message: 'denied' } }), /denied/)
  assert.throws(() => unwrapResponse({ data: { entries: [] } }), /格式/)
  assert.throws(() => normalizeSettings({ cookie: '' }), /不完整/)
  assert.deepEqual(normalizeSettings(config()), config())
})
test('instance props/API/injection take precedence over source ID; never hardcodes ID', async () => {
  assert.equal(resolvePluginId({ pluginId: 'copy', sourcePluginId: 'source' }, { pluginId: 'api' }, 'injected'), 'copy')
  assert.equal(resolvePluginId({ sourcePluginId: 'source' }, { pluginId: 'api-copy' }), 'api-copy')
  assert.equal(resolvePluginId({ sourcePluginId: 'source' }, {}, 'injected'), 'injected')
  const f = fixture(); const client = createClient(() => ({ api: f.api, props: { pluginId: 'copy/2' } }))
  await client.get('search', { path: '/媒体/A&B', query: 'a + b', recursive: false })
  assert.match(f.gets[0], /^plugin\/copy%2F2\/search\?/)
  assert.equal(new URL(f.gets[0], 'https://mock/').searchParams.get('query'), 'a + b')
  await assert.rejects(createClient(() => ({ api: f.api, props: {} })).get('status'), /实例 ID/)
})
test('generation ticket invalidates stale responses', () => { const g = createGeneration(); const a = g.next(), b = g.next(); assert.equal(g.current(a), false); assert.equal(g.current(b), true); g.invalidate(); assert.equal(g.current(b), false) })
test('roots -> child makes one-level requests only; selecting folders never expands', async () => {
  const f = fixture(), p = useLocalPicker(clientFor(f))
  await p.show(); assert.equal(f.gets.length, 1); assert.match(f.gets[0], /\/roots$/)
  p.toggle('/media'); p.toggle('/media/child'); assert.equal(f.gets.length, 1)
  await p.enter('/media'); assert.equal(f.gets.length, 2)
  assert.equal(new URL(f.gets[1], 'https://mock/').searchParams.get('path'), '/media')
  await p.enter('/media/child'); assert.equal(f.gets.length, 3)
  p.selectCurrent(); assert.equal(f.gets.length, 3)
  assert.deepEqual(p.selected.value, ['/media', '/media/child'])
  assert.deepEqual(p.crumbs.value.map(x => x.path), ['/media', '/media/child'])
})
test('empty query sends nothing; typing/recursive checkbox never searches automatically', async () => {
  const f = fixture(), p = useLocalPicker(clientFor(f)); await p.enter('/media')
  await p.search(); assert.equal(f.gets.length, 1)
  p.query.value = 'movie'; p.recursive.value = true; assert.equal(f.gets.length, 1)
  await p.search(); assert.equal(f.gets.length, 2)
  assert.equal(new URL(f.gets.at(-1), 'https://mock/').searchParams.get('recursive'), 'true')
  p.query.value = 'changed draft'; p.recursive.value = false
  await p.page(100)
  const url = new URL(f.gets.at(-1), 'https://mock/')
  assert.equal(url.searchParams.get('query'), 'movie'); assert.equal(url.searchParams.get('recursive'), 'true'); assert.equal(url.searchParams.get('offset'), '100')
})
test('cross-page and cross-layer selections remain removable', async () => {
  const f = fixture(), p = useLocalPicker(clientFor(f)); await p.enter('/media')
  p.toggle('/media/one.mkv'); await p.page(100); p.toggle('/media/two.mkv'); await p.enter('/media/child'); p.selectCurrent()
  assert.deepEqual(p.selected.value, ['/media/one.mkv', '/media/two.mkv', '/media/child'])
  p.remove('/media/one.mkv'); assert.equal(p.selected.value.length, 2)
  await p.locate(directory('/media/child/deep')); assert.equal(p.path.value, '/media/child')
})
test('browse/search share a generation; stale failure/success/finally cannot overwrite latest', async () => {
  const f = fixture(), p = useLocalPicker(clientFor(f)); await p.enter('/media')
  const old = defer(), fresh = defer(); f.getOverride = url => url.includes('/search?') ? old.promise : fresh.promise
  p.query.value = 'a'; const searching = p.search(); const browsing = p.enter('/media/new')
  old.reject(new Error('stale')); await searching
  assert.equal(p.loading.value, true); assert.equal(p.error.value, '')
  fresh.resolve(ok(listing('/media/new'))); await browsing; assert.equal(p.path.value, '/media/new')
  const a = defer(), b = defer(); f.getOverride = url => url.includes('old') ? a.promise : b.promise
  const x = p.enter('/media/old'), y = p.enter('/media/new')
  b.resolve(ok(listing('/media/new'))); await y; a.resolve(ok(listing('/media/old'))); await x
  assert.equal(p.path.value, '/media/new')
})
test('failed directory clears prior contents and cannot select current path', async () => {
  const f = fixture(), p = useLocalPicker(clientFor(f)); await p.enter('/media')
  f.getOverride = () => Promise.reject(new Error('permission denied')); await p.enter('/media/private')
  assert.equal(p.result.value, null); p.selectCurrent(); assert.equal(p.selected.value.length, 0)
  assert.match(p.error.value, /permission/)
})
test('remote is lazy, supports parent CID zero, rejects stale and failed directory choice', async () => {
  const f = fixture(), p = useRemotePicker(clientFor(f)); assert.equal(f.gets.length, 0)
  await p.show(); assert.match(f.gets[0], /cid=0/)
  f.getOverride = () => Promise.resolve(ok(remoteListing('5', '/five', '0'))); await p.load('5')
  await p.up(); assert.match(f.gets.at(-1), /cid=0/)
  const old = defer(), fresh = defer(); f.getOverride = url => url.includes('cid=8') ? old.promise : fresh.promise
  const a = p.load('8'), b = p.load('9'); old.resolve(ok(remoteListing('8', '/eight', '0'))); await a
  assert.equal(p.loading.value, true); assert.equal(p.result.value, null)
  fresh.reject(new Error('deleted')); await b; assert.equal(p.choose(), false); assert.equal(p.result.value, null)
  f.getOverride = () => Promise.resolve(ok(remoteListing('9', '/nine', '0'))); await p.load('9'); assert.equal(p.choose(), true)
  assert.deepEqual(p.target.value, { path: '/nine', cid: '9' }); p.invalidate(); assert.equal(p.target.value.cid, null)
})

test('remote next_offset handles hidden files and previous-page cursor without guessing', async () => {
  const f = fixture(), p = useRemotePicker(clientFor(f))
  f.getOverride = url => { const offset = Number(new URL(url, 'https://mock/').searchParams.get('offset')); return Promise.resolve(ok(remoteListing('0', '/', '0', { offset, has_more: true, next_offset: offset + 300 }))) }
  await p.show(); const count = f.gets.length; await p.up(); assert.equal(f.gets.length, count)
  await p.nextPage(); assert.equal(p.result.value.offset, 300); assert.deepEqual(p.previousOffsets.value, [0])
  await p.nextPage(); assert.equal(p.result.value.offset, 600)
  await p.previousPage(); assert.equal(p.result.value.offset, 300)
  await p.previousPage(); assert.equal(p.result.value.offset, 0)
})
