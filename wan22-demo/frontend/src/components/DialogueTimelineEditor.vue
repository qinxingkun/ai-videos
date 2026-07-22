<script setup>
import { computed } from 'vue'
import { createUtterance, validateUtterances } from '../services/dubbing.js'

const utterances = defineModel({ type: Array, default: () => [] })
const props = defineProps({
  characters: { type: Array, default: () => [] },
  maxFrame: { type: Number, default: 125 },
  disabled: { type: Boolean, default: false }
})
const validation = computed(() =>
  validateUtterances(utterances.value, {
    maxFrame: props.maxFrame,
    speakerIds: props.characters.map((item) => String(item.speakerId || item.id))
  })
)

function addUtterance() {
  const speakerId = props.characters[0]?.speakerId || props.characters[0]?.id || ''
  const lastEnd = Number(utterances.value.at(-1)?.endFrame ?? 0)
  const item = createUtterance(utterances.value.length, speakerId)
  item.startFrame = Math.min(props.maxFrame - 1, lastEnd)
  item.endFrame = Math.min(props.maxFrame, item.startFrame + 25)
  utterances.value.push(item)
}
</script>

<template>
  <section class="timeline-editor">
    <div class="editor-title">
      <strong>结构化台词时间线（25fps）</strong>
      <button type="button" class="mini" :disabled="disabled" @click="addUtterance">+ 添加台词</button>
    </div>
    <div v-for="(item, index) in utterances" :key="item.id" class="utterance-row">
      <select v-model="item.speakerId" :disabled="disabled" aria-label="说话人">
        <option value="" disabled>选择说话人</option>
        <option v-for="character in characters" :key="character.speakerId || character.id" :value="character.speakerId || character.id">
          {{ character.name }} · {{ character.speakerId || character.id }}
        </option>
      </select>
      <textarea v-model="item.text" rows="2" :disabled="disabled" placeholder="台词"></textarea>
      <div class="frame-range">
        <input v-model.number="item.startFrame" type="number" min="0" :max="maxFrame - 1" :disabled="disabled" />
        <span>–</span>
        <input v-model.number="item.endFrame" type="number" min="1" :max="maxFrame" :disabled="disabled" />
      </div>
      <select v-model="item.lipSyncPolicy" :disabled="disabled" aria-label="口型策略">
        <option value="required">必须同步</option>
        <option value="preferred">优先同步</option>
        <option value="off">仅配音</option>
      </select>
      <button type="button" class="remove" :disabled="disabled || utterances.length <= 1" @click="utterances.splice(index, 1)">×</button>
    </div>
    <p class="timeline-hint" :class="{ invalid: !validation.ok }">
      {{ validation.ok ? `时间线有效，帧范围 0–${maxFrame}，相邻台词可首尾相接` : validation.error }}
    </p>
  </section>
</template>

<style scoped>
.timeline-editor { margin-top: 12px; padding: 12px; border: 1px solid rgba(120,180,255,.25); border-radius: 8px; }
.editor-title { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
.utterance-row { display: grid; grid-template-columns: 150px minmax(180px, 1fr) 145px 120px 30px; gap: 7px; align-items: center; margin-top: 8px; }
.frame-range { display: flex; align-items: center; gap: 4px; }
.frame-range input { min-width: 0; width: 64px; }
textarea,select,input { width: 100%; }
.mini,.remove { font-size: 11px; padding: 4px 9px; border: 1px solid rgba(255,255,255,.2); border-radius: 6px; background: transparent; color: inherit; }
.remove { padding: 5px; color: #ff9b86; }
.timeline-hint { margin: 8px 0 0; font-size: 12px; color: #78d996; }
.timeline-hint.invalid { color: #ff9b86; }
@media (max-width: 900px) { .utterance-row { grid-template-columns: 1fr 1fr; } .remove { justify-self: end; } }
</style>
