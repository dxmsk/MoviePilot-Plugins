<script setup>
// VAlert/VBtn/VDialog/VProgressLinear are registered by the MoviePilot host.
import { sizeText } from '../utils/api.js'
defineProps({ picker: { type: Object, required: true } })
</script>
<template>
  <VDialog v-model="picker.open" max-width="820" scrollable>
    <section class="m115 m-dialog" aria-label="本地逐层目录选择">
      <header class="m-header"><div><div class="m-kicker">LOCAL · MP MOUNTS</div><h2>选择本地文件与文件夹</h2></div><VBtn variant="text" @click="picker.open = false">完成（{{ picker.selected.length }}）</VBtn></header>
      <p class="m-muted">只显示 MoviePilot Docker 挂载根目录。点击目录名称进入一层；勾选不会展开目录。</p>
      <nav class="m-breadcrumbs" aria-label="本地目录面包屑"><button type="button" @click="picker.showRoots">挂载根目录</button><button v-for="crumb in picker.crumbs" :key="crumb.path" type="button" @click="picker.enter(crumb.path)">{{ crumb.name }}</button></nav>
      <div v-if="picker.path" class="m-toolbar"><VBtn variant="text" :disabled="picker.loading || !picker.result" @click="picker.up">返回上级</VBtn><VBtn color="primary" variant="tonal" :disabled="picker.loading || !!picker.error || !picker.result" @click="picker.selectCurrent">选当前文件夹</VBtn><span class="m-path m-muted">{{ picker.path }}</span></div>
      <form v-if="picker.path" class="m-card m-spacer" @submit.prevent="picker.search">
        <label for="m115-search" class="m-label">本地文件搜索</label>
        <div class="m-row"><input id="m115-search" v-model="picker.query" class="m-input m-grow" placeholder="文件或文件夹名称（非正则）" type="search"><VBtn type="submit" color="primary" :disabled="picker.loading || !picker.query.trim()">搜索</VBtn></div>
        <label class="m-check"><input v-model="picker.recursive" type="checkbox">包括子目录</label>
        <p class="m-muted">默认只搜当前层。输入文字或勾选不发请求，仅点击“搜索”或按回车执行；包含子目录可能耗时。</p>
        <VBtn v-if="picker.mode === 'search'" variant="text" @click="picker.enter(picker.path)">退出搜索，浏览当前目录</VBtn>
      </form>
      <VProgressLinear v-if="picker.loading" class="m-spacer" indeterminate aria-label="读取本地当前层" />
      <VAlert v-if="picker.error" class="m-spacer" type="error" variant="tonal" role="alert">{{ picker.error }}<VBtn variant="text" :disabled="picker.loading" @click="picker.retry">重试当前请求</VBtn></VAlert>
      <VAlert v-for="warning in picker.warnings" :key="warning" class="m-spacer" type="warning" variant="tonal">{{ warning }}</VAlert>
      <template v-if="!picker.loading && !picker.error">
        <ul v-if="picker.mode === 'roots'" class="m-list">
          <li v-for="root in picker.roots" :key="root.path" class="m-entry">
            <label class="m-check"><input type="checkbox" :checked="picker.selected.includes(root.path)" :aria-label="`选择目录 ${root.path}`" @change="picker.toggle(root.path)"></label>
            <div class="m-grow"><button type="button" class="m-entry-action" @click="picker.enter(root.path)"><strong class="m-name">▸ {{ root.name || root.path }}</strong><div class="m-muted m-path">{{ root.path }}</div></button></div>
            <VBtn variant="text" @click="picker.enter(root.path)">进入</VBtn>
          </li>
          <li v-if="!picker.roots.length" class="m-muted m-spacer">没有可用的 MP Docker 挂载根目录，请检查挂载设置。</li>
        </ul>
        <template v-else-if="picker.result">
          <p v-if="picker.mode === 'search'" class="m-muted m-spacer">搜索结果 · {{ picker.searchSpec?.recursive ? '包括子目录' : '仅当前层' }} · 已扫描 {{ picker.result.scanned ?? '—' }} 项 {{ picker.result.message || '' }}</p>
          <VAlert v-if="picker.result.truncated" type="warning" variant="tonal" class="m-spacer">搜索／列表已达服务端上限，结果可能不完整。请缩小目录或关键词。</VAlert>
          <ul class="m-list">
            <li v-for="entry in picker.result.entries" :key="entry.path" class="m-entry">
              <label class="m-check"><input type="checkbox" :checked="picker.selected.includes(entry.path)" :disabled="entry.selectable === false" :aria-label="`选择 ${entry.path}`" @change="picker.toggle(entry.path)"></label>
              <div class="m-grow"><button v-if="entry.is_dir" type="button" class="m-entry-action" @click="picker.enter(entry.path)"><strong class="m-name">▸ {{ entry.name }}</strong></button><strong v-else class="m-name">{{ entry.name }}</strong><div class="m-muted m-path">{{ picker.mode === 'search' ? entry.path : entry.is_dir ? '文件夹' : sizeText(entry.size) }}{{ entry.selectable === false ? ' · 不可选择' : '' }}</div></div>
              <VBtn v-if="picker.mode === 'search'" variant="text" @click="picker.locate(entry)">定位</VBtn><VBtn v-else-if="entry.is_dir" variant="text" @click="picker.enter(entry.path)">进入</VBtn>
            </li>
          </ul>
          <p v-if="!picker.result.entries.length" class="m-muted m-spacer">{{ picker.mode === 'search' ? '未找到匹配项，试试其他关键词或包括子目录。' : '此目录为空。' }}</p>
          <div class="m-pager"><VBtn variant="text" :disabled="!picker.result.offset" @click="picker.page(picker.result.offset - 100)">上一页</VBtn><span class="m-muted">第 {{ Math.floor((picker.result.offset || 0) / 100) + 1 }} 页 · {{ picker.result.total ?? '—' }} 项</span><VBtn variant="text" :disabled="!picker.result.has_more" @click="picker.page(picker.result.offset + 100)">下一页</VBtn></div>
        </template>
      </template>
      <p class="m-muted m-spacer">已选 {{ picker.selected.length }} 个路径，跨层与翻页保留；可回首页移除。</p>
    </section>
  </VDialog>
</template>
<style scoped src="../styles/panel.css"></style>
