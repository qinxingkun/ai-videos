#!/usr/bin/env node
/**
 * Wan 2.2 + LTX 2.3 短剧 6 段 × 5s
 */
import t2vLightx2vWorkflow from '../workflows/t2v_lightx2v.api.json'
import i2vWorkflow from '../workflows/i2v.api.json'
import ltx23T2vWorkflow from '../workflows/ltx23_t2v.api.json'
import ltx23I2vWorkflow from '../workflows/ltx23_i2v.api.json'
import ltx23Flf2vWorkflow from '../workflows/ltx23_flf2v.api.json'
import { buildT2V, buildI2V, buildLTX23T2V, buildLTX23I2V, buildLTX23FLF2V } from './workflow.js'
import {
  FPS as WAN_FPS,
  FRAMES_5S as WAN_FRAMES_5S,
  RES_30S as WAN_RES,
  TIMEOUT_5S_MS as WAN_TIMEOUT_5S_MS
} from './frameUtils.js'
import {
  LTX_FPS,
  LTX_FRAMES_5S,
  LTX_LATENT_RES,
  LTX_OUTPUT_RES
} from './chainConfig.js'
import { ANTI_DRIFT_NEGATIVE } from './characterBible.js'

export { LTX_FPS, LTX_FRAMES_5S }
export const LTX_RES = LTX_LATENT_RES
export const LTX_OUTPUT = LTX_OUTPUT_RES
export const WAN_OUTPUT_RES = { width: WAN_RES.width, height: WAN_RES.height }
export const LTX_TIMEOUT_5S_MS = 20 * 60 * 1000

/** 长链人设漂移是多分镜场景的核心质量风险，默认负向提示统一追加防漂移词条 */
export const WAN_DEFAULT_NEG =
  `色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, 整体发灰, 最差质量, 低质量, ${ANTI_DRIFT_NEGATIVE}`

export const LTX_ANTI_SUBTITLE_NEG =
  'on-screen subtitles, burned-in captions, subtitle overlay, closed captions, caption text, Chinese subtitles, blurry text, illegible text, garbled text, screen text, text overlay, floating text, subtitle bar, 字幕, 中文字幕, 烧录字幕, 画面文字, 模糊字幕, 乱码字幕'

export const LTX_ANTI_EXTRA_JANITOR_NEG =
  'two janitors, multiple cleaners, second janitor, engineers in cleaning uniform, engineers holding mop, all characters in blue coveralls, everyone wearing janitor clothes, duplicate janitor, cleaning crew of three'

export const LTX_DEFAULT_NEG =
  `pc game, console game, video game, cartoon, childish, ugly, blurry, low quality, watermark, text, subtitles, ${LTX_ANTI_SUBTITLE_NEG}, ${LTX_ANTI_EXTRA_JANITOR_NEG}, frozen opening, static hold, looping motion, repeated frame, stuttering video, replay previous shot, ${ANTI_DRIFT_NEGATIVE}`

export const LTX_DIALOGUE_NEG =
  `pc game, cartoon, childish, ugly, blurry, low quality, watermark, silent audio, muted audio, no speech, lip sync error, distorted voice, frozen opening, static hold, looping motion, repeated frame, stuttering video, replay previous shot, still pose hold, frozen first frames, ${ANTI_DRIFT_NEGATIVE}`

/** @typedef {'anchor' | 'chain' | 'chain+anchor' | 'production'} ContinuityMode */

export function isProductionMode(continuityMode) {
  return continuityMode === 'production'
}

export function needsChainOrchestrator(continuityMode, mode) {
  if (isProductionMode(continuityMode)) return true
  return mode === 'i2v' && continuityMode !== 'anchor'
}

/** @typedef {'wan' | 'ltx'} MultiShotEngine */

