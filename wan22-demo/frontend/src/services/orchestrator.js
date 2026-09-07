// 短剧辅助能力：REST API 封装（保持原函数名供 composable 使用）

import {
  checkHealth,
  checkHealthFull,
  extractVideoFrame as extractFrameApi,
  analyzeSplice as analyzeSpliceApi,
  validateSegment as validateSegmentApi,
  normalizeSegment as normalizeSegmentApi,
  validateFinal as validateFinalApi,
  detectDuplicateFrames as detectDupApi,
  detectFace as detectFaceApi,
  animateRelock as animateRelockApi,
  generateLookbook as generateLookbookApi,
  lookbookStatus as lookbookStatusApi,
  concatSegments as concatApi,
  dubMedia as dubMediaApi,
  analyzeDub as analyzeDubApi,
  renderDub as renderDubApi,
  getDubSession as getDubSessionApi,
  dubTrackUrl,
  listCharacters as listCharactersApi,
  saveCharacter as saveCharacterApi,
  deleteCharacter as deleteCharacterApi,
  viewUrl as toolViewUrl
} from './api.js'

export async function checkOrchestrator() {
  try {
    const data = await checkHealth()
    return data.ok === true
  } catch {
    return false
  }
}

export async function checkOrchestratorFull() {
  return checkHealthFull()
}

export async function extractVideoFrame(media, { position = 'last', outputName, offsetBeforeEnd, outputWidth, outputHeight } = {}) {
  if (!media?.filename) throw new Error('缺少视频文件名')
  return extractFrameApi({
    filename: media.filename,
    subfolder: media.subfolder ?? 'video',
    type: media.type ?? 'output',
    position,
    outputName,
    offsetBeforeEnd,
    outputWidth,
    outputHeight
  })
}

export async function analyzeSplice(filenames, options = {}) {
  return analyzeSpliceApi({
    files: filenames,
    inputDir: options.inputDir,
    fps: options.fps ?? 24,
    tailSec: options.tailSec,
    headSec: options.headSec,
    headMaxSec: options.headMaxSec
  })
}

/** 与后端 character_qa.DEFAULT_IDENTITY_THRESHOLD 对齐 */
export const DEFAULT_IDENTITY_THRESHOLD = 0.32

export async function validateSegment(media, options = {}) {
  return validateSegmentApi({
    filename: media.filename,
    subfolder: media.subfolder ?? 'video',
    type: media.type ?? 'output',
    expectedWidth: options.expectedWidth,
    expectedHeight: options.expectedHeight,
    minDuration: options.minDuration,
    maxDuration: options.maxDuration,
    requireAudio: options.requireAudio ?? false,
    expectedFrames: options.expectedFrames,
    expectedFps: options.expectedFps,
    referenceImageName: options.referenceImageName,
    identityThreshold: options.identityThreshold,
    checkIdentity: options.checkIdentity,
    identityMaxFrames: options.identityMaxFrames
  })
}

export async function detectFaceInImage(imageName, options = {}) {
  if (!imageName) throw new Error('缺少图片文件名')
  return detectFaceApi({
    imageName,
    filename: imageName,
    subfolder: options.subfolder ?? '',
    type: options.type ?? 'input',
    path: options.path
  })
}

export async function createLookbook(params) {
  return generateLookbookApi(params)
}

export async function getLookbookStatus() {
  return lookbookStatusApi()
}

export async function normalizeSegmentDuration(media, options = {}) {
  if (!media?.filename) throw new Error('缺少视频文件名')
  return normalizeSegmentApi({
    filename: media.filename,
    subfolder: media.subfolder ?? 'video',
    type: media.type ?? 'output',
    path: media.path,
    expectedFrames: options.expectedFrames ?? 81,
    fps: options.fps ?? 16,
    maxDuration: options.maxDuration,
    outputName: options.outputName
  })
}

export function isDurationOnlyFailure(issues = []) {
  return Array.isArray(issues) && issues.length > 0 && issues.every((item) => String(item).startsWith('duration '))
}

/** 宽高不符：换 seed / 自愈重试无法修复，应立即人工介入并核对 UI 分辨率与工作流。 */
export function isResolutionMismatchFailure(issues = []) {
  if (!Array.isArray(issues) || !issues.length) return false
  return issues.every((item) => {
    const s = String(item)
    return s.startsWith('width ') || s.startsWith('height ')
  })
}

