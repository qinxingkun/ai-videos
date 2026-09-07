// 生成任务状态机：REST 提交 → 轮询任务状态
// 状态: idle | uploading | queued | running | done | error

import { ref, computed, onUnmounted } from 'vue'
import {
  uploadImage,
  viewUrl,
  generateT2V,
  generateI2V,
  generateFLF2V,
  waitForVideoTask
} from '../services/api.js'
import { analyzeDubSession, renderDubSession, extractVideoFrame } from '../services/orchestrator.js'
import { saveActiveJob, loadActiveJob, claimActiveJobResume, releaseActiveJobResume } from './useJobPersistence.js'
import { LTX_TIMEOUT_5S_MS } from '../services/multiShotModels.js'

function isVideoMedia(item) {
  return item?.kind === 'video' || /\.(mp4|webm|mov|mkv)$/i.test(item?.filename || '')
}

/** 为视频结果抽取末帧缩略图（失败不阻断主流程）。 */
async function attachLastFrame(mediaItem) {
  if (!isVideoMedia(mediaItem) || !mediaItem?.filename) return mediaItem
  try {
    const stamp = Date.now().toString(36)
    const shortId = String(mediaItem.filename)
      .replace(/\.[^.]+$/, '')
      .slice(-40)
      .replace(/[^a-zA-Z0-9_-]/g, '_')
    const last = await extractVideoFrame(mediaItem, {
      position: 'last',
      offsetBeforeEnd: 0.15,
      outputName: `last_${shortId}_${stamp}.jpg`
    })
    return {
      ...mediaItem,
      lastFrameName: last.name,
      lastFrameUrl: viewUrl({ filename: last.name, subfolder: '', type: 'input' }),
      lastFrameError: null
    }
  } catch (e) {
    console.warn('last frame extract failed', e)
    return {
      ...mediaItem,
      lastFrameError: e?.message || String(e)
    }
  }
}

async function attachLastFrames(mediaList) {
  if (!Array.isArray(mediaList) || !mediaList.length) return mediaList || []
  return Promise.all(mediaList.map(attachLastFrame))
}

/** 全局轮询代际：新任务会作废旧轮询，避免并发 fetch 占满连接。 */
let pollGeneration = 0

