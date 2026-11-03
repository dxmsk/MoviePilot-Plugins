import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
const assets = new URL('../../dist/assets/', import.meta.url)
const files = await readdir(assets)
assert.ok(files.includes('remoteEntry.js'))
assert.ok(files.some(name => name.startsWith('__federation_expose_Page-')))
assert.ok(files.some(name => name.startsWith('__federation_expose_Config-')))
assert.ok(files.some(name => name.startsWith('__federation_expose_AppPage-')))
assert.ok(!files.some(name => /__federation_shared_vuetify|^theme-/.test(name)), 'must not ship a duplicate Vuetify runtime/style chunk')
for (const name of files) {
  const source = await readFile(new URL(name, assets), 'utf8')
  if (name.endsWith('.css')) assert.doesNotMatch(source, /^\s*(?:\.v-|\.mdi-|html\b|body\b|:root\b)/m, `${name}: global CSS selector`)
  if (name.endsWith('.js')) assert.doesNotMatch(source, /function createVuetify\b|Symbol\.for\(['"]vuetify:/, `${name}: bundled Vuetify runtime`)
}
console.log('Build contract OK: Page/Config/AppPage; no global CSS or duplicate Vuetify runtime')
