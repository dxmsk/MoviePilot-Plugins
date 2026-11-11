import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeSettings } from '../utils/api.js'
import { config, fixture, mount, compileComponent, settle } from './harness.js'

test('old five-field config migrates with disabled destructive actions', () => {
  const old = { cookie: 'fixture', user_agent: '', extensions: '', local_paths: [], remote_dir: '/' }
  const migrated = normalizeSettings(old)
  assert.equal(migrated.delete_on_success, false)
  assert.equal(migrated.failure_move_enabled, false)
  assert.equal(migrated.failure_move_dir, '')
  assert.equal(migrated.failure_move_preserve_structure, true)
  assert.throws(() => normalizeSettings({ ...old, delete_on_success: 'false' }))
})

test('embedded settings persist all file policy choices', async t => {
  const { component: Config } = await compileComponent('Config')
  const f = fixture()
  const view = mount(t, Config, { api: f.api, pluginId: 'instance', initialConfig: config(), isEmbedded: true })
  await settle()
  Object.assign(view.state.form.draft, { failure_move_enabled: true, failure_move_dir: '/media-failed', delete_on_success: true, failure_move_preserve_structure: false })
  await view.state.form.save()
  const body = f.posts.at(-1).body
  assert.equal(body.failure_move_enabled, true)
  assert.equal(body.delete_on_success, true)
  assert.equal(body.failure_move_dir, '/media-failed')
  assert.equal(body.failure_move_preserve_structure, false)
})
