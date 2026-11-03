<script setup>
// VAlert/VBtn/VDialog/VProgressLinear are registered by the MoviePilot host.
defineProps({ picker: { type: Object, required: true } })
</script>
<template>
  <VDialog v-model="picker.open" max-width="700" scrollable>
    <section class="m115 m-dialog" aria-label="115目标目录选择">
      <header class="m-header"><div><div class="m-kicker">115 · DESTINATION</div><h2>选择115目标目录</h2></div><VBtn variant="text" @click="picker.open = false">关闭</VBtn></header>
      <p class="m-muted">按层读取真实目录，不自动遍历网盘。进入文件夹后点击“选当前目录”。</p>
      <div class="m-toolbar"><VBtn variant="text" @click="picker.load('0')">115根目录</VBtn><VBtn variant="text" :disabled="picker.loading || !picker.result || String(picker.result.cid) === '0' || picker.result.parent_cid == null" @click="picker.up">返回上级</VBtn></div>
      <VProgressLinear v-if="picker.loading" indeterminate aria-label="读取115当前层" />
      <VAlert v-if="picker.error" type="error" variant="tonal" role="alert">{{ picker.error }}<p>此目录未加载成功，不能选择。可能已删除或 Cookie 失效；可返回根目录重试。</p><VBtn variant="text" @click="picker.load(picker.pendingCid)">重试</VBtn></VAlert>
      <template v-if="picker.result && !picker.loading && !picker.error">
        <p class="m-path m-spacer"><strong>{{ picker.result.path }}</strong></p>
        <ul class="m-list"><li v-for="entry in picker.result.entries" :key="entry.cid" class="m-entry"><button type="button" class="m-entry-action m-grow" @click="picker.load(entry.cid)"><span class="m-name">▸ {{ entry.name }}</span></button><VBtn variant="text" @click="picker.load(entry.cid)">进入</VBtn></li></ul>
        <p v-if="!picker.result.entries.length" class="m-muted m-spacer">当前目录没有子文件夹，仍可选为目标。</p>
        <div class="m-pager"><VBtn variant="text" :disabled="!picker.previousOffsets.length" @click="picker.previousPage">上一页</VBtn><span class="m-muted">第 {{ picker.previousOffsets.length + 1 }} 页</span><VBtn variant="text" :disabled="!picker.result.has_more" @click="picker.nextPage">下一页</VBtn></div>
      </template>
      <VBtn color="primary" class="m-spacer" :disabled="picker.loading || !!picker.error || !picker.result" @click="picker.choose">选当前目录</VBtn>
    </section>
  </VDialog>
</template>
<style scoped src="../styles/panel.css"></style>