export const MULTI_SHOT_PROFILES = {
  'wan-t2v': {
    id: 'wan22',
    engine: 'wan',
    label: 'Wan 2.2 14B + LightX2V',
    mode: 't2v',
    description: '6 段 × 5s，16fps，1280×720，Smart Splice 拼接。首段约 4–5 分钟，后续每段约 40 秒。',
    baseGraph: t2vLightx2vWorkflow,
    buildGraph: buildT2V,
    fps: WAN_FPS,
    frames5s: WAN_FRAMES_5S,
    res: WAN_RES,
    outputRes: WAN_OUTPUT_RES,
    timeoutMs: WAN_TIMEOUT_5S_MS,
    defaultNeg: WAN_DEFAULT_NEG,
    filenamePrefix: (name) => `video/shot_${name}`,
    buildOptions: { useLightX2V: true },
    supportsI2v: false,
    supportsContinuity: true
  },
  'wan-i2v': {
    id: 'wan22',
    engine: 'wan',
    label: 'Wan 2.2 14B I2V',
    mode: 'i2v',
    description: '图生视频 + 链式末帧衔接，1280×720。每段约 40 秒–2 分钟。',
    baseGraph: i2vWorkflow,
    buildGraph: buildI2V,
    fps: WAN_FPS,
    frames5s: WAN_FRAMES_5S,
    res: WAN_RES,
    outputRes: WAN_OUTPUT_RES,
    timeoutMs: WAN_TIMEOUT_5S_MS,
    defaultNeg: WAN_DEFAULT_NEG,
    filenamePrefix: (name) => `video/shot_${name}`,
    buildOptions: {},
    supportsI2v: true,
    supportsContinuity: true
  },
  'ltx-t2v': {
    id: 'ltx23',
    engine: 'ltx',
    label: 'LTX 2.3 22B（蒸馏 LoRA）',
    mode: 't2v',
    description: '文生视频：768×512，24fps，含音频。每段约 10–20 分钟。',
    baseGraph: ltx23T2vWorkflow,
    buildGraph: buildLTX23T2V,
    fps: LTX_FPS,
    frames5s: LTX_FRAMES_5S,
    res: LTX_LATENT_RES,
    outputRes: LTX_OUTPUT_RES,
    timeoutMs: LTX_TIMEOUT_5S_MS,
    defaultNeg: LTX_DEFAULT_NEG,
    filenamePrefix: (name) => `video/LTX23_t2v_${name}`,
    buildOptions: {},
    supportsI2v: false,
    supportsContinuity: true
  },
  'ltx-i2v': {
    id: 'ltx23',
    engine: 'ltx',
    label: 'LTX 2.3 22B（蒸馏 LoRA）',
    mode: 'i2v',
    description: '图生视频 + 链式首尾帧：定妆照锚定 + 段间末帧衔接。每段约 10–20 分钟。',
    baseGraph: ltx23I2vWorkflow,
    buildGraph: buildLTX23I2V,
    fps: LTX_FPS,
    frames5s: LTX_FRAMES_5S,
    res: LTX_LATENT_RES,
    outputRes: LTX_OUTPUT_RES,
    timeoutMs: LTX_TIMEOUT_5S_MS,
    defaultNeg: LTX_DEFAULT_NEG,
    filenamePrefix: (name) => `video/LTX23_i2v_${name}`,
    buildOptions: {},
    supportsI2v: true,
    supportsContinuity: true
  },
  'ltx-flf2v': {
    id: 'ltx23',
    engine: 'ltx',
    label: 'LTX 2.3 FLF2V',
    mode: 'flf2v',
    description: '首尾帧双端约束，用于每 3 段锚点刷新。',
    baseGraph: ltx23Flf2vWorkflow,
    buildGraph: buildLTX23FLF2V,
    fps: LTX_FPS,
    frames5s: LTX_FRAMES_5S,
    res: LTX_LATENT_RES,
    outputRes: LTX_OUTPUT_RES,
    timeoutMs: LTX_TIMEOUT_5S_MS,
    defaultNeg: LTX_DEFAULT_NEG,
    filenamePrefix: (name) => `video/LTX23_flf2v_${name}`,
    buildOptions: {},
    supportsI2v: true,
    supportsContinuity: true
  }
}

/**
 * @param {MultiShotEngine} engine
 * @param {'t2v' | 'i2v' | 'flf2v'} mode
 */
export function getMultiShotProfile(engine, mode = 't2v') {
  if (engine === 'wan' && mode === 'i2v') return MULTI_SHOT_PROFILES['wan-i2v']
  if (engine === 'wan') return MULTI_SHOT_PROFILES['wan-t2v']
  if (engine === 'ltx' && mode === 'flf2v') return MULTI_SHOT_PROFILES['ltx-flf2v']
  if (engine === 'ltx' && mode === 'i2v') return MULTI_SHOT_PROFILES['ltx-i2v']
  return MULTI_SHOT_PROFILES['ltx-t2v']
}

/**
 * 第 i 段（0-based）是否应使用 FLF2V 锚点刷新。
 * 生产环境默认仅最后一段拉回定妆照；若指定 anchorRefreshEvery（长链场景，
 * 如 90s/20 段预设），则按节奏每 N 段刷新一次，抑制误差累积导致的人设漂移。
 * chain+anchor 模式仍保留每 3 段刷新行为。
 * @param {number} [shotCount=6]
 * @param {number|null} [anchorRefreshEvery] 生产模式下的刷新节奏（段数），null/0 表示仅末段
 */
