<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { useGeneration } from '../composables/useGeneration.js'
import ImageUploader from './ImageUploader.vue'
import ImageCollageBuilder from './ImageCollageBuilder.vue'
import ProgressBar from './ProgressBar.vue'
import VideoResult from './VideoResult.vue'
import CastPanel from './CastPanel.vue'
import DialogueTimelineEditor from './DialogueTimelineEditor.vue'
import FaceTrackPicker from './FaceTrackPicker.vue'
import ResolutionPicker from './ResolutionPicker.vue'
import { createCharacter, createUtterance, toDubCharacters, validateUtterances } from '../services/dubbing.js'
import {
  FPS as WAN_FPS,
  FRAMES_5S as WAN_FRAMES_5S,
  RES_480P,
  formatDuration,
  formatResolution,
  isValidFrameCount,
  validateWanResolution,
  TIMEOUT_5S_MS
} from '../services/frameUtils.js'
import { LTX_FPS, LTX_FRAMES_5S, LTX_OUTPUT_RES } from '../services/chainConfig.js'
import { WAN_DEFAULT_NEG, LTX_DEFAULT_NEG } from '../services/multiShotModels.js'

const props = defineProps({
  mode: { type: String, required: true },
  engine: { type: String, default: 'wan' },
  simple: { type: Boolean, default: true },
  baseGraph: { type: Object, required: true },
  lightx2vGraph: { type: Object, default: null }
})
const emit = defineEmits(['done'])

const form = reactive({
  positivePrompt:
    props.mode === 't2v'
      ? '一只橘猫在阳光下的草地上奔跑，电影感，慢动作，景深虚化'
      : props.mode === 'flf2v'
        ? '首尾帧之间平滑过渡，主体自然运动，电影感光影，连贯运镜'
        : '镜头缓慢推进，主体轻微运动，电影感光影',
  negativePrompt: props.engine === 'ltx' ? LTX_DEFAULT_NEG : WAN_DEFAULT_NEG,
  width: 1280,
  height: 720,
  length: 121,
  steps: 20,
  cfg: 3.5,
  seed: 0,
  randomSeed: true,
  batchGenerate5: false,
  dubbingEnabled: false,
  faceBindingMode: 'auto'
})
const resolutionPreset = ref('720p')
const characters = reactive([createCharacter(0)])
characters[0].voiceId = 'default.wav'
const utterances = reactive([createUtterance(0, characters[0].speakerId)])
const bindingOverrides = ref({})

const imageFile = ref(null)
const firstImageFile = ref(null)
const lastImageFile = ref(null)
/** VACE 专用：定妆照文件（与起始图分离） */
const lookbookFile = ref(null)
const imageSourceMode = ref('single')
const validationError = ref('')
/** 定妆照 input 文件名（上传 / InstantID / 手递时写入，供 VACE / 开下一段） */
const lookbookName = ref('')
const useVace = ref(false)
const handoffNotice = ref('')
/** 开下一段：直接用已在 input/ 的文件名，无需再上传 */
const pendingStartImageName = ref('')

const useLightX2V = computed(
  () => props.engine === 'wan' && props.mode === 't2v' && props.lightx2vGraph
)

const activeGraph = computed(() => (useLightX2V.value ? props.lightx2vGraph : props.baseGraph))

const presetFps = computed(() => (props.engine === 'ltx' ? LTX_FPS : WAN_FPS))
const presetFrames = computed(() => (props.engine === 'ltx' ? LTX_FRAMES_5S : WAN_FRAMES_5S))
const presetRes = computed(() =>
  props.engine === 'ltx' ? LTX_OUTPUT_RES : { width: form.width, height: form.height }
)

const resolutionLabel = computed(() => formatResolution(form.width, form.height))

