<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
// VAlert/VBtn/VDialog/VProgressLinear are registered by the MoviePilot host.
import { hostProps, useClient } from '../composables/useClient.js'
import { useSettings } from '../composables/useSettings.js'

const props = defineProps({ ...hostProps, initialConfig: { type: Object, default: () => ({}) }, isEmbedded: { type: Boolean, default: false } })
const emit = defineEmits(['save', 'saved', 'switch', 'close'])
const form = reactive(useSettings(useClient(props), props.initialConfig, props.isEmbedded, emit))
const showCookie = ref(false), leaveKind = ref('')
const rawPaths = ref(form.draft.local_paths.join('\n'))
const parsePaths = text => [...new Set(text.split('\n').map(path => path.trim()).filter(Boolean))]
const pathsText = computed({ get: () => rawPaths.value, set: value => { rawPaths.value = value; form.draft.local_paths = parsePaths(value) } })
watch(() => form.draft.local_paths, paths => { if (JSON.stringify(parsePaths(rawPaths.value)) !== JSON.stringify(paths)) rawPaths.value = paths.join('\n') }, { deep: true, flush: 'sync' })
watch(() => props.initialConfig, config => { form.seed(config) }, { deep: true })
function requestLeave(kind) { if (form.saving || form.testing) return; if (form.dirty) leaveKind.value = kind; else emit(kind) }
function confirmLeave() { const kind = leaveKind.value; leaveKind.value = ''; form.discard(); emit(kind) }
function beforeUnload(event) { if (form.dirty || form.saving) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => { if (props.isEmbedded || !form.loaded) form.load(); if (typeof window !== 'undefined') window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => { form.dispose(); if (typeof window !== 'undefined') window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <section class="m115 m-page" aria-label="手动秒传115配置">
    <header class="m-header"><div><div class="m-kicker">MANUAL PUSH · SETTINGS</div><h1>连接与默认配置</h1><p class="m-muted">完整保留原配置。选择本地文件与秒传操作均在首页完成。</p></div><VBtn variant="text" :disabled="form.saving || form.testing" @click="requestLeave('close')">关闭</VBtn></header>
    <div class="m-stack">
      <VAlert v-if="form.error" type="error" variant="tonal" role="alert">{{ form.error }}<VBtn v-if="!form.loaded" variant="text" :disabled="form.loading" @click="form.load">重新加载配置</VBtn></VAlert>
      <VAlert v-if="form.notice" type="info" variant="tonal" role="status">{{ form.notice }}</VAlert>
      <VProgressLinear v-if="form.loading" indeterminate aria-label="加载完整配置" />
      <VAlert v-if="!form.loaded" type="warning" variant="tonal">配置尚未成功载入，禁止保存，避免用空值覆盖 Cookie 等原配置。</VAlert>
      <fieldset :disabled="!form.loaded || form.loading" class="m-stack">
        <div class="m-card m-stack">
          <div><label for="m115-cookie" class="m-label">115 Cookie</label><input id="m115-cookie" v-model="form.draft.cookie" class="m-input" :type="showCookie ? 'text' : 'password'" autocomplete="off" spellcheck="false" placeholder="填入115登录 Cookie"><label class="m-check"><input v-model="showCookie" type="checkbox">显示 Cookie（请勿截图分享）</label><p class="m-muted">仅配置接口加载 Cookie，首页状态与历史不显示密钥。留空保存将清除 Cookie。</p></div>
          <div><label for="m115-ua" class="m-label">User-Agent</label><textarea id="m115-ua" v-model="form.draft.user_agent" class="m-input" rows="2" spellcheck="false" placeholder="可选，与取得 Cookie 的客户端一致" /></div>
          <div><label for="m115-ext" class="m-label">文件扩展名过滤</label><input id="m115-ext" v-model="form.draft.extensions" class="m-input" placeholder="例如 mkv,mp4；留空使用默认媒体扩展名"><p class="m-muted">留空使用默认媒体扩展列表；填 * 包含所有文件。保留原过滤规则；目录由后台收集，不在首页递归统计。</p></div>
        </div>
        <div class="m-card m-stack">
          <div><label for="m115-default-remote" class="m-label">默认115目标目录</label><input id="m115-default-remote" v-model="form.draft.remote_dir" class="m-input" placeholder="/"><p class="m-muted">可保留或编辑原路径；首页可逐层选择真实115目录，无需手填。</p></div>
          <div><label for="m115-default-paths" class="m-label">默认本地路径（每行一项）</label><textarea id="m115-default-paths" v-model="pathsText" class="m-input" rows="3" spellcheck="false" /><p class="m-muted">兼容保留已有配置；推荐在首页选择文件／文件夹后点击“保存为默认”。</p></div>
        </div>
        <div class="m-card m-stack">
          <div><label class="m-check"><input v-model="form.draft.failure_move_enabled" type="checkbox">本次文件失败后移动至指定目录</label><p class="m-muted">默认关闭。包括网络或登录错误（远端结果可能未知）；文件签名变化或归档异常时保留源文件。</p></div>
          <div v-if="form.draft.failure_move_enabled"><label for="m115-failure-dir" class="m-label">失败文件目录</label><input id="m115-failure-dir" v-model="form.draft.failure_move_dir" class="m-input" placeholder="/media/failed"><p class="m-muted">填写绝对路径；可使用相邻目录。开启后本次收集会排除失败目录内文件。</p><label class="m-check"><input v-model="form.draft.failure_move_preserve_structure" type="checkbox">保留原目录结构</label></div>
          <div><label class="m-check"><input v-model="form.draft.delete_on_success" type="checkbox">秒传明确成功后删除原文件</label><p class="m-muted">默认关闭。删除前会重新校验文件签名，文件变化时保留原文件。</p></div>
        </div>
      </fieldset>
      <div class="m-row"><VBtn color="primary" :loading="form.saving" :disabled="!form.canSave" @click="form.save">{{ isEmbedded ? '保存配置' : '保存至宿主' }}</VBtn><VBtn variant="tonal" :loading="form.testing" :disabled="!form.loaded || form.saving" @click="form.testSaved">测试已保存配置</VBtn><VBtn variant="text" :disabled="form.saving || form.testing" @click="requestLeave('switch')">返回秒传首页</VBtn><span class="m-muted">{{ form.dirty ? '有未保存更改' : '无未保存更改' }}</span></div>
      <p class="m-muted">连接测试只使用服务端已保存的 Cookie，不会提交当前未保存的输入。保存配置不会启动任务或创建调度。</p>
    </div>
    <VDialog :model-value="!!leaveKind" persistent max-width="460">
      <section class="m115 m-dialog"><h2>保留未保存的输入？</h2><p>离开会丢弃尚未保存的配置。</p><div class="m-row m-spacer"><VBtn color="primary" @click="leaveKind = ''">继续编辑</VBtn><VBtn variant="text" @click="confirmLeave">丢弃并离开</VBtn></div></section>
    </VDialog>
  </section>
</template>
<style scoped src="../styles/panel.css"></style>
