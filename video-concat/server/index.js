import express from 'express'
import cors from 'cors'
import multer from 'multer'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { v4 as uuidv4 } from 'uuid'
import { checkCosyVoiceHealth, getCosyVoiceConfig, listAvailableVoices, synthesizeSpeech } from './cosyvoice.js'
import { mixDubbingIntoVideo, probeMedia, probeStreamDurations, runFfmpeg } from './ffmpeg.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const UPLOAD_DIR = path.join(ROOT, 'uploads')
const OUTPUT_DIR = path.join(ROOT, 'output')

const PORT = process.env.PORT || 3040
const isProd = process.env.NODE_ENV === 'production'

await fs.mkdir(UPLOAD_DIR, { recursive: true })
await fs.mkdir(OUTPUT_DIR, { recursive: true })

const storage = multer.diskStorage({
  destination: UPLOAD_DIR,
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname) || '.mp4'
    cb(null, `${uuidv4()}${ext}`)
  },
})

const VIDEO_EXTENSIONS = new Set(['.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v', '.flv', '.wmv'])

const upload = multer({
  storage,
  limits: { fileSize: 500 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase()
    if (file.mimetype.startsWith('video/') || VIDEO_EXTENSIONS.has(ext)) {
      cb(null, true)
    } else {
      cb(new Error('仅支持视频文件'))
    }
  },
})

const app = express()
app.use(cors())
app.use(express.json())

