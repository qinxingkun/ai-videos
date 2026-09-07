// LTX 2.3 / Wan 多分镜：串行生成，支持 30s / 90s 时长预设、链式 I2V / FLF2V / 单段重生成

import { ref, computed, onUnmounted } from 'vue'
import { uploadImage, viewUrl, generateT2V, generateI2V, generateFLF2V, waitForVideoTask } from '../services/api.js'
import { extractVideoFrame, concatSegments, dubFinalVideo, renderDubSession, getDubSession, checkOrchestrator, analyzeSplice, validateSegment, normalizeSegmentDuration, isDurationOnlyFailure, isResolutionMismatchFailure, validateFinalVideo, applyAnimateRelock, detectFaceInImage, DEFAULT_IDENTITY_THRESHOLD } from '../services/orchestrator.js'
import {
  CHAIN_EXTRACT_OFFSET_SEC,
  CHAIN_I2V_STRENGTH,
  LTX_OUTPUT_RES,
  resolveConcatOptionsFromChain,
  trimHeadFrames,
  trimTailFrames,
  chainExtractOffsetSec,
  SPLICE_DEFAULTS
} from '../services/chainConfig.js'
import {
  buildCharacterBibleBlock,
  buildShotPrompt,
  resolveSegmentSeed,
  DEFAULT_CHARACTER
} from '../services/characterBible.js'
import { buildShotPromptWithDialogue } from '../services/dialoguePrompt.js'
import { MULTI_SHOT_COUNT } from '../services/frameUtils.js'
import { getMultiShotProfile, resolveSegmentProfile, isProductionMode, needsChainOrchestrator, shouldUseFlf2vRefresh } from '../services/multiShotModels.js'
import {
  DEFAULT_DURATION_PRESET,
  resolveRunConfig
} from '../services/durationPresets.js'
import { detectRepeatedShotGrammar } from '../services/shotGrammar.js'
import { buildUtterancesFromShots, toDubCharacters, validateUtterances } from '../services/dubbing.js'
import { saveActiveJob, loadActiveJob, jobModeFor } from './useJobPersistence.js'

/** 长链生产模式（对应 90s/长时长预设）建议强制场景圣经非空的段数门槛 */
const SCENE_BIBLE_REQUIRED_AT_SHOT_COUNT = 12

export { DEFAULT_CHARACTER, buildCharacterBibleBlock }

export const DEFAULT_STYLE_SUFFIX =
  ', contemporary urban drama, soft daylight, clean color grade, shallow depth of field, photorealistic, 4k detail'

export const DEFAULT_SHOTS = [
  ['01_establish', 'Wide two-shot at a cafe table by the window, soft afternoon sunlight, two people sitting opposite'],
  ['02_pitch', 'Close medium of a man in navy blazer leaning forward at the cafe table, daylight on his face'],
  ['03_reply', 'Close medium of a woman in cream sweater tapping a tablet at the same cafe table'],
  ['04_exchange', 'Over-the-shoulder shot across the cafe table, a printed one-pager sliding between them'],
  ['05_negotiate', 'Medium two-shot both leaning closer, steam from coffee cups, city blur outside'],
  ['06_handshake', 'Wide two-shot handshake across the cafe table, sunny afternoon, slight smiles']
]

export const COMFYUI_VIDEO_DIR = '../ComfyUI/output/video'

export function buildConcatCommand(
  filenames,
  {
    outputName = 'final_30s_xfade.mp4',
    fadeDuration = 0.2,
    inputDir = COMFYUI_VIDEO_DIR,
    fps = 24,
    frames = 121,
    smartSplice = false,
    chainTrim = false,
    trimHeadFrames: headFrames = trimHeadFrames(fps),
    trimTailFrames: tailFrames = trimTailFrames(fps),
    outputWidth = LTX_OUTPUT_RES.width,
    outputHeight = LTX_OUTPUT_RES.height,
    microVideoFadeSec = 0,
    discardZoneSec = CHAIN_EXTRACT_OFFSET_SEC
  } = {}
) {
  const files = filenames.join(',')
  const chainFlags = smartSplice
    ? ` \\
  --smart-splice \\
  --tail-sec ${discardZoneSec} \\
  --head-sec ${discardZoneSec} \\
  --audio-crossfade ${SPLICE_DEFAULTS.audioCrossfadeSec} \\
  --micro-fade ${microVideoFadeSec || SPLICE_DEFAULTS.microVideoFadeFrames / fps} \\
  --output-width ${outputWidth} \\
  --output-height ${outputHeight}`
    : chainTrim
      ? ` \\
  --chain-trim \\
  --trim-head-frames ${headFrames} \\
  --trim-tail-frames ${tailFrames}`
      : ` \\
  --fade ${fadeDuration}`
  return `# 在 wan22-demo 目录下执行（需本机 ffmpeg）
python backend/scripts/concat_xfade.py \\
  --input-dir ${inputDir} \\
  --files ${files} \\
  --output ${outputName} \\
  --fps ${fps} \\
  --frames ${frames}${chainFlags}`
}

function getOutputRes(profile) {
  return profile?.outputRes ?? LTX_OUTPUT_RES
}

function resolveConcatOptions(continuityMode, mode, profile, runConfig = null, seamOpts = {}, engineName = 'wan') {
  const opts = resolveConcatOptionsFromChain(continuityMode, mode, isProductionMode, getOutputRes(profile), {
    discardZoneSec: runConfig?.discardZoneSec,
    fps: runConfig?.fps ?? profile?.fps,
    seamInterp: seamOpts.seamInterp,
    seamInterpFrames: seamOpts.seamInterpFrames
  })
  // LTX：不做 Smart Splice / 重复帧等生产质检，只用简单拼接保留原生出片
  if (engineName === 'ltx') {
    return {
      ...opts,
      smartSplice: false,
      chainTrim: false,
      noFade: false,
      trimHeadFrames: 0,
      trimTailFrames: 0,
      fadeDuration: 0.12,
      microVideoFadeSec: 0,
      seamInterp: false,
      discardZoneSec: 0
    }
  }
  return opts
}

function needsAnchorUpload(continuityMode, mode, productionSeg1I2v = false) {
  // T2V 禁止定妆照；仅 I2V 模式要求上传参考图
  if (mode === 'i2v') return true
  return false
}

