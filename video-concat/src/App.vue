<script setup>
import { ref, computed, onMounted } from 'vue'

const files = ref([])
const isDragging = ref(false)
const loading = ref(false)
const error = ref('')
const resultUrl = ref('')
const resultCount = ref(0)
const resultDubbed = ref(false)
const dubWarning = ref('')
const fileInput = ref(null)

const dubbingEnabled = ref(false)
const dubbingText = ref('')
const voiceId = ref('default.wav')
const voiceOptions = ref([])
const audioMode = ref('mix')
const speechSpeed = ref(1.0)
const paceMode = ref('uniform')
const cosyVoiceOk = ref(null)
const cosyVoiceHint = ref('')

const canConcat = computed(() => {
  const minFiles = dubbingEnabled.value ? 1 : 2
  if (files.value.length < minFiles || loading.value) return false
  if (dubbingEnabled.value && !dubbingText.value.trim()) return false
  return true
})

const actionLabel = computed(() => {
  if (loading.value) {
    if (dubbingEnabled.value && files.value.length === 1) return '配音中…'
    return dubbingEnabled.value ? '拼接并配音中…' : '拼接中…'
  }
  if (dubbingEnabled.value && files.value.length === 1) return '开始配音'
  if (dubbingEnabled.value) return `开始拼接并配音（${files.value.length} 个视频）`
  return `开始拼接（${files.value.length} 个视频）`
})

const statusText = computed(() => {
  if (!loading.value) return ''
  if (dubbingEnabled.value && files.value.length === 1) {
    return '正在生成 CosyVoice 配音并混入视频…'
  }
  if (dubbingEnabled.value) return '正在拼接视频并生成 CosyVoice 配音…'
  return '正在使用 ffmpeg 拼接视频，请稍候…'
})

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function addFiles(newFiles) {
  const videoFiles = [...newFiles].filter((f) => f.type.startsWith('video/'))
  if (!videoFiles.length) {
    error.value = '请选择视频文件'
    return
  }
  error.value = ''
  files.value.push(...videoFiles)
}