function escapeConcatPath(filePath) {
  return filePath.replace(/'/g, "'\\''")
}

function parseBool(value) {
  return value === true || value === 'true' || value === '1' || value === 1
}

async function cleanupFiles(files) {
  await Promise.all(
    files.map(async (file) => {
      if (!file) return
      try {
        await fs.unlink(file)
      } catch {
        /* ignore */
      }
    }),
  )
}

async function concatVideos(inputPaths, outputPath, listPath) {
  const listContent = inputPaths.map((p) => `file '${escapeConcatPath(p)}'`).join('\n')
  await fs.writeFile(listPath, listContent, 'utf8')

  try {
    await runFfmpeg(['-y', '-f', 'concat', '-safe', '0', '-i', listPath, '-c', 'copy', outputPath])
  } catch {
    await runFfmpeg([
      '-y',
      '-f',
      'concat',
      '-safe',
      '0',
      '-i',
      listPath,
      '-c:v',
      'libx264',
      '-preset',
      'fast',
      '-crf',
      '23',
      '-c:a',
      'aac',
      '-b:a',
      '192k',
      '-movflags',
      '+faststart',
      outputPath,
    ])
  }
}

app.post('/api/concat', upload.array('videos', 100), async (req, res) => {
  const files = req.files
  if (!files?.length) {
    return res.status(400).json({ error: '请至少上传一个视频' })
  }

  const dubbingEnabled = parseBool(req.body?.dubbingEnabled)
  const dubbingText = String(req.body?.dubbingText || '').trim()
  const voiceId = String(req.body?.voiceId || getCosyVoiceConfig().voiceId).trim()
  const audioMode = req.body?.audioMode === 'replace' ? 'replace' : 'mix'
  const speechSpeed = Math.max(0.5, Math.min(2.0, Number(req.body?.speechSpeed) || 1.0))
  const paceMode = req.body?.paceMode === 'natural' ? 'natural' : 'uniform'

  if (files.length < 2 && !dubbingEnabled) {
    await cleanupFiles(files.map((f) => f.path))
    return res.status(400).json({ error: '拼接至少需要两个视频；单个视频请开启配音' })
  }

  if (dubbingEnabled && !dubbingText) {
    await cleanupFiles(files.map((f) => f.path))
    return res.status(400).json({ error: '已开启配音，请填写配音文本' })
  }

  if (dubbingEnabled) {
    const health = await checkCosyVoiceHealth()
    if (!health.ok) {
      await cleanupFiles(files.map((f) => f.path))
      return res.status(503).json({
        error: `CosyVoice 服务不可用（${health.error || '未启动'}），请先启动配音服务或关闭配音选项`,
      })
    }
  }

  const jobId = uuidv4()
  const outputName = `${jobId}.mp4`
  const outputPath = path.join(OUTPUT_DIR, outputName)
  const listPath = path.join(UPLOAD_DIR, `${jobId}-list.txt`)
  const concatPath = path.join(UPLOAD_DIR, `${jobId}-concat.mp4`)
  const dubbingPath = path.join(UPLOAD_DIR, `${jobId}-dub.wav`)
  const inputPaths = files.map((f) => f.path)
  const tempFiles = [...inputPaths, listPath, concatPath, dubbingPath]

  try {
    if (inputPaths.length === 1) {
      await fs.copyFile(inputPaths[0], concatPath)
    } else {
      await concatVideos(inputPaths, concatPath, listPath)
    }

    let dubbed = false
    let dubMeta = null
    if (dubbingEnabled) {
      const media = await probeStreamDurations(concatPath)
      const videoDuration = media.videoDuration || media.formatDuration
      const synth = await synthesizeSpeech({
        text: dubbingText,
        voiceId,
        outputPath: dubbingPath,
        videoDuration,
        speechSpeed,
        paceMode,
      })
      const dub = await probeMedia(dubbingPath)
      await mixDubbingIntoVideo({
        videoPath: concatPath,
        audioPath: dubbingPath,
        outputPath,
        hasOriginalAudio: media.hasAudio,
        audioMode,
        videoDuration,
        speechSpeed: paceMode === 'uniform' ? 1 : speechSpeed,
      })
      dubbed = true
      dubMeta = {
        videoDuration,
        dubDuration: dub.duration,
        speechSpeed,
        audioMode,
        paceMode: synth.paceMode,
        normalized: synth.normalized,
        segmentCount: synth.segmentCount,
        shortfall: dub.duration < videoDuration - 1,
        stretched: dub.duration < videoDuration * 0.98,
        truncated: dub.duration > videoDuration * 1.05,
      }
    } else {
      await fs.rename(concatPath, outputPath)
      tempFiles.splice(tempFiles.indexOf(concatPath), 1)
    }

    res.json({
      id: jobId,
      filename: outputName,
      url: `/api/output/${outputName}`,
      count: files.length,
      dubbed,
      dubbingText: dubbed ? dubbingText : undefined,
      dubMeta,
    })
  } catch (err) {
    console.error('Concat failed:', err.message)
    res.status(500).json({ error: err.message || '视频拼接失败，请确认视频格式有效' })
  } finally {
    await cleanupFiles(tempFiles)
  }
})

app.get('/api/output/:filename', async (req, res) => {
  const filename = path.basename(req.params.filename)
  const filePath = path.join(OUTPUT_DIR, filename)

  try {
    await fs.access(filePath)
    res.sendFile(filePath)
  } catch {
    res.status(404).json({ error: '文件不存在' })
  }
})

app.get('/api/cosyvoice/voices', async (_req, res) => {
  const config = getCosyVoiceConfig()
  const voices = await listAvailableVoices()
  res.json({ voices, defaultVoice: config.voiceId })
})

app.get('/api/cosyvoice/health', async (_req, res) => {
  const config = getCosyVoiceConfig()
  const health = await checkCosyVoiceHealth()
  const voices = await listAvailableVoices()
  res.json({ ...health, synthesizeUrl: config.url, defaultVoice: config.voiceId, voices })
})

app.get('/api/health', (_req, res) => {
  res.json({ ok: true })
})

if (isProd) {
  const distPath = path.join(ROOT, 'dist')
  app.use(express.static(distPath))
  app.get('*', (_req, res) => {
    res.sendFile(path.join(distPath, 'index.html'))
  })
}

app.use((err, _req, res, _next) => {
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ error: err.message })
  }
  res.status(400).json({ error: err.message || '请求错误' })
})

app.listen(PORT, () => {
  const { url, voiceId } = getCosyVoiceConfig()
  console.log(`Server running at http://localhost:${PORT}`)
  console.log(`CosyVoice: ${url} (default voice: ${voiceId})`)
})
