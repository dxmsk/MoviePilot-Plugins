<script setup>
import Workbench from './Workbench.vue'
import Config from './Config.vue'
import { hostProps } from '../composables/useClient.js'
defineProps({ ...hostProps, navKey: { type: String, default: 'main' }, initialConfig: { type: Object, default: () => ({}) } })
defineEmits(['action', 'save', 'switch', 'close'])
</script>
<template>
  <Config v-if="navKey === 'settings'" :api="api" :plugin-id="pluginId" :source-plugin-id="sourcePluginId" :initial-config="initialConfig" is-embedded @save="$emit('save', $event)" @switch="$emit('switch', $event)" @close="$emit('close', $event)" />
  <Workbench v-else :api="api" :plugin-id="pluginId" :source-plugin-id="sourcePluginId" :native-subscribe="nativeSubscribe" @action="$emit('action', $event)" @save="$emit('save', $event)" @switch="$emit('switch', $event)" @close="$emit('close', $event)" />
</template>
