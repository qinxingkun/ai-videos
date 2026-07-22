import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { adjustAudioDuration, concatWavWithGaps } from './ffmpeg.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DEFAULT_URL = 'http://127.0.0.1:8191/synthesize'
const DEFAULT_VOICE = 'default.wav'
const DEFAULT_VOICE_ROOT = path.join(__dirname, '../../wan22-demo/backend/data/voices')
const DEFAULT_TIMEOUT_MS = 120_000
const SEGMENT_MAX_CHARS = 80
const SEGMENT_GAP_SEC = 0.12
const SPEECH_BUDGET_RATIO = 0.96

const VOICE_LABELS = {
  'default.wav': '默认音色',
  'zero_shot_prompt.wav': '零样本示例（中文）',
  'cross_lingual_prompt.wav': '跨语种示例（英文）',
  '000002.wav': '000002',
}

export function getCosyVoiceConfig() {
  const url = (process.env.COSYVOICE_URL || DEFAULT_URL).replace(/\/$/, '')
  const voiceId = process.env.COSYVOICE_VOICE_ID || DEFAULT_VOICE
  const voiceRoot = process.env.COSYVOICE_VOICE_ROOT || DEFAULT_VOICE_ROOT
  const timeoutMs = Number(process.env.COSYVOICE_TIMEOUT_MS || DEFAULT_TIMEOUT_MS)
  return { url, voiceId, voiceRoot, timeoutMs }
}

/** CosyVoice 对超长单段会提前截断，按句子拆成多段分别合成。 */
export function splitTextForTTS(text, maxChars = SEGMENT_MAX_CHARS) {
  const trimmed = String(text || '').trim()
  if (!trimmed) return []

  const sentences = trimmed.split(/(?<=[。！？；.!?;\n])/).map((s) => s.trim()).filter(Boolean)
  const parts = sentences.length ? sentences : [trimmed]

  const segments = []
  let buf = ''
  for (const part of parts) {
    if (part.length > maxChars) {
      if (buf) {
        segments.push(buf)
        buf = ''
      }
      for (let i = 0; i < part.length; i += maxChars) {
        segments.push(part.slice(i, i + maxChars))
      }
      continue
    }
    if ((buf + part).length > maxChars && buf) {
      segments.push(buf)
      buf = part
    } else {
      buf += part
    }
  }
  if (buf) segments.push(buf)
  return segments
}

export async function listAvailableVoices() {
  const { voiceRoot, voiceId: defaultVoice } = getCosyVoiceConfig()
  let entries = []
  try {
    entries = await fs.readdir(voiceRoot)
  } catch {
    return []
  }

  const voices = []
  for (const name of entries.sort()) {
    if (!/\.(wav|mp3|flac|m4a)$/i.test(name)) continue
    const filePath = path.join(voiceRoot, name)
    try {
      const stat = await fs.stat(filePath)
      if (!stat.isFile()) continue
      voices.push({
        id: name,
        label: VOICE_LABELS[name] || name,
        isDefault: name === defaultVoice,
      })
    } catch {
      /* skip */
    }
  }
  return voices
}

export async function checkCosyVoiceHealth() {
  const { url, timeoutMs } = getCosyVoiceConfig()
  const healthUrl = url.replace(/\/synthesize$/, '/health')
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), Math.min(timeoutMs, 15_000))
  try {
    const res = await fetch(healthUrl, { signal: controller.signal })
    if (!res.ok) return { ok: false, url: healthUrl, error: `HTTP ${res.status}` }
    const data = await res.json().catch(() => ({}))
    if (data.busy) {
      return {
        ok: true,
        url: healthUrl,
        sampleRate: data.sampleRate,
        busy: true,
        hint: 'CosyVoice 正在合成配音，提交后可能需要排队等待',
      }
    }
    return { ok: Boolean(data.ok ?? true), url: healthUrl, sampleRate: data.sampleRate }
  } catch (err) {
    const msg = err.message || String(err)
    if (/aborted|AbortError/i.test(msg)) {
      return {
        ok: false,
        url: healthUrl,
        error: 'CosyVoice 响应超时（可能正在合成其他任务），请稍后再试',
      }
    }
    if (/fetch failed|ECONNREFUSED|ENOTFOUND|connection/i.test(msg)) {
      return {
        ok: false,
        url: healthUrl,
        error: '无法连接 CosyVoice（8191 端口），请先启动配音服务',
      }
    }
    return { ok: false, url: healthUrl, error: msg }
  } finally {
    clearTimeout(timer)
  }
}

