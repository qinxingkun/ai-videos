<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import {
  useMultiShotGeneration,
  DEFAULT_SHOTS,
  DEFAULT_STYLE_SUFFIX,
  DEFAULT_CHARACTER
} from '../composables/useMultiShotGeneration.js'
import { DEFAULT_CHARACTERS, DEFAULT_DIALOGUE_SHOTS, applyTwoPersonDialogueTestCase, applyLongStoryTestCase, applyLtxHiksemiJanitorTestCase } from '../services/dialoguePrompt.js'
import { getMultiShotProfile, LTX_DEFAULT_NEG } from '../services/multiShotModels.js'
import { listCharacters, saveCharacter } from '../services/orchestrator.js'
import { validateCharacterBible } from '../services/characterBible.js'
import {
  DURATION_PRESETS,
  DEFAULT_DURATION_PRESET,
  MAX_SEGMENT_SEC,
  padShotsToCount,
  resolveRunConfig
} from '../services/durationPresets.js'
import ImageUploader from './ImageUploader.vue'
import ImageCollageBuilder from './ImageCollageBuilder.vue'
import ProgressBar from './ProgressBar.vue'
import VideoResult from './VideoResult.vue'
import CastPanel from './CastPanel.vue'
import FaceTrackPicker from './FaceTrackPicker.vue'
import DialogueTimelineEditor from './DialogueTimelineEditor.vue'
import ResolutionPicker from './ResolutionPicker.vue'
import {
  estimatedMasterMaxFrame,
  mergeUtterancesFromShots,
  validateUtterances
} from '../services/dubbing.js'
import { RES_720P, formatResolution, validateWanResolution } from '../services/frameUtils.js'

const props = defineProps({
  engine: { type: String, required: true },
  mode: { type: String, default: 't2v' }
})
const emit = defineEmits(['done'])

const profile = computed(() => getMultiShotProfile(props.engine, props.mode))

const outputWidth = ref(RES_720P.width)
const outputHeight = ref(RES_720P.height)
const resolutionPreset = ref('720p')

const effectiveRes = computed(() =>
  props.engine === 'wan'
    ? { width: outputWidth.value, height: outputHeight.value }
    : profile.value.res
)

const resolutionLabel = computed(() => formatResolution(effectiveRes.value.width, effectiveRes.value.height))

const engineLabel = computed(() => (props.engine === 'wan' ? 'Wan 2.2' : 'LTX 2.3'))

const durationPreset = ref(DEFAULT_DURATION_PRESET)
const durationPresetOptions = Object.values(DURATION_PRESETS)
const runConfig = computed(() => resolveRunConfig(durationPreset.value, props.engine, profile.value))
const presetHint = computed(() => {
  const c = runConfig.value
  const anchorHint = c.anchorRefreshEvery
    ? `；每 ${c.anchorRefreshEvery} 段 FLF2V 锚点刷新 + 锚点软拉回权重 ${c.anchorBlendWeight}`
    : ''
  return `${c.shotCount} 段 × ${c.segmentSec}s（成片约 ${c.expectedFinalSec}s，头尾各裁 ${c.discardZoneSec}s${anchorHint}）`
})
/** 长链生产（>=12 段，对应 90s 预设）建议强制场景圣经非空，与 useMultiShotGeneration 的硬校验一致 */
const sceneBibleRequired = computed(() => runConfig.value.shotCount >= 12)

const styleSuffix = ref(DEFAULT_STYLE_SUFFIX.trim().replace(/^,\s*/, ''))
const baseSeed = ref(100)
const imageFile = ref(null)
const imageSourceMode = ref('single')
const copied = ref(false)
const continuityMode = ref(props.mode === 'i2v' ? 'chain+anchor' : 'production')
/** T2V 不允许定妆照；仅 I2V 模式使用图片锚定 */
const productionSeg1I2v = ref(false)
/** LTX 不支持配音/对白生产；仅 Wan 可开配音 */
const dialogueMode = ref(false)
const dubbingEnabled = ref(false)
const faceBindingMode = ref('auto')
const utterances = ref([])
const sceneBible = ref('')
/** 接缝微观插帧（RIFE，需 ComfyUI-Frame-Interpolation）：默认关闭，失败自动回退 micro-xfade */
const seamInterp = ref(false)
/** 阶段四（可选）：关键镜头（默认首尾两段）身份锁定重渲染（Wan2.2-Animate），默认关闭 */
const animateRelock = ref(false)
const useVace = ref(false)

const usesProduction = computed(
  () => props.mode === 't2v' && continuityMode.value === 'production'
)

const showMultiCast = computed(
  () => props.engine === 'wan' && (usesProduction.value || dubbingEnabled.value)
)

const needsImageUpload = computed(() => props.mode === 'i2v')

const character = reactive({ ...DEFAULT_CHARACTER })
const characters = reactive(DEFAULT_CHARACTERS.map((c, index) => ({
  ...c,
  speakerId: c.speakerId || c.id || `speaker-${index + 1}`,
  voiceId: c.voiceId || '',
  referenceImageName: c.referenceImageName || '',
  faceTrackId: c.faceTrackId || null
})))

