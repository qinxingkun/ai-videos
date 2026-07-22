import { computed, ref } from 'vue'
import { generateT2I, getImageTask, viewUrl } from '../services/api.js'
import {
  claimActiveJobResume,
  jobModeFor,
  loadActiveJob,
  releaseActiveJobResume,
  saveActiveJob
} from './useJobPersistence.js'

const JOB_MODE = jobModeFor({ engine: 'qwen', mode: 't2i' })

export function useImageGeneration({ onDone } = {}) {
  const status = ref('idle')
  const errorMsg = ref('')
  const results = ref([])
  const queueHint = ref('')
  const elapsedSec = ref(0)
  const taskId = ref(null)

  let pollAbort = false
  let pollController = null

  function reset() {
    status.value = 'idle'
    errorMsg.value = ''
    results.value = []
    queueHint.value = ''
    elapsedSec.value = 0
    taskId.value = null
  }

  function cleanup() {
    pollAbort = true
    pollController?.abort()
    pollController = null
    releaseActiveJobResume(JOB_MODE)
  }

  function fail(msg) {
    errorMsg.value = msg
    status.value = 'error'
    saveActiveJob(null)
    cleanup()
  }

  async function finish(media, tid) {
    results.value = media.map((m) => ({ ...m, url: m.url || viewUrl(m), kind: 'image' }))
    onDone?.({
      taskId: tid,
      media: results.value,
      mode: JOB_MODE,
      time: new Date().toLocaleTimeString('zh-CN', { hour12: false })
    })
    status.value = 'done'
    saveActiveJob(null)
    cleanup()
  }

  async function waitPoll(tid, timeoutMs = 3600000) {
    pollController = new AbortController()
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      if (pollAbort || pollController.signal.aborted) {
        throw new DOMException('轮询已取消', 'AbortError')
      }
      const task = await getImageTask(tid, { signal: pollController.signal })
      elapsedSec.value = task.elapsed_sec ?? Math.round((Date.now() - start) / 1000)
      if (task.status === 'completed') return task.media || []
      if (task.status === 'failed') throw new Error(task.error || '文生图失败')
      if (task.status === 'running') {
        status.value = 'running'
        queueHint.value = 'Qwen-Image 正在推理…'
      } else {
        status.value = 'queued'
        queueHint.value = '任务已提交，等待推理服务…'
      }
      await new Promise((r) => setTimeout(r, 2000))
    }
    throw new Error('等待超时，请检查 Qwen-Image 推理服务日志')
  }

  async function generate(params) {
    cleanup()
    reset()
    pollAbort = false

    try {
      status.value = 'queued'
      queueHint.value = '提交文生图任务…'
      const submitted = await generateT2I({
        prompt: params.prompt,
        negative_prompt: params.negativePrompt,
        width: params.width,
        height: params.height,
        seed: params.seed,
        steps: params.steps,
        cfg: params.cfg,
        turbo: params.turbo,
        aspect_ratio: params.aspectRatio,
        filename_prefix: params.filenamePrefix || 'qwen_t2i'
      })
      taskId.value = submitted.task_id
      saveActiveJob({
        taskId: submitted.task_id,
        mode: JOB_MODE,
        submittedAt: Date.now()
      })
      const media = await waitPoll(submitted.task_id, params.timeoutMs)
      if (!pollAbort) await finish(media, submitted.task_id)
    } catch (e) {
      if (e?.name === 'AbortError') return
      fail(e?.message || String(e))
    }
  }

  async function resumeFromStorage() {
    const job = loadActiveJob()
    if (!job || job.mode !== JOB_MODE || !job.taskId) return false
    if (!claimActiveJobResume(JOB_MODE)) return false
    reset()
    pollAbort = false
    taskId.value = job.taskId
    status.value = 'running'
    queueHint.value = '恢复轮询文生图任务…'
    try {
      const media = await waitPoll(job.taskId)
      if (!pollAbort) await finish(media, job.taskId)
      return true
    } catch (e) {
      if (e?.name !== 'AbortError') fail(e?.message || String(e))
      return false
    }
  }

  const isBusy = computed(() => ['queued', 'running'].includes(status.value))

  return {
    status,
    errorMsg,
    results,
    queueHint,
    elapsedSec,
    taskId,
    isBusy,
    generate,
    resumeFromStorage,
    cleanup
  }
}