const durationHint = computed(() => {
  if (!props.simple) return ''
  if (props.engine === 'wan' && props.mode === 't2v' && useLightX2V.value) {
    return `Wan 2.2 LightX2V · ${formatDuration(WAN_FRAMES_5S, WAN_FPS)} · ${resolutionLabel.value} · 可选生产配音`
  }
  if (props.engine === 'wan' && props.mode === 'i2v') {
    return `Wan 2.2 I2V · ${formatDuration(WAN_FRAMES_5S, WAN_FPS)} · ${resolutionLabel.value} · 可选生产配音`
  }
  if (props.engine === 'wan' && props.mode === 'flf2v') {
    const flf2vNote =
      form.width === RES_480P.width && form.height === RES_480P.height
        ? ' · 480P 推荐首尾帧'
        : ''
    return `Wan 2.2 首尾帧 · ${formatDuration(WAN_FRAMES_5S, WAN_FPS)} · ${resolutionLabel.value} · 复用 I2V 模型${flf2vNote}`
  }
  if (props.engine === 'ltx') {
    return `LTX 2.3 · ${formatDuration(LTX_FRAMES_5S, LTX_FPS)} · 768×512 · 约 10–20 分钟 · 不含后期配音`
  }
  return ''
})

const showAdvancedSampler = computed(() => !props.simple && !useLightX2V.value)

function onImageSourceChange(mode) {
  if (mode === imageSourceMode.value) return
  imageSourceMode.value = mode
  imageFile.value = null
}

function applyTimingPreset() {
  form.length = presetFrames.value
  form.negativePrompt = props.engine === 'ltx' ? LTX_DEFAULT_NEG : WAN_DEFAULT_NEG
  if (props.engine === 'ltx') {
    form.width = LTX_OUTPUT_RES.width
    form.height = LTX_OUTPUT_RES.height
  }
}

const {
  status,
  progress,
  progressPercent,
  currentNode,
  errorMsg,
  results,
  queueHint,
  elapsedSec,
  dubbingQa,
  dubbingSessionId,
  faceAtlas,
  bindings,
  pendingDubbing,
  isBusy,
  batchProgress,
  generate,
  generateBatch,
  renderPendingDubbing,
  resumeFromStorage
} = useGeneration(props.mode, {
  engine: props.engine,
  onDone: (record) => emit('done', record)
})

const STATUS_TEXT = {
  idle: '就绪',
  uploading: '上传图片中…',
  queued: '排队中…',
  running: '生成中…',
  analyzing: '分析人脸轨迹中…',
  awaiting_binding: '等待确认人脸绑定',
  rendering: '配音与口型渲染中…',
  done: '完成',
  error: '出错'
}

const showBatchOption = computed(
  () => props.simple && props.engine === 'wan' && ['t2v', 'i2v', 'flf2v'].includes(props.mode)
)

const submitLabel = computed(() => {
  if (isBusy.value) {
    if (batchProgress.value) {
      return `生成中 (${batchProgress.value.current}/${batchProgress.value.total})…`
    }
    return '生成中…'
  }
  if (status.value === 'awaiting_binding') return '请先确认人脸绑定'
  if (form.batchGenerate5 && showBatchOption.value) return '开始连续生成 5 次'
  return '开始生成'
})

