// 把用户填的参数注入到 ComfyUI 的 API 格式工作流里。
// 设计目标：不依赖固定节点 id —— 通过 class_type + 顺着连线遍历来定位节点，
// 这样你重新导出、节点 id 变了也能正常工作。找不到时再用 workflowConfig.js 的手动覆盖。

import { overrides, CLASS } from './workflowConfig.js'

const isLink = (v) => Array.isArray(v) && v.length === 2 && typeof v[1] === 'number'

// ComfyUI 的 /prompt 只接受 { "节点id": { class_type, inputs } }。
// 顶层若混入 __comment__ 等字段会直接 500，提交前必须剔除。
export function sanitizePromptGraph(graph) {
  const clean = {}
  for (const [id, node] of Object.entries(graph || {})) {
    if (node && typeof node === 'object' && node.class_type) {
      clean[id] = node
    }
  }
  return clean
}

export function clone(graph) {
  return sanitizePromptGraph(JSON.parse(JSON.stringify(graph)))
}

function entries(graph) {
  return Object.entries(graph).filter(([, node]) => node && typeof node === 'object' && node.class_type)
}

function findByClass(graph, classNames) {
  const set = new Set(classNames)
  return entries(graph)
    .filter(([, node]) => set.has(node.class_type))
    .map(([id, node]) => ({ id, node }))
}

function getNode(graph, id) {
  return id != null ? graph[id] : undefined
}

// 从某个起点节点的某个输入开始，顺着连线找到第一个匹配 class_type 的上游节点 id。
// 向上递归时优先沿用同名输入（如 positive/negative），避免在中间节点（如 WanImageToVideo
// 同时含 positive 和 negative 输入）上选错分支。
function resolveUpstream(graph, startId, inputName, targetClasses, depth = 0) {
  if (depth > 8) return null
  const node = getNode(graph, startId)
  if (!node?.inputs) return null
  const link = node.inputs[inputName]
  if (!isLink(link)) return null
  const upstreamId = link[0]
  const upstream = getNode(graph, upstreamId)
  if (!upstream) return null
  if (targetClasses.includes(upstream.class_type)) return upstreamId

  // 优先沿同名输入向上，其次再尝试其它输入
  const keys = Object.keys(upstream.inputs || {})
  const ordered = keys.includes(inputName) ? [inputName, ...keys.filter((k) => k !== inputName)] : keys
  for (const key of ordered) {
    if (isLink(upstream.inputs[key])) {
      const found = resolveUpstream(graph, upstreamId, key, targetClasses, depth + 1)
      if (found) return found
    }
  }
  return null
}

// 定位正/负向提示词节点：优先从采样器的 positive/negative 输入顺线找 CLIPTextEncode。
function locatePrompts(graph, samplerIds, ov) {
  let positive = ov.positivePrompt
  let negative = ov.negativePrompt

  for (const sid of samplerIds) {
    if (!positive) positive = resolveUpstream(graph, sid, 'positive', CLASS.clipTextEncode)
    if (!negative) negative = resolveUpstream(graph, sid, 'negative', CLASS.clipTextEncode)
    if (positive && negative) break
  }

  // 实在找不到（比如只有一个采样器没连两端），退化为按 class_type 取前两个。
  if (!positive || !negative) {
    const encs = findByClass(graph, CLASS.clipTextEncode).map((e) => e.id)
    if (!positive) positive = encs[0] ?? null
    if (!negative) negative = encs.find((id) => id !== positive) ?? null
  }
  return { positive, negative }
}

function setInput(graph, id, key, value) {
  const node = getNode(graph, id)
  if (node?.inputs && key in node.inputs && !isLink(node.inputs[key])) {
    node.inputs[key] = value
    return true
  }
  // 即使原本不存在该字段，部分节点也允许直接写入
  if (node?.inputs && !isLink(node.inputs[key])) {
    node.inputs[key] = value
    return true
  }
  return false
}

/** 覆盖连线型输入（Primitive/表达式节点在 API 导出中常需替换为字面量） */
export function forceSetInput(graph, id, key, value) {
  const node = getNode(graph, id)
  if (!node?.inputs) return false
  node.inputs[key] = value
  return true
}

