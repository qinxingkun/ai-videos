/** Qwen-Image-2512 官方推荐宽高比（来自模型 README） */

export const QWEN_DEFAULT_NEGATIVE =
  '低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。'

export const QWEN_ASPECT_PRESETS = [
  { id: '1:1', label: '1:1 方形', width: 1328, height: 1328 },
  { id: '16:9', label: '16:9 横屏', width: 1664, height: 928 },
  { id: '9:16', label: '9:16 竖屏', width: 928, height: 1664 },
  { id: '4:3', label: '4:3 横屏', width: 1472, height: 1104 },
  { id: '3:4', label: '3:4 竖屏', width: 1104, height: 1472 },
  { id: '3:2', label: '3:2 横屏', width: 1584, height: 1056 },
  { id: '2:3', label: '2:3 竖屏', width: 1056, height: 1584 },
  { id: 'custom', label: '自定义', width: null, height: null }
]

export const QWEN_DEFAULT_STEPS = 50
export const QWEN_DEFAULT_CFG = 4.0
export const QWEN_TURBO_STEPS = 4
export const QWEN_TURBO_CFG = 1.0

export function findAspectPreset(id) {
  return QWEN_ASPECT_PRESETS.find((item) => item.id === id)
}

export function formatSize(width, height) {
  return `${width}×${height}`
}