async function onSubmit() {
  validationError.value = ''
  if (!props.simple && props.mode === 't2v' && !isValidFrameCount(form.length)) {
    validationError.value = '帧数须满足 4n+1（如 81、161、481）'
    return
  }
  if (props.engine === 'wan') {
    const resCheck = validateWanResolution(form.width, form.height)
    if (!resCheck.ok) {
      validationError.value = resCheck.error
      return
    }
  }
  if (props.engine === 'wan' && form.dubbingEnabled) {
    if (characters.length < 1 || characters.length > 4) {
      validationError.value = '配音角色数须为 1–4 人'
      return
    }
    const speakerIds = characters.map((item) => String(item.speakerId || item.id))
    if (new Set(speakerIds).size !== speakerIds.length || speakerIds.some((item) => !item.trim())) {
      validationError.value = '每个角色必须有唯一的 speakerId'
      return
    }
    const timeline = validateUtterances(utterances, { maxFrame: 125, speakerIds })
    if (!timeline.ok) {
      validationError.value = timeline.error
      return
    }
  }

  if (form.batchGenerate5 && showBatchOption.value && form.dubbingEnabled) {
    validationError.value = '连续生成与配音不能同时使用，请先关闭配音'
    return
  }

  const vaceOn = props.engine === 'wan' && props.mode === 'i2v' && useVace.value
  if (vaceOn && !lookbookFile.value && !lookbookName.value && !imageFile.value && !pendingStartImageName.value) {
    validationError.value = 'VACE 需要定妆照：请上传「定妆照」或「起始图片」'
    return
  }

  const seed = form.randomSeed ? Math.floor(Math.random() * 2 ** 31) : Number(form.seed)
  if (form.randomSeed) form.seed = seed

  const timeoutMs = useLightX2V.value ? TIMEOUT_5S_MS : undefined

  const payload = {
    positivePrompt: form.positivePrompt,
    negativePrompt: form.negativePrompt,
    width: Number(form.width),
    height: Number(form.height),
    length: Number(form.length),
    steps: Number(form.steps),
    cfg: Number(form.cfg),
    seed,
    randomSeed: form.randomSeed,
    useLightX2V: Boolean(useLightX2V.value),
    fps: presetFps.value,
    imageFile: imageFile.value,
    imageName: pendingStartImageName.value || undefined,
    firstImageFile: firstImageFile.value,
    lastImageFile: lastImageFile.value,
    useVace: vaceOn,
    lookbookFile: vaceOn ? lookbookFile.value : undefined,
    lookbookName: lookbookName.value || undefined,
    refImageName: lookbookName.value || undefined,
    dubbingEnabled: props.engine === 'wan' && props.mode !== 'flf2v' && form.dubbingEnabled,
    characters: toDubCharacters(characters),
    utterances: utterances.map((item) => ({ ...item })),
    faceBindingMode: form.faceBindingMode,
    hint: durationHint.value || undefined
  }

  if (form.batchGenerate5 && showBatchOption.value) {
    await generateBatch(payload, null, { count: 5, timeoutMs })
  } else {
    await generate(payload, null, { timeoutMs })
  }
  pendingStartImageName.value = ''
}

function onHandoff({ mode, lastFrameName, lookbookName: lb }) {
  const lookbook = lb || lookbookName.value
  if (!lookbook && mode !== 'last') {
    handoffNotice.value = '缺少定妆照：请先上传定妆照，或用起始图生成一段'
    return
  }
  imageFile.value = null
  lookbookFile.value = null
  handoffNotice.value = ''
  pendingStartImageName.value = ''
  if (mode === 'lookbook') {
    lookbookName.value = lookbook
    pendingStartImageName.value = lookbook
    useVace.value = false
    handoffNotice.value = `已设起始图为定妆照「${lookbook}」，可直接点生成`
  } else if (mode === 'vace-ref') {
    lookbookName.value = lookbook
    pendingStartImageName.value = lookbook
    useVace.value = true
    handoffNotice.value = `已设 VACE 参考=定妆照「${lookbook}」，起始暂同定妆照；可再换一张「起始图片」`
  } else if (mode === 'last+lookbook') {
    if (!lastFrameName) {
      handoffNotice.value = '缺少末帧，无法用末帧+定妆照开下一段'
      return
    }
    lookbookName.value = lookbook
    pendingStartImageName.value = lastFrameName
    useVace.value = true
    handoffNotice.value = `已设起始=末帧「${lastFrameName}」+ VACE 参考定妆照「${lookbook}」`
  }
}

watch(useVace, (on) => {
  if (!on) lookbookFile.value = null
})

async function onConfirmBindings() {
  await renderPendingDubbing(bindingOverrides.value)
}