function applySamplerParams(graph, samplerIds, { seed, steps, cfg }) {
  for (const sid of samplerIds) {
    const node = getNode(graph, sid)
    if (!node) continue
    if (seed != null) {
      if ('noise_seed' in node.inputs) setInput(graph, sid, 'noise_seed', seed)
      else if ('seed' in node.inputs) setInput(graph, sid, 'seed', seed)
    }
    if (steps != null && 'steps' in node.inputs) setInput(graph, sid, 'steps', steps)
    if (cfg != null && 'cfg' in node.inputs) setInput(graph, sid, 'cfg', cfg)
  }
}

function findCreateVideo(graph) {
  return findByClass(graph, ['CreateVideo'])[0]?.id ?? null
}

function findSaveVideo(graph) {
  const ids = findByClass(graph, CLASS.saveVideo).map((e) => e.id)
  return ids[0] ?? null
}

export function setFps(graph, fps) {
  const id = findCreateVideo(graph)
  if (id != null && fps != null) forceSetInput(graph, id, 'fps', fps)
}

export function setFilenamePrefix(graph, prefix) {
  const id = findSaveVideo(graph)
  if (id != null && prefix != null) setInput(graph, id, 'filename_prefix', prefix)
}

// LightX2V：4 步、cfg 1.0，高噪 0–2 / 低噪 2–4（按 start_at_step 区分两段采样器）
export function applyLightX2VDefaults(graph, samplerIds) {
  const ids = samplerIds || findByClass(graph, CLASS.samplers).map((s) => s.id)
  const samplers = ids
    .map((id) => ({ id, node: getNode(graph, id) }))
    .filter((s) => s.node?.class_type === 'KSamplerAdvanced')
    .sort((a, b) => (a.node.inputs?.start_at_step ?? 0) - (b.node.inputs?.start_at_step ?? 0))

  const steps = 4
  const cfg = 1.0
  const split = 2

  for (const { id, node } of samplers) {
    setInput(graph, id, 'steps', steps)
    setInput(graph, id, 'cfg', cfg)
    const start = node.inputs?.start_at_step ?? 0
    if (start === 0) {
      setInput(graph, id, 'end_at_step', split)
      setInput(graph, id, 'add_noise', 'enable')
      setInput(graph, id, 'return_with_leftover_noise', 'enable')
    } else {
      setInput(graph, id, 'start_at_step', split)
      setInput(graph, id, 'end_at_step', steps)
      setInput(graph, id, 'add_noise', 'disable')
      setInput(graph, id, 'return_with_leftover_noise', 'disable')
    }
  }
}

// 文生视频参数注入
export function buildT2V(baseGraph, params) {
  const graph = clone(baseGraph)
  const ov = overrides.t2v
  const samplerIds = ov.samplers || findByClass(graph, CLASS.samplers).map((s) => s.id)

  const { positive, negative } = locatePrompts(graph, samplerIds, ov)
  if (positive && params.positivePrompt != null) setInput(graph, positive, 'text', params.positivePrompt)
  if (negative && params.negativePrompt != null) setInput(graph, negative, 'text', params.negativePrompt)

  const latentId = ov.latent || findByClass(graph, CLASS.t2vLatent)[0]?.id
  if (latentId) {
    if (params.width != null) setInput(graph, latentId, 'width', params.width)
    if (params.height != null) setInput(graph, latentId, 'height', params.height)
    if (params.length != null) setInput(graph, latentId, 'length', params.length)
  }

  if (params.useLightX2V) {
    applyLightX2VDefaults(graph, samplerIds)
    if (params.seed != null) applySamplerParams(graph, samplerIds, { seed: params.seed })
  } else {
    applySamplerParams(graph, samplerIds, params)
  }

  if (params.fps != null) setFps(graph, params.fps)
  if (params.filenamePrefix != null) setFilenamePrefix(graph, params.filenamePrefix)

  return { graph, located: { positive, negative, latentId, samplerIds } }
}