export async function validateFinalVideo(media, options = {}) {
  return validateFinalApi({
    filename: media.filename,
    output: media.filename,
    inputDir: options.inputDir,
    expectedWidth: options.expectedWidth,
    expectedHeight: options.expectedHeight,
    minDuration: options.minDuration,
    maxDuration: options.maxDuration,
    requireAudio: options.requireAudio ?? true
  })
}

export async function detectDuplicateFrames(media, options = {}) {
  return detectDupApi({
    filename: media.filename,
    subfolder: media.subfolder ?? 'video',
    type: media.type ?? 'output',
    path: media.path,
    ssimThreshold: options.ssimThreshold,
    minFrames: options.minFrames,
    sampleFps: options.sampleFps
  })
}

/**
 * 阶段四（可选）：对单个关键分段做 Wan2.2-Animate 身份锁定重渲染。
 * 失败时后端会返回 applied=false 并原样回传输入分段，调用方据此回退，不抛错。
 */
export async function applyAnimateRelock(media, { referenceImageName, seed, output } = {}) {
  if (!media?.filename) throw new Error('缺少视频文件名')
  if (!referenceImageName) throw new Error('身份锁定重渲染需要参考定妆照')
  return animateRelockApi({
    filename: media.filename,
    subfolder: media.subfolder ?? 'video',
    type: media.type ?? 'output',
    referenceImageName,
    seed,
    output
  })
}

export async function concatSegments(filenames, options = {}) {
  return concatApi({
    files: filenames,
    inputDir: options.inputDir,
    output: options.outputName || `final_${Date.now()}.mp4`,
    fade: options.fadeDuration ?? 0.2,
    fps: options.fps ?? 24,
    frames: options.frames ?? 121,
    noFade: options.noFade ?? false,
    chainTrim: options.chainTrim ?? false,
    smartSplice: options.smartSplice ?? false,
    splicePlan: options.splicePlan ?? null,
    trimHeadFrames: options.trimHeadFrames,
    trimTailFrames: options.trimTailFrames,
    tailSec: options.tailSec,
    headSec: options.headSec,
    audioCrossfadeSec: options.audioCrossfadeSec,
    microVideoFadeSec: options.microVideoFadeSec,
    outputWidth: options.outputWidth,
    outputHeight: options.outputHeight,
    seamInterp: options.seamInterp ?? false,
    seamInterpFrames: options.seamInterpFrames
  })
}

function normalizeBindingOverrides(value) {
  if (!value) return {}
  if (Array.isArray(value)) {
    return Object.fromEntries(
      value
        .map((item) => [item.speakerId || item.characterId || item.id, item.faceTrackId || item.trackId])
        .filter(([speakerId, trackId]) => speakerId && trackId)
    )
  }
  return Object.fromEntries(
    Object.entries(value).map(([speakerId, binding]) => [
      speakerId,
      typeof binding === 'object' ? binding.faceTrackId || binding.trackId || binding.id : binding
    ])
  )
}

export async function dubFinalVideo(media, options = {}) {
  const analyzed = await analyzeDubSession(media, {
    characters: options.characters ?? [],
    faceBindingMode: options.faceBindingMode ?? 'auto'
  })
  if (analyzed.status === 'awaiting_binding' && !options.bindingOverrides) {
    if (options.allowAwaitingBinding) {
      return {
        awaitingBinding: true,
        sessionId: analyzed.sessionId,
        faceAtlas: analyzed.faceAtlas,
        bindings: analyzed.bindings,
        analysis: analyzed
      }
    }
    const error = new Error('人脸绑定存在歧义，请完成人工绑定或为角色设置 faceTrackId')
    error.code = 'AWAITING_BINDING'
    error.analysis = analyzed
    throw error
  }
  const rendered = await renderDubSession({
    sessionId: analyzed.sessionId,
    characters: options.characters ?? [],
    utterances: options.utterances ?? [],
    bindingOverrides: normalizeBindingOverrides(options.bindingOverrides ?? {}),
    output: options.output
  })
  return { ...rendered, sessionId: analyzed.sessionId, bindings: rendered.bindings ?? analyzed.bindings }
}