const CHARACTER_FIELD_LABELS = { face: '脸型/五官', hair: '发型', clothing: '服装', immutable: '不可变特征' }
/** 角色圣经必填字段校验：缺失时在 UI 提示，而非静默跳过导致长链人设漂移 */
const characterBibleCheck = computed(() => validateCharacterBible(character))

function defaultLipSyncPolicy(prompt = '') {
  return /(close(?:-up| medium)?|特写|近景|近距离)/i.test(prompt) ? 'preferred' : 'off'
}

const shots = reactive(
  DEFAULT_SHOTS.map(([name, prompt]) => ({
    name,
    prompt,
    dialogue: '',
    startFrame: null,
    endFrame: null,
    lipSyncPolicy: defaultLipSyncPolicy(prompt)
  }))
)
const sceneGroups = reactive(DEFAULT_SHOTS.map(() => 0))

function syncShotCount(count) {
  const padded = padShotsToCount(shots, count)
  for (const shot of padded) {
    if (!Object.hasOwn(shot, 'startFrame')) shot.startFrame = null
    if (!Object.hasOwn(shot, 'endFrame')) shot.endFrame = null
    if (!shot.lipSyncPolicy) shot.lipSyncPolicy = defaultLipSyncPolicy(shot.prompt)
  }
  shots.splice(0, shots.length, ...padded)
  while (sceneGroups.length < count) sceneGroups.push(0)
  while (sceneGroups.length > count) sceneGroups.pop()
}

watch(
  () => runConfig.value.shotCount,
  (n) => syncShotCount(n),
  { immediate: true }
)

const {
  status,
  statusLabel,
  currentShot,
  totalShots,
  shotResults,
  errorMsg,
  concatCommand,
  finalVideo,
  splicePlan,
  orchestratorOnline,
  elapsedSec,
  progressPercent,
  grammarWarnings,
  dubbingStatus,
  dubbingQa,
  dubbingSessionId,
  faceAtlas,
  bindingOverrides,
  bindings,
  lastDubError,
  renderPendingDubbing,
  resumeFromStorage,
  isBusy,
  isBindingInteractive,
  generateShots,
  regenerateFromShot,
  probeOrchestrator
} = useMultiShotGeneration({
  engine: props.engine,
  mode: props.mode,
  onDone: (record) => emit('done', record)
})

const qaRows = computed(() =>
  shotResults.value.map((r, i) => ({
    index: i + 1,
    qaIssues: r.qaIssues || [],
    seamMotionScore: r.seamMotionScore,
    avgSimilarity: r.avgSimilarity ?? r.identity?.avgSimilarity ?? null,
    faceGateFallback: !!r.faceGateFallback,
    animateRelockApplied: r.animateRelockApplied || false,
    ok: !(r.qaIssues || []).length
  }))
)
const hasQaData = computed(() =>
  qaRows.value.some(
    (r) =>
      r.seamMotionScore != null ||
      r.qaIssues.length ||
      r.animateRelockApplied ||
      r.avgSimilarity != null ||
      r.faceGateFallback
  )
)

const masterMaxFrame = computed(() =>
  estimatedMasterMaxFrame(runConfig.value.shotCount, runConfig.value.frames)
)

const utteranceValidation = computed(() =>
  validateUtterances(utterances.value, {
    maxFrame: masterMaxFrame.value,
    speakerIds: characters.map((item) => String(item.speakerId || item.id))
  })
)

const bindingRows = computed(() =>
  characters.map((character) => {
    const speakerId = character.speakerId || character.id
    const binding = (bindings.value || []).find((item) => item.speakerId === speakerId) || {}
    return {
      speakerId,
      name: character.name,
      status: binding.status || (bindingOverrides.value[speakerId] ? 'manual' : 'pending'),
      faceTrackId: bindingOverrides.value[speakerId] || binding.faceTrackId || null,
      candidateTrackId: binding.candidateTrackId || null,
      confidence: binding.confidence,
      reason: binding.reason || null
    }
  })
)

function syncUtterancesFromShots({ preserveEdits = true } = {}) {
  if (!(props.engine === 'wan' && dubbingEnabled.value)) return
  const next = preserveEdits
    ? mergeUtterancesFromShots(utterances.value, shots, characters, {
        framesPerShot: runConfig.value.frames
      })
    : mergeUtterancesFromShots([], shots, characters, {
        framesPerShot: runConfig.value.frames
      })
  utterances.value = next
}

watch(
  () => [dubbingEnabled.value, runConfig.value.shotCount, runConfig.value.frames, JSON.stringify(shots.map((s) => [s.dialogue, s.startFrame, s.endFrame, s.lipSyncPolicy])), JSON.stringify(characters.map((c) => [c.id, c.speakerId, c.name]))],
  () => {
    if (props.engine === 'wan' && dubbingEnabled.value) syncUtterancesFromShots()
  }
)