watch(() => form.dubbingEnabled, (enabled) => {
  if (enabled && showBatchOption.value) form.batchGenerate5 = false
})

watch(() => form.batchGenerate5, (enabled) => {
  if (enabled && showBatchOption.value) form.dubbingEnabled = false
})

watch(bindings, (value) => {
  bindingOverrides.value = { ...(value || {}) }
}, { deep: true, immediate: true })

watch(pendingDubbing, (value) => {
  if (!value) return
  characters.splice(0, characters.length, ...(value.characters || []).map((item) => ({ ...item })))
  utterances.splice(0, utterances.length, ...(value.utterances || []).map((item) => ({ ...item })))
  form.faceBindingMode = value.faceBindingMode || 'auto'
}, { deep: true })

watch(results, (list) => {
  const first = list?.[0]
  if (first?.lookbookName || first?.startImageName) {
    lookbookName.value = first.lookbookName || first.startImageName || lookbookName.value
  }
}, { deep: true })

onMounted(() => {
  applyTimingPreset()
  if (props.engine === 'wan' && props.mode === 'flf2v') {
    resolutionPreset.value = '480p'
    form.width = RES_480P.width
    form.height = RES_480P.height
  }
  if (!props.simple && props.mode === 't2v' && props.lightx2vGraph) {
    form.length = WAN_FRAMES_5S
  }
  resumeFromStorage()
})
</script>

