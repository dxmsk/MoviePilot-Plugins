<script setup>
import { onMounted } from 'vue'
import Workbench from './Workbench.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['layout', 'close'])
onMounted(() => emit('layout', { maxWidth: '86rem' }))
</script>

<template>
  <Workbench :api="api" compact show-close initial-tab="settings" @close="$emit('close')" />
</template>
