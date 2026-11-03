<script setup>
import Workbench from './Workbench.vue'

defineProps({ api: { type: Object, default: () => ({}) } })
defineEmits(['action', 'close'])
</script>

<template>
  <Workbench :api="api" compact show-close @action="$emit('action')" @close="$emit('close')" />
</template>