function onFileSelect(e) {
  addFiles(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  isDragging.value = false
  addFiles(e.dataTransfer.files)
}

function removeFile(index) {
  files.value.splice(index, 1)
}

function moveUp(index) {
  if (index === 0) return
  const arr = files.value
  ;[arr[index - 1], arr[index]] = [arr[index], arr[index - 1]]
}

function moveDown(index) {
  if (index >= files.value.length - 1) return
  const arr = files.value
  ;[arr[index], arr[index + 1]] = [arr[index + 1], arr[index]]
}

function formatDuration(sec) {
  const s = Math.max(0, Number(sec) || 0)
  const m = Math.floor(s / 60)
  const r = Math.round(s % 60)
  return m > 0 ? `${m}分${r}秒` : `${r}秒`
}

function clearAll() {
  files.value = []
  resultUrl.value = ''
  resultDubbed.value = false
  dubWarning.value = ''
  error.value = ''
}

async function loadCosyVoiceHealth() {
  try {
    const res = await fetch('/api/cosyvoice/health')
    const data = await res.json()
    cosyVoiceOk.value = Boolean(data.ok)
    voiceOptions.value = Array.isArray(data.voices) ? data.voices : []
    if (data.ok) {
      const defaultVoice = data.defaultVoice || 'default.wav'
      cosyVoiceHint.value = data.hint || data.busy
        ? 'CosyVoice 正在合成中，可提交任务但需排队等待'
        : `CosyVoice 已就绪 · ${voiceOptions.value.length} 个可选音色`
      voiceId.value = voiceOptions.value.some((v) => v.id === defaultVoice)
        ? defaultVoice
        : voiceOptions.value[0]?.id || defaultVoice
    } else {
      cosyVoiceHint.value = `CosyVoice 未连接（${data.error || '服务未启动'}），开启配音前需先启动服务`
    }
  } catch {
    cosyVoiceOk.value = false
    cosyVoiceHint.value = '无法检测 CosyVoice 状态'
  }
}

async function concatVideos() {
  if (!canConcat.value) return

  if (dubbingEnabled.value && cosyVoiceOk.value === false) {
    error.value = 'CosyVoice 服务不可用，请先启动配音服务或关闭配音选项'
    return
  }

  loading.value = true
  error.value = ''
  resultUrl.value = ''
  resultDubbed.value = false
  dubWarning.value = ''

  const formData = new FormData()
  for (const file of files.value) {
    formData.append('videos', file)
  }
  formData.append('dubbingEnabled', dubbingEnabled.value ? 'true' : 'false')
  if (dubbingEnabled.value) {
    formData.append('dubbingText', dubbingText.value.trim())
    formData.append('voiceId', voiceId.value.trim())
    formData.append('audioMode', audioMode.value)
    formData.append('speechSpeed', String(speechSpeed.value))
    formData.append('paceMode', paceMode.value)
  }

  try {
    const res = await fetch('/api/concat', {
      method: 'POST',
      body: formData,
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '拼接失败')

    resultUrl.value = `${data.url}?t=${Date.now()}`
    resultCount.value = data.count
    resultDubbed.value = Boolean(data.dubbed)
    if (data.dubMeta?.truncated) {
      dubWarning.value =
        `配音完整时长约 ${formatDuration(data.dubMeta.dubDuration)}，超过视频 ${formatDuration(data.dubMeta.videoDuration)}，` +
        `已自动加速；若仍听不全，请缩短文案或提高语速滑块。`
    } else if (data.dubMeta?.shortfall) {
      const { videoDuration, dubDuration, audioMode: mode, stretched } = data.dubMeta
      const stretchNote = stretched ? ' 系统已尝试自动放慢语速铺满。' : ''
      dubWarning.value =
        mode === 'replace'
          ? `配音原始约 ${formatDuration(dubDuration)}，视频 ${formatDuration(videoDuration)}。` +
            `${stretchNote}` +
            `若末尾仍静音，请加长文案或改用「与原声混合」。`
          : `配音约 ${formatDuration(dubDuration)}，视频 ${formatDuration(videoDuration)}。` +
            `${stretchNote}` +
            `「与原声混合」模式下，配音结束后仍可听到原视频声音。`
    } else if (data.dubMeta) {
      const paceNote =
        data.dubMeta.paceMode === 'uniform'
          ? `已启用均匀语速（${data.dubMeta.segmentCount || 1} 段）。`
          : ''
      dubWarning.value = `${paceNote}配音时长约 ${formatDuration(data.dubMeta.dubDuration)}，与视频 ${formatDuration(data.dubMeta.videoDuration)} 基本匹配。`
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(loadCosyVoiceHealth)
</script>

<template>
  <div>
    <header class="header">
      <h1>视频拼接工具</h1>
      <p class="subtitle">上传视频拼接，或对单个视频添加 CosyVoice 配音</p>
    </header>

    <div
      class="dropzone"
      :class="{ dragover: isDragging }"
      @click="fileInput.click()"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
    >
      <div class="dropzone-icon">🎬</div>
      <p>拖拽视频到此处，或 <strong>点击选择文件</strong></p>
      <p style="margin-top: 0.4rem">支持 MP4、MOV、WebM 等常见格式，单文件最大 500MB</p>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept="video/*"
      multiple
      class="hidden-input"
      @change="onFileSelect"
    />

    <ul v-if="files.length" class="file-list">
      <li v-for="(file, i) in files" :key="`${file.name}-${i}`" class="file-item">
        <span class="file-index">{{ i + 1 }}</span>
        <span class="file-name" :title="file.name">{{ file.name }}</span>
        <span class="file-size">{{ formatSize(file.size) }}</span>
        <div class="file-actions">
          <button class="icon-btn" :disabled="i === 0" title="上移" @click="moveUp(i)">↑</button>
          <button
            class="icon-btn"
            :disabled="i === files.length - 1"
            title="下移"
            @click="moveDown(i)"
          >
            ↓
          </button>
          <button class="icon-btn danger" title="移除" @click="removeFile(i)">✕</button>
        </div>
      </li>
    </ul>

    <section class="dubbing-panel">
      <label class="toggle-row">
        <input v-model="dubbingEnabled" type="checkbox" :disabled="loading" />
        <span>添加 CosyVoice 配音（可选）</span>
      </label>
      <p class="dubbing-hint" :class="{ warn: cosyVoiceOk === false }">{{ cosyVoiceHint }}</p>

      <template v-if="dubbingEnabled">
        <div class="field">
          <label for="dubbing-text">配音文本</label>
          <textarea
            id="dubbing-text"
            v-model="dubbingText"
            rows="4"
            :disabled="loading"
            placeholder="输入旁白或解说词，将在视频处理完成后合成并混入"
          />
        </div>
        <div class="field-grid">
          <div class="field">
            <label for="voice-id">参考音色</label>
            <select id="voice-id" v-model="voiceId" :disabled="loading || !voiceOptions.length">
              <option v-for="voice in voiceOptions" :key="voice.id" :value="voice.id">
                {{ voice.label }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="audio-mode">原声处理</label>
            <select id="audio-mode" v-model="audioMode" :disabled="loading">
              <option value="mix">与原声混合</option>
              <option value="replace">仅保留配音</option>
            </select>
          </div>
          <div class="field">
            <label for="pace-mode">语速策略</label>
            <select id="pace-mode" v-model="paceMode" :disabled="loading">
              <option value="uniform">均匀语速（推荐）</option>
              <option value="natural">自然语速</option>
            </select>
          </div>
          <div class="field">
            <label for="speech-speed">整体语速 {{ speechSpeed.toFixed(1) }}x</label>
            <input
              id="speech-speed"
              v-model.number="speechSpeed"
              type="range"
              min="0.8"
              max="2"
              step="0.1"
              :disabled="loading"
            />
          </div>
        </div>
        <p class="dubbing-hint">
          <template v-if="paceMode === 'uniform'">
            均匀语速：按字数把每句分配到固定时长，段与段之间语速一致（推荐长文案）。
          </template>
          <template v-else>
            自然语速：保留 CosyVoice 原始节奏，仅整体适配视频，段与段之间可能快慢不一。
          </template>
          60 秒视频建议 200–350 字。
        </p>
      </template>
    </section>

    <p v-if="files.length === 1 && !dubbingEnabled" class="dubbing-hint warn">
      当前只上传了 1 个视频，请开启「添加 CosyVoice 配音」后再处理
    </p>

    <div class="actions">
      <button class="btn btn-primary" :disabled="!canConcat" @click="concatVideos">
        {{ actionLabel }}
      </button>
      <button class="btn btn-secondary" :disabled="!files.length || loading" @click="clearAll">
        清空
      </button>
    </div>

    <div v-if="loading" class="status loading">
      <span class="spinner"></span>
      {{ statusText }}
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="dubWarning" class="status" :class="dubWarning.includes('静音') ? 'warn' : 'success'">
      {{ dubWarning }}
    </div>

    <section v-if="resultUrl" class="result-section">
      <h2>{{ resultDubbed && resultCount === 1 ? '处理结果' : '拼接结果' }}</h2>
      <video class="video-player" :src="resultUrl" controls autoplay />
      <div class="result-meta">
        <span>
          {{ resultCount === 1 && resultDubbed ? '已为 1 个视频添加配音' : `共拼接 ${resultCount} 个视频` }}
          <template v-if="resultDubbed"> · 已添加 CosyVoice 配音</template>
        </span>
        <a
          :href="resultUrl"
          download="merged.mp4"
          class="btn btn-secondary"
          style="padding: 0.4rem 0.9rem; text-decoration: none; font-size: 0.85rem"
        >
          下载视频
        </a>
      </div>
    </section>
  </div>
</template>
