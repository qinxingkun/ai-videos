/**
 * 成片时长预设（以 Wan 2.2 为主）。
 * 单段上限 MAX_SEGMENT_SEC=5s；更长成片靠增加段数，不靠加长单段。
 * 有效区 ≈ segmentSec - 2×discardZoneSec（生产模式头尾各裁）。
 */

import { DEFAULT_ANCHOR_BLEND_WEIGHT, LONG_CHAIN_ANCHOR_BLEND_WEIGHT } from './chainConfig.js'

/** 模型单次生成硬上限（秒） */
export const MAX_SEGMENT_SEC = 5

export const DURATION_PRESETS = {
  '30s': {
    id: '30s',
    label: '约 30 秒（6×5s）',
    shotCount: 6,
    segmentSec: 5,
    discardZoneSec: 1.0,
    timeoutScale: 1,
    /** 6×~3s 有效区 */
    finalDuration: { min: 15, max: 22 },
    segmentDuration: { min: 4.5, max: 6.0 },
    outputNamePrefix: 'final_30s',
    /** 短链只在末段拉回定妆照，中间不额外刷新 */
    anchorRefreshEvery: null,
    anchorBlendWeight: DEFAULT_ANCHOR_BLEND_WEIGHT
  },
  '90s': {
    id: '90s',
    /** 20×5s，头尾各裁 0.25s → 有效约 4.5s/段 → 成片约 90s */
    label: '约 90 秒（20×5s）',
    shotCount: 20,
    segmentSec: 5,
    discardZoneSec: 0.25,
    timeoutScale: 1,
    finalDuration: { min: 80, max: 100 },
    segmentDuration: { min: 4.5, max: 6.0 },
    outputNamePrefix: 'final_90s',
    /** 长链每 5 段做一次 FLF2V 锚点刷新，抑制误差累积漂移 */
    anchorRefreshEvery: 5,
    anchorBlendWeight: LONG_CHAIN_ANCHOR_BLEND_WEIGHT
  }
}

export const DEFAULT_DURATION_PRESET = '30s'

/** Wan length 为 4n+1；LTX 多为 8n+1 */
export function framesForSegmentSec(segmentSec, fps, engine = 'wan') {
  const capped = Math.min(MAX_SEGMENT_SEC, Math.max(1, segmentSec))
  const step = engine === 'wan' ? 4 : 8
  const target = Math.round(capped * fps) + 1
  const n = Math.max(1, Math.round((target - 1) / step))
  return n * step + 1
}

export function getDurationPreset(id = DEFAULT_DURATION_PRESET) {
  return DURATION_PRESETS[id] || DURATION_PRESETS[DEFAULT_DURATION_PRESET]
}

/**
 * @param {string} presetId
 * @param {'wan'|'ltx'} engine
 * @param {{ fps: number, timeoutMs?: number, frames5s?: number }} profile
 */
export function resolveRunConfig(presetId, engine, profile) {
  const preset = getDurationPreset(presetId)
  const fps = profile.fps
  const segmentSec = Math.min(MAX_SEGMENT_SEC, preset.segmentSec)
  // 优先用 profile 的 5s 帧数，保证与工作流默认一致
  const frames =
    segmentSec === 5 && profile.frames5s
      ? profile.frames5s
      : framesForSegmentSec(segmentSec, fps, engine)
  const nominal = frames / fps
  const timeoutMs = Math.round((profile.timeoutMs || 10 * 60 * 1000) * (preset.timeoutScale || 1))
  const discardZoneSec = preset.discardZoneSec
  return {
    ...preset,
    segmentSec,
    discardZoneSec,
    fps,
    frames,
    timeoutMs,
    segmentDuration: {
      min: preset.segmentDuration.min,
      max: preset.segmentDuration.max,
      nominal
    },
    expectedFinalSec: Math.round(
      preset.shotCount * Math.max(0.5, segmentSec - 2 * discardZoneSec)
    )
  }
}

/** 保证分镜数组长度为 shotCount（不足则补空位，过多则截断副本） */
export function padShotsToCount(shots, shotCount) {
  const list = (shots || []).map((s) =>
    Array.isArray(s)
      ? { name: s[0], prompt: s[1], dialogue: s[2] || '' }
      : { name: s.name, prompt: s.prompt || '', dialogue: s.dialogue || '', storyBeat: s.storyBeat }
  )
  while (list.length < shotCount) {
    const i = list.length + 1
    const prev = list[list.length - 1]
    list.push({
      name: `${String(i).padStart(2, '0')}_shot`,
      prompt:
        prev?.prompt
          ? `Continue the same scene and story after the previous beat, matching continuity, new camera angle, beat ${i}`
          : '',
      dialogue: ''
    })
  }
  return list.slice(0, shotCount)
}
