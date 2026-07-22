<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import ImageGenerationForm from './components/ImageGenerationForm.vue'
import GenerationForm from './components/GenerationForm.vue'
import MultiShotEditor from './components/MultiShotEditor.vue'
import HistoryGallery from './components/HistoryGallery.vue'
import t2vWorkflow from './workflows/t2v.api.json'
import t2vLightx2vWorkflow from './workflows/t2v_lightx2v.api.json'
import i2vWorkflow from './workflows/i2v.api.json'
import ltx23T2vWorkflow from './workflows/ltx23_t2v.api.json'
import ltx23I2vWorkflow from './workflows/ltx23_i2v.api.json'
import flf2vWorkflow from './workflows/flf2v.api.json'
import { loadHistory, saveHistory, loadActiveJob, appendHistoryRecord, mergeImportedVideos } from './composables/useJobPersistence.js'
import { listRecentVideos } from './services/api.js'

const tab = ref('wan-t2v-5s')
const history = ref(loadHistory())
const online = ref(null)
const qwenOnline = ref(null)
const importingHistory = ref(false)
const importStatus = ref('')

function resolveTabFromJobMode(m) {
  if (!m) return null
  if (m.startsWith('qwen-t2i')) return 'qwen-t2i'
  if (m.endsWith('-5s')) {
    if (m.startsWith('ltx-t2v')) return 'ltx-t2v-5s'
    if (m.startsWith('ltx-i2v')) return 'ltx-i2v-5s'
    if (m.startsWith('wan-flf2v')) return 'wan-flf2v-5s'
    if (m.startsWith('wan-t2v')) return 'wan-t2v-5s'
    if (m.startsWith('wan-i2v')) return 'wan-i2v-5s'
  }
  if (m.includes('multishot')) {
    if (m.includes('ltx') && m.includes('i2v')) return 'ltx-i2v-6'
    if (m.includes('ltx')) return 'ltx-t2v-6'
    if (m.includes('wan') && m.includes('i2v')) return 'wan-i2v-6'
    if (m.includes('wan')) return 'wan-t2v-6'
  }
  if (m.includes('ltx') && m.includes('i2v')) return 'ltx-i2v-6'
  if (m.includes('ltx')) return 'ltx-t2v-6'
  if (m.includes('wan') && m.includes('i2v')) return 'wan-i2v-6'
  if (m.includes('wan')) return 'wan-t2v-6'
  return null
}

const pending = loadActiveJob()
const restoredTab = resolveTabFromJobMode(pending?.mode)
if (restoredTab) tab.value = restoredTab

function onDone(record) {
  history.value = appendHistoryRecord(record, history.value)
  saveHistory(history.value)
}

function clearHistory() {
  history.value = []
  saveHistory([])
}

async function importFromComfyUI(limit = 100, { silent = false } = {}) {
  importingHistory.value = true
  if (!silent) importStatus.value = ''
  try {
    const data = await listRecentVideos({ limit })
    const before = new Set(history.value.map((item) => item.filename))
    history.value = saveHistory(mergeImportedVideos(data.videos, history.value))
    const added = history.value.filter((item) => !before.has(item.filename)).length
    if (!silent || added > 0) {
      importStatus.value = `扫描 ${data.totalFiles ?? data.returned ?? 0} 个文件，新增 ${added} 条，当前共 ${history.value.length} 条`
    }
  } catch (e) {
    const msg = e?.message || '导入失败'
    importStatus.value = e?.status === 404
      ? `${msg}（请重启后端：cd backend && python main.py）`
      : msg
  } finally {
    importingHistory.value = false
  }
}

async function checkConnection() {
  try {
    const res = await fetch('/health')
    const data = res.ok ? await res.json() : null
    online.value = !!(data && data.ok)
    qwenOnline.value = data?.qwenImage?.ok === true ? true : data?.qwenImage ? false : null
    if (online.value) {
      // 延迟导入，避免与任务轮询抢占浏览器到后端的连接（HTTP/1.1 每域约 6 条）
      const pending = loadActiveJob()
      const delayMs = pending?.taskId ? 8000 : 2000
      setTimeout(() => importFromComfyUI(100, { silent: true }), delayMs)
    }
  } catch {
    online.value = false
  }
}

onMounted(() => {
  checkConnection()
})

const qwenHealthTimer = setInterval(() => {
  if (qwenOnline.value !== true) checkConnection()
}, 10000)

onBeforeUnmount(() => clearInterval(qwenHealthTimer))
</script>