function loadDialogueTemplate() {
  if (props.engine !== 'wan') return
  applyTwoPersonDialogueTestCase({
    dialogueMode,
    styleSuffix,
    baseSeed,
    characters,
    shots,
    sceneBible,
    continuityMode,
    productionSeg1I2v
  })
  dialogueMode.value = false
  dubbingEnabled.value = true
  syncShotCount(runConfig.value.shotCount)
  syncUtterancesFromShots({ preserveEdits: false })
}

function loadHiksemiStory() {
  applyLtxHiksemiJanitorTestCase(
    {
      dialogueMode,
      styleSuffix,
      baseSeed,
      character,
      characters,
      shots,
      sceneBible,
      continuityMode,
      productionSeg1I2v,
      durationPreset,
      dubbingEnabled
    },
    { mode: props.mode }
  )
  syncShotCount(runConfig.value.shotCount)
}

function loadStoryTemplate() {
  if (props.engine === 'ltx') {
    loadHiksemiStory()
    return
  }
  applyLongStoryTestCase(
    {
      dialogueMode,
      styleSuffix,
      baseSeed,
      characters,
      shots,
      sceneBible,
      continuityMode,
      productionSeg1I2v
    },
    { engine: props.engine, withDialogue: props.engine === 'wan' && dubbingEnabled.value }
  )
  if (props.engine !== 'wan') dialogueMode.value = false
  syncShotCount(runConfig.value.shotCount)
}

const storyTemplateButtonLabel = computed(() =>
  props.engine === 'ltx' ? '加载默认剧情（海康扫地生）' : '加载长剧情测试用例（咖啡馆谈判）'
)

const savedCharacters = ref([])
const saveCharName = ref('')

async function refreshCharacters() {
  try {
    savedCharacters.value = await listCharacters()
  } catch {
    savedCharacters.value = []
  }
}

async function onSaveCharacter() {
  const label = saveCharName.value.trim() || character.name || '角色'
  const id = label.replace(/\s+/g, '_').toLowerCase() + '_' + Date.now()
  await saveCharacter({ id, name: label, character: { ...character } })
  saveCharName.value = ''
  await refreshCharacters()
}

function loadCharacterPreset(c) {
  Object.assign(character, DEFAULT_CHARACTER, c.character || {})
}

function onImageSourceChange(mode) {
  if (mode === imageSourceMode.value) return
  imageSourceMode.value = mode
  imageFile.value = null
}

onMounted(async () => {
  await probeOrchestrator()
  if (orchestratorOnline.value) await refreshCharacters()
  const resumed = await resumeFromStorage()
  // LTX I2V/T2V：无恢复任务时默认填入海康「扫地生」剧情用例
  if (!resumed && props.engine === 'ltx') {
    loadHiksemiStory()
  }
})

async function onSubmit() {
  if (props.engine === 'wan' && dubbingEnabled.value) {
    syncUtterancesFromShots()
    if (!utteranceValidation.value.ok) {
      errorMsg.value = utteranceValidation.value.error
      return
    }
  }
  if (props.engine === 'wan') {
    const resCheck = validateWanResolution(outputWidth.value, outputHeight.value)
    if (!resCheck.ok) {
      errorMsg.value = resCheck.error
      return
    }
  }
  const list = shots.map((s) => ({
    name: s.name,
    prompt: s.prompt,
    dialogue: s.dialogue,
    startFrame: s.startFrame,
    endFrame: s.endFrame,
    lipSyncPolicy: s.lipSyncPolicy,
    storyBeat: s.storyBeat,
    forceT2v: !!s.forceT2v,
    ambientSound: s.ambientSound || '',
    presentCharacterIds: Array.isArray(s.presentCharacterIds) ? [...s.presentCharacterIds] : undefined
  }))
  const p = profile.value
  await generateShots({
    shots: list,
    styleSuffix: styleSuffix.value,
    negativePrompt: props.engine === 'ltx' ? LTX_DEFAULT_NEG : p.defaultNeg,
    width: effectiveRes.value.width,
    height: effectiveRes.value.height,
    baseSeed: baseSeed.value,
    imageFile: props.mode === 'i2v' ? imageFile.value : undefined,
    character: { ...character },
    // Wan 配音多角色，或 LTX 海康等已加载的三人卡司，都注入 cast
    characters:
      showMultiCast.value || (props.engine === 'ltx' && characters.length > 0)
        ? characters.map((c) => ({ ...c }))
        : [],
    utterances: props.engine === 'wan' && dubbingEnabled.value ? utterances.value.map((item) => ({ ...item })) : undefined,
    dialogueMode: false,
    dubbingEnabled: props.engine === 'wan' && dubbingEnabled.value,
    faceBindingMode: faceBindingMode.value,
    continuityMode: continuityMode.value,
    productionSeg1I2v: false,
    sceneBible: sceneBible.value,
    sceneGroups: [...sceneGroups],
    durationPreset: durationPreset.value,
    seamInterp: props.engine === 'wan' && seamInterp.value,
    animateRelock: props.engine === 'wan' && animateRelock.value,
    useVace: props.engine === 'wan' && props.mode === 'i2v' && useVace.value
  })
}

