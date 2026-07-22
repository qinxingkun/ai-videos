/** 浏览器端拼图：最多 9 张 → 1 张 canvas 输出 */

export const COLLAGE_MAX = 9

/** 根据图片数量推荐行列 */
export function suggestGrid(count, colsOverride) {
  const n = Math.min(Math.max(count, 1), COLLAGE_MAX)
  if (colsOverride) {
    const cols = Math.min(3, Math.max(1, colsOverride))
    return { cols, rows: Math.ceil(n / cols) }
  }
  if (n === 1) return { cols: 1, rows: 1 }
  if (n === 2) return { cols: 2, rows: 1 }
  if (n <= 4) return { cols: 2, rows: 2 }
  if (n <= 6) return { cols: 3, rows: 2 }
  return { cols: 3, rows: 3 }
}

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error(`无法加载图片: ${file.name}`))
    }
    img.src = url
  })
}

function drawCover(ctx, img, dx, dy, dw, dh) {
  const ir = img.width / img.height
  const cr = dw / dh
  let sw, sh, sx, sy
  if (ir > cr) {
    sh = img.height
    sw = sh * cr
    sx = (img.width - sw) / 2
    sy = 0
  } else {
    sw = img.width
    sh = sw / cr
    sx = 0
    sy = (img.height - sh) / 2
  }
  ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh)
}

/**
 * @param {File[]} files 1–9 张图片
 * @param {object} options
 * @returns {Promise<Blob>}
 */
export async function buildCollageBlob(
  files,
  {
    cols,
    outputWidth = 768,
    outputHeight = 512,
    gap = 6,
    background = '#141414',
    quality = 0.92
  } = {}
) {
  const list = files.slice(0, COLLAGE_MAX)
  if (!list.length) throw new Error('请至少选择 1 张图片')

  const images = await Promise.all(list.map(loadImageFromFile))
  const { cols: c, rows: r } = suggestGrid(images.length, cols)

  const canvas = document.createElement('canvas')
  canvas.width = outputWidth
  canvas.height = outputHeight
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = background
  ctx.fillRect(0, 0, outputWidth, outputHeight)

  const totalGapX = gap * (c - 1)
  const totalGapY = gap * (r - 1)
  const cellW = (outputWidth - totalGapX) / c
  const cellH = (outputHeight - totalGapY) / r

  images.forEach((img, i) => {
    const col = i % c
    const row = Math.floor(i / c)
    const x = col * (cellW + gap)
    const y = row * (cellH + gap)
    drawCover(ctx, img, x, y, cellW, cellH)
  })

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) reject(new Error('拼图导出失败'))
        else resolve(blob)
      },
      'image/jpeg',
      quality
    )
  })
}

export async function buildCollageFile(files, options = {}) {
  const blob = await buildCollageBlob(files, options)
  const name = options.filename || `collage_${Date.now()}.jpg`
  return new File([blob], name, { type: 'image/jpeg' })
}

export function blobToPreviewUrl(blob) {
  return URL.createObjectURL(blob)
}
