<script setup>
import { createCharacter } from '../services/dubbing.js'

const characters = defineModel({ type: Array, default: () => [] })
const props = defineProps({
  disabled: { type: Boolean, default: false },
  min: { type: Number, default: 1 },
  max: { type: Number, default: 4 },
  compact: { type: Boolean, default: false }
})

function addCharacter() {
  if (characters.value.length >= props.max) return
  characters.value.push(createCharacter(characters.value.length))
}

function removeCharacter(index, minimum) {
  if (characters.value.length <= minimum) return
  const removed = characters.value[index]
  characters.value.splice(index, 1)
  if (removed && characters.value.length) {
    characters.value.forEach((item, itemIndex) => {
      if (!item.speakerId) item.speakerId = item.id || `speaker-${itemIndex + 1}`
    })
  }
}
</script>

<template>
  <section class="cast-panel">
    <div class="cast-title">
      <strong>角色与声线（{{ characters.length }}/{{ max }}）</strong>
      <button v-if="characters.length < max" type="button" class="mini" :disabled="disabled" @click="addCharacter">
        + 添加角色
      </button>
    </div>
    <div v-for="(character, index) in characters" :key="character.id || index" class="cast-row">
      <div class="row-head">
        <span>{{ character.name || `角色 ${index + 1}` }}</span>
        <button
          v-if="characters.length > min"
          type="button"
          class="mini danger"
          :disabled="disabled"
          @click="removeCharacter(index, min)"
        >
          删除
        </button>
      </div>
      <div class="fields" :class="{ compact }">
        <label>名称<input v-model="character.name" :disabled="disabled" placeholder="角色名" /></label>
        <label>speakerId<input v-model="character.speakerId" :disabled="disabled" placeholder="唯一说话人 ID" /></label>
        <label>voiceId<input v-model="character.voiceId" :disabled="disabled" placeholder="例如 default.wav" /></label>
        <label>参考图<input v-model="character.referenceImageName" :disabled="disabled" placeholder="可选 input 文件名" /></label>
      </div>
    </div>
  </section>
</template>

<style scoped>
.cast-panel { padding: 12px; border: 1px solid rgba(120, 180, 255, .25); border-radius: 8px; }
.cast-title,.row-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.cast-row { margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(255,255,255,.12); }
.row-head { font-size: 12px; margin-bottom: 6px; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.fields.compact { grid-template-columns: repeat(4, minmax(120px, 1fr)); }
label { min-width: 0; font-size: 11px; color: var(--muted, #aaa); }
input { width: 100%; margin-top: 3px; padding: 7px; }
.mini { font-size: 11px; padding: 4px 9px; border: 1px solid rgba(255,255,255,.2); border-radius: 6px; background: transparent; color: inherit; }
.danger { color: #ff9b86; }
@media (max-width: 720px) { .fields,.fields.compact { grid-template-columns: 1fr; } }
</style>