async function synthesizeOneSegment({ text, voiceId, outputPath, timeoutMs, url, defaultVoice }) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        voice_id: voiceId || defaultVoice,
        sample_rate: 48_000,
        speed: 1.0,
      }),
      signal: controller.signal,
    })

    if (!res.ok) {
      const detail = await res.text().catch(() => '')
      const msg = detail.trim().slice(-500)
      if (msg === 'Internal Server Error' || /CUDA error|Kernel size can't be greater/i.test(msg)) {
        throw new Error('CosyVoice 配音服务异常（GPU/CUDA 可能已失效），请重启 CosyVoice 服务后重试')
      }
      throw new Error(msg || `CosyVoice 请求失败 (HTTP ${res.status})`)
    }

    const wav = Buffer.from(await res.arrayBuffer())
    await fs.writeFile(outputPath, wav)
  } catch (err) {
    const msg = err.message || String(err)
    if (/aborted|AbortError/i.test(msg)) {
      throw new Error('CosyVoice 合成超时，请缩短文案或稍后重试')
    }
    if (/fetch failed|ECONNREFUSED|connection attempts failed|ENOTFOUND/i.test(msg)) {
      throw new Error('无法连接 CosyVoice（8191 端口），请先启动配音服务')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

async function concatWavFiles(inputPaths, outputPath) {
  await concatWavWithGaps(inputPaths, outputPath, 0)
}

function computeUniformTargets(segments, videoDuration, speechSpeed) {
  const totalChars = segments.reduce((sum, text) => sum + text.length, 0)
  if (!totalChars || videoDuration <= 0) return null

  const gapTotal = SEGMENT_GAP_SEC * Math.max(0, segments.length - 1)
  const speechBudget = Math.max(1, (videoDuration * SPEECH_BUDGET_RATIO - gapTotal) / speechSpeed)
  return segments.map((text) => ({
    text,
    targetDuration: (text.length / totalChars) * speechBudget,
  }))
}

export async function synthesizeSpeech({
  text,
  voiceId,
  outputPath,
  videoDuration = 0,
  speechSpeed = 1,
  paceMode = 'uniform',
}) {
  const trimmed = String(text || '').trim()
  if (!trimmed) throw new Error('配音文本不能为空')

  const { url, voiceId: defaultVoice, timeoutMs } = getCosyVoiceConfig()
  const segments = splitTextForTTS(trimmed)
  const useUniform = paceMode === 'uniform' && videoDuration > 0
  const targets = useUniform ? computeUniformTargets(segments, videoDuration, speechSpeed) : null

  const tempFiles = []
  const normalizedFiles = []

  try {
    for (let i = 0; i < segments.length; i++) {
      const rawPath = `${outputPath}.raw${i}.wav`
      tempFiles.push(rawPath)
      await synthesizeOneSegment({
        text: segments[i],
        voiceId,
        outputPath: rawPath,
        timeoutMs,
        url,
        defaultVoice,
      })

      if (targets?.[i]?.targetDuration) {
        const normPath = `${outputPath}.norm${i}.wav`
        normalizedFiles.push(normPath)
        tempFiles.push(normPath)
        await adjustAudioDuration(rawPath, normPath, targets[i].targetDuration)
      } else {
        normalizedFiles.push(rawPath)
      }
    }

    if (normalizedFiles.length <= 1) {
      await fs.copyFile(normalizedFiles[0], outputPath)
    } else if (useUniform) {
      await concatWavWithGaps(normalizedFiles, outputPath, SEGMENT_GAP_SEC)
    } else {
      await concatWavFiles(normalizedFiles, outputPath)
    }

    return {
      outputPath,
      segmentCount: segments.length,
      paceMode: useUniform ? 'uniform' : 'natural',
      normalized: Boolean(useUniform),
    }
  } finally {
    await Promise.all(tempFiles.map((f) => fs.unlink(f).catch(() => {})))
  }
}
