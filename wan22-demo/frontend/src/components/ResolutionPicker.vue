<script setup>
import { computed } from 'vue'
import {
  WAN_RES_PRESETS,
  WAN_RES_STEP,
  snapWanDimension,
  detectWanPreset,
  formatResolution
} from '../services/frameUtils.js'

const width = defineModel('width', { type: Number, required: true })
const height = defineModel('height', { type: Number, required: true })
const preset = defineModel('preset', { type: String, default: '720p' })

defineProps({
  disabled: { type: Boolean, default: false }
})

const activeHint = computed(() => {
  if (preset.value === 'custom') {
    return WAN_RES_PRESETS.find((item) => item.id === 'custom')?.hint || ''
  }
  return WAN_RES_PRESETS.find((item) => item.id === preset.value)?.hint || ''
})

function selectPreset(id) {
  preset.value = id
  if (id === 'custom') return
  const item = WAN_RES_PRESETS.find((p) => p.id === id)
  if (!item) return
  width.value = item.width
  height.value = item.height
}

function onCustomInput() {
  preset.value = detectWanPreset(width.value, height.value)
}

function onWidthChange(event) {
  width.value = snapWanDimension(event.target.value)
  onCustomInput()
}

function onHeightChange(event) {
  height.value = snapWanDimension(event.target.value)
  onCustomInput()
}
</script>

<template>
  <div class="field resolution-picker">
    <label>输出分辨率</label>
    <div class="preset-row">
      <button
        v-for="item in WAN_RES_PRESETS"
        :key="item.id"
        type="button"
        class="preset-btn"
        :class="{ active: preset === item.id }"
        :disabled="disabled"
        @click="selectPreset(item.id)"
      >
        {{ item.label }}
        <span v-if="item.id !== 'custom'" class="preset-dim">{{ formatResolution(item.width, item.height) }}</span>
      </button>
    </div>
    <div v-if="preset === 'custom'" class="grid-2 custom-grid">
      <div class="field compact">
        <label>宽度</label>
        <input
          type="number"
          :value="width"
          :step="WAN_RES_STEP"
          :min="WAN_RES_STEP"
          :disabled="disabled"
          @change="onWidthChange"
        />
      </div>
      <div class="field compact">
        <label>高度</label>
        <input
          type="number"
          :value="height"
          :step="WAN_RES_STEP"
          :min="WAN_RES_STEP"
          :disabled="disabled"
          @change="onHeightChange"
        />
      </div>
    </div>
    <div v-else class="muted resolution-summary">
      当前：{{ formatResolution(width, height) }}
    </div>
    <div v-if="activeHint" class="muted resolution-hint">{{ activeHint }}</div>
  </div>
</template>

<style scoped>
.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}
.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  cursor: pointer;
  font-size: 13px;
}
.preset-btn.active {
  border-color: rgba(80, 200, 120, 0.55);
  background: rgba(80, 200, 120, 0.12);
}
.preset-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.preset-dim {
  font-size: 11px;
  opacity: 0.75;
}
.custom-grid {
  margin-top: 10px;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field.compact {
  margin: 0;
}
.field.compact label {
  font-size: 11px;
}
.resolution-summary,
.resolution-hint {
  margin-top: 8px;
  font-size: 12px;
}
</style>
