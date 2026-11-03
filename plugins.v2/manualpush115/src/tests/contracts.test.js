import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { compileComponent } from './harness.js'
for (const name of ['Page', 'AppPage', 'Config', 'Workbench', 'LocalPicker', 'RemotePicker']) {
  test(`${name} template/style compiles; host props and events remain intact`, async () => {
    const { source } = await compileComponent(name)
    assert.doesNotMatch(source, /v-html|vuetify\/styles|@mdi\/font/)
    if (['Page', 'AppPage'].includes(name)) {
      assert.match(source, /:plugin-id="pluginId"/); assert.match(source, /:source-plugin-id="sourcePluginId"/)
      for (const event of ['save', 'switch', 'close']) assert.ok(source.includes(`@${event}="$emit('${event}'`))
    }
    if (name === 'LocalPicker') assert.match(source, /@change="picker.toggle\(entry.path\)"/)
  })
}
test('build declares all remotes with no global styles shared/imported or selector filtering', async () => {
  const vite = await readFile(new URL('../../vite.config.js', import.meta.url), 'utf8')
  for (const name of ['Page', 'Config', 'AppPage']) assert.ok(vite.includes(`'./${name}'`))
  assert.doesNotMatch(vite, /vuetify\/styles|walkRules|selector\.includes/)
  assert.match(vite, /generate: false/)
})
