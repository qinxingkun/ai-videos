<script setup>
defineProps({
  results: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  /** 当前页是否 I2V（显示开下一段快捷入口） */
  showHandoff: { type: Boolean, default: false },
  /** 定妆照 input 文件名（可与起始图相同） */
  lookbookName: { type: String, default: '' }
})

const emit = defineEmits(['regenerate', 'handoff'])

function bindingEntries(bindings) {
  if (!bindings) return []
  if (Array.isArray(bindings)) {
    return bindings.map((item) => [item.speakerId || item.characterId || item.id, item.faceTrackId || item.trackId])
  }
  return Object.entries(bindings)
}

function utteranceQa(qa) {
  return qa?.utterances || qa?.utteranceQa || qa?.items || []
}

function handoff(mode, r) {
  emit('handoff', {
    mode,
    lastFrameName: r.lastFrameName || null,
    lookbookName: r.lookbookName || null,
    startImageName: r.startImageName || null
  })
}
</script>

<template>
  <div class="video-result">
    <div v-for="(r, i) in results" :key="r.index ?? i" class="shot-card">
      <div class="shot-head">
        <span class="shot-title">{{ r.index }}. {{ r.shotName || r.filename }}</span>
        <span v-if="r.mode === 'flf2v'" class="tag">FLF2V 刷新</span>
        <span v-if="r.mode === 'vace'" class="tag">VACE</span>
        <span v-if="r.dubbed" class="tag">已配音</span>
        <span v-if="r.degraded" class="tag warn">配音降级</span>
        <button
          v-if="!busy"
          type="button"
          class="btn-regen"
          @click="emit('regenerate', r.index)"
        >
          重生成此段
        </button>
      </div>
      <video
        v-if="r.kind === 'video' || r.filename?.endsWith('.mp4')"
        :src="r.url"
        controls
        playsinline
        class="shot-video"
      ></video>
      <img v-else :src="r.url" :alt="r.filename" class="shot-video" />
      <div v-if="r.firstFrameUrl || r.lastFrameUrl || r.lastFrameError" class="frame-row">
        <div v-if="r.firstFrameUrl" class="frame-thumb">
          <img :src="r.firstFrameUrl" alt="首帧" />
          <span>首帧</span>
        </div>
        <div v-if="r.lastFrameUrl" class="frame-thumb">
          <img :src="r.lastFrameUrl" alt="末帧" />
          <span>{{ r.index != null ? '末帧（下段衔接）' : '末帧' }}</span>
          <a
            class="frame-dl"
            :href="r.lastFrameUrl"
            :download="r.lastFrameName || 'last_frame.jpg'"
            target="_blank"
            rel="noopener"
          >下载末帧</a>
        </div>
        <div v-else-if="r.lastFrameError" class="frame-error">
          末帧截取失败：{{ r.lastFrameError }}
        </div>
      </div>
      <div
        v-if="showHandoff && !busy && (lookbookName || r.lastFrameName)"
        class="handoff-row"
      >
        <span class="handoff-label">开下一段：</span>
        <button
          v-if="lookbookName"
          type="button"
          class="btn-handoff"
          @click="handoff('lookbook', { ...r, lookbookName })"
        >
          定妆照
        </button>
        <button
          v-if="lookbookName"
          type="button"
          class="btn-handoff"
          @click="handoff('vace-ref', { ...r, lookbookName })"
        >
          VACE 参考
        </button>
        <button
          v-if="lookbookName && r.lastFrameName"
          type="button"
          class="btn-handoff"
          @click="handoff('last+lookbook', { ...r, lookbookName })"
        >
          末帧+定妆照
        </button>
      </div>
      <div class="status-line shot-meta">
        <span>{{ r.filename }}</span>
        <a :href="r.url" :download="r.filename" target="_blank" rel="noopener">下载视频</a>
      </div>
      <div v-if="bindingEntries(r.bindings).length" class="qa-summary">
        <strong>人脸绑定</strong>
        <span v-for="[speaker, track] in bindingEntries(r.bindings)" :key="speaker">
          {{ speaker }} → {{ track }}
        </span>
      </div>
      <div v-if="utteranceQa(r.qa).length" class="qa-summary">
        <strong>逐句 QA</strong>
        <span v-for="(item, qaIndex) in utteranceQa(r.qa)" :key="item.id || qaIndex" :class="{ fail: item.ok === false }">
          {{ item.speakerId || `台词 ${qaIndex + 1}` }}：{{ item.ok === false ? '未通过' : '通过' }}
          <template v-if="item.message || item.issue"> · {{ item.message || item.issue }}</template>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shot-card {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.shot-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.shot-title {
  font-size: 13px;
  font-weight: 600;
}
.tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(120, 180, 255, 0.15);
  color: #8cb4ff;
}
.tag.warn {
  background: rgba(255, 180, 80, 0.15);
  color: #ffc070;
}
.btn-regen {
  margin-left: auto;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.btn-regen:hover {
  background: rgba(255, 255, 255, 0.06);
}
.shot-video {
  width: 100%;
  border-radius: 10px;
  display: block;
}
.frame-row {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}
.frame-thumb {
  flex: 1;
  text-align: center;
}
.frame-thumb img {
  width: 100%;
  max-height: 160px;
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.25);
}
.frame-thumb span {
  display: block;
  font-size: 11px;
  color: var(--muted, #888);
  margin-top: 4px;
}
.frame-dl {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
}
.frame-error {
  flex: 1;
  font-size: 12px;
  color: #ff9b86;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 120, 100, 0.08);
  border: 1px solid rgba(255, 120, 100, 0.25);
}
.handoff-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}
.handoff-label {
  font-size: 12px;
  color: var(--muted, #888);
}
.btn-handoff {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(120, 180, 255, 0.35);
  background: rgba(120, 180, 255, 0.1);
  color: #8cb4ff;
  cursor: pointer;
}
.btn-handoff:hover {
  background: rgba(120, 180, 255, 0.2);
}
.shot-meta {
  margin-top: 6px;
  font-size: 12px;
  justify-content: space-between;
}
.qa-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin-top: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(120, 180, 255, .07);
  font-size: 11px;
}
.qa-summary strong { width: 100%; }
.qa-summary .fail { color: #ff9b86; }
</style>