export function shouldUseFlf2vRefresh(
  segmentIndex,
  continuityMode,
  engine = 'ltx',
  shotCount = 6,
  anchorRefreshEvery = null
) {
  if (engine !== 'ltx') return false
  if (isProductionMode(continuityMode)) {
    const lastIndex = Math.max(0, shotCount - 1)
    if (segmentIndex === lastIndex) return true
    if (anchorRefreshEvery && anchorRefreshEvery > 0) {
      return segmentIndex > 0 && (segmentIndex + 1) % anchorRefreshEvery === 0
    }
    return false
  }
  if (continuityMode !== 'chain+anchor') return false
  return (segmentIndex + 1) % 3 === 0 && segmentIndex > 0
}

function resolveBaseProfile(engine, mode, segmentIndex, continuityMode, opts) {
  const shotCount = opts.shotCount ?? 6
  const anchorRefreshEvery = opts.anchorRefreshEvery ?? null

  // 品牌包产品等镜头：强制纯 T2V，避免链式/FLF2V 以上一段暗场作首帧导致全黑虚影
  if (opts.forceT2v && engine === 'ltx') {
    return MULTI_SHOT_PROFILES['ltx-t2v']
  }

  if (engine === 'wan' && isProductionMode(continuityMode)) {
    if (segmentIndex === 0) {
      return opts.productionSeg1I2v
        ? MULTI_SHOT_PROFILES['wan-i2v']
        : MULTI_SHOT_PROFILES['wan-t2v']
    }
    return MULTI_SHOT_PROFILES['wan-i2v']
  }
  if (engine === 'ltx' && isProductionMode(continuityMode)) {
    if (shouldUseFlf2vRefresh(segmentIndex, continuityMode, engine, shotCount, anchorRefreshEvery)) {
      return MULTI_SHOT_PROFILES['ltx-flf2v']
    }
    if (segmentIndex === 0) {
      return opts.productionSeg1I2v
        ? MULTI_SHOT_PROFILES['ltx-i2v']
        : MULTI_SHOT_PROFILES['ltx-t2v']
    }
    return MULTI_SHOT_PROFILES['ltx-i2v']
  }
  if (
    engine === 'ltx' &&
    mode === 'i2v' &&
    shouldUseFlf2vRefresh(segmentIndex, continuityMode, engine, shotCount, anchorRefreshEvery)
  ) {
    return MULTI_SHOT_PROFILES['ltx-flf2v']
  }
  return getMultiShotProfile(engine, mode)
}

/**
 * 该分段是否属于"关键镜头"（默认首尾两段，如特写/开场/结尾），
 * 用于阶段四可选的 Wan2.2-Animate 身份锁定重渲染。
 * @param {number} segmentIndex
 * @param {number} shotCount
 * @param {number[]|null} [explicitShots] 显式指定的关键镜头下标（0-based），未指定则默认首尾两段
 */
export function isKeyRelockShot(segmentIndex, shotCount, explicitShots = null) {
  if (Array.isArray(explicitShots) && explicitShots.length > 0) {
    return explicitShots.includes(segmentIndex)
  }
  const lastIndex = Math.max(0, shotCount - 1)
  return segmentIndex === 0 || segmentIndex === lastIndex
}

/**
 * @param {object} [opts]
 * @param {boolean} [opts.productionSeg1I2v] production 模式下第 1 段是否 I2V 定妆
 * @param {number} [opts.shotCount]
 * @param {number|null} [opts.anchorRefreshEvery]
 * @param {boolean} [opts.animateRelock] 阶段四（可选）：关键镜头身份锁定重渲染开关，默认关闭
 * @param {number[]|null} [opts.animateRelockShots] 显式指定关键镜头下标，未指定默认首尾两段
 * @param {boolean} [opts.forceT2v] 该段强制纯 T2V（品牌包产品等，跳过链式/FLF2V）
 */
export function resolveSegmentProfile(engine, mode, segmentIndex, continuityMode, opts = {}) {
  const base = resolveBaseProfile(engine, mode, segmentIndex, continuityMode, opts)
  const shotCount = opts.shotCount ?? 6
  if (opts.animateRelock && isKeyRelockShot(segmentIndex, shotCount, opts.animateRelockShots)) {
    return { ...base, animateRelock: true }
  }
  return base
}