// LTX 2.3 文生视频参数注入（两阶段 SamplerCustomAdvanced + RandomNoise）
export function buildLTX23T2V(baseGraph, params) {
  const graph = clone(baseGraph)
  const ov = overrides.ltx23

  const positive = ov.positivePrompt ?? '305'
  const negative = ov.negativePrompt ?? '315'
  const videoLatent = ov.videoLatent ?? '297'
  const audioLatent = ov.audioLatent ?? '307'
  const conditioning = ov.conditioning ?? '306'
  const noiseIds = ov.noiseSeeds ?? ['279', '278']
  const fps = params.fps ?? 24

  if (positive && params.positivePrompt != null) forceSetInput(graph, positive, 'text', params.positivePrompt)
  if (negative && params.negativePrompt != null) forceSetInput(graph, negative, 'text', params.negativePrompt)

  if (params.width != null) forceSetInput(graph, videoLatent, 'width', params.width)
  if (params.height != null) forceSetInput(graph, videoLatent, 'height', params.height)
  if (params.length != null) {
    forceSetInput(graph, videoLatent, 'length', params.length)
    forceSetInput(graph, audioLatent, 'frames_number', params.length)
  }
  forceSetInput(graph, audioLatent, 'frame_rate', fps)
  forceSetInput(graph, conditioning, 'frame_rate', fps)
  setFps(graph, fps)

  if (params.seed != null) {
    for (const nid of noiseIds) forceSetInput(graph, nid, 'noise_seed', params.seed)
  }

  if (params.filenamePrefix != null) setFilenamePrefix(graph, params.filenamePrefix)

  return {
    graph,
    located: { positive, negative, videoLatent, audioLatent, noiseIds }
  }
}

// LTX 2.3 图生视频参数注入（参考图 + 两阶段采样）
export function buildLTX23I2V(baseGraph, params) {
  const graph = clone(baseGraph)
  const ov = overrides.ltx23i2v

  const positive = ov.positivePrompt ?? '305'
  const negative = ov.negativePrompt ?? '315'
  const videoLatent = ov.videoLatent ?? '297'
  const audioLatent = ov.audioLatent ?? '307'
  const conditioning = ov.conditioning ?? '306'
  const noiseIds = ov.noiseSeeds ?? ['279', '278']
  const loadImage = ov.loadImage ?? '322'
  const resizeImage = ov.resizeImage ?? '292'
  const fps = params.fps ?? 24
  const width = params.width ?? 768
  const height = params.height ?? 512

  if (positive && params.positivePrompt != null) forceSetInput(graph, positive, 'text', params.positivePrompt)
  if (negative && params.negativePrompt != null) forceSetInput(graph, negative, 'text', params.negativePrompt)

  if (params.width != null) forceSetInput(graph, videoLatent, 'width', params.width)
  if (params.height != null) forceSetInput(graph, videoLatent, 'height', params.height)
  if (params.length != null) {
    forceSetInput(graph, videoLatent, 'length', params.length)
    forceSetInput(graph, audioLatent, 'frames_number', params.length)
  }
  forceSetInput(graph, audioLatent, 'frame_rate', fps)
  forceSetInput(graph, conditioning, 'frame_rate', fps)
  setFps(graph, fps)

  if (resizeImage) {
    forceSetInput(graph, resizeImage, 'resize_type.width', width)
    forceSetInput(graph, resizeImage, 'resize_type.height', height)
  }
  if (loadImage && params.imageName) forceSetInput(graph, loadImage, 'image', params.imageName)

  if (params.i2vStrength != null) {
    for (const nid of ['298', '290']) {
      if (graph[nid]?.inputs && 'strength' in graph[nid].inputs) {
        forceSetInput(graph, nid, 'strength', params.i2vStrength)
      }
    }
  }

  if (params.seed != null) {
    for (const nid of noiseIds) forceSetInput(graph, nid, 'noise_seed', params.seed)
  }

  if (params.filenamePrefix != null) setFilenamePrefix(graph, params.filenamePrefix)

  return {
    graph,
    located: { positive, negative, videoLatent, audioLatent, noiseIds, loadImage }
  }
}

