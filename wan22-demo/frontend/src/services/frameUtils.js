// Wan 2.2 帧数 / 时长工具（VAE 要求 length 为 4n+1）

export const FPS = 16
export const FRAMES_5S = 81
export const FRAMES_10S = 161
export const FRAMES_30S = 481
export const MULTI_SHOT_COUNT = 6

/** Wan 2.2 标准分辨率 */
export const RES_480P = { width: 832, height: 480 }
export const RES_720P = { width: 1280, height: 720 }

/** 30s 多分镜默认分辨率（720P） */
export const RES_30S = RES_720P

/** ComfyUI Wan 节点要求宽高为 16 的倍数 */
export const WAN_RES_STEP = 16

export const WAN_RES_PRESETS = [
  {
    id: '480p',
    label: '480P',
    width: RES_480P.width,
    height: RES_480P.height,
    hint: '832×480 · 模型原生分辨率，显存占用低，FLF2V 更稳'
  },
  {
    id: '720p',
    label: '720P',
    width: RES_720P.width,
    height: RES_720P.height,
    hint: '1280×720 · 高清输出，显存占用较高'
  },
  {
    id: 'custom',
    label: '自定义',
    width: null,
    height: null,
    hint: '宽高须为 16 的倍数（16–16384）'
  }
]

export function snapWanDimension(value) {
  const n = Math.round(Number(value) || WAN_RES_STEP)
  const clamped = Math.max(WAN_RES_STEP, Math.min(16384, n))
  return Math.round(clamped / WAN_RES_STEP) * WAN_RES_STEP
}

export function formatResolution(width, height) {
  return `${width}×${height}`
}

export function detectWanPreset(width, height) {
  for (const preset of WAN_RES_PRESETS) {
    if (preset.id === 'custom') continue
    if (preset.width === width && preset.height === height) return preset.id
  }
  return 'custom'
}

export function validateWanResolution(width, height) {
  const w = Number(width)
  const h = Number(height)
  if (!Number.isFinite(w) || !Number.isFinite(h)) {
    return { ok: false, error: '分辨率须为有效数字' }
  }
  if (w < WAN_RES_STEP || h < WAN_RES_STEP) {
    return { ok: false, error: `分辨率不能小于 ${WAN_RES_STEP}` }
  }
  if (w % WAN_RES_STEP !== 0 || h % WAN_RES_STEP !== 0) {
    return { ok: false, error: `宽高须为 ${WAN_RES_STEP} 的倍数（如 832×480、1280×720）` }
  }
  return { ok: true }
}

export function isValidFrameCount(n) {
  return Number.isInteger(n) && n >= 1 && (n - 1) % 4 === 0
}

export function durationSec(frames, fps = FPS) {
  return frames / fps
}

export function formatDuration(frames, fps = FPS) {
  const sec = durationSec(frames, fps)
  return `${sec.toFixed(2)}s (${frames} 帧 @ ${fps}fps)`
}

/** 单次 30s 生成超时（毫秒） */
export const TIMEOUT_30S_MS = 30 * 60 * 1000

/** LightX2V 5s 段生成超时 */
export const TIMEOUT_5S_MS = 10 * 60 * 1000