export function useMultiShotGeneration({ engine = 'ltx', mode = 't2v', onDone } = {}) {
  const status = ref('idle')
  const currentShot = ref(0)
  const totalShots = ref(MULTI_SHOT_COUNT)
  const shotResults = ref([])
  const errorMsg = ref('')
  const concatCommand = ref('')
  const finalVideo = ref(null)
  const splicePlan = ref(null)
  const orchestratorOnline = ref(null)
  const elapsedSec = ref(0)
  const progress = ref({ value: 0, max: 0 })
  const grammarWarnings = ref([])
  const selfHealNotice = ref('')
  const relockNotice = ref('')
  const dubbingStatus = ref('idle')
  const dubbingQa = ref(null)
  const dubbingSessionId = ref(null)
  const faceAtlas = ref(null)
  const bindingOverrides = ref({})
  const pendingDubPayload = ref(null)
  const bindings = ref([])
  const lastDubError = ref(null)

  /** @type {ReturnType<typeof resolveRunConfig> | null} */
  let activeRunConfig = null
  const jobMode = jobModeFor({ engine, mode, kind: 'multishot-dub' })

  function persistDubJob(phase, extra = {}) {
    saveActiveJob({
      mode: jobMode,
      phase,
      submittedAt: Date.now(),
      dubbingSessionId: dubbingSessionId.value,
      faceAtlas: faceAtlas.value,
      bindingOverrides: bindingOverrides.value,
      bindings: bindings.value,
      pendingDubPayload: pendingDubPayload.value,
      shotResults: shotResults.value,
      concatCommand: concatCommand.value,
      splicePlan: splicePlan.value,
      finalVideo: finalVideo.value,
      lastDubError: lastDubError.value,
      ...extra
    })
  }

  const progressPercent = computed(() => {
    if (!progress.value.max) return 0
    return Math.min(100, Math.round((progress.value.value / progress.value.max) * 100))
  })

  const isBusy = computed(
    () =>
      status.value === 'running' ||
      status.value === 'queued' ||
      status.value === 'uploading' ||
      status.value === 'extracting' ||
      status.value === 'concatenating' ||
      status.value === 'dubbing' ||
      status.value === 'validating-dub' ||
      status.value === 'rendering'
  )
  const isBindingInteractive = computed(() => status.value === 'awaiting_binding')

  const statusLabel = computed(() => {
    if (selfHealNotice.value) return selfHealNotice.value
    if (relockNotice.value) return relockNotice.value
    if (status.value === 'uploading') return '上传定妆照中…'
    if (status.value === 'extracting') return '抽取衔接帧中…'
    if (status.value === 'concatenating') return 'Smart Splice 拼接成片中…'
    if (status.value === 'dubbing') return 'Wan 成片配音与口型同步中…'
    if (status.value === 'validating-dub') return '校验配音成片音轨中…'
    if (status.value === 'awaiting_binding') return '等待确认人脸绑定…'
    if (status.value === 'rendering') return '按已确认绑定渲染配音成片…'
    if (status.value === 'running' && currentShot.value > 0) {
      return `第 ${currentShot.value}/${totalShots.value} 段生成中…`
    }
    const map = {
      idle: '就绪',
      queued: '排队中…',
      running: '生成中…',
      done: '全部完成',
      error: '出错'
    }
    return map[status.value] || status.value
  })

  let abort = false
  let anchorImageName = null
  let chainImageName = null
  let cachedParams = null

  function getRunConfig(params, profile) {
    return resolveRunConfig(params?.durationPreset || DEFAULT_DURATION_PRESET, engine, profile)
  }

  function shotCountOf(runConfig) {
    return runConfig?.shotCount ?? MULTI_SHOT_COUNT
  }

  /** 质检/抽帧分辨率必须与本段实际生成宽高一致（优先 UI params，其次 profile）。 */
  function resolveGenRes(params, profile, segmentProfile = null) {
    const fallback = getOutputRes(segmentProfile || profile)
    const width = Number(params?.width)
    const height = Number(params?.height)
    return {
      width: Number.isFinite(width) && width > 0 ? width : fallback.width,
      height: Number.isFinite(height) && height > 0 ? height : fallback.height
    }
  }

  /** 把 Smart Splice 分析出的接缝运动分数（越低越"静"，接缝更干净）回填到对应分段，供质检可视化 */
  function applySeamMotionScores(plan) {
    for (const j of plan?.joins || []) {
      const seg = shotResults.value[j.joinIndex]
      if (seg) seg.seamMotionScore = j.seamMotionScore ?? null
    }
  }

  async function validateDubbedFinal(finalMedia, runConfig, profile, params = null) {
    dubbingStatus.value = 'validating'
    status.value = 'validating-dub'
    const res = resolveGenRes(params, profile)
    const dubbedCheck = await validateFinalVideo(finalMedia, {
      expectedWidth: res.width,
      expectedHeight: res.height,
      minDuration: runConfig.finalDuration.min,
      maxDuration: runConfig.finalDuration.max,
      requireAudio: true
    })
    dubbingQa.value = { ...(dubbingQa.value || {}), finalValidation: dubbedCheck }
    if (!dubbedCheck.ok) {
      throw new Error(`配音成片校验失败: ${dubbedCheck.issues.join('; ')}`)
    }
    dubbingStatus.value = 'done'
  }

  async function runMultishotDubbing(merged, params, list, runConfig, profile) {
    if (engine !== 'wan') {
      throw new Error('仅 Wan 支持成片配音；LTX 已禁用配音管线')
    }
    status.value = 'dubbing'
    dubbingStatus.value = 'running'
    lastDubError.value = null
    const characters = toDubCharacters(params.characters || [])
    const speakerIds = characters.map((item) => item.speakerId)
    let utterances = Array.isArray(params.utterances) && params.utterances.length
      ? params.utterances
      : buildUtterancesFromShots(list, params.characters || [], {
          framesPerShot: runConfig.frames
        })
    const maxFrame = Math.max(1, (runConfig.shotCount || list.length) * (runConfig.frames || 125))
    const validated = validateUtterances(utterances, { maxFrame, speakerIds })
    if (!validated.ok) throw new Error(validated.error)
    utterances = validated.utterances

    const dubbed = await dubFinalVideo(merged, {
      characters,
      utterances,
      faceBindingMode: params.faceBindingMode || 'auto',
      allowAwaitingBinding: true
    })
    if (dubbed.awaitingBinding) {
      dubbingSessionId.value = dubbed.sessionId
      faceAtlas.value = dubbed.faceAtlas || { tracks: [] }
      bindings.value = dubbed.bindings || []
      bindingOverrides.value = {}
      pendingDubPayload.value = {
        merged,
        params,
        list,
        runConfig,
        profile,
        utterances,
        characters,
        maxFrame
      }
      status.value = 'awaiting_binding'
      dubbingStatus.value = 'awaiting_binding'
      persistDubJob('awaiting_binding')
      return null
    }
    dubbingQa.value = dubbed.qa ?? null
    bindings.value = dubbed.bindings || []
    return {
      ...dubbed.media,
      dubbed: true,
      qa: dubbed.qa,
      bindings: dubbed.bindings,
      sessionId: dubbed.sessionId,
      degradations: dubbed.degradations
    }
  }

  async function renderPendingDubbing(overrides = bindingOverrides.value) {
    if (!pendingDubPayload.value || !dubbingSessionId.value) {
      throw new Error('没有待渲染的配音会话')
    }
    const { runConfig, profile, utterances, characters } = pendingDubPayload.value
    status.value = 'rendering'
    dubbingStatus.value = 'running'
    lastDubError.value = null
    bindingOverrides.value = { ...overrides }
    persistDubJob('rendering')
    try {
      const dubbed = await renderDubSession({
        sessionId: dubbingSessionId.value,
        characters,
        utterances,
        bindingOverrides: overrides
      })
      dubbingQa.value = dubbed.qa ?? null
      bindings.value = dubbed.bindings || []
      const finalMedia = {
        ...dubbed.media,
        dubbed: true,
        qa: dubbed.qa,
        bindings: dubbed.bindings,
        sessionId: dubbingSessionId.value
      }
      await validateDubbedFinal(finalMedia, runConfig, profile, params)
      finalVideo.value = { ...finalMedia, url: viewUrl(finalMedia) }
      pendingDubPayload.value = null
      lastDubError.value = null
      saveActiveJob(null)
      status.value = 'done'
      onDone?.({
        promptId: `multishot-${Date.now()}`,
        mode: `${engine}-${mode}-multishot`,
        media: shotResults.value,
        finalVideo: finalVideo.value,
        concatCommand: concatCommand.value,
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false })
      })
      return finalMedia
    } catch (error) {
      lastDubError.value = {
        code: error.code,
        message: error.message,
        sessionId: error.sessionId || dubbingSessionId.value,
        utteranceIds: error.utteranceIds || [],
        issues: error.issues || []
      }
      if (error.code === 'BINDING_REQUIRED') {
        status.value = 'awaiting_binding'
        dubbingStatus.value = 'awaiting_binding'
      } else {
        status.value = 'awaiting_binding'
        dubbingStatus.value = 'error'
      }
      persistDubJob(status.value)
      errorMsg.value = error.message || '配音渲染失败'
      throw error
    }
  }

  async function resumeFromStorage() {
    const job = loadActiveJob()
    if (!job || job.mode !== jobMode) return false
    if (!(job.phase === 'awaiting_binding' || job.phase === 'rendering')) return false
    if (!job.dubbingSessionId || !job.pendingDubPayload) return false

    cleanup()
    abort = false
    dubbingSessionId.value = job.dubbingSessionId
    faceAtlas.value = job.faceAtlas || { tracks: [] }
    bindingOverrides.value = job.bindingOverrides || {}
    bindings.value = job.bindings || []
    pendingDubPayload.value = job.pendingDubPayload
    shotResults.value = job.shotResults || []
    concatCommand.value = job.concatCommand || ''
    splicePlan.value = job.splicePlan || null
    finalVideo.value = job.finalVideo || null
    lastDubError.value = job.lastDubError || null
    cachedParams = job.pendingDubPayload.params || null
    activeRunConfig = job.pendingDubPayload.runConfig || null

    try {
      const session = await getDubSession(job.dubbingSessionId)
      if (session.status === 'done' && session.result?.media) {
        const media = {
          ...session.result.media,
          dubbed: true,
          qa: session.result.qa,
          bindings: session.bindings,
          sessionId: job.dubbingSessionId
        }
        finalVideo.value = { ...media, url: viewUrl(media) }
        dubbingQa.value = session.result.qa || null
        bindings.value = session.bindings || []
        pendingDubPayload.value = null
        saveActiveJob(null)
        status.value = 'done'
        dubbingStatus.value = 'done'
        return true
      }
      if (session.faceAtlas) faceAtlas.value = session.faceAtlas
      if (session.bindings) bindings.value = session.bindings
      status.value = 'awaiting_binding'
      dubbingStatus.value = 'awaiting_binding'
      return true
    } catch (error) {
      status.value = 'awaiting_binding'
      dubbingStatus.value = 'awaiting_binding'
      lastDubError.value = {
        code: error.code,
        message: error.message || '无法恢复配音会话详情，但本地绑定状态仍可用'
      }
      return true
    }
  }

  function cleanup() {
    abort = true
  }

  function reset() {
    currentShot.value = 0
    shotResults.value = []
    errorMsg.value = ''
    concatCommand.value = ''
    finalVideo.value = null
    splicePlan.value = null
    elapsedSec.value = 0
    progress.value = { value: 0, max: 0 }
    grammarWarnings.value = []
    selfHealNotice.value = ''
    relockNotice.value = ''
    dubbingStatus.value = 'idle'
    dubbingQa.value = null
    dubbingSessionId.value = null
    faceAtlas.value = null
    bindingOverrides.value = {}
    pendingDubPayload.value = null
    bindings.value = []
    lastDubError.value = null
    anchorImageName = null
    chainImageName = null
    cachedParams = null
    activeRunConfig = null
    saveActiveJob(null)
  }

  async function probeOrchestrator() {
    orchestratorOnline.value = await checkOrchestrator()
    return orchestratorOnline.value
  }

  async function extractAndCacheFrames(
    media,
    shotIndex,
    { chainLink = false, outputRes, fps = 24, discardZoneSec } = {}
  ) {
    if (!orchestratorOnline.value) return {}
    const res = outputRes ?? LTX_OUTPUT_RES
    status.value = 'extracting'
    try {
      // 链式：取有效区最后一帧（丢弃区起点前一帧），避免用模糊的 -1.0s 造成下段片头重播
      const offsetBeforeEnd = chainLink
        ? chainExtractOffsetSec(fps, discardZoneSec ?? activeRunConfig?.discardZoneSec)
        : 0.05
      const last = await extractVideoFrame(media, {
        position: 'last',
        offsetBeforeEnd,
        outputName: `chain_last_${String(shotIndex + 1).padStart(2, '0')}.jpg`,
        outputWidth: res.width,
        outputHeight: res.height
      })
      // 无脸门控：末帧无人脸时下一段条件图回退定妆照（身份不依赖无脸末帧）
      let gatedChainName = last.name
      let faceGate = null
      if (anchorImageName) {
        try {
          faceGate = await detectFaceInImage(last.name)
          if (faceGate && faceGate.skipped !== true && faceGate.hasFace === false) {
            gatedChainName = anchorImageName
          }
        } catch (e) {
          console.warn('face gate failed', e)
        }
      }
      chainImageName = gatedChainName
      const first = await extractVideoFrame(media, {
        position: 'first',
        outputName: `chain_first_${String(shotIndex + 1).padStart(2, '0')}.jpg`,
        outputWidth: res.width,
        outputHeight: res.height
      })
      return {
        lastFrameName: last.name,
        firstFrameName: first.name,
        lastFrameUrl: viewUrl({ filename: last.name, subfolder: '', type: 'input' }),
        firstFrameUrl: viewUrl({ filename: first.name, subfolder: '', type: 'input' }),
        chainImageName: gatedChainName,
        faceGateFallback: gatedChainName === anchorImageName && last.name !== anchorImageName,
        faceGate
      }
    } catch (e) {
      console.warn('extract frame failed', e)
      return {}
    }
  }

  function resolveStartImage(segmentIndex, continuityMode, params) {
    const n = shotCountOf(activeRunConfig)
    const refreshEvery = activeRunConfig?.anchorRefreshEvery
    if (isProductionMode(continuityMode)) {
      if (segmentIndex === 0 && params.productionSeg1I2v) return anchorImageName
      if (segmentIndex > 0 && !shouldUseFlf2vRefresh(segmentIndex, continuityMode, engine, n, refreshEvery)) {
        return chainImageName || anchorImageName
      }
      return null
    }
    if (mode !== 'i2v') return null
    if (continuityMode === 'anchor' || segmentIndex === 0) return anchorImageName
    return chainImageName || anchorImageName
  }

  function shouldExtractChainFrames(continuityMode) {
    if (isProductionMode(continuityMode)) return true
    return mode === 'i2v' && continuityMode !== 'anchor'
  }

  function isChainedSegment(segmentIndex, continuityMode, params) {
    const n = shotCountOf(activeRunConfig)
    const refreshEvery = activeRunConfig?.anchorRefreshEvery
    if (isProductionMode(continuityMode)) {
      if (segmentIndex === 0) return false
      if (shouldUseFlf2vRefresh(segmentIndex, continuityMode, engine, n, refreshEvery)) return false
      return true
    }
    return mode === 'i2v' && continuityMode !== 'anchor' && segmentIndex > 0
  }

  const MAX_SELF_HEAL_RETRIES = 2

  /**
   * 自愈重试参数：把"质检失败"变成自动动作，而非直接中止整批生成。
   * attempt=1：seed 偏移 + 提高锚点软拉回权重（更贴近定妆照，不打断运镜）；
   * attempt>=2：强制拉回定妆照锚点——LTX 有链式起点时临时切 FLF2V（首尾帧双端约束），
   * 否则（如 Wan 无 FLF2V）直接把起始图换成定妆照本身。
   */
  function computeSelfHealAdjustments(attempt, { chainImage, hasAnchor, canFlf2v }) {
    if (attempt <= 0) return {}
    if (attempt === 1) {
      return {
        seedOffset: 1009,
        blendWeightOverride: hasAnchor && chainImage ? 0.45 : undefined
      }
    }
    // 末次自愈：优先 FLF2V/定妆照拉回；同时标记可走 Animate 身份兜底
    if (canFlf2v && chainImage && hasAnchor) {
      return { seedOffset: 1997 * attempt, forceFlf2v: true, forceAnimateRelock: true }
    }
    return { seedOffset: 1997 * attempt, forceAnchorImage: hasAnchor, forceAnimateRelock: true }
  }

  async function runOneSegment({
    segmentIndex,
    name,
    basePrompt,
    profile,
    segmentProfile,
    continuityMode,
    params,
    selfHeal = {}
  }) {
    const attempt = selfHeal.attempt || 0
    const sceneGroup = params.sceneGroups?.[segmentIndex] ?? 0
    const baseSeed = resolveSegmentSeed({
      baseSeed: params.baseSeed,
      segmentIndex,
      sceneGroup,
      mode: segmentProfile.mode === 't2v' ? 't2v' : 'i2v'
    })

    const positivePrompt = buildShotPromptWithDialogue({
      shotPrompt: basePrompt,
      dialogueText: params.dialogueText,
      characters: params.characters,
      character: params.character,
      styleSuffix: params.styleSuffix,
      dialogueMode: params.dialogueMode,
      engine,
      mode,
      segmentIndex,
      allShots: params.allShots || [],
      sceneBible: params.sceneBible || '',
      chained: params.chained
    })

    const chainImage = resolveStartImage(segmentIndex, continuityMode, params)
    const heal = computeSelfHealAdjustments(attempt, {
      chainImage,
      hasAnchor: !!anchorImageName,
      canFlf2v: engine === 'ltx'
    })
    const seed = baseSeed + (heal.seedOffset || 0)
    const isFlf2v = segmentProfile.mode === 'flf2v' || heal.forceFlf2v

    const body = {
      prompt: positivePrompt,
      negative_prompt: params.negativePrompt || '',
      engine,
      width: params.width ?? profile.res.width,
      height: params.height ?? profile.res.height,
      length: activeRunConfig?.frames ?? profile.frames5s,
      seed,
      fps: profile.fps,
      filename_prefix: segmentProfile.filenamePrefix(name),
      use_lightx2v: !!segmentProfile.buildOptions?.useLightX2V,
      i2v_strength: isChainedSegment(segmentIndex, continuityMode, params) ? CHAIN_I2V_STRENGTH : 1.0
    }

    let submitted
    if (isFlf2v) {
      if (!anchorImageName) {
        throw new Error('缺少 FLF2V 锚点帧：请确认第 1 段已生成且后端可抽帧')
      }
      body.first_image_name = chainImage || chainImageName || anchorImageName
      body.last_image_name = anchorImageName
      submitted = await generateFLF2V(body)
    } else if (chainImage || segmentProfile.mode === 'i2v') {
      body.image_name = heal.forceAnchorImage && anchorImageName ? anchorImageName : chainImage
      if (!body.image_name) {
        throw new Error(`第 ${segmentIndex + 1} 段 I2V 缺少起始图`)
      }
      // 锚点软拉回：链式图与定妆照按权重混合，逐段小幅抑制人设漂移（仅长链预设默认开启，重试时可临时提权）
      const blendWeight = heal.blendWeightOverride ?? (activeRunConfig?.anchorBlendWeight || 0)
      if (anchorImageName && blendWeight > 0 && body.image_name !== anchorImageName) {
        body.anchor_image_name = anchorImageName
        body.anchor_blend_weight = blendWeight
      }
      // Wan-VACE：定妆照作 ref_images；场景起始用末帧（无脸门控后可能已是定妆照）
      if (engine === 'wan' && params.useVace && anchorImageName) {
        body.use_vace = true
        body.ref_image_name = anchorImageName
        body.engine = 'wan'
      }
      submitted = await generateI2V(body)
    } else {
      submitted = await generateT2V(body)
    }

    status.value = 'queued'
    const media = await waitForVideoTask(submitted.task_id, {
      intervalMs: 2000,
      timeoutMs: activeRunConfig?.timeoutMs ?? segmentProfile.timeoutMs,
      onTick: ({ elapsed, phase }) => {
        elapsedSec.value = elapsed
        if (phase === 'running') status.value = 'running'
        if (phase === 'queued') status.value = 'queued'
      }
    })

    const item = media[0]
    if (!item) throw new Error(`第 ${segmentIndex + 1} 段未找到输出视频`)

    // VACE/I2V 初渲后先做时长规范 + ArcFace 质检；Animate 作为关键镜/身份失败兜底（见 FACE_CONSISTENCY_SOP）
    let finalItem = item
    let animateRelockApplied = false
    let animateRelockSkipped = false

    let durationNormalized = false
    const expectedFrames = activeRunConfig?.frames ?? profile.frames5s ?? segmentProfile.frames5s
    const expectedFps = profile.fps ?? segmentProfile.fps ?? 16
    const segDur = activeRunConfig?.segmentDuration
    const maxDuration = segmentProfile.mode === 'flf2v'
      ? Math.max(segDur?.max ?? 6.5, 6.5)
      : (segDur?.max ?? 6.0)

    // LTX：跳过时长规范 / 段级质检，直接使用模型原生输出
    if (engine === 'wan' && orchestratorOnline.value && expectedFrames) {
      try {
        const normalized = await normalizeSegmentDuration(finalItem, {
          expectedFrames,
          fps: expectedFps,
          maxDuration
        })
        if (normalized?.applied) {
          finalItem = {
            ...finalItem,
            filename: normalized.filename || normalized.name || finalItem.filename,
            subfolder: normalized.subfolder ?? finalItem.subfolder,
            type: normalized.type ?? finalItem.type,
            path: normalized.path || finalItem.path
          }
          durationNormalized = true
        }
      } catch (e) {
        console.warn('normalize segment duration failed', e)
      }
    }

    async function runIdentityValidate(mediaItem) {
      if (!(engine === 'wan' && orchestratorOnline.value)) return null
      const isFlf2vSeg = segmentProfile.mode === 'flf2v'
      const genRes = resolveGenRes(params, profile, segmentProfile)
      const validation = await validateSegment(mediaItem, {
        expectedWidth: genRes.width,
        expectedHeight: genRes.height,
        minDuration: segDur?.min ?? 4.5,
        maxDuration: isFlf2vSeg ? Math.max(segDur?.max ?? 6.5, 6.5) : (segDur?.max ?? 6.0),
        requireAudio: false,
        expectedFrames,
        expectedFps,
        referenceImageName: anchorImageName || undefined,
        identityThreshold: params.identityThreshold ?? DEFAULT_IDENTITY_THRESHOLD,
        checkIdentity: !!anchorImageName
      })
      if (validation && !validation.durationOnly) {
        validation.durationOnly = isDurationOnlyFailure(validation.issues)
      }
      if (validation) validation.durationNormalized = durationNormalized
      return validation
    }

    let validation = await runIdentityValidate(finalItem)

    async function tryAnimateRelock(reason) {
      if (!orchestratorOnline.value || !anchorImageName) {
        animateRelockSkipped = true
        return false
      }
      relockNotice.value = `第 ${segmentIndex + 1} 段身份锁定重渲染中（Wan2.2-Animate，${reason}）…`
      try {
        const relocked = await applyAnimateRelock(finalItem, { referenceImageName: anchorImageName, seed })
        if (relocked?.applied) {
          finalItem = {
            ...finalItem,
            filename: relocked.filename,
            subfolder: relocked.subfolder,
            type: relocked.type,
            path: relocked.path
          }
          animateRelockApplied = true
          validation = await runIdentityValidate(finalItem)
          return true
        }
        animateRelockSkipped = true
      } catch (e) {
        console.warn('animate relock failed', e)
        animateRelockSkipped = true
      } finally {
        relockNotice.value = ''
      }
      return false
    }

    // 关键镜头：VACE 初渲质检后跑 Animate 兜底抛光
    if (segmentProfile.animateRelock) {
      await tryAnimateRelock('关键镜头兜底')
    }
    // 自愈末次：身份不达标时强制 Animate 再检一次
    if (
      heal.forceAnimateRelock &&
      validation &&
      !validation.ok &&
      validation.identity &&
      !validation.identity.skipped &&
      !validation.identity.ok
    ) {
      await tryAnimateRelock('质检失败兜底')
    }

    // 质检未过时不在此处抽帧/落链：由调用方决定重试或中止，避免污染链式起点
    const frames = (!validation || validation.ok) && shouldExtractChainFrames(continuityMode)
      ? await extractAndCacheFrames(finalItem, segmentIndex, {
          chainLink: segmentIndex < shotCountOf(activeRunConfig) - 1,
          outputRes: resolveGenRes(params, profile, segmentProfile),
          fps: profile.fps ?? segmentProfile.fps ?? 24,
          discardZoneSec: activeRunConfig?.discardZoneSec
        })
      : {}

    return {
      result: {
        ...finalItem,
        kind: finalItem.kind || 'video',
        url: viewUrl(finalItem),
        shotName: name,
        seed,
        index: segmentIndex + 1,
        mode: isFlf2v ? 'flf2v' : (params.useVace ? 'vace' : segmentProfile.mode || mode),
        continuityMode,
        seamMotionScore: null,
        qaIssues: validation?.issues || [],
        identity: validation?.identity || null,
        avgSimilarity: validation?.identity?.avgSimilarity ?? null,
        animateRelockApplied,
        animateRelockSkipped,
        ...frames
      },
      validation
    }
  }

  /** 自愈重试环：仅 Wan 走质检自愈；LTX 直接采用原生出片，不因质检重跑。 */
  async function runSegmentWithSelfHeal(ctx) {
    if (engine === 'ltx') {
      const { result } = await runOneSegment({ ...ctx, selfHeal: { attempt: 0 } })
      selfHealNotice.value = ''
      return result
    }
    let lastValidation = null
    for (let attempt = 0; attempt <= MAX_SELF_HEAL_RETRIES; attempt++) {
      if (attempt > 0) {
        const reason = (lastValidation?.issues || []).join('; ') || '未知原因'
        selfHealNotice.value = `第 ${ctx.segmentIndex + 1} 段质检未过，自动重试 (${attempt}/${MAX_SELF_HEAL_RETRIES})：${reason}`
      }
      const { result, validation } = await runOneSegment({ ...ctx, selfHeal: { attempt } })
      if (!validation || validation.ok) {
        selfHealNotice.value = ''
        return result
      }
      lastValidation = validation
      const durationOnly = validation.durationOnly || isDurationOnlyFailure(validation.issues)
      if (durationOnly) {
        selfHealNotice.value = ''
        const reason = (validation.issues || []).join('; ') || '未知原因'
        const hint = validation.durationNormalized
          ? '已尝试规范时长仍失败'
          : '时长超限无法靠换 seed 修复'
        throw new Error(
          `第 ${ctx.segmentIndex + 1} 段质检未达标：${reason}；${hint}${profileFpsHint(ctx)}；请用下方"重试该段"人工介入`
        )
      }
      // 分辨率不符换 seed 无效：立刻停，避免空转 3 次
      if (isResolutionMismatchFailure(validation.issues)) {
        selfHealNotice.value = ''
        const reason = (validation.issues || []).join('; ') || '未知原因'
        const want = resolveGenRes(ctx.params, ctx.profile, ctx.segmentProfile)
        throw new Error(
          `第 ${ctx.segmentIndex + 1} 段分辨率不符：${reason}；生成期望 ${want.width}×${want.height}，请核对 UI 分辨率选择后重试该段（换 seed 无法修复）`
        )
      }
      if (attempt === MAX_SELF_HEAL_RETRIES) {
        selfHealNotice.value = ''
        const reason = (validation.issues || []).join('; ') || '未知原因'
        throw new Error(
          `第 ${ctx.segmentIndex + 1} 段质检连续 ${MAX_SELF_HEAL_RETRIES + 1} 次未达标：${reason}；请用下方"重试该段"人工介入`
        )
      }
    }
  }

  function profileFpsHint(ctx) {
    const frames = activeRunConfig?.frames ?? ctx.profile?.frames5s
    const fps = ctx.profile?.fps ?? ctx.segmentProfile?.fps
    if (frames != null && fps != null) return `（期望 ${frames}@${fps}）`
    return ''
  }

  async function generateShots(params) {
    cleanup()
    reset()
    abort = false
    // LTX 明确不支持配音管线，避免误开后走 CosyVoice/口型。
    if (engine !== 'wan') {
      params = { ...params, dubbingEnabled: false, dialogueMode: false }
    }
    cachedParams = { ...params }

    const profile = getMultiShotProfile(engine, mode)
    const runConfig = getRunConfig(params, profile)
    activeRunConfig = runConfig
    totalShots.value = runConfig.shotCount
    const shotCount = runConfig.shotCount
    const list = (params.shots || []).slice(0, shotCount)
    const continuityMode = params.continuityMode ?? (mode === 'i2v' ? 'chain+anchor' : 'production')
    // T2V 一律不允许定妆照 / 段1 I2V
    if (mode === 't2v') {
      params.productionSeg1I2v = false
      params.imageFile = undefined
    }

    if (list.length < shotCount) {
      errorMsg.value = `需要 ${shotCount} 段分镜描述（当前时长预设：${runConfig.label}）`
      status.value = 'error'
      return
    }

    const emptyIdx = list.findIndex((s) => !(s.prompt ?? s[1] ?? '').toString().trim())
    if (emptyIdx >= 0) {
      errorMsg.value = `第 ${emptyIdx + 1} 段画面描述为空，请补全后再生成`
      status.value = 'error'
      return
    }

    if (shotCount >= SCENE_BIBLE_REQUIRED_AT_SHOT_COUNT && !params.sceneBible?.toString().trim()) {
      errorMsg.value = `长链生产（${shotCount} 段）需要填写"场景圣经"以维持跨段连贯性，请补全后再生成`
      status.value = 'error'
      return
    }

    grammarWarnings.value = detectRepeatedShotGrammar(list)

    await probeOrchestrator()
    if (needsChainOrchestrator(continuityMode, mode) && !orchestratorOnline.value) {
      errorMsg.value = '生产/链式模式需要后端 API：cd backend && python main.py（端口 8190）'
      status.value = 'error'
      return
    }

    if (needsAnchorUpload(continuityMode, mode, params.productionSeg1I2v)) {
      if (!params.imageFile) {
        errorMsg.value = '请先上传角色定妆照'
        status.value = 'error'
        return
      }
      status.value = 'uploading'
      try {
        const uploaded = await uploadImage(params.imageFile)
        anchorImageName = uploaded.name
        chainImageName = isProductionMode(continuityMode) && params.productionSeg1I2v ? uploaded.name : chainImageName
      } catch (e) {
        errorMsg.value = e.message || '定妆照上传失败'
        status.value = 'error'
        return
      }
    }

    // VACE：可选段1场景起始图（与定妆照分离，避免首帧贴定妆照）
    if (engine === 'wan' && params.useVace && params.startImageFile) {
      status.value = 'uploading'
      try {
        const startUp = await uploadImage(params.startImageFile)
        chainImageName = startUp.name
      } catch (e) {
        errorMsg.value = e.message || '段1起始图上传失败'
        status.value = 'error'
        return
      }
    }

    if (mode === 'i2v' && !isProductionMode(continuityMode)) {
      if (!(engine === 'wan' && params.useVace && params.startImageFile && chainImageName)) {
        chainImageName = anchorImageName
      }
    }

    status.value = 'running'
    progress.value = { value: 0, max: 1 }

    const filenames = []

    try {
      for (let i = 0; i < list.length; i++) {
        if (abort) return
        const shot = list[i]
        const name = shot.name ?? shot[0]
        const basePrompt = shot.prompt ?? shot[1]
        const dialogueText = shot.dialogue ?? ''
        currentShot.value = i + 1

        const segmentProfile = resolveSegmentProfile(engine, mode, i, continuityMode, {
          productionSeg1I2v: params.productionSeg1I2v,
          shotCount,
          anchorRefreshEvery: runConfig.anchorRefreshEvery,
          animateRelock: params.animateRelock,
          animateRelockShots: params.animateRelockShots,
          forceT2v: !!shot.forceT2v
        })
        const result = await runSegmentWithSelfHeal({
          segmentIndex: i,
          name,
          basePrompt,
          profile,
          segmentProfile,
          continuityMode,
          params: {
            ...params,
            dialogueText,
            allShots: list,
            sceneBible: params.sceneBible,
            chained: !shot.forceT2v && isChainedSegment(i, continuityMode, params)
          }
        })

        if (
          i === 0 &&
          isProductionMode(continuityMode) &&
          mode === 't2v' &&
          !params.productionSeg1I2v &&
          !anchorImageName &&
          result.firstFrameName
        ) {
          anchorImageName = result.firstFrameName
        }

        filenames.push(result.filename)
        shotResults.value.push(result)
        progress.value = { value: 0, max: 0 }
      }

      const concatOpts = resolveConcatOptions(continuityMode, mode, profile, runConfig, {
        seamInterp: params.seamInterp,
        seamInterpFrames: params.seamInterpFrames
      }, engine)
      concatCommand.value = buildConcatCommand(filenames, {
        fps: profile.fps,
        frames: runConfig.frames,
        outputName: `${runConfig.outputNamePrefix}_xfade.mp4`,
        ...concatOpts,
        discardZoneSec: runConfig.discardZoneSec
      })

      if (orchestratorOnline.value && filenames.length) {
        status.value = 'concatenating'
        try {
          let plan = null
          if (concatOpts.smartSplice) {
            const analyzed = await analyzeSplice(filenames, {
              fps: profile.fps,
              tailSec: concatOpts.trimTailFrames / profile.fps,
              headSec: concatOpts.trimHeadFrames / profile.fps
            })
            plan = analyzed.plan
            splicePlan.value = plan
            applySeamMotionScores(plan)
          }

          const merged = await concatSegments(filenames, {
            fps: profile.fps,
            frames: runConfig.frames,
            outputName: `${runConfig.outputNamePrefix}_${Date.now()}.mp4`,
            ...concatOpts,
            splicePlan: plan
          })

          let finalMedia = merged
          if (engine === 'wan' && params.dubbingEnabled) {
            const dubbedMedia = await runMultishotDubbing(merged, params, list, runConfig, profile)
            if (!dubbedMedia) return
            finalMedia = dubbedMedia
            await validateDubbedFinal(finalMedia, runConfig, profile, params)
          }

          finalVideo.value = {
            ...finalMedia,
            url: viewUrl(finalMedia)
          }
        } catch (e) {
          if (engine === 'wan' && params.dubbingEnabled) dubbingStatus.value = 'error'
          errorMsg.value = e.message || '自动拼接失败'
          status.value = 'error'
          cleanup()
          return
        }
      }

      status.value = 'done'
      onDone?.({
        promptId: `multishot-${Date.now()}`,
        mode: `${engine}-${mode}-multishot`,
        media: shotResults.value,
        finalVideo: finalVideo.value,
        concatCommand: concatCommand.value,
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false })
      })
    } catch (e) {
      errorMsg.value = e.message || String(e)
      status.value = 'error'
      cleanup()
    }
  }

  /** 从第 k 段（1-based）重生成，保留前段结果与衔接帧 */
  async function regenerateFromShot(shotIndex1Based) {
    if (!cachedParams) {
      errorMsg.value = '无缓存任务参数，请完整生成一次后再重试单段'
      status.value = 'error'
      return
    }
    const profile = getMultiShotProfile(engine, mode)
    const runConfig = getRunConfig(cachedParams, profile)
    activeRunConfig = runConfig
    totalShots.value = runConfig.shotCount
    const shotCount = runConfig.shotCount

    const k = shotIndex1Based - 1
    if (k < 0 || k >= shotCount) return

    cleanup()
    abort = false
    errorMsg.value = ''

    const outputRes = getOutputRes(profile)
    const params = cachedParams
    const continuityMode = params.continuityMode ?? (mode === 'i2v' ? 'chain+anchor' : 'production')
    // T2V 一律不允许定妆照 / 段1 I2V
    if (mode === 't2v') {
      params.productionSeg1I2v = false
      params.imageFile = undefined
    }
    const list = params.shots.slice(0, shotCount)

    await probeOrchestrator()

    const restoreChain = () => {
      const prev = shotResults.value[k - 1]
      if (prev?.lastFrameName) {
        chainImageName = prev.lastFrameName
      } else if (orchestratorOnline.value && prev) {
        return extractVideoFrame(prev, {
          position: 'last',
          offsetBeforeEnd: chainExtractOffsetSec(profile.fps, runConfig.discardZoneSec),
          outputName: `chain_regen_${k}.jpg`,
          outputWidth: outputRes.width,
          outputHeight: outputRes.height
        }).then((ext) => {
          chainImageName = ext.name
        })
      } else {
        chainImageName = anchorImageName
        return Promise.resolve()
      }
    }

    if (needsAnchorUpload(continuityMode, mode, params.productionSeg1I2v)) {
      if (!params.imageFile && !anchorImageName) {
        errorMsg.value = '缺少定妆照'
        status.value = 'error'
        return
      }
      if (params.imageFile) {
        const uploaded = await uploadImage(params.imageFile)
        anchorImageName = uploaded.name
      }
    } else if (isProductionMode(continuityMode) && mode === 't2v' && !params.productionSeg1I2v && !anchorImageName) {
      const seg1 = shotResults.value[0]
      if (seg1?.firstFrameName) {
        anchorImageName = seg1.firstFrameName
      } else if (seg1 && orchestratorOnline.value) {
        status.value = 'extracting'
        try {
          const first = await extractVideoFrame(seg1, {
            position: 'first',
            outputName: 'anchor_from_seg1.jpg',
            outputWidth: outputRes.width,
            outputHeight: outputRes.height
          })
          anchorImageName = first.name
        } catch (e) {
          errorMsg.value = e.message || '无法从第 1 段抽取 FLF2V 锚点帧'
          status.value = 'error'
          return
        }
      } else if (k >= 2) {
        errorMsg.value = '缺少 FLF2V 锚点：请先生成第 1 段或上传定妆照'
        status.value = 'error'
        return
      }
    }

    if (mode === 'i2v' || isProductionMode(continuityMode)) {
      if (k === 0) {
        chainImageName =
          isProductionMode(continuityMode) && params.productionSeg1I2v ? anchorImageName : chainImageName
        if (mode === 'i2v') chainImageName = anchorImageName
      } else if (continuityMode !== 'anchor' || isProductionMode(continuityMode)) {
        await restoreChain()
      } else {
        chainImageName = anchorImageName
      }
    }

    shotResults.value = shotResults.value.slice(0, k)
    status.value = 'running'
    progress.value = { value: 0, max: 1 }

    const filenames = shotResults.value.map((r) => r.filename)

    try {
      for (let i = k; i < list.length; i++) {
        if (abort) return
        const shot = list[i]
        const name = shot.name ?? shot[0]
        const basePrompt = shot.prompt ?? shot[1]
        currentShot.value = i + 1
        const segmentProfile = resolveSegmentProfile(engine, mode, i, continuityMode, {
          productionSeg1I2v: params.productionSeg1I2v,
          shotCount,
          anchorRefreshEvery: runConfig.anchorRefreshEvery,
          animateRelock: params.animateRelock,
          animateRelockShots: params.animateRelockShots,
          forceT2v: !!shot.forceT2v
        })
        const result = await runSegmentWithSelfHeal({
          segmentIndex: i,
          name,
          basePrompt,
          profile,
          segmentProfile,
          continuityMode,
          params: {
            ...params,
            dialogueText: shot.dialogue ?? '',
            allShots: list,
            sceneBible: params.sceneBible,
            chained: !shot.forceT2v && isChainedSegment(i, continuityMode, params)
          }
        })
        if (
          i === 0 &&
          isProductionMode(continuityMode) &&
          mode === 't2v' &&
          !params.productionSeg1I2v &&
          result.firstFrameName
        ) {
          anchorImageName = result.firstFrameName
        }
        if (i < shotResults.value.length) shotResults.value[i] = result
        else shotResults.value.push(result)
        filenames[i] = result.filename
        progress.value = { value: 0, max: 0 }
      }

      const concatOpts = resolveConcatOptions(continuityMode, mode, profile, runConfig, {
        seamInterp: params.seamInterp,
        seamInterpFrames: params.seamInterpFrames
      }, engine)
      concatCommand.value = buildConcatCommand(filenames.filter(Boolean), {
        fps: profile.fps,
        frames: runConfig.frames,
        outputName: `${runConfig.outputNamePrefix}_xfade.mp4`,
        ...concatOpts
      })

      if (orchestratorOnline.value && filenames.filter(Boolean).length === shotCount) {
        status.value = 'concatenating'
        try {
          let plan = null
          if (concatOpts.smartSplice) {
            const analyzed = await analyzeSplice(filenames.filter(Boolean), {
              fps: profile.fps,
              tailSec: concatOpts.trimTailFrames / profile.fps,
              headSec: concatOpts.trimHeadFrames / profile.fps
            })
            plan = analyzed.plan
            splicePlan.value = plan
            applySeamMotionScores(plan)
          }
          const merged = await concatSegments(filenames.filter(Boolean), {
            outputName: `${runConfig.outputNamePrefix}_${Date.now()}.mp4`,
            fps: profile.fps,
            frames: runConfig.frames,
            ...concatOpts,
            splicePlan: plan
          })
          let finalMedia = merged
          if (engine === 'wan' && params.dubbingEnabled) {
            const dubbedMedia = await runMultishotDubbing(merged, params, list, runConfig, profile)
            if (!dubbedMedia) return
            finalMedia = dubbedMedia
            await validateDubbedFinal(finalMedia, runConfig, profile, params)
          }
          finalVideo.value = { ...finalMedia, url: viewUrl(finalMedia) }
        } catch (e) {
          if (engine === 'wan' && params.dubbingEnabled) dubbingStatus.value = 'error'
          errorMsg.value = e.message || '自动拼接失败'
          status.value = 'error'
          cleanup()
          return
        }
      }

      status.value = 'done'
    } catch (e) {
      errorMsg.value = e.message || String(e)
      status.value = 'error'
      cleanup()
    }
  }

  onUnmounted(cleanup)

  return {
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
    progress,
    progressPercent,
    grammarWarnings,
    selfHealNotice,
    relockNotice,
    dubbingStatus,
    dubbingQa,
    dubbingSessionId,
    faceAtlas,
    bindingOverrides,
    bindings,
    lastDubError,
    pendingDubPayload,
    isBusy,
    isBindingInteractive,
    generateShots,
    regenerateFromShot,
    renderPendingDubbing,
    resumeFromStorage,
    probeOrchestrator,
    reset,
    cleanup
  }
}
