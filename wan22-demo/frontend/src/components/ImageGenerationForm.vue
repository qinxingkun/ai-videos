<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useImageGeneration } from '../composables/useImageGeneration.js'
import VideoResult from './VideoResult.vue'
import {
  QWEN_ASPECT_PRESETS,
  QWEN_DEFAULT_CFG,
  QWEN_DEFAULT_NEGATIVE,
  QWEN_DEFAULT_STEPS,
  QWEN_TURBO_CFG,
  QWEN_TURBO_STEPS,
  findAspectPreset,
  formatSize
} from '../services/qwenImageConfig.js'

const emit = defineEmits(['done'])

const form = reactive({
  prompt:
    '一位 20 岁东亚女生，精致五官，明亮棕色大眼睛，自然波浪长发，室内漫展背景，' +
    'iPhone 随手拍风格，清新真实，柔和自然光',
  negativePrompt: QWEN_DEFAULT_NEGATIVE,
  aspectRatio: '16:9',
  width: 1664,
  height: 928,
  steps: QWEN_DEFAULT_STEPS,
  cfg: QWEN_DEFAULT_CFG,
  turbo: false,
  seed: 0,
  randomSeed: true
})

const validationError = ref('')

const {
  status,
  errorMsg,
  results,
  queueHint,
  elapsedSec,
  isBusy,
  generate,
  resumeFromStorage
} = useImageGeneration({ onDone: (record) => emit('done', record) })

const busy = computed(() => isBusy.value)

const sizeLabel = computed(() => formatSize(form.width, form.height))

const paramSummary = computed(() => {
  const mode = form.turbo ? `Turbo ${QWEN_TURBO_STEPS} 步 / CFG ${QWEN_TURBO_CFG}` : `${form.steps} 步 / CFG ${form.cfg}`
  return `Qwen-Image-2512 · ${sizeLabel.value} · ${mode} · diffusers`
})

function applyAspectPreset(id) {
  form.aspectRatio = id
  const preset = findAspectPreset(id)
  if (!preset || id === 'custom') return
  form.width = preset.width
  form.height = preset.height
}

function onTurboChange(enabled) {
  if (enabled) {
    form.steps = QWEN_TURBO_STEPS
    form.cfg = QWEN_TURBO_CFG
  } else {
    form.steps = QWEN_DEFAULT_STEPS
    form.cfg = QWEN_DEFAULT_CFG
  }
}

function onCustomSizeChange() {
  form.aspectRatio = 'custom'
}

async function onSubmit() {
  validationError.value = ''
  if (!form.prompt.trim()) {
    validationError.value = '请填写正向提示词'
    return
  }
  const seed = form.randomSeed ? Math.floor(Math.random() * 2 ** 31) : Number(form.seed)
  if (form.randomSeed) form.seed = seed

  await generate({
    prompt: form.prompt.trim(),
    negativePrompt: form.negativePrompt,
    width: Number(form.width),
    height: Number(form.height),
    steps: Number(form.steps),
    cfg: Number(form.cfg),
    turbo: Boolean(form.turbo),
    seed,
    aspectRatio: form.aspectRatio,
    timeoutMs: 60 * 60 * 1000
  })
}

onMounted(() => {
  applyAspectPreset(form.aspectRatio)
  resumeFromStorage()
})
</script>

<template>
  <div class="row" style="flex-wrap: wrap">
    <div class="panel" style="flex: 1 1 420px; min-width: 340px">
      <div class="field">
        <div class="muted hint-box">{{ paramSummary }}</div>
      </div>

      <div class="field">
        <label>正向提示词</label>
        <textarea v-model="form.prompt" rows="5" placeholder="描述主体、场景、镜头、风格…"></textarea>
      </div>

      <div class="field">
        <label>负向提示词</label>
        <textarea v-model="form.negativePrompt" rows="3"></textarea>
      </div>

      <div class="field">
        <label>宽高比</label>
        <div class="preset-row">
          <button
            v-for="item in QWEN_ASPECT_PRESETS"
            :key="item.id"
            type="button"
            class="preset-btn"
            :class="{ active: form.aspectRatio === item.id }"
            :disabled="busy"
            @click="applyAspectPreset(item.id)"
          >
            {{ item.label }}
            <span v-if="item.id !== 'custom'" class="preset-dim">{{ formatSize(item.width, item.height) }}</span>
          </button>
        </div>
      </div>

      <div v-if="form.aspectRatio === 'custom'" class="grid-2">
        <div class="field">
          <label>宽度</label>
          <input v-model.number="form.width" type="number" min="256" max="2048" step="16" :disabled="busy" @change="onCustomSizeChange" />
        </div>
        <div class="field">
          <label>高度</label>
          <input v-model.number="form.height" type="number" min="256" max="2048" step="16" :disabled="busy" @change="onCustomSizeChange" />
        </div>
      </div>
      <div v-else class="muted size-hint">当前输出：{{ sizeLabel }}</div>

      <div class="grid-3">
        <div class="field">
          <label>采样步数 (steps)</label>
          <input v-model.number="form.steps" type="number" min="1" max="100" :disabled="busy || form.turbo" />
        </div>
        <div class="field">
          <label>CFG (true_cfg_scale)</label>
          <input v-model.number="form.cfg" type="number" min="0" max="20" step="0.1" :disabled="busy || form.turbo" />
        </div>
        <div class="field">
          <label>随机种子</label>
          <input v-model.number="form.seed" type="number" :disabled="busy || form.randomSeed" />
        </div>
      </div>

      <label class="toggle-row">
        <input v-model="form.turbo" type="checkbox" :disabled="busy" @change="onTurboChange(form.turbo)" />
        <span>Turbo 快速模式（4 步 / CFG 1.0，质量低于标准 50 步）</span>
      </label>

      <label class="muted seed-toggle">
        <input v-model="form.randomSeed" type="checkbox" style="width: auto" :disabled="busy" />
        每次随机种子
      </label>

      <div style="margin-top: 16px">
        <button class="btn" :disabled="busy" @click="onSubmit">
          {{ busy ? '生成中…' : '开始生成图片' }}
        </button>
      </div>

      <div class="status-line">
        <span class="dot" :class="{ ok: status === 'done', err: status === 'error' }"></span>
        <span>{{ { idle: '就绪', queued: '排队中', running: '推理中', done: '完成', error: '出错' }[status] || status }}</span>
        <span v-if="elapsedSec > 0" class="muted">· 已等待 {{ elapsedSec }}s</span>
      </div>
      <div v-if="queueHint" class="muted hint-line">{{ queueHint }}</div>

      <div v-if="validationError || errorMsg" class="error-box">{{ validationError || errorMsg }}</div>
    </div>

    <div class="panel" style="flex: 1 1 420px; min-width: 340px">
      <div class="section-title"><h3>生成结果</h3></div>
      <VideoResult v-if="results.length" :results="results" />
      <div v-else class="empty">提交任务后，生成的图片会显示在这里。</div>
    </div>
  </div>
</template>

<style scoped>
.hint-box {
  font-size: 12px;
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(120, 180, 255, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(120, 180, 255, 0.25);
}
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
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  cursor: pointer;
  font-size: 12px;
}
.preset-btn.active {
  border-color: rgba(120, 180, 255, 0.55);
  background: rgba(120, 180, 255, 0.12);
}
.preset-dim {
  font-size: 11px;
  opacity: 0.75;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 10px 0;
}
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 12px;
}
.size-hint,
.hint-line {
  font-size: 12px;
  margin-top: 8px;
}
.toggle-row,
.seed-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 13px;
}
.toggle-row input,
.seed-toggle input {
  width: auto;
}
</style>
