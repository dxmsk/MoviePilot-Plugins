import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  plugins: [vue(), federation({
    name: 'ManualPush115', filename: 'remoteEntry.js',
    exposes: {
      './Page': './src/components/Page.vue',
      './Config': './src/components/Config.vue',
      './AppPage': './src/components/AppPage.vue',
    },
    shared: {
      vue: { requiredVersion: false, generate: false, singleton: true },
      vuetify: { requiredVersion: false, generate: false, singleton: true },
    },
    format: 'esm',
  })],
  build: { target: 'esnext', minify: false, cssCodeSplit: true },
  // The host registers Vuetify components. No duplicate runtime or global CSS.
})