<template>
  <div class="row" style="flex-wrap: wrap">
    <div class="panel" style="flex: 1 1 420px; min-width: 340px">
      <div v-if="durationHint" class="field">
        <div class="muted hint-box">{{ durationHint }}</div>
      </div>

      <div v-if="mode === 'flf2v'" class="field">
        <label>首帧图片</label>
        <ImageUploader v-model="firstImageFile" :disabled="isBusy" />
      </div>

      <div v-if="mode === 'flf2v'" class="field">
        <label>尾帧图片</label>
        <ImageUploader v-model="lastImageFile" :disabled="isBusy" />
      </div>

      <div v-if="mode === 'i2v'" class="field">
        <label>起始图片（场景开场）</label>
        <template v-if="!simple">
          <div class="image-source-tabs">
            <button
              type="button"
              class="btn-mini"
              :class="{ active: imageSourceMode === 'single' }"
              :disabled="isBusy"
              @click="onImageSourceChange('single')"
            >
              单张上传
            </button>
            <button
              type="button"
              class="btn-mini"
              :class="{ active: imageSourceMode === 'collage' }"
              :disabled="isBusy"
              @click="onImageSourceChange('collage')"
            >
              拼图（最多 9 张）
            </button>
          </div>
        </template>
        <ImageUploader v-if="simple || imageSourceMode === 'single'" v-model="imageFile" :disabled="isBusy" />
        <ImageCollageBuilder
          v-else
          v-model="imageFile"
          :output-width="form.width"
          :output-height="form.height"
          :disabled="isBusy"
        />
        <label
          v-if="engine === 'wan' && mode === 'i2v'"
          class="toggle-row"
          style="margin-top: 8px"
        >
          <input v-model="useVace" type="checkbox" :disabled="isBusy" />
          <span>Wan-VACE 参考引导（另传定妆照锁身份）</span>
        </label>
        <div v-if="engine === 'wan' && mode === 'i2v' && useVace" class="field" style="margin-top: 10px">
          <label>定妆照 / VACE 参考（锁脸，勿与起始图相同）</label>
          <ImageUploader v-model="lookbookFile" :disabled="isBusy" />
          <p class="muted" style="font-size: 12px; margin-top: 6px">
            未单独上传时回退用起始图作参考（首帧会很像起始图）。推荐：正脸定妆照 ≠ 场景起始图。
          </p>
        </div>
        <p v-if="lookbookName || pendingStartImageName" class="muted" style="font-size: 12px; margin-top: 6px">
          <template v-if="pendingStartImageName">下一段起始：{{ pendingStartImageName }}</template>
          <template v-if="lookbookName"> · 定妆照：{{ lookbookName }}</template>
        </p>
        <p v-if="handoffNotice" class="muted hint-box" style="margin-top: 6px">{{ handoffNotice }}</p>
      </div>

      <div class="field">
        <label>正向提示词</label>
        <textarea v-model="form.positivePrompt" placeholder="描述你想要的画面、动作、镜头、风格…"></textarea>
      </div>

      <div class="field">
        <label>负向提示词</label>
        <textarea v-model="form.negativePrompt"></textarea>
      </div>

      <ResolutionPicker
        v-if="engine === 'wan'"
        v-model:width="form.width"
        v-model:height="form.height"
        v-model:preset="resolutionPreset"
        :disabled="isBusy"
      />

      <div v-if="engine === 'wan' && mode !== 'flf2v'" class="dub-box">
        <label class="toggle-row">
          <input
            v-model="form.dubbingEnabled"
            type="checkbox"
            :disabled="isBusy || (form.batchGenerate5 && showBatchOption)"
          />
          <span>为此 5 秒视频生成配音（CosyVoice 3 / 25fps / 48kHz）</span>
        </label>
        <template v-if="form.dubbingEnabled">
          <div class="field binding-mode">
            <label>人脸绑定</label>
            <select v-model="form.faceBindingMode" :disabled="isBusy">
              <option value="auto">自动，歧义时人工确认</option>
              <option value="manual">始终人工确认</option>
            </select>
          </div>
          <CastPanel v-model="characters" :disabled="isBusy" :min="1" :max="4" />
          <DialogueTimelineEditor
            v-model="utterances"
            :characters="characters"
            :max-frame="125"
            :disabled="isBusy"
          />
          <div class="muted dub-hint">
            台词使用 [startFrame, endFrame) 区间，严格禁止重叠；视频生成后先分析人脸，再执行配音渲染。
          </div>
          <FaceTrackPicker
            v-if="status === 'awaiting_binding' && dubbingSessionId"
            v-model="bindingOverrides"
            :session-id="dubbingSessionId"
            :tracks="faceAtlas?.tracks || []"
            :characters="characters"
            :disabled="isBusy"
            @confirm="onConfirmBindings"
          />
        </template>
      </div>

      <template v-if="!simple">
        <div class="grid-3">
          <template v-if="engine !== 'wan'">
            <div class="field">
              <label>宽度</label>
              <input type="number" v-model.number="form.width" step="8" min="16" />
            </div>
            <div class="field">
              <label>高度</label>
              <input type="number" v-model.number="form.height" step="8" min="16" />
            </div>
          </template>
          <div class="field" :class="{ 'span-3': engine === 'wan' }">
            <label>帧数 (length)</label>
            <input type="number" v-model.number="form.length" step="4" min="1" />
          </div>
        </div>

        <div v-if="showAdvancedSampler" class="grid-3">
          <div class="field">
            <label>步数 (steps)</label>
            <input type="number" v-model.number="form.steps" min="1" />
          </div>
          <div class="field">
            <label>CFG</label>
            <input type="number" v-model.number="form.cfg" step="0.1" min="0" />
          </div>
          <div class="field">
            <label>随机种子</label>
            <input type="number" v-model.number="form.seed" :disabled="form.randomSeed" />
          </div>
        </div>
        <div v-else-if="useLightX2V" class="grid-3">
          <div class="field">
            <label>采样</label>
            <div class="muted" style="font-size: 13px; padding-top: 8px">LightX2V 4 步 / CFG 1.0</div>
          </div>
          <div class="field">
            <label>帧率</label>
            <div class="muted" style="font-size: 13px; padding-top: 8px">{{ WAN_FPS }} fps</div>
          </div>
          <div class="field">
            <label>随机种子</label>
            <input type="number" v-model.number="form.seed" :disabled="form.randomSeed" />
          </div>
        </div>
      </template>

      <div v-if="simple" class="field">
        <label>随机种子</label>
        <input type="number" v-model.number="form.seed" :disabled="form.randomSeed" />
      </div>

      <label class="muted" style="display: flex; align-items: center; gap: 6px; font-size: 13px">
        <input type="checkbox" v-model="form.randomSeed" style="width: auto" />
        每次随机种子
      </label>

      <label
        v-if="showBatchOption"
        class="muted batch-option"
        :class="{ disabled: form.dubbingEnabled }"
      >
        <input
          v-model="form.batchGenerate5"
          type="checkbox"
          style="width: auto"
          :disabled="isBusy || form.dubbingEnabled"
        />
        <span>连续生成 5 次（顺序执行，非并发）</span>
      </label>

      <div style="margin-top: 16px">
        <button class="btn" :disabled="isBusy || status === 'awaiting_binding'" @click="onSubmit">
          {{ submitLabel }}
        </button>
      </div>

      <div class="status-line">
        <span class="dot" :class="{ ok: status === 'done', err: status === 'error' }"></span>
        <span>{{ STATUS_TEXT[status] || status }}</span>
        <span v-if="elapsedSec > 0" class="muted">· 已等待 {{ elapsedSec }}s</span>
        <span v-if="status === 'running' && currentNode">· 节点 {{ currentNode }}</span>
      </div>

      <div v-if="queueHint" class="muted" style="font-size: 12px; margin-top: 6px">{{ queueHint }}</div>

      <div v-if="isBusy" style="margin-top: 10px">
        <ProgressBar :percent="progressPercent" />
        <div class="muted" style="font-size: 12px; margin-top: 6px">
          <template v-if="progress.max > 0">
            采样进度 {{ progress.value }} / {{ progress.max }} ({{ progressPercent }}%)
          </template>
          <template v-else>等待 ComfyUI 返回采样进度…（若排队较久属正常）</template>
        </div>
      </div>

      <div v-if="validationError || errorMsg" class="error-box">{{ validationError || errorMsg }}</div>
      <div v-if="dubbingQa" class="muted dub-qa">
        配音 QA：{{ dubbingQa.ok ? '通过' : '未通过' }}
        <span v-if="dubbingQa.loudness?.integratedLufs != null">
          · {{ dubbingQa.loudness.integratedLufs }} LUFS
        </span>
      </div>
    </div>

    <div class="panel" style="flex: 1 1 420px; min-width: 340px">
      <div class="section-title"><h3>生成结果</h3></div>
      <VideoResult
        v-if="results.length"
        :results="results"
        :busy="isBusy"
        :show-handoff="engine === 'wan' && mode === 'i2v'"
        :lookbook-name="lookbookName || results[0]?.lookbookName || results[0]?.startImageName || ''"
        @handoff="onHandoff"
      />
      <div v-else class="empty">提交任务后，生成的视频会显示在这里。</div>
    </div>
  </div>
</template>

<style scoped>
.hint-box {
  font-size: 12px;
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(255, 200, 80, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(255, 200, 80, 0.2);
}
.image-source-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.btn-mini {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.btn-mini.active {
  border-color: rgba(80, 200, 120, 0.55);
  background: rgba(80, 200, 120, 0.12);
}
.dub-box {
  margin: 14px 0;
  padding: 12px;
  border: 1px solid rgba(120, 180, 255, 0.25);
  border-radius: 8px;
  background: rgba(120, 180, 255, 0.06);
}
.toggle-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toggle-row input {
  width: auto;
}
.frame-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}
.frame-inputs input {
  min-width: 0;
}
.dub-hint,
.dub-qa {
  margin-top: 8px;
  font-size: 12px;
}
.batch-option {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 13px;
}
.batch-option.disabled {
  opacity: 0.55;
}
.span-3 {
  grid-column: 1 / -1;
}
</style>
