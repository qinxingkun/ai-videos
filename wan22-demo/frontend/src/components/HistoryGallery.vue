<script setup>
import { computed, ref, watch, onBeforeUnmount, nextTick } from 'vue'
import { HISTORY_MAX_VIDEOS } from '../composables/useJobPersistence.js'

const PAGE_SIZE = 12
const DEFAULT_IMPORT_LIMIT = 100

const props = defineProps({
  items: { type: Array, default: () => [] },
  importing: { type: Boolean, default: false },
  importStatus: { type: String, default: '' }
})
const emit = defineEmits(['clear', 'import'])

const importLimit = ref(DEFAULT_IMPORT_LIMIT)

function triggerImport() {
  const limit = Math.min(HISTORY_MAX_VIDEOS, Math.max(1, Number(importLimit.value) || DEFAULT_IMPORT_LIMIT))
  importLimit.value = limit
  emit('import', limit)
}

const visibleCount = ref(PAGE_SIZE)
const loadedSrc = ref({})
const MAX_CONCURRENT_VIDEO_LOADS = 2
let observer = null
let videoLoadsInFlight = 0
const videoLoadQueue = []

function flushVideoLoadQueue() {
  while (videoLoadsInFlight < MAX_CONCURRENT_VIDEO_LOADS && videoLoadQueue.length) {
    const item = videoLoadQueue.shift()
    const key = itemKey(item)
    if (loadedSrc.value[key] || !item.url) continue
    videoLoadsInFlight += 1
    loadedSrc.value = { ...loadedSrc.value, [key]: item.url }
  }
}

function enqueueVideoLoad(item) {
  const key = itemKey(item)
  if (loadedSrc.value[key] || !item.url) return
  if (videoLoadQueue.some((row) => itemKey(row) === key)) return
  videoLoadQueue.push(item)
  flushVideoLoadQueue()
}

function onVideoLoadDone() {
  videoLoadsInFlight = Math.max(0, videoLoadsInFlight - 1)
  flushVideoLoadQueue()
}

const sortedItems = computed(() => {
  const list = Array.isArray(props.items) ? props.items : []
  return [...list].sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
})

const visibleItems = computed(() => sortedItems.value.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < sortedItems.value.length)

function isVideo(item) {
  return item?.kind === 'video' || /\.(mp4|webm|mov|mkv)$/i.test(item?.filename || '')
}

function itemKey(item) {
  return item.id || `${item.filename}-${item.createdAt}`
}

function videoSrc(item) {
  return loadedSrc.value[itemKey(item)] || ''
}

function loadVideo(item) {
  enqueueVideoLoad(item)
}

function observeVideos() {
  if (typeof IntersectionObserver === 'undefined') return
  observer?.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const id = entry.target.dataset.historyId
        const item = visibleItems.value.find((row) => itemKey(row) === id)
        if (item) enqueueVideoLoad(item)
      }
    },
    { rootMargin: '80px' }
  )
  document.querySelectorAll('[data-history-id]').forEach((el) => observer?.observe(el))
}

function showMore() {
  visibleCount.value = Math.min(visibleCount.value + PAGE_SIZE, sortedItems.value.length)
}

watch(visibleItems, async () => {
  await nextTick()
  observeVideos()
}, { immediate: true })

watch(sortedItems, () => {
  visibleCount.value = PAGE_SIZE
  loadedSrc.value = {}
  videoLoadQueue.length = 0
  videoLoadsInFlight = 0
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})
</script>

<template>
  <div class="panel">
    <div class="section-title">
      <div class="title-row">
        <h3>历史记录</h3>
        <span v-if="sortedItems.length" class="count-hint">
          共 {{ sortedItems.length }} 条 · 按时间倒序 · 最多保留 {{ HISTORY_MAX_VIDEOS }} 条
        </span>
        <span v-if="importStatus" class="import-status">{{ importStatus }}</span>
      </div>
      <div class="title-actions">
        <label class="import-row">
          <span class="import-label">导入最近</span>
          <input
            v-model.number="importLimit"
            class="import-input"
            type="number"
            min="1"
            :max="HISTORY_MAX_VIDEOS"
            :disabled="importing"
          />
          <span class="import-label">条</span>
          <button
            type="button"
            class="btn btn-ghost"
            :disabled="importing"
            @click="triggerImport"
          >
            {{ importing ? '导入中…' : '从 ComfyUI 导入' }}
          </button>
        </label>
        <button v-if="sortedItems.length" class="btn btn-ghost" @click="$emit('clear')">清空</button>
      </div>
    </div>

    <div v-if="!sortedItems.length" class="empty">还没有生成记录，提交一个任务试试吧。</div>

    <div v-else class="gallery">
      <div
        v-for="item in visibleItems"
        :key="itemKey(item)"
        class="item"
        :data-history-id="itemKey(item)"
      >
        <video
          v-if="isVideo(item) && videoSrc(item)"
          :src="videoSrc(item)"
          controls
          loop
          playsinline
          preload="none"
          @loadeddata="onVideoLoadDone"
          @error="onVideoLoadDone"
        ></video>
        <button
          v-else-if="isVideo(item)"
          type="button"
          class="video-placeholder"
          @click="loadVideo(item)"
        >
          点击加载预览
          <span class="filename">{{ item.filename }}</span>
        </button>
        <img v-else :src="item.url" :alt="item.filename" loading="lazy" />
        <div class="meta">
          <span>
            {{ item.mode?.toUpperCase?.() || item.mode }} · {{ item.time }}
            <template v-if="item.label"> · {{ item.label }}</template>
          </span>
          <a :href="item.url" :download="item.filename" target="_blank" rel="noopener">下载</a>
        </div>
      </div>
    </div>

    <div v-if="hasMore" class="more-row">
      <button type="button" class="btn btn-ghost" @click="showMore">
        加载更多（还剩 {{ sortedItems.length - visibleCount }} 条）
      </button>
    </div>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.count-hint {
  font-size: 12px;
  color: var(--muted, #888);
}
.import-status {
  font-size: 12px;
  color: var(--accent, #6ea8fe);
}
.title-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}
.import-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted, #888);
}
.import-input {
  width: 56px;
  padding: 4px 6px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
}
.video-placeholder {
  width: 100%;
  min-height: 160px;
  border: 1px dashed rgba(255, 255, 255, 0.18);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
}
.video-placeholder .filename {
  font-size: 11px;
  color: var(--muted, #888);
  word-break: break-all;
}
.more-row {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
</style>