async function onRegenerate(index) {
  await regenerateFromShot(index)
}

async function onConfirmBindings() {
  try {
    await renderPendingDubbing(bindingOverrides.value)
  } catch (e) {
    errorMsg.value = e.message || '配音渲染失败'
  }
}

async function copyConcatCommand() {
  if (!concatCommand.value) return
  try {
    await navigator.clipboard.writeText(concatCommand.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    /* noop */
  }
}
</script>

<template>
  <div class="row" style="flex-wrap: wrap">
    <div class="panel" style="flex: 1 1 480px; min-width: 360px">
      <div class="section-title">
        <h3>
          {{ engineLabel }} · {{ mode === 'i2v' ? '图生视频 I2V 短剧' : '文生视频 T2V' }} ·
          {{ runConfig.shotCount }} 段 × {{ runConfig.segmentSec }} 秒
        </h3>
      </div>
      <p class="muted intro">
        <template v-if="engine === 'ltx' && mode === 't2v'">
          段1 T2V 定调 → 中间段 I2V 链式 → 末段 FLF2V → 简单拼接。LTX 不做 Smart Splice / 重复帧质检，直接用模型原生出片。
        </template>
        <template v-else-if="engine === 'wan' && mode === 't2v'">
          生产方案：Smart Splice + {{ resolutionLabel }}。段1 T2V 定调 → 后续 I2V 链式 → 自动拼接，可选成片配音与口型同步
          （无 FLF2V）。
        </template>
        <template v-else-if="engine === 'wan' && mode === 'i2v'">
          {{ runConfig.shotCount }} 段 I2V 链式衔接，{{ resolutionLabel }}，可选成片配音；需上传定妆照 + 启动后端。
        </template>
        <template v-else-if="engine === 'ltx' && mode === 'i2v'">
          {{ runConfig.shotCount }} 段 I2V 链式衔接（含 FLF2V 刷新）+ 简单拼接；需上传定妆照。LTX 不做成片质检门禁。
        </template>
        <template v-else>
          串行生成 {{ runConfig.shotCount }} 段，链式末帧衔接 + 角色圣经保持人脸一致。
        </template>
        {{ profile.description }}
      </p>

      <ResolutionPicker
        v-if="engine === 'wan'"
        v-model:width="outputWidth"
        v-model:height="outputHeight"
        v-model:preset="resolutionPreset"
        :disabled="isBusy"
      />

      <div class="field">
        <label>成片时长预设</label>
        <select v-model="durationPreset" :disabled="isBusy">
          <option v-for="p in durationPresetOptions" :key="p.id" :value="p.id">{{ p.label }}</option>
        </select>
        <p class="muted hint-box">
          {{ presetHint }}。单段最长 {{ MAX_SEGMENT_SEC }}s；90s 靠增加段数（Wan LightX2V
          串行约数十分钟量级）。
        </p>
        <template v-if="engine === 'wan'">
          <label class="toggle-row" style="margin-top: 8px">
            <input v-model="seamInterp" type="checkbox" :disabled="isBusy" />
            <span>接缝微观插帧（RIFE，需 ComfyUI-Frame-Interpolation；未安装/失败自动回退硬切拼接）</span>
          </label>
          <label class="toggle-row" style="margin-top: 6px">
            <input v-model="animateRelock" type="checkbox" :disabled="isBusy" />
            <span>
              关键镜头 Animate 兜底（VACE/I2V 初渲 + ArcFace 质检之后；默认首尾两段；失败回退初渲）
            </span>
          </label>
          <label v-if="mode === 'i2v'" class="toggle-row" style="margin-top: 6px">
            <input v-model="useVace" type="checkbox" :disabled="isBusy" />
            <span>
              Wan-VACE 参考图引导（定妆照 → ref_images；需 VACE 权重；无脸末帧仍靠定妆照锁身份）
            </span>
          </label>
        </template>
        <p v-else class="muted hint-box" style="margin-top: 8px">
          LTX 多分镜仅用模型原生出片 + 简单拼接，不做 Smart Splice / 重复帧 / 段级质检门禁。
        </p>
      </div>

      <div class="dialogue-bar">
        <template v-if="engine === 'wan'">
          <label class="toggle-row">
            <input v-model="dubbingEnabled" type="checkbox" :disabled="isBusy" />
            <span>Wan 成片生产配音（25fps / 48kHz，多人指定说话人）</span>
          </label>
          <div v-if="dubbingEnabled" class="field binding-mode">
            <label>人脸绑定</label>
            <select v-model="faceBindingMode" :disabled="isBusy">
              <option value="auto">自动，歧义时人工确认</option>
              <option value="manual">始终人工确认</option>
            </select>
          </div>
          <button
            v-if="mode === 't2v'"
            type="button"
            class="btn-mini"
            :disabled="isBusy"
            @click="loadDialogueTemplate"
          >
            加载双人配音测试用例
          </button>
        </template>
        <p v-else class="muted" style="margin: 0">LTX 多分镜不支持配音（无 CosyVoice / 口型管线）。</p>
        <button type="button" class="btn-mini" :disabled="isBusy" @click="loadStoryTemplate">
          {{ storyTemplateButtonLabel }}
        </button>
      </div>

      <div v-if="showMultiCast" class="character-card multi-cast">
        <CastPanel v-model="characters" :disabled="isBusy" :min="2" :max="4" compact />
      </div>

      <div v-if="engine === 'wan' && dubbingEnabled" class="dub-structure-box">
        <div class="dub-structure-actions">
          <button type="button" class="btn-mini" :disabled="isBusy" @click="syncUtterancesFromShots({ preserveEdits: false })">
            从分镜台词同步时间线
          </button>
          <span class="muted">全片帧范围 0–{{ masterMaxFrame }}（按 25fps 母版口径校验）</span>
        </div>
        <DialogueTimelineEditor
          v-model="utterances"
          :characters="characters"
          :max-frame="masterMaxFrame"
          :disabled="isBusy"
        />
        <p v-if="!utteranceValidation.ok" class="warn-hint">{{ utteranceValidation.error }}</p>
      </div>

      <div v-if="orchestratorOnline !== null" class="orch-status">
        <span class="dot" :class="{ ok: orchestratorOnline, err: orchestratorOnline === false }"></span>
        <span v-if="orchestratorOnline">辅助服务已连接（链式抽帧 / 自动拼接）</span>
        <span v-else-if="orchestratorOnline === false">
          辅助服务未启动 — 请运行 <code>cd backend && python main.py</code>
        </span>
        <span v-else>检测辅助服务…</span>
      </div>

      <div v-if="mode === 't2v'" class="field">
        <label>生产模式</label>
        <select v-model="continuityMode" :disabled="isBusy">
          <option value="production">
            混合生产（推荐：T2V定调 + I2V链式{{ engine === 'ltx' ? ' + FLF2V' : '' }}）
          </option>
          <option value="anchor">独立 T2V（{{ runConfig.shotCount }} 段互不衔接）</option>
        </select>
      </div>

      <div v-if="mode === 't2v' && continuityMode === 'production'" class="field continuity-hint">
        <label>混合生产流程</label>
        <p class="muted hint-box">
          <template v-if="engine === 'ltx'">
            段1 T2V 定调 → 中间段 I2V 链式（以上段有效区末帧衔接）→ 末段 FLF2V（锚点=段1首帧）→ Smart
            Splice（头尾各裁 {{ runConfig.discardZoneSec }}s + 2帧 micro-xfade）。T2V 不上传定妆照。
          </template>
          <template v-else>
            段1 T2V 定调 → 后续 I2V 链式 → Smart Splice。T2V 不上传定妆照。
          </template>
          需启动后端 API。
        </p>
      </div>

      <div v-if="mode === 't2v' && continuityMode === 'anchor'" class="field continuity-hint">
        <label>独立 T2V</label>
        <p class="muted hint-box">
          {{ runConfig.shotCount }} 段独立 T2V，靠场景圣经 + 角色卡；拼接短淡入淡出。人脸一致较弱，但无衔接重复。
        </p>
      </div>

      <div class="field">
        <label>
          场景圣经（全段共用：地点 / 时间 / 天气，保持剧情一致）
          <span v-if="sceneBibleRequired" class="required-tag">长链必填</span>
        </label>
        <textarea
          v-model="sceneBible"
          rows="3"
          :disabled="isBusy"
          placeholder="例：晴朗午后同一咖啡馆，连续时间线，无换场…"
        ></textarea>
        <p v-if="sceneBibleRequired && !sceneBible.trim()" class="warn-hint">
          当前预设 {{ runConfig.shotCount }} 段（长链生产），未填写场景圣经会显著放大跨段漂移，生成前必须补全。
        </p>
      </div>

      <div v-if="grammarWarnings.length" class="warn-box">
        <label class="card-label">镜头语法提示（不阻断生成，建议手动调整景别）</label>
        <ul>
          <li v-for="(w, i) in grammarWarnings" :key="i">{{ w.message }}</li>
        </ul>
      </div>

      <div v-if="mode === 'i2v'" class="field">
        <label>一致性模式</label>
        <select v-model="continuityMode" :disabled="isBusy">
          <option v-if="engine === 'ltx'" value="chain+anchor">链式 + 每 3 段 FLF2V 刷新（推荐）</option>
          <option v-if="engine === 'wan'" value="chain+anchor">链式 + 段1定妆照锚定（推荐）</option>
          <option value="chain">纯链式（上段末帧 → 下段首帧）</option>
          <option value="anchor">仅定妆照（{{ runConfig.shotCount }} 段共用，不衔接）</option>
        </select>
      </div>

      <div v-if="mode === 'i2v' || engine === 'ltx'" class="character-card">
        <label class="card-label">角色卡（固定外观，注入每段 prompt）</label>
        <div class="char-grid">
          <input v-model="character.name" placeholder="姓名" :disabled="isBusy" />
          <input v-model="character.age" placeholder="年龄" :disabled="isBusy" />
          <input v-model="character.gender" placeholder="性别" :disabled="isBusy" />
          <input v-model="character.face" placeholder="脸型/五官" :disabled="isBusy" class="span2" />
          <input v-model="character.hair" placeholder="发型" :disabled="isBusy" class="span2" />
          <input v-model="character.clothing" placeholder="服装" :disabled="isBusy" class="span2" />
          <input v-model="character.accessories" placeholder="配饰" :disabled="isBusy" class="span2" />
          <input
            v-model="character.immutable"
            placeholder="不可变特征（疤痕、发色等）"
            :disabled="isBusy"
            class="span2"
          />
        </div>
        <p v-if="!characterBibleCheck.ok" class="warn-hint">
          角色圣经缺少：{{ characterBibleCheck.missing.map((f) => CHARACTER_FIELD_LABELS[f] || f).join('、') }}
          —— 缺失字段会明显放大长链人设漂移，建议补全后再生成。
        </p>
        <div v-if="mode === 'i2v' || engine === 'ltx'" class="char-save-row">
          <input v-model="saveCharName" placeholder="保存为预设名" :disabled="isBusy" />
          <button type="button" class="btn-mini" :disabled="isBusy" @click="onSaveCharacter">保存角色</button>
        </div>
        <div v-if="savedCharacters.length" class="char-presets">
          <button
            v-for="c in savedCharacters"
            :key="c.id"
            type="button"
            class="btn-mini"
            :disabled="isBusy"
            @click="loadCharacterPreset(c)"
          >
            {{ c.name }}
          </button>
        </div>
      </div>

      <div v-if="needsImageUpload" class="field">
        <label>
          角色定妆照（{{ engine === 'ltx' ? '第1段 + FLF2V 锚点' : '第1段链式起点' }}，I2V 必填）
        </label>
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
        <ImageUploader v-if="imageSourceMode === 'single'" v-model="imageFile" :disabled="isBusy" />
        <ImageCollageBuilder
          v-else
          v-model="imageFile"
          :output-width="effectiveRes.width"
          :output-height="effectiveRes.height"
          :disabled="isBusy"
        />
      </div>

      <div class="field">
        <label>共用风格后缀（追加到每段 prompt 末尾）</label>
        <textarea v-model="styleSuffix" rows="2" :disabled="isBusy"></textarea>
      </div>

      <div class="field">
        <label>基础种子（同场景共用；切换场景可在分镜行改 sceneGroup）</label>
        <input type="number" v-model.number="baseSeed" :disabled="isBusy" />
      </div>

      <div class="shots-list">
        <div v-for="(shot, idx) in shots" :key="shot.name" class="shot-row">
          <div class="shot-label-row">
            <span class="shot-label">{{ idx + 1 }}. {{ shot.name }}</span>
            <label v-if="mode === 'i2v'" class="scene-group">
              场景组
              <input type="number" v-model.number="sceneGroups[idx]" min="0" max="9" :disabled="isBusy" />
            </label>
          </div>
          <textarea
            v-model="shot.prompt"
            rows="2"
            :disabled="isBusy"
            placeholder="画面描述：景别、动作、环境…"
          ></textarea>
          <textarea
            v-if="engine === 'ltx' || (engine === 'wan' && dubbingEnabled)"
            v-model="shot.dialogue"
            rows="2"
            class="dialogue-input"
            :disabled="isBusy"
            :placeholder="
              engine === 'ltx'
                ? '台词（写入 LTX 口型/语音提示），每行：角色: &quot;内容&quot;'
                : '台词，每行一个：陈默: &quot;台词内容&quot;'
            "
          ></textarea>
          <div v-if="engine === 'wan' && dubbingEnabled" class="dub-shot-options">
            <label>
              起始帧（可空）
              <input v-model.number="shot.startFrame" type="number" min="0" :disabled="isBusy" placeholder="自动" />
            </label>
            <label>
              结束帧（可空）
              <input v-model.number="shot.endFrame" type="number" min="0" :disabled="isBusy" placeholder="自动" />
            </label>
            <label>
              口型策略
              <select v-model="shot.lipSyncPolicy" :disabled="isBusy">
                <option value="required">required · 必须</option>
                <option value="preferred">preferred · 优先</option>
                <option value="off">off · 关闭</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      <div style="margin-top: 16px">
        <button class="btn" :disabled="isBusy" @click="onSubmit">
          {{ isBusy ? statusLabel : `开始 ${runConfig.shotCount} 段串行生成` }}
        </button>
      </div>

      <div class="status-line" style="margin-top: 12px">
        <span class="dot" :class="{ ok: status === 'done', err: status === 'error' }"></span>
        <span>{{ statusLabel }}</span>
        <span v-if="elapsedSec > 0" class="muted">· 本段已等待 {{ elapsedSec }}s</span>
      </div>

      <div v-if="isBusy" style="margin-top: 10px">
        <ProgressBar :percent="progressPercent" />
        <div class="muted" style="font-size: 12px; margin-top: 6px">
          单卡串行。已完成 {{ shotResults.length }}/{{ totalShots }} 段。
        </div>
      </div>

      <div v-if="errorMsg" class="error-box">{{ errorMsg }}</div>

      <div v-if="engine === 'wan' && dubbingEnabled" class="splice-box">
        <label>配音状态</label>
        <p class="muted" style="margin: 6px 0 0">
          {{
            {
              idle: '等待拼接',
              running: '正在生成配音与口型',
              validating: '正在校验音轨',
              awaiting_binding: '等待人工确认人脸绑定',
              done: '配音及音轨校验通过',
              error: '配音失败，可修正绑定后重试'
            }[dubbingStatus] || dubbingStatus
          }}
        </p>
        <div v-if="bindingRows.length && (status === 'awaiting_binding' || bindings.length)" class="binding-status">
          <label style="display:block;margin-top:10px">自动绑定结果</label>
          <table class="splice-table">
            <thead>
              <tr>
                <th>角色</th>
                <th>状态</th>
                <th>轨道</th>
                <th>置信度</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in bindingRows" :key="row.speakerId">
                <td>{{ row.name }} · {{ row.speakerId }}</td>
                <td>{{ row.status }}</td>
                <td>{{ row.faceTrackId || row.candidateTrackId || '—' }}</td>
                <td>{{ row.confidence != null ? row.confidence : '—' }}</td>
                <td>{{ row.reason || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <FaceTrackPicker
          v-if="(status === 'awaiting_binding' || dubbingStatus === 'error') && dubbingSessionId"
          v-model="bindingOverrides"
          :session-id="dubbingSessionId"
          :tracks="faceAtlas?.tracks || []"
          :characters="characters"
          :disabled="!isBindingInteractive && dubbingStatus !== 'error'"
          @confirm="onConfirmBindings"
        />
        <p v-if="lastDubError" class="warn-hint" style="margin-top: 8px">
          {{ lastDubError.message }}
          <span v-if="lastDubError.code">（{{ lastDubError.code }}）</span>
        </p>
        <template v-if="dubbingQa">
          <label style="display: block; margin-top: 10px">配音 QA</label>
          <pre class="dub-qa">{{ JSON.stringify(dubbingQa, null, 2) }}</pre>
        </template>
      </div>

      <div v-if="finalVideo" class="final-box">
        <label>自动拼接成片</label>
        <video :src="finalVideo.url" controls class="final-video"></video>
        <a :href="finalVideo.url" :download="finalVideo.filename" target="_blank" rel="noopener">下载成片</a>
        <p v-if="seamInterp" class="muted" style="font-size: 12px; margin-top: 6px">
          接缝插帧：{{ finalVideo.seamInterpApplied ? '已生效（RIFE 过渡）' : '未生效（已回退硬切拼接）' }}
        </p>
      </div>

      <div v-if="engine === 'wan' && splicePlan?.joins?.length" class="splice-box">
        <label>Smart Splice 诊断</label>
        <table class="splice-table">
          <thead>
            <tr>
              <th>边界</th>
              <th>段N 尾裁</th>
              <th>段N+1 头裁</th>
              <th>重叠帧</th>
              <th>置信度</th>
              <th>接缝运动分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="j in splicePlan.joins" :key="j.joinIndex">
              <td>{{ j.joinIndex + 1 }} → {{ j.joinIndex + 2 }}</td>
              <td>{{ j.tailCutSec }}s</td>
              <td>{{ j.headCutSec }}s</td>
              <td>{{ j.overlapFrames }}</td>
              <td>{{ j.confidence }}</td>
              <td>{{ j.seamMotionScore ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="engine === 'wan' && hasQaData" class="splice-box">
        <label>分段质检得分（时长/分辨率/人脸相似度；未达标可"重试该段"）</label>
        <table class="splice-table">
          <thead>
            <tr>
              <th>段</th>
              <th>人脸相似度</th>
              <th>无脸回退</th>
              <th>接缝运动分</th>
              <th>Animate 兜底</th>
              <th>状态</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in qaRows" :key="r.index">
              <td>{{ r.index }}</td>
              <td>{{ r.avgSimilarity != null ? r.avgSimilarity.toFixed(3) : '—' }}</td>
              <td>{{ r.faceGateFallback ? '定妆照' : '—' }}</td>
              <td>{{ r.seamMotionScore != null ? r.seamMotionScore : '—' }}</td>
              <td>{{ r.animateRelockApplied ? '已生效' : '—' }}</td>
              <td :class="{ 'qa-ok': r.ok, 'qa-fail': !r.ok }">
                {{ r.ok ? '达标' : r.qaIssues.join('; ') }}
              </td>
              <td>
                <button
                  v-if="!r.ok"
                  type="button"
                  class="btn-mini"
                  :disabled="isBusy"
                  @click="onRegenerate(r.index)"
                >
                  重试该段
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="concatCommand && !finalVideo" class="concat-box">
        <label>ffmpeg 拼接命令（辅助服务未运行时手动执行）</label>
        <pre class="concat-cmd">{{ concatCommand }}</pre>
        <button type="button" class="btn btn-secondary" @click="copyConcatCommand">
          {{ copied ? '已复制' : '复制命令' }}
        </button>
      </div>
    </div>

    <div class="panel" style="flex: 1 1 400px; min-width: 320px">
      <div class="section-title"><h3>分段预览</h3></div>
      <VideoResult
        v-if="shotResults.length"
        :results="shotResults"
        :busy="isBusy"
        @regenerate="onRegenerate"
      />
      <div v-else class="empty">{{ runConfig.shotCount }} 段视频会逐段出现在这里，含首/末帧缩略图。</div>
    </div>
  </div>
</template>

<style scoped>
.dialogue-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(100, 180, 255, 0.06);
  border: 1px solid rgba(100, 180, 255, 0.2);
}
.toggle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}
.multi-cast .cast-row {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
}
.cast-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
}
.dialogue-input {
  margin-top: 6px;
  width: 100%;
  font-size: 13px;
  border-color: rgba(100, 180, 255, 0.35) !important;
}
.dub-shot-options {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr;
  gap: 8px;
  margin-top: 6px;
}
.dub-shot-options label {
  font-size: 11px;
  color: var(--muted, #aaa);
}
.dub-shot-options input,
.dub-shot-options select {
  width: 100%;
  margin-top: 3px;
  padding: 6px;
}
.dub-qa {
  max-height: 220px;
  overflow: auto;
  margin: 6px 0 0;
  padding: 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.25);
  font-size: 11px;
  white-space: pre-wrap;
}
.intro {
  font-size: 13px;
  margin: 0 0 16px;
  line-height: 1.5;
}
.orch-status {
  font-size: 12px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.character-card {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 200, 100, 0.2);
  background: rgba(255, 200, 100, 0.04);
}
.required-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
  color: #ff9a3c;
  border: 1px solid rgba(255, 154, 60, 0.4);
  background: rgba(255, 154, 60, 0.1);
}
.warn-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #ffb454;
}
.dub-structure-box {
  margin: 12px 0 16px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(120, 180, 255, 0.22);
  background: rgba(80, 140, 220, 0.06);
}
.dub-structure-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}
.binding-status {
  margin: 10px 0;
  overflow-x: auto;
}
.binding-status table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.binding-status th,
.binding-status td {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
  vertical-align: top;
}
.binding-status th {
  opacity: 0.75;
  font-weight: 600;
}
.warn-box {
  margin-bottom: 16px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 154, 60, 0.25);
  background: rgba(255, 154, 60, 0.06);
}
.warn-box ul {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12px;
}
.warn-box li {
  margin-bottom: 2px;
}
.card-label {
  display: block;
  font-size: 13px;
  margin-bottom: 8px;
}
.char-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.char-grid .span2 {
  grid-column: span 2;
}
.char-grid input {
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.2);
  color: inherit;
}
.char-save-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.char-save-row input {
  flex: 1;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.2);
  color: inherit;
}
.char-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
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
.image-source-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.shots-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 420px;
  overflow-y: auto;
  margin-top: 12px;
}
.shot-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.shot-label {
  font-size: 12px;
  color: var(--muted, #888);
}
.scene-group {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.scene-group input {
  width: 48px;
}
.final-box {
  margin-top: 16px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(80, 200, 120, 0.08);
  border: 1px solid rgba(80, 200, 120, 0.25);
}
.final-video {
  width: 100%;
  border-radius: 8px;
  margin: 8px 0;
}
.concat-box {
  margin-top: 12px;
}
.splice-box {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(120, 200, 120, 0.06);
  border: 1px solid rgba(120, 200, 120, 0.2);
}
.splice-table {
  width: 100%;
  font-size: 12px;
  border-collapse: collapse;
  margin-top: 6px;
}
.splice-table th,
.splice-table td {
  padding: 4px 8px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.qa-ok {
  color: #6ee08a;
}
.qa-fail {
  color: #ff8a6b;
}
.concat-box {
  margin-top: 20px;
  padding: 12px;
  background: rgba(80, 160, 255, 0.06);
  border-radius: 8px;
  border: 1px solid rgba(80, 160, 255, 0.2);
}
.concat-cmd {
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  background: rgba(0, 0, 0, 0.3);
  padding: 10px;
  border-radius: 6px;
  margin: 8px 0;
}
.btn-secondary {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  font-size: 13px;
  padding: 6px 14px;
}
select {
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.2);
  color: inherit;
}
</style>