// LTX 2.3 首尾帧 FLF2V（first_frame + last_frame 双端约束）
export function buildLTX23FLF2V(baseGraph, params) {
  const graph = clone(baseGraph)
  const ov = overrides.ltx23flf2v

  const positive = ov.positivePrompt ?? '222'
  const negative = ov.negativePrompt ?? '217'
  const videoLatent = ov.videoLatent ?? '201'
  const audioLatent = ov.audioLatent ?? '197'
  const conditioning = ov.conditioning ?? '202'
  const noiseIds = ov.noiseSeeds ?? ['196']
  const loadFirst = ov.loadImageFirst ?? '801'
  const loadLast = ov.loadImageLast ?? '802'
  const fps = params.fps ?? 24
  const width = params.width ?? 768
  const height = params.height ?? 512

  if (positive && params.positivePrompt != null) forceSetInput(graph, positive, 'text', params.positivePrompt)
  if (negative && params.negativePrompt != null) forceSetInput(graph, negative, 'text', params.negativePrompt)

  if (params.width != null) forceSetInput(graph, videoLatent, 'width', width)
  if (params.height != null) forceSetInput(graph, videoLatent, 'height', height)
  if (params.length != null) {
    forceSetInput(graph, videoLatent, 'length', params.length)
    forceSetInput(graph, audioLatent, 'frames_number', params.length)
  }
  forceSetInput(graph, audioLatent, 'frame_rate', fps)
  forceSetInput(graph, conditioning, 'frame_rate', fps)
  setFps(graph, fps)

  for (const rid of [ov.resizeFirst ?? '213', ov.resizeLast ?? '214']) {
    if (rid && graph[rid]?.inputs) {
      forceSetInput(graph, rid, 'resize_type.width', width)
      forceSetInput(graph, rid, 'resize_type.height', height)
    }
  }

  if (loadFirst && params.firstImageName) forceSetInput(graph, loadFirst, 'image', params.firstImageName)
  if (loadLast && params.lastImageName) forceSetInput(graph, loadLast, 'image', params.lastImageName)

  if (params.seed != null) {
    for (const nid of noiseIds) forceSetInput(graph, nid, 'noise_seed', params.seed)
  }

  if (params.filenamePrefix != null) setFilenamePrefix(graph, params.filenamePrefix)

  return {
    graph,
    located: { positive, negative, videoLatent, audioLatent, noiseIds, loadFirst, loadLast }
  }
}

// 图生视频参数注入（需先上传图片拿到 imageName）
export function buildI2V(baseGraph, params) {
  const graph = clone(baseGraph)
  const ov = overrides.i2v
  const samplerIds = ov.samplers || findByClass(graph, CLASS.samplers).map((s) => s.id)

  const { positive, negative } = locatePrompts(graph, samplerIds, ov)
  if (positive && params.positivePrompt != null) setInput(graph, positive, 'text', params.positivePrompt)
  if (negative && params.negativePrompt != null) setInput(graph, negative, 'text', params.negativePrompt)

  const wanId = ov.wanI2V || findByClass(graph, CLASS.wanI2V)[0]?.id
  if (wanId) {
    if (params.width != null) forceSetInput(graph, wanId, 'width', params.width)
    if (params.height != null) forceSetInput(graph, wanId, 'height', params.height)
    if (params.length != null) forceSetInput(graph, wanId, 'length', params.length)
  }

  // 起始图：优先顺着 WanImageToVideo.start_image 找 LoadImage，找不到再按 class_type 取。
  let loadImageId = ov.loadImage
  if (!loadImageId && wanId) loadImageId = resolveUpstream(graph, wanId, 'start_image', CLASS.loadImage)
  if (!loadImageId) loadImageId = findByClass(graph, CLASS.loadImage)[0]?.id
  if (loadImageId && params.imageName) forceSetInput(graph, loadImageId, 'image', params.imageName)

  applySamplerParams(graph, samplerIds, params)
  if (params.fps != null) setFps(graph, params.fps)
  return { graph, located: { positive, negative, wanId, loadImageId, samplerIds } }
}

// 从 /history 的 outputs 里提取生成的视频（兼容 images/gifs/videos 等多种产出键）。
export function extractMediaFromHistory(history, promptId) {
  const entry = history?.[promptId]
  if (!entry?.outputs) return []
  const results = []
  for (const nodeId of Object.keys(entry.outputs)) {
    const out = entry.outputs[nodeId]
    for (const key of Object.keys(out)) {
      const arr = out[key]
      if (!Array.isArray(arr)) continue
      for (const item of arr) {
        if (item && typeof item === 'object' && item.filename) {
          const isVideo = /\.(mp4|webm|mkv|mov|gif)$/i.test(item.filename)
          results.push({
            nodeId,
            kind: isVideo ? 'video' : 'image',
            filename: item.filename,
            subfolder: item.subfolder || '',
            type: item.type || 'output'
          })
        }
      }
    }
  }
  // 视频优先排前面
  results.sort((a, b) => (a.kind === 'video' ? -1 : 1) - (b.kind === 'video' ? -1 : 1))
  return results
}
