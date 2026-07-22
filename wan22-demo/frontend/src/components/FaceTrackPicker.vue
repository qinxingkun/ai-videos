<script setup>
import { computed } from 'vue'
import { faceTrackThumbnailUrl } from '../services/orchestrator.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  tracks: { type: Array, default: () => [] },
  characters: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'confirm'])

const complete = computed(() =>
  props.characters.every((character) => Boolean(props.modelValue[character.speakerId || character.id]))
)

function choose(character, trackId) {
  emit('update:modelValue', {
    ...props.modelValue,
    [character.speakerId || character.id]: trackId
  })
}
</script>

<template>
  <section class="picker">
    <h4>需要人工确认人脸绑定</h4>
    <p class="hint">为每位说话人选择画面中的人脸轨迹，再继续渲染。</p>
    <div v-for="character in characters" :key="character.speakerId || character.id" class="character-bind">
      <strong>{{ character.name }} · {{ character.speakerId || character.id }}</strong>
      <div class="tracks">
        <button
          v-for="track in tracks"
          :key="track.id"
          type="button"
          class="track"
          :class="{ selected: modelValue[character.speakerId || character.id] === track.id }"
          :disabled="disabled"
          @click="choose(character, track.id)"
        >
          <img :src="faceTrackThumbnailUrl(sessionId, track)" :alt="`人脸轨迹 ${track.id}`" />
          <span>{{ track.id }}</span>
          <small>可见率 {{ Math.round(Number(track.visibleRatio || 0) * 100) }}% · {{ track.frameCount || 0 }} 帧</small>
        </button>
      </div>
    </div>
    <button type="button" class="confirm" :disabled="disabled || !complete" @click="emit('confirm')">确认绑定并渲染</button>
  </section>
</template>

<style scoped>
.picker { margin-top: 12px; padding: 14px; border: 1px solid rgba(255,190,80,.4); border-radius: 9px; background: rgba(255,190,80,.06); }
h4 { margin: 0 0 4px; }
.hint { margin: 0 0 12px; font-size: 12px; color: var(--muted, #aaa); }
.character-bind { margin-top: 12px; }
.tracks { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.track { width: 128px; padding: 6px; border: 2px solid transparent; border-radius: 8px; background: rgba(0,0,0,.25); color: inherit; text-align: left; }
.track.selected { border-color: #75c8ff; }
.track img { width: 100%; height: 82px; object-fit: cover; border-radius: 5px; display: block; }
.track span,.track small { display: block; margin-top: 4px; }
.track small { color: var(--muted, #aaa); font-size: 10px; }
.confirm { margin-top: 14px; padding: 8px 14px; }
</style>