<template>
  <div>
    <header class="app-header">
      <div>
        <h1>AI 视频 / 图像生成</h1>
        <div class="subtitle">Wan 2.2 视频 · LTX 2.3 · Qwen-Image-2512 文生图 · 本地 ComfyUI / diffusers</div>
      </div>
      <div class="badge">
        <span class="dot" :class="{ ok: online === true, err: online === false }"></span>
        <span v-if="online === true">后端已连接</span>
        <span v-else-if="online === false">未连接到后端</span>
        <span v-else>检测中…</span>
      </div>
    </header>

    <div class="tab-groups">
      <div class="tab-group">
        <span class="tab-group-label">Wan 2.2</span>
        <div class="tabs">
          <button class="tab" :class="{ active: tab === 'wan-t2v-5s' }" @click="tab = 'wan-t2v-5s'">T2V 5s</button>
          <button class="tab" :class="{ active: tab === 'wan-i2v-5s' }" @click="tab = 'wan-i2v-5s'">I2V 5s</button>
          <button class="tab" :class="{ active: tab === 'wan-flf2v-5s' }" @click="tab = 'wan-flf2v-5s'">首尾帧 5s</button>
          <button class="tab" :class="{ active: tab === 'wan-t2v-6' }" @click="tab = 'wan-t2v-6'">T2V 多分镜</button>
          <button class="tab" :class="{ active: tab === 'wan-i2v-6' }" @click="tab = 'wan-i2v-6'">I2V 多分镜</button>
        </div>
      </div>
      <div class="tab-group">
        <span class="tab-group-label">Qwen-Image</span>
        <div class="tabs">
          <button class="tab" :class="{ active: tab === 'qwen-t2i' }" @click="tab = 'qwen-t2i'">文生图 T2I</button>
        </div>
        <span v-if="qwenOnline === false" class="service-hint">推理服务未就绪（需单独启动，且与 ComfyUI 不宜同卡满载）</span>
      </div>
      <div class="tab-group">
        <span class="tab-group-label">LTX 2.3</span>
        <div class="tabs">
          <button class="tab" :class="{ active: tab === 'ltx-t2v-5s' }" @click="tab = 'ltx-t2v-5s'">T2V 5s</button>
          <button class="tab" :class="{ active: tab === 'ltx-i2v-5s' }" @click="tab = 'ltx-i2v-5s'">I2V 5s</button>
          <button class="tab" :class="{ active: tab === 'ltx-t2v-6' }" @click="tab = 'ltx-t2v-6'">T2V 多分镜</button>
          <button class="tab" :class="{ active: tab === 'ltx-i2v-6' }" @click="tab = 'ltx-i2v-6'">I2V 多分镜</button>
        </div>
      </div>
    </div>

    <ImageGenerationForm v-if="tab === 'qwen-t2i'" @done="onDone" />

    <GenerationForm
      v-if="tab === 'wan-t2v-5s'"
      engine="wan"
      mode="t2v"
      simple
      :base-graph="t2vWorkflow"
      :lightx2v-graph="t2vLightx2vWorkflow"
      @done="onDone"
    />
    <GenerationForm
      v-if="tab === 'wan-i2v-5s'"
      engine="wan"
      mode="i2v"
      simple
      :base-graph="i2vWorkflow"
      @done="onDone"
    />
    <GenerationForm
      v-if="tab === 'wan-flf2v-5s'"
      engine="wan"
      mode="flf2v"
      simple
      :base-graph="flf2vWorkflow"
      @done="onDone"
    />
    <GenerationForm
      v-if="tab === 'ltx-t2v-5s'"
      engine="ltx"
      mode="t2v"
      simple
      :base-graph="ltx23T2vWorkflow"
      @done="onDone"
    />
    <GenerationForm
      v-if="tab === 'ltx-i2v-5s'"
      engine="ltx"
      mode="i2v"
      simple
      :base-graph="ltx23I2vWorkflow"
      @done="onDone"
    />

    <MultiShotEditor v-if="tab === 'wan-t2v-6'" engine="wan" mode="t2v" @done="onDone" />
    <MultiShotEditor v-if="tab === 'wan-i2v-6'" engine="wan" mode="i2v" @done="onDone" />
    <MultiShotEditor v-if="tab === 'ltx-t2v-6'" engine="ltx" mode="t2v" @done="onDone" />
    <MultiShotEditor v-if="tab === 'ltx-i2v-6'" engine="ltx" mode="i2v" @done="onDone" />

    <div style="margin-top: 24px">
      <HistoryGallery
        :items="history"
        :importing="importingHistory"
        :import-status="importStatus"
        @clear="clearHistory"
        @import="importFromComfyUI"
      />
    </div>
  </div>
</template>

<style scoped>
.tab-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 32px;
  margin-bottom: 16px;
  align-items: flex-end;
}
.tab-group-label {
  display: block;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted, #888);
  margin-bottom: 6px;
}
.tab-group .tabs {
  margin-bottom: 0;
}
.service-hint {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: #ffc070;
  max-width: 280px;
  line-height: 1.35;
}
</style>