export function useGeneration(mode, { engine = 'wan', onDone } = {}) {
  const jobMode = `${engine}-${mode}-5s`

  const status = ref('idle')
  const progress = ref({ value: 0, max: 0 })
  const currentNode = ref(null)
  const errorMsg = ref('')
  const results = ref([])
  const promptId = ref(null)
  const taskId = ref(null)
  const queueHint = ref('')
  const elapsedSec = ref(0)
  const dubbingQa = ref(null)
  const dubbingSessionId = ref(null)
  const faceAtlas = ref(null)
  const bindings = ref({})
  const pendingDubbing = ref(null)
  const batchProgress = ref(null) // { current, total } | null

  const progressPercent = computed(() => {
    if (!progress.value.max) return 0
    return Math.min(100, Math.round((progress.value.value / progress.value.max) * 100))
  })
  const isBusy = computed(() =>
    ['uploading', 'queued', 'running', 'dubbing', 'analyzing', 'rendering'].includes(status.value)
  )

  let pollAbort = false
  let pollController = null
  let pollToken = 0

  function normalizeBindings(value) {
    if (!Array.isArray(value)) {
      return Object.fromEntries(
        Object.entries(value || {}).map(([speakerId, binding]) => [
          speakerId,
          typeof binding === 'object' ? binding.faceTrackId || binding.trackId || binding.id : binding
        ])
      )
    }
    return Object.fromEntries(
      value
        .map((item) => [item.speakerId || item.characterId || item.id, item.faceTrackId || item.trackId])
        .filter(([speakerId, trackId]) => speakerId && trackId)
    )
  }

  function reset() {
    progress.value = { value: 0, max: 0 }
    currentNode.value = null
    errorMsg.value = ''
    results.value = []
    promptId.value = null
    taskId.value = null
    queueHint.value = ''
    elapsedSec.value = 0
    dubbingQa.value = null
    dubbingSessionId.value = null
    faceAtlas.value = null
    bindings.value = {}
    pendingDubbing.value = null
    batchProgress.value = null
  }

  function abortPoll() {
    pollAbort = true
    pollGeneration += 1
    pollController?.abort()
    pollController = null
  }

  function cleanup() {
    abortPoll()
    releaseActiveJobResume(jobMode)
  }

  function formatTaskError(error) {
    if (error?.name === 'AbortError') return null
    if (error?.status === 404) {
      return '任务已过期（后端可能重启过），请重新点击「开始生成」'
    }
    return error?.message || String(error)
  }

  function fail(msg) {
    errorMsg.value = msg
    status.value = 'error'
    batchProgress.value = null
    saveActiveJob(null)
    cleanup()
  }

  async function finish(media, pid, tid, { batchIntermediate = false, lookbookName = null, startImageName = null } = {}) {
    queueHint.value = '视频已完成，正在截取末帧…'
    const enriched = await attachLastFrames(media)
    results.value = enriched.map((m) => ({
      ...m,
      url: m.url || viewUrl(m),
      lookbookName: lookbookName || m.lookbookName || null,
      startImageName: startImageName || m.startImageName || null
    }))
    onDone?.({
      promptId: pid || promptId.value,
      taskId: tid || taskId.value,
      media: results.value,
      mode: jobMode,
      time: new Date().toLocaleTimeString('zh-CN', { hour12: false })
    })
    if (batchIntermediate) return
    status.value = 'done'
    batchProgress.value = null
    saveActiveJob(null)
    cleanup()
  }

  function batchHint(current, total) {
    return `第 ${current}/${total} 次`
  }

  function normalizeRendered(result) {
    dubbingQa.value = result.qa ?? null
    return [{
      ...result.media,
      kind: 'video',
      dubbed: true,
      degraded: Boolean(result.degraded),
      degradations: result.degradations ?? [],
      qa: result.qa ?? null,
      bindings: result.bindings ?? bindings.value,
      sessionId: dubbingSessionId.value
    }]
  }

  async function renderPendingDubbing(bindingOverrides = {}) {
    if (!pendingDubbing.value || !dubbingSessionId.value) throw new Error('没有等待渲染的配音会话')
    status.value = 'rendering'
    queueHint.value = '正在按已确认的人脸绑定生成配音与口型…'
    try {
      const config = pendingDubbing.value
      const result = await renderDubSession({
        sessionId: dubbingSessionId.value,
        characters: config.characters,
        utterances: config.utterances,
        bindingOverrides
      })
      const media = normalizeRendered(result)
      await finish(media, promptId.value, taskId.value)
      return true
    } catch (e) {
      fail(e.message || String(e))
      return false
    }
  }

  async function applyDubbing(media, options) {
    if (engine !== 'wan' || !options?.enabled) return media
    const video = media.find((item) =>
      item.kind === 'video' || /\.(mp4|webm|mov|mkv)$/i.test(item.filename || '')
    )
    if (!video) throw new Error('生成结果中没有可配音的视频')

    status.value = 'analyzing'
    queueHint.value = '正在分析视觉母版中的人脸轨迹…'
    const config = {
      characters: options.characters || [],
      utterances: options.utterances || [],
      faceBindingMode: options.faceBindingMode || 'auto'
    }
    const analyzed = await analyzeDubSession(video, config)
    dubbingSessionId.value = analyzed.sessionId
    faceAtlas.value = analyzed.faceAtlas || { tracks: [] }
    bindings.value = normalizeBindings(analyzed.bindings)
    pendingDubbing.value = config
    saveActiveJob({
      promptId: promptId.value,
      taskId: taskId.value,
      mode: jobMode,
      phase: analyzed.status,
      media,
      dubbingSessionId: analyzed.sessionId,
      faceAtlas: faceAtlas.value,
      bindings: bindings.value,
      dubbing: config
    })
    if (analyzed.status === 'awaiting_binding') {
      status.value = 'awaiting_binding'
      queueHint.value = '请选择每位说话人对应的人脸轨迹'
      return null
    }
    status.value = 'rendering'
    queueHint.value = '人脸绑定完成，正在生成配音与口型…'
    const rendered = await renderDubSession({
      sessionId: analyzed.sessionId,
      characters: config.characters,
      utterances: config.utterances,
      bindingOverrides: bindings.value
    })
    return normalizeRendered(rendered)
  }

  function toBody(params, imageName, extra = {}) {
    const args = {
      prompt: params.positivePrompt ?? params.prompt ?? '',
      negative_prompt: params.negativePrompt ?? params.negative_prompt ?? '',
      engine,
      width: params.width,
      height: params.height,
      length: params.length,
      fps: params.fps,
      seed: params.seed,
      steps: params.steps,
      cfg: params.cfg,
      filename_prefix: params.filenamePrefix,
      use_lightx2v: Boolean(params.useLightX2V ?? params.use_lightx2v ?? false)
    }
    if (params.i2vStrength != null) args.i2v_strength = params.i2vStrength
    if (imageName) args.image_name = imageName
    if (extra.firstImageName) args.first_image_name = extra.firstImageName
    if (extra.lastImageName) args.last_image_name = extra.lastImageName
    if (params.firstImageName) args.first_image_name = params.firstImageName
    if (params.lastImageName) args.last_image_name = params.lastImageName
    // Wan-VACE：定妆照作 ref；场景起始可用末帧或定妆照本身
    if (params.useVace) {
      args.use_vace = true
      args.engine = 'wan'
      args.ref_image_name = params.refImageName || params.lookbookName || imageName
      if (params.imageName && !args.image_name) args.image_name = params.imageName
    }
    return Object.fromEntries(Object.entries(args).filter(([, v]) => v !== undefined && v !== null))
  }

  async function submit(body) {
    if (mode === 'i2v') return generateI2V(body)
    if (mode === 'flf2v') return generateFLF2V(body)
    return generateT2V(body)
  }

  async function uploadInputs(params) {
    let imageName = params.imageName || null
    let firstImageName = params.firstImageName || null
    let lastImageName = params.lastImageName || null
    let lookbookName = params.lookbookName || params.refImageName || null

    if (mode === 'i2v') {
      if (params.useVace && params.lookbookFile) {
        status.value = 'uploading'
        queueHint.value = '正在上传定妆照…'
        const upLb = await uploadImage(params.lookbookFile)
        lookbookName = upLb.name
      }

      if (!params.imageFile && !imageName) {
        // VACE：允许只传定妆照（起始回退为定妆照）；普通 I2V 必须有起始图
        if (params.useVace && lookbookName) {
          imageName = lookbookName
        } else {
          throw new Error('请先选择起始图片')
        }
      }
      if (params.imageFile) {
        status.value = 'uploading'
        queueHint.value = '正在上传起始图片…'
        const up = await uploadImage(params.imageFile)
        imageName = up.name
      }

      if (params.useVace && !lookbookName) {
        lookbookName = imageName
      }
    }

    if (mode === 'flf2v') {
      if ((!params.firstImageFile && !firstImageName) || (!params.lastImageFile && !lastImageName)) {
        throw new Error('请先选择首帧和尾帧图片')
      }
      status.value = 'uploading'
      queueHint.value = '正在上传首尾帧…'
      if (params.firstImageFile) {
        const up = await uploadImage(params.firstImageFile)
        firstImageName = up.name
      }
      if (params.lastImageFile) {
        const up = await uploadImage(params.lastImageFile)
        lastImageName = up.name
      }
    }

    return { imageName, firstImageName, lastImageName, lookbookName }
  }

  async function runOnce(params, uploaded, { timeoutMs, batchMeta } = {}) {
    const { imageName, firstImageName, lastImageName, lookbookName: uploadedLookbook } = uploaded
    const batchPrefix = batchMeta ? `${batchHint(batchMeta.current, batchMeta.total)} · ` : ''

    status.value = 'queued'
    queueHint.value = batchPrefix + (params.hint || '已提交，等待后端 / ComfyUI 执行…')
    progress.value = { value: 0, max: 0 }
    elapsedSec.value = 0

    const paramsWithRef = {
      ...params,
      lookbookName: uploadedLookbook || params.lookbookName,
      refImageName: uploadedLookbook || params.refImageName || params.lookbookName
    }

    const submitted = await submit(
      toBody(paramsWithRef, imageName, { firstImageName, lastImageName })
    )
    promptId.value = submitted.prompt_id
    taskId.value = submitted.task_id
    saveActiveJob({
      promptId: submitted.prompt_id,
      taskId: submitted.task_id,
      clientId: submitted.client_id,
      mode: jobMode,
      submittedAt: Date.now(),
      batch: batchMeta || null,
      dubbing: params.dubbingEnabled
        ? {
            enabled: true,
            characters: params.characters,
            utterances: params.utterances,
            faceBindingMode: params.faceBindingMode
          }
        : null
    })

    const defaultTimeout = engine === 'ltx' ? LTX_TIMEOUT_5S_MS : undefined
    const media = await waitPoll(submitted.task_id, timeoutMs ?? defaultTimeout, batchMeta)
    if (pollAbort) return

    const finalMedia = await applyDubbing(media, {
      enabled: engine === 'wan' && params.dubbingEnabled,
      characters: params.characters,
      utterances: params.utterances,
      faceBindingMode: params.faceBindingMode
    })
    const batchIntermediate = Boolean(batchMeta && batchMeta.current < batchMeta.total)
    const lookbook =
      uploaded.lookbookName || paramsWithRef.lookbookName || paramsWithRef.refImageName || uploaded.imageName || null
    const finishOpts = {
      batchIntermediate,
      lookbookName: lookbook,
      startImageName: uploaded.imageName || null
    }
    if (finalMedia) {
      await finish(finalMedia, submitted.prompt_id, submitted.task_id, finishOpts)
    } else if (media?.length) {
      await finish(media, submitted.prompt_id, submitted.task_id, finishOpts)
    }
  }

  async function generate(params, _unusedGraph, { timeoutMs } = {}) {
    cleanup()
    reset()
    pollAbort = false
    pollToken = pollGeneration

    try {
      const uploaded = await uploadInputs(params)
      await runOnce(params, uploaded, { timeoutMs })
    } catch (e) {
      const msg = formatTaskError(e)
      if (msg) fail(msg)
    }
  }

  async function generateBatch(params, _unusedGraph, { count = 5, timeoutMs } = {}) {
    if (params.dubbingEnabled) {
      throw new Error('连续生成与配音不能同时使用，请先关闭配音')
    }
    cleanup()
    reset()
    pollAbort = false
    pollToken = pollGeneration
    batchProgress.value = { current: 0, total: count }

    try {
      const uploaded = await uploadInputs(params)

      for (let i = 0; i < count; i++) {
        if (pollAbort) break
        batchProgress.value = { current: i + 1, total: count }

        const seed = params.randomSeed
          ? Math.floor(Math.random() * 2 ** 31)
          : params.seed

        await runOnce(
          { ...params, seed },
          uploaded,
          { timeoutMs, batchMeta: { current: i + 1, total: count } }
        )
        if (pollAbort) break
      }

      if (!pollAbort) {
        status.value = 'done'
        queueHint.value = `连续生成完成，共 ${count} 次`
        batchProgress.value = null
        saveActiveJob(null)
        cleanup()
      }
    } catch (e) {
      const msg = formatTaskError(e)
      if (msg) fail(msg)
    }
  }

  async function waitPoll(tid, timeoutMs, batchMeta) {
    pollController = new AbortController()
    const token = pollToken
    const batchPrefix = batchMeta ? `${batchHint(batchMeta.current, batchMeta.total)} · ` : ''
    return waitForVideoTask(tid, {
      intervalMs: 3000,
      timeoutMs: timeoutMs ?? 7200000,
      signal: pollController.signal,
      shouldContinue: () => !pollAbort && token === pollGeneration,
      onTick: ({ phase, elapsed, queuePos }) => {
        if (pollAbort) return
        elapsedSec.value = elapsed
        if (phase === 'queued') {
          status.value = 'queued'
          queueHint.value = batchPrefix + (queuePos > 0 ? `排队中，前面还有 ${queuePos} 个任务` : '排队中…')
        } else if (phase === 'running' || phase === 'waiting') {
          status.value = 'running'
          queueHint.value = batchPrefix + (phase === 'running' ? 'ComfyUI 正在生成…' : '等待写入结果…')
          progress.value = { value: phase === 'running' ? 1 : 0, max: 1 }
        }
      }
    })
  }

  async function resumeFromStorage() {
    const job = loadActiveJob()
    if (!job || job.mode !== jobMode || !(job.taskId || job.promptId)) return false

    abortPoll()
    if (!claimActiveJobResume(jobMode)) return false

    reset()
    pollAbort = false
    pollToken = pollGeneration
    promptId.value = job.promptId
    taskId.value = job.taskId
    if (job.phase === 'awaiting_binding' && job.dubbingSessionId) {
      dubbingSessionId.value = job.dubbingSessionId
      faceAtlas.value = job.faceAtlas || { tracks: [] }
      bindings.value = normalizeBindings(job.bindings)
      pendingDubbing.value = job.dubbing
      results.value = (job.media || []).map((item) => ({ ...item, url: item.url || viewUrl(item) }))
      status.value = 'awaiting_binding'
      queueHint.value = '已恢复待确认的人脸绑定会话'
      return true
    }
    status.value = 'running'
    queueHint.value = '检测到未完成任务，正在恢复…'

    if (!job.taskId) {
      fail('旧任务缺少 task_id，请重新提交')
      return false
    }

    const defaultTimeout = engine === 'ltx' ? LTX_TIMEOUT_5S_MS : undefined
    try {
      const media = await waitPoll(job.taskId, defaultTimeout)
      if (!pollAbort) {
        const finalMedia = await applyDubbing(media, job.dubbing)
        if (finalMedia) await finish(finalMedia, job.promptId, job.taskId)
        else if (media?.length) await finish(media, job.promptId, job.taskId)
      }
    } catch (e) {
      const msg = formatTaskError(e)
      if (msg) fail(msg)
    }
    return true
  }

  onUnmounted(cleanup)

  return {
    status,
    progress,
    progressPercent,
    currentNode,
    errorMsg,
    results,
    promptId,
    taskId,
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
    resumeFromStorage,
    reset,
    cleanup
  }
}
