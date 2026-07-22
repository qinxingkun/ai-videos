// 活跃任务与历史记录的 localStorage 持久化（刷新页面后可恢复轮询 / 配音绑定）。

import { viewUrl as buildViewUrl } from '../services/api.js'

const ACTIVE_JOB_KEY = 'wan22-active-job'
const HISTORY_KEY = 'wan22-history'
const LEGACY_HISTORY_KEYS = ['wan22-demo-history', 'comfy-history']
export const HISTORY_MAX_VIDEOS = 100

/** 防止多个 GenerationForm 实例同时恢复同一活跃任务。 */
let activeJobResumeOwner = null

export function claimActiveJobResume(ownerId) {
  if (activeJobResumeOwner && activeJobResumeOwner !== ownerId) return false
  activeJobResumeOwner = ownerId
  return true
}

export function releaseActiveJobResume(ownerId) {
  if (activeJobResumeOwner === ownerId) activeJobResumeOwner = null
}

function safeReadStorage(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeWriteStorage(key, value) {
  try {
    localStorage.setItem(key, value)
    return true
  } catch (e) {
    console.warn('localStorage write failed', e)
    return false
  }
}
export function saveActiveJob(job) {
  if (!job) {
    try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch { /* ignore */ }
    return
  }
  safeWriteStorage(ACTIVE_JOB_KEY, JSON.stringify(job))
}

export function loadActiveJob() {
  try {
    const raw = localStorage.getItem(ACTIVE_JOB_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function clearActiveJob() {
  localStorage.removeItem(ACTIVE_JOB_KEY)
}

/** Build stable mode id for Wan/LTX single-shot and multi-shot jobs. */
export function jobModeFor({ engine, mode, kind = '5s' } = {}) {
  if (engine === 'qwen') {
    return `${engine}-${mode}`
  }
  if (kind === 'multishot' || kind === 'multishot-dub') {
    return `${engine}-${mode}-multishot${kind === 'multishot-dub' ? '-dub' : ''}`
  }
  return `${engine}-${mode}-5s`
}

export function isMultishotDubJob(job) {
  return Boolean(job?.mode && String(job.mode).includes('multishot'))
}

function normalizeMediaItem(item) {
  if (!item || typeof item !== 'object') return null
  const filename = item.filename || item.name
  if (!filename) return null
  const kind =
    item.kind ||
    (/\.(mp4|webm|mov|mkv)$/i.test(filename) ? 'video' : 'image')
  return {
    ...item,
    filename,
    kind,
    url: item.url || buildViewUrl({
      filename,
      subfolder: item.subfolder || '',
      type: item.type || 'output'
    })
  }
}

/** 从 ComfyUI 输出文件名解析时间戳（如 ...-20260717-1441_00001_.mp4）。 */
export function parseFilenameTimestamp(filename) {
  const match = String(filename || '').match(/-(\d{8})-(\d{4})_/)
  if (!match) return 0
  const [, ymd, hm] = match
  const year = Number(ymd.slice(0, 4))
  const month = Number(ymd.slice(4, 6)) - 1
  const day = Number(ymd.slice(6, 8))
  const hour = Number(hm.slice(0, 2))
  const minute = Number(hm.slice(2, 4))
  const ts = new Date(year, month, day, hour, minute).getTime()
  return Number.isFinite(ts) ? ts : 0
}

function formatHistoryTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

function resolveCreatedAt(entry, mediaItem, fallbackTs) {
  const fromName = parseFilenameTimestamp(mediaItem?.filename || entry?.filename)
  if (fromName > 0) return fromName
  if (Number.isFinite(mediaItem?.createdAt) && mediaItem.createdAt > 0) return mediaItem.createdAt
  if (Number.isFinite(entry?.createdAt) && entry.createdAt > 0) return entry.createdAt
  return fallbackTs
}

/** 归一化历史条目：补全 url/kind，合并 finalVideo 到可展示的 media 列表。 */
export function normalizeHistoryEntry(entry) {
  if (!entry || typeof entry !== 'object') return null
  const media = (Array.isArray(entry.media) ? entry.media : [])
    .map(normalizeMediaItem)
    .filter(Boolean)
  const finalVideo = normalizeMediaItem(entry.finalVideo)
  if (finalVideo && !media.some((m) => m.filename === finalVideo.filename)) {
    media.unshift({ ...finalVideo, label: '成片' })
  }
  if (!media.length) return null
  return {
    ...entry,
    media,
    finalVideo: finalVideo || entry.finalVideo || null
  }
}

/** 将单条生成记录展开为扁平视频项。 */
export function entryToVideoItems(entry, fallbackTs = Date.now()) {
  const normalized = normalizeHistoryEntry(entry)
  if (!normalized) return []
  const baseTs = resolveCreatedAt(normalized, null, fallbackTs)
  const displayTime =
    normalized.time ||
    formatHistoryTime(baseTs) ||
    formatHistoryTime(fallbackTs)

  return normalized.media.map((media, index) => {
    const createdAt = resolveCreatedAt(normalized, media, baseTs - index)
    return {
      id: `${media.filename}-${createdAt}-${index}`,
      ...media,
      mode: normalized.mode || 'unknown',
      time: media.time || displayTime,
      createdAt,
      promptId: normalized.promptId,
      taskId: normalized.taskId
    }
  })
}

/** 判断是否为扁平视频历史项（相对旧版 job 包裹结构）。 */
export function isFlatHistoryVideo(item) {
  return Boolean(item?.filename && item?.url && !Array.isArray(item.media))
}

function flattenHistoryItems(items) {
  if (!Array.isArray(items)) return []
  const flat = []
  for (const item of items) {
    if (isFlatHistoryVideo(item)) {
      const media = normalizeMediaItem(item)
      if (!media) continue
      const createdAt = resolveCreatedAt(item, media, Date.now())
      flat.push({
        ...media,
        id: item.id || `${media.filename}-${createdAt}`,
        mode: item.mode || 'unknown',
        time: item.time || formatHistoryTime(createdAt),
        createdAt,
        promptId: item.promptId,
        taskId: item.taskId,
        label: item.label
      })
      continue
    }
    flat.push(...entryToVideoItems(item))
  }
  return flat
}

/** 去重、按时间倒序、截断至上限。 */
export function sortAndTrimVideos(videos, max = HISTORY_MAX_VIDEOS) {
  const deduped = new Map()
  for (const item of videos) {
    if (!item?.filename) continue
    const key = item.filename
    const prev = deduped.get(key)
    const ts = item.createdAt || 0
    if (!prev || ts >= (prev.createdAt || 0)) {
      deduped.set(key, item)
    }
  }
  return [...deduped.values()]
    .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
    .slice(0, max)
}

/** 合并 ComfyUI 目录扫描结果到历史（按 filename 去重，保留较新 createdAt）。 */
export function mergeImportedVideos(imported, existing = []) {
  const flat = flattenHistoryItems(existing)
  const incoming = (Array.isArray(imported) ? imported : [])
    .map(normalizeMediaItem)
    .filter(Boolean)
    .map((media, index) => {
      const createdAt = resolveCreatedAt(null, media, Date.now() - index)
      return {
        id: `${media.filename}-${createdAt}`,
        ...media,
        mode: media.mode || 'comfyui-import',
        time: media.time || formatHistoryTime(createdAt),
        createdAt,
        label: media.label || 'ComfyUI 导入',
        source: media.source || 'comfyui_dir'
      }
    })
  return sortAndTrimVideos([...incoming, ...flat])
}

/** 追加一条生成记录到历史（返回新的扁平视频列表）。 */
export function appendHistoryRecord(record, existing = []) {
  const incoming = entryToVideoItems(record)
  return sortAndTrimVideos([...incoming, ...flattenHistoryItems(existing)])
}

export function saveHistory(items) {
  try {
    const trimmed = sortAndTrimVideos(flattenHistoryItems(items))
    safeWriteStorage(HISTORY_KEY, JSON.stringify(trimmed))
    return trimmed
  } catch (e) {
    console.warn('saveHistory failed', e)
    return flattenHistoryItems(items)
  }
}

export function loadHistory() {
  try {
    let raw = safeReadStorage(HISTORY_KEY)
    if (!raw) {
      for (const key of LEGACY_HISTORY_KEYS) {
        raw = safeReadStorage(key)
        if (raw) break
      }
    }
    const parsed = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    return sortAndTrimVideos(flattenHistoryItems(parsed))
  } catch (e) {
    console.warn('loadHistory failed, resetting cache', e)
    try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
    return []
  }
}
