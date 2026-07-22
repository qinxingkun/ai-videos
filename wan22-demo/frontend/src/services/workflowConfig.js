// 兜底配置：当自动探测（按 class_type + 连线遍历）找不到目标节点，或你的导出 JSON
// 结构特殊时，可在这里手动指定节点 id。留空表示完全交给自动探测。
//
// 用法：把对应字段填成导出 JSON 里的节点 id 字符串，例如 positivePrompt: "6"。
// 你可以在 ComfyUI 里把节点标题改清楚，导出的 API JSON 里 _meta.title 也会带上，便于核对。

export const overrides = {
  t2v: {
    positivePrompt: null, // CLIPTextEncode（正向）
    negativePrompt: null, // CLIPTextEncode（负向）
    latent: null, // EmptyHunyuanLatentVideo（width/height/length）
    samplers: null // [id,...] KSamplerAdvanced，用于写 seed/steps/cfg
  },
  i2v: {
    positivePrompt: null,
    negativePrompt: null,
    wanI2V: null, // WanImageToVideo（width/height/length）
    loadImage: null, // LoadImage（image 文件名）
    samplers: null
  },
  ltx23: {
    positivePrompt: '305',
    negativePrompt: '315',
    videoLatent: '297',
    audioLatent: '307',
    conditioning: '306',
    noiseSeeds: ['279', '278']
  },
  ltx23i2v: {
    positivePrompt: '305',
    negativePrompt: '315',
    videoLatent: '297',
    audioLatent: '307',
    conditioning: '306',
    noiseSeeds: ['279', '278'],
    loadImage: '322',
    resizeImage: '292',
    preprocess: '291'
  },
  ltx23flf2v: {
    positivePrompt: '222',
    negativePrompt: '217',
    videoLatent: '201',
    audioLatent: '197',
    conditioning: '202',
    noiseSeeds: ['196'],
    loadImageFirst: '801',
    loadImageLast: '802',
    resizeFirst: '213',
    resizeLast: '214'
  }
}

// 各类节点的 class_type 候选，便于兼容不同模板/版本。
export const CLASS = {
  samplers: ['KSamplerAdvanced', 'KSampler', 'SamplerCustomAdvanced'],
  clipTextEncode: ['CLIPTextEncode'],
  t2vLatent: ['EmptyHunyuanLatentVideo', 'EmptySD3LatentImage', 'EmptyLatentImage', 'EmptyLTXVLatentVideo'],
  wanI2V: ['WanImageToVideo'],
  loadImage: ['LoadImage', 'LoadImageOutput'],
  saveVideo: ['SaveVideo', 'VHS_VideoCombine', 'SaveWEBM']
}
