// 链式衔接与 Smart Splice 单一真相源（生产环境：防重复帧 / 流畅拼接）

export const LTX_FPS = 24
export const LTX_FRAMES_5S = 121

/** latent 注入尺寸（EmptyLTXVLatentVideo） */
export const LTX_LATENT_RES = { width: 768, height: 512 }

/** 期望 MP4 输出尺寸（与 latent 一致，无 2× upscaler） */
export const LTX_OUTPUT_RES = { width: 768, height: 512 }

/**
 * 对称丢弃区（秒）：每段头/尾各裁掉，消除链式 I2V 片头重播与片尾衔接冗余。
 * 有效区 ≈ segmentSec - 2×discard；默认 5s 段 → ~3s/段，6 段成片约 18s。
 */
export const DISCARD_ZONE_SEC = 1.0

/** @deprecated 使用 DISCARD_ZONE_SEC；保留别名兼容旧引用 */
export const CHAIN_EXTRACT_OFFSET_SEC = DISCARD_ZONE_SEC

/**
 * 链式抽帧：取「有效区最后一帧」相对文件末尾的偏移。
 * offset = discardTail + 1/fps，使参考帧 = 进成片的最后一帧，而非模糊的 -1.0s。
 */
export function chainExtractOffsetSec(fps = LTX_FPS, discardZoneSec = DISCARD_ZONE_SEC) {
  return discardZoneSec + 1 / fps
}

/** 链式 I2V strength：略降，减少片头冻结重播（原 0.68） */
export const CHAIN_I2V_STRENGTH = 0.58

/**
 * 锚点软拉回混合权重：链式起始图与角色定妆照按 (1-weight)/weight 混合后再送入 I2V。
 * 0 = 不拉回（纯链式，向后兼容）；数值越大越贴近定妆照但可能牺牲运镜连续性。
 * 短链（30s/6段）默认不开启；长链（90s/20段）默认小幅开启，逐段抑制人设漂移。
 */
export const DEFAULT_ANCHOR_BLEND_WEIGHT = 0
export const LONG_CHAIN_ANCHOR_BLEND_WEIGHT = 0.22

export const SPLICE_DEFAULTS = {
  tailSec: DISCARD_ZONE_SEC,
  headSec: DISCARD_ZONE_SEC,
  headMaxSec: 1.5,
  audioCrossfadeSec: 0.05,
  audioEdgeFadeSec: 0.03,
  /** 边界 micro-xfade 帧数（仅 smart-splice） */
  microVideoFadeFrames: 2,
  overlapSimilarityThreshold: 0.9,
  overlapMaxFrames: 48,
  /** 成片相邻帧 SSIM 连续超阈值的帧数 → 判为重复 */
  duplicateSsimThreshold: 0.97,
  duplicateMinFrames: 4,
  /** 接缝微观插帧（RIFE，需 ComfyUI-Frame-Interpolation）：默认关闭，失败自动回退 micro-xfade */
  seamInterp: false,
  seamInterpFrames: 3
}

export function trimHeadFrames(fps = LTX_FPS, discardZoneSec = DISCARD_ZONE_SEC) {
  return Math.round(discardZoneSec * fps)
}

export function trimTailFrames(fps = LTX_FPS, discardZoneSec = DISCARD_ZONE_SEC) {
  return Math.round(discardZoneSec * fps)
}

export function microVideoFadeSec(fps = LTX_FPS) {
  return SPLICE_DEFAULTS.microVideoFadeFrames / fps
}

/** 分段时长容差（秒）— 默认 5s 段；90s 预设由 durationPresets 覆盖 */
export const SEGMENT_DURATION = {
  min: 4.5,
  max: 6.0,
  nominal: LTX_FRAMES_5S / LTX_FPS
}

/** 6 段 smart-splice 成片预期时长（秒）：6×~3s 有效区 */
export const FINAL_DURATION = {
  min: 15,
  max: 22
}

/**
 * @param {object} [opts]
 * @param {number} [opts.discardZoneSec]
 * @param {number} [opts.fps]
 * @param {boolean} [opts.seamInterp]
 * @param {number} [opts.seamInterpFrames]
 */
export function resolveConcatOptionsFromChain(
  continuityMode,
  mode,
  isProductionModeFn,
  outputRes = LTX_OUTPUT_RES,
  opts = {}
) {
  const discard = opts.discardZoneSec ?? DISCARD_ZONE_SEC
  const fps = opts.fps ?? LTX_FPS
  const useSmartSplice =
    isProductionModeFn(continuityMode) ||
    (mode === 'i2v' && (continuityMode === 'chain' || continuityMode === 'chain+anchor'))

  if (useSmartSplice) {
    return {
      smartSplice: true,
      chainTrim: true,
      noFade: true,
      trimHeadFrames: trimHeadFrames(fps, discard),
      trimTailFrames: trimTailFrames(fps, discard),
      fadeDuration: 0,
      audioCrossfadeSec: SPLICE_DEFAULTS.audioCrossfadeSec,
      audioEdgeFadeSec: SPLICE_DEFAULTS.audioEdgeFadeSec,
      microVideoFadeSec: microVideoFadeSec(fps),
      outputWidth: outputRes.width,
      outputHeight: outputRes.height,
      discardZoneSec: discard,
      seamInterp: opts.seamInterp ?? SPLICE_DEFAULTS.seamInterp,
      seamInterpFrames: opts.seamInterpFrames ?? SPLICE_DEFAULTS.seamInterpFrames
    }
  }

  return {
    smartSplice: false,
    chainTrim: false,
    noFade: false,
    trimHeadFrames: 0,
    trimTailFrames: 0,
    fadeDuration: 0.12,
    audioCrossfadeSec: 0.12,
    microVideoFadeSec: 0,
    outputWidth: outputRes.width,
    outputHeight: outputRes.height,
    discardZoneSec: 0
  }
}