/** 为独立的 Wan T2V / I2V 5s 视频生成单段配音。帧号基于 25fps 视觉母版。 */
export async function dubSingleVideo(media, options = {}) {
  if (!media?.filename) throw new Error('配音缺少视频文件名')
  const text = String(options.text || '').trim()
  if (!text) throw new Error('启用配音后必须填写台词')
  const startFrame = Number(options.startFrame ?? 0)
  const endFrame = Number(options.endFrame ?? 125)
  if (!Number.isInteger(startFrame) || !Number.isInteger(endFrame) || endFrame <= startFrame) {
    throw new Error('配音起止帧无效')
  }

  const result = await dubMediaApi({
    media: {
      filename: media.filename,
      subfolder: media.subfolder ?? 'video',
      type: media.type ?? 'output',
      path: media.path
    },
    segments: [{
      text,
      voiceId: String(options.voiceId || '').trim() || null,
      startFrame,
      endFrame,
      lipSyncPolicy: options.lipSyncPolicy ?? 'off',
      shotIndex: 0
    }],
    fps: 25,
    sampleRate: 48000
  })
  if (!result?.media?.filename) throw new Error('配音接口未返回 media.filename')
  return result
}

function normalizeMedia(media) {
  if (!media?.filename) throw new Error('配音缺少视频文件名')
  return {
    filename: media.filename,
    subfolder: media.subfolder ?? 'video',
    type: media.type ?? 'output',
    path: media.path
  }
}

export async function analyzeDubSession(media, { characters = [], faceBindingMode = 'auto' } = {}) {
  return analyzeDubApi({
    media: normalizeMedia(media),
    characters,
    faceBindingMode
  })
}

export async function renderDubSession({
  sessionId,
  characters = [],
  utterances = [],
  bindingOverrides = {},
  output
} = {}) {
  if (!sessionId) throw new Error('缺少配音 sessionId')
  try {
    const result = await renderDubApi({
      sessionId,
      characters,
      utterances,
      bindingOverrides: normalizeBindingOverrides(bindingOverrides),
      ...(output ? { output } : {})
    })
    if (!result?.media?.filename) throw new Error('配音渲染接口未返回 media.filename')
    return result
  } catch (error) {
    const mapped = formatDubbingError(error, sessionId)
    throw mapped
  }
}

export async function getDubSession(sessionId) {
  if (!sessionId) throw new Error('缺少配音 sessionId')
  return getDubSessionApi(sessionId)
}

export function formatDubbingError(error, sessionId) {
  const detail = error?.detail
  const issues = Array.isArray(error?.issues)
    ? error.issues
    : Array.isArray(detail?.issues)
      ? detail.issues
      : []
  const code = error?.code || detail?.code
  const sid = error?.sessionId || detail?.sessionId || sessionId
  let message = error?.message || String(error)
  if (code === 'BINDING_REQUIRED') {
    message = `仍有台词未绑定人脸轨道：${(error.utteranceIds || detail?.utteranceIds || []).join(', ') || '请人工确认'}`
  } else if (code === 'REQUIRED_LIPSYNC_FAILED') {
    message = `必须口型同步失败：${issues.join('; ') || message}`
  } else if (code === 'AV_QA_FAILED') {
    message = `配音成片质检失败：${issues.join('; ') || message}`
  } else if (issues.length) {
    message = `${message}${message.endsWith('。') ? '' : '。'}${issues.join('; ')}`
  }
  const mapped = new Error(message)
  mapped.code = code
  mapped.sessionId = sid
  mapped.utteranceIds = error?.utteranceIds || detail?.utteranceIds || []
  mapped.issues = issues
  mapped.detail = detail
  mapped.retainSession = true
  return mapped
}

export function faceTrackThumbnailUrl(sessionId, track) {
  return dubTrackUrl(sessionId, track?.thumbnail || track?.filename || '')
}

export async function listCharacters() {
  return listCharactersApi()
}

export async function saveCharacter({ id, name, character }) {
  return saveCharacterApi({ id, name, character })
}

export async function deleteCharacter(id) {
  return deleteCharacterApi(id)
}

export { toolViewUrl as viewUrl }
