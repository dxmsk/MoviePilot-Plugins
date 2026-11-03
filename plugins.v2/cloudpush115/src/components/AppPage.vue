<script setup>
import { inject } from 'vue'
import Workbench from './Workbench.vue'

const api = inject('api')
</script>

<template><Workbench :api="api" /></template>
