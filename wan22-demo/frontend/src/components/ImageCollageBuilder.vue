<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { buildCollageFile, blobToPreviewUrl, COLLAGE_MAX, suggestGrid } from '../services/imageCollage.js'

const props = defineProps({
  modelValue: { type: Object, default: null },
  outputWidth: { type: Number, default: 768 },
  outputHeight: { type: Number, default: 512 },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const slots = ref([])
const slotPreviews = ref([])
const cols = ref(0)
const gap = ref(6)
const previewUrl = ref('')
const building = ref(false)
const errorMsg = ref('')
const inputRef = ref(null)

const filledCount = computed(() => slots.value.filter(Boolean).length)
const gridHint = computed(() => {
  const { cols: c, rows: r } = suggestGrid(filledCount.value || 1, cols.value || undefined)
  return `${c}×${r} 网格（${filledCount.value} 张）`
})

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

onBeforeUnmount(() => {
  revokePreview()
  revokeSlotPreviews()
})

watch(
  () => props.modelValue,
  (file) => {
    if (!file && !building.value) revokePreview()
  }
)

function revokeSlotPreviews() {
  slotPreviews.value.forEach((u) => u && URL.revokeObjectURL(u))
  slotPreviews.value = []
}

function syncSlotPreviews() {
  revokeSlotPreviews()
  slotPreviews.value = slots.value.map((f) => (f ? URL.createObjectURL(f) : ''))
}

function pickFiles() {
  if (props.disabled) return
  inputRef.value?.click()
}

function onFilesSelected(e) {
  const picked = Array.from(e.target.files || [])
  if (!picked.length) return
  const room = COLLAGE_MAX - filledCount.value
  const toAdd = picked.slice(0, room)
  let idx = 0
  for (let i = 0; i < slots.value.length && idx < toAdd.length; i++) {
    if (!slots.value[i]) {
      slots.value[i] = toAdd[idx++]
    }
  }
  while (idx < toAdd.length && slots.value.length < COLLAGE_MAX) {
    slots.value.push(toAdd[idx++])
  }
  if (inputRef.value) inputRef.value.value = ''
  errorMsg.value = ''
  syncSlotPreviews()
}

function removeSlot(i) {
  slots.value.splice(i, 1)
  syncSlotPreviews()
}

function clearAll() {
  slots.value = []
  revokeSlotPreviews()
  revokePreview()
  emit('update:modelValue', null)
  errorMsg.value = ''
}

function moveSlot(i, dir) {
  const j = i + dir
  if (j < 0 || j >= slots.value.length) return
  const t = slots.value[i]
  slots.value[i] = slots.value[j]
  slots.value[j] = t
  syncSlotPreviews()
}

async function generateCollage() {
  const files = slots.value.filter(Boolean)
  if (!files.length) {
    errorMsg.value = '请先添加至少 1 张图片'
    return
  }
  building.value = true
  errorMsg.value = ''
  try {
    const file = await buildCollageFile(files, {
      cols: cols.value || undefined,
      outputWidth: props.outputWidth,
      outputHeight: props.outputHeight,
      gap: gap.value,
      filename: `collage_${props.outputWidth}x${props.outputHeight}.jpg`
    })
    revokePreview()
    previewUrl.value = blobToPreviewUrl(file)
    emit('update:modelValue', file)
  } catch (e) {
    errorMsg.value = e.message || String(e)
  } finally {
    building.value = false
  }
}
</script>

<template>
  <div class="collage-builder" :class="{ disabled }">
    <div class="collage-toolbar">
      <button type="button" class="btn-mini" :disabled="disabled || filledCount >= COLLAGE_MAX" @click="pickFiles">
        + 添加图片（{{ filledCount }}/{{ COLLAGE_MAX }}）
      </button>
      <label class="mini-field">
        列数
        <select v-model.number="cols" :disabled="disabled">
          <option :value="0">自动</option>
          <option :value="1">1 列</option>
          <option :value="2">2 列</option>
          <option :value="3">3 列</option>
        </select>
      </label>
      <label class="mini-field">
        间距
        <input v-model.number="gap" type="number" min="0" max="24" :disabled="disabled" />
      </label>
      <span class="muted grid-hint">{{ gridHint }}</span>
    </div>

    <input ref="inputRef" type="file" accept="image/*" multiple hidden @change="onFilesSelected" />

    <div v-if="slots.length" class="slot-grid">
      <div v-for="(file, i) in slots" :key="i" class="slot-item">
        <img v-if="slotPreviews[i]" :src="slotPreviews[i]" :alt="file.name" />
        <div class="slot-actions">
          <button type="button" :disabled="disabled || i === 0" @click="moveSlot(i, -1)">←</button>
          <button type="button" :disabled="disabled" @click="removeSlot(i)">×</button>
          <button type="button" :disabled="disabled || i === slots.length - 1" @click="moveSlot(i, 1)">→</button>
        </div>
        <span class="slot-idx">{{ i + 1 }}</span>
      </div>
      <div
        v-if="filledCount < COLLAGE_MAX"
        class="slot-add"
        :class="{ disabled: disabled }"
        @click="pickFiles"
      >
        +
      </div>
    </div>
    <div v-else class="slot-empty" @click="pickFiles">
      <div class="empty-icon">⊞</div>
      <div>点击添加 1–9 张图片，拼成一张参考图</div>
      <div class="muted">适合多角色定妆照、分镜板、九宫格参考</div>
    </div>

    <div class="collage-actions">
      <button type="button" class="btn" :disabled="disabled || building || !filledCount" @click="generateCollage">
        {{ building ? '拼图中…' : '生成拼图' }}
      </button>
      <button type="button" class="btn-mini" :disabled="disabled" @click="clearAll">清空</button>
      <span class="muted out-size">输出 {{ outputWidth }}×{{ outputHeight }}</span>
    </div>

    <div v-if="errorMsg" class="error-box">{{ errorMsg }}</div>

    <div v-if="previewUrl || modelValue" class="collage-preview">
      <label>拼图结果（将作为 I2V 参考图）</label>
      <img :src="previewUrl" alt="拼图预览" />
      <div v-if="modelValue" class="muted file-name">{{ modelValue.name }}</div>
    </div>
  </div>
</template>

<style scoped>
.collage-builder.disabled {
  opacity: 0.65;
  pointer-events: none;
}
.collage-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.mini-field {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.mini-field select,
.mini-field input {
  width: 64px;
  padding: 4px 6px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.2);
  color: inherit;
}
.grid-hint {
  font-size: 12px;
}
.slot-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.slot-item {
  position: relative;
  aspect-ratio: 4/3;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.3);
}
.slot-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.slot-actions {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 4px;
  padding: 4px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.75));
}
.slot-actions button {
  font-size: 11px;
  padding: 2px 8px;
  border: none;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
}
.slot-idx {
  position: absolute;
  top: 4px;
  left: 6px;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.55);
  padding: 1px 6px;
  border-radius: 4px;
}
.slot-add,
.slot-empty {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  min-height: 100px;
  text-align: center;
  font-size: 13px;
  padding: 12px;
}
.slot-add {
  aspect-ratio: 4/3;
  font-size: 28px;
  color: var(--muted, #888);
}
.slot-add.disabled {
  cursor: not-allowed;
}
.empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
  opacity: 0.5;
}
.collage-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.out-size {
  font-size: 12px;
}
.collage-preview {
  margin-top: 12px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid rgba(80, 200, 120, 0.25);
  background: rgba(80, 200, 120, 0.05);
}
.collage-preview label {
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
}
.collage-preview img {
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  border-radius: 6px;
  background: #111;
}
.file-name {
  font-size: 11px;
  margin-top: 4px;
}
.error-box {
  color: #f88;
  font-size: 12px;
  margin-top: 8px;
}
</style>
