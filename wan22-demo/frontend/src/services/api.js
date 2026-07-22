// 后端 REST API 客户端

const API_BASE =
  typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE != null
    ? import.meta.env.VITE_API_BASE
    : ''

function api(path) {
  return `${API_BASE}${path}`
}

function mapNetworkError(error) {
  const msg = error?.message || String(error)
  if (msg === 'Failed to fetch' || /networkerror|load failed/i.test(msg)) {
    return new Error(
      '无法连接后端（8190）。常见原因：1) 后端未运行或刚重启（cd backend && python main.py）；2) 历史视频预览与任务轮询同时占用连接，请稍等几秒重试；3) 请用 http://localhost:5173 访问'
    )
  }
  return error instanceof Error ? error : new Error(msg)
}

async function request(path, { method = 'GET', body, headers, retries = 0, signal } = {}) {
  const opts = { method, headers: { ...headers }, signal }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  let res
  let lastError
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      res = await fetch(api(path), opts)
      lastError = null
      break
    } catch (error) {
      if (error?.name === 'AbortError') throw error
      lastError = error
      if (attempt >= retries) throw mapNetworkError(error)
      await sleep(800 * (attempt + 1))
    }
  }
  if (lastError) throw mapNetworkError(lastError)
  let data = {}
  try {
    data = await res.json()
  } catch {
    data = {}
  }
  if (!res.ok) {
    const detail = data.detail || data.error || JSON.stringify(data).slice(0, 300)
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || JSON.stringify(detail)
    const error = new Error(message)
    error.status = res.status
    error.detail = detail
    if (detail && typeof detail === 'object') {
      error.code = detail.code
      error.sessionId = detail.sessionId
      error.utteranceIds = detail.utteranceIds
      error.issues = detail.issues
    }
    throw error
  }
  return data
}

export async function listRecentVideos({ limit = 50 } = {}) {
  const q = new URLSearchParams({ limit: String(limit) })
  return request(`/v1/media/recent-videos?${q.toString()}`)
}

export function viewUrl({ filename, subfolder = '', type = 'output' } = {}) {
  if (!filename) return ''
  const params = new URLSearchParams({ filename, subfolder, type })
  return api(`/v1/media/view?${params.toString()}`)
}

export async function uploadImage(file, { subfolder = '', overwrite = true } = {}) {
  const form = new FormData()
  form.append('file', file, file.name)
  const q = new URLSearchParams()
  if (subfolder) q.set('subfolder', subfolder)
  if (overwrite) q.set('overwrite', 'true')
  const qs = q.toString()
  const res = await fetch(api(`/v1/media/upload${qs ? `?${qs}` : ''}`), { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error(`上传图片失败: ${res.status} ${await res.text().catch(() => '')}`)
  }
  return res.json()
}

export async function generateT2V(body) {
  return request('/v1/videos/t2v', { method: 'POST', body, retries: 3 })
}

export async function generateI2V(body) {
  return request('/v1/videos/i2v', { method: 'POST', body, retries: 3 })
}

export async function generateFLF2V(body) {
  return request('/v1/videos/flf2v', { method: 'POST', body, retries: 3 })
}

export async function generateT2I(body) {
  return request('/v1/images/t2i', { method: 'POST', body, retries: 3 })
}

export async function getVideoTask(taskId, { signal } = {}) {
  return request(`/v1/videos/tasks/${encodeURIComponent(taskId)}`, { retries: 3, signal })
}

export async function getImageTask(taskId, { signal } = {}) {
  return request(`/v1/images/tasks/${encodeURIComponent(taskId)}`, { retries: 3, signal })
}

export async function extractVideoFrame(body) {
  return request('/v1/media/extract-frame', { method: 'POST', body })
}

export async function concatSegments(body) {
  return request('/v1/media/concat', { method: 'POST', body })
}

/** 为已拼接成片生成对白、口型与音轨。 */
export async function dubMedia(body) {
  return request('/v1/media/dub', { method: 'POST', body })
}

export async function analyzeDub(body) {
  return request('/v1/media/dub/analyze', { method: 'POST', body })
}

export async function renderDub(body) {
  return request('/v1/media/dub/render', { method: 'POST', body })
}

export async function getDubSession(sessionId) {
  return request(`/v1/media/dub/sessions/${encodeURIComponent(sessionId)}`)
}

export function dubTrackUrl(sessionId, filename) {
  if (!sessionId || !filename) return ''
  return api(
    `/v1/media/dub/sessions/${encodeURIComponent(sessionId)}/tracks/${encodeURIComponent(filename)}`
  )
}

export async function analyzeSplice(body) {
  return request('/v1/media/analyze-splice', { method: 'POST', body })
}

export async function validateSegment(body) {
  return request('/v1/media/validate/segment', { method: 'POST', body })
}

export async function normalizeSegment(body) {
  return request('/v1/media/normalize-segment', { method: 'POST', body })
}

export async function validateFinal(body) {
  return request('/v1/media/validate/final', { method: 'POST', body })
}

export async function detectDuplicateFrames(body) {
  return request('/v1/media/detect-duplicate-frames', { method: 'POST', body })
}

export async function detectFace(body) {
  return request('/v1/media/detect-face', { method: 'POST', body })
}

export async function animateRelock(body) {
  return request('/v1/media/animate-relock', { method: 'POST', body })
}

/** InstantID 定妆照 / 段首帧 */
export async function generateLookbook(body) {
  return request('/v1/images/lookbook', { method: 'POST', body })
}

export async function lookbookStatus() {
  return request('/v1/images/lookbook/status')
}

export async function listCharacters() {
  const data = await request('/v1/characters')
  return data.characters || []
}

export async function saveCharacter({ id, name, character }) {
  return request('/v1/characters', { method: 'POST', body: { id, name, character } })
}

export async function deleteCharacter(id) {
  return request(`/v1/characters/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export async function checkHealth() {
  return request('/health')
}

export async function checkHealthFull() {
  return request('/health/full')
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

/** 轮询任务直到 completed / failed / 超时 */
export async function waitForVideoTask(
  taskId,
  { intervalMs = 2000, timeoutMs = 7200000, onTick, signal, shouldContinue } = {}
) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    if (signal?.aborted || shouldContinue?.() === false) {
      throw new DOMException('轮询已取消', 'AbortError')
    }
    const task = await getVideoTask(taskId, { signal })
    const elapsed = Math.round((Date.now() - start) / 1000)
    onTick?.({
      phase: task.status,
      elapsed,
      queuePos: task.queue_pos || 0,
      task
    })
    if (task.status === 'completed') {
      return task.media || []
    }
    if (task.status === 'failed') {
      throw new Error(task.error || '视频生成失败')
    }
    await sleep(intervalMs)
  }
  throw new Error('等待超时，请稍后在 ComfyUI 输出目录查看')
}

export { API_BASE, request, api }
