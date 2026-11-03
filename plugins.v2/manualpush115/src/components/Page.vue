<script setup>
import Workbench from './Workbench.vue'
import { hostProps } from '../composables/useClient.js'
defineProps(hostProps)
defineEmits(['action', 'save', 'switch', 'close'])
</script>
<template><Workbench :api="api" :plugin-id="pluginId" :source-plugin-id="sourcePluginId" :native-subscribe="nativeSubscribe" show-close @action="$emit('action', $event)" @save="$emit('save', $event)" @switch="$emit('switch', $event)" @close="$emit('close', $event)" /></template>
