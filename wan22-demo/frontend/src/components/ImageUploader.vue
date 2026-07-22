<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Object, default: null }, // File
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const previewUrl = ref('')
const inputRef = ref(null)

watch(
  () => props.modelValue,
  (file) => {
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = file ? URL.createObjectURL(file) : ''
  }
)

function pick() {
  if (props.disabled) return
  inputRef.value?.click()
}

function onChange(e) {
  const file = e.target.files?.[0]
  if (file) emit('update:modelValue', file)
}

function clear(e) {
  e.stopPropagation()
  emit('update:modelValue', null)
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<template>
  <div class="uploader" :class="{ 'has-image': !!previewUrl, disabled }" @click="pick">
    <input ref="inputRef" type="file" accept="image/*" hidden :disabled="disabled" @change="onChange" />
    <template v-if="previewUrl">
      <img :src="previewUrl" alt="起始图预览" />
      <div style="margin-top: 8px">
        <button class="btn-ghost btn" type="button" @click="clear">移除图片</button>
      </div>
    </template>
    <template v-else>
      <div style="font-size: 28px; margin-bottom: 6px">+</div>
      <div>点击选择起始图片</div>
      <div class="muted" style="margin-top: 4px; font-size: 12px">图生视频会以这张图作为视频首帧</div>
    </template>
  </div>
</template>
