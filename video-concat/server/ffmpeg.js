import { spawn } from 'node:child_process'

export function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    proc.stdout.on('data', (chunk) => {
      stdout += chunk.toString()
    })
    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString()
    })
    proc.on('close', (code) => {
      if (code === 0) resolve({ stdout, stderr })
      else reject(new Error(stderr.slice(-2000) || `${command} exited with code ${code}`))
    })
    proc.on('error', reject)
  })
}

export function runFfmpeg(args) {
  return runCommand('ffmpeg', args).then(({ stderr }) => stderr)
}

export async function probeMedia(filePath) {
  const { stdout } = await runCommand('ffprobe', [
    '-v',
    'error',
    '-show_entries',
    'format=duration:stream=codec_type,sample_rate',
    '-of',
    'json',
    filePath,
  ])
  const parsed = JSON.parse(stdout || '{}')
  const streams = parsed.streams || []
  const audioStream = streams.find((stream) => stream.codec_type === 'audio')
  return {
    duration: Number(parsed.format?.duration || 0),
    hasAudio: Boolean(audioStream),
    hasVideo: streams.some((stream) => stream.codec_type === 'video'),
    sampleRate: Number(audioStream?.sample_rate || 0),
  }
}

export async function probeStreamDurations(filePath) {
  const { stdout } = await runCommand('ffprobe', [
    '-v',
    'error',
    '-show_entries',
    'stream=codec_type,duration',
    '-show_entries',
    'format=duration',
    '-of',
    'json',
    filePath,
  ])
  const parsed = JSON.parse(stdout || '{}')
  const streams = parsed.streams || []
  const videoStream = streams.find((s) => s.codec_type === 'video')
  const audioStream = streams.find((s) => s.codec_type === 'audio')
  return {
    formatDuration: Number(parsed.format?.duration || 0),
    videoDuration: Number(videoStream?.duration || 0),
    audioDuration: Number(audioStream?.duration || 0),
    hasAudio: Boolean(audioStream),
    hasVideo: Boolean(videoStream),
  }
}

/** ffmpeg atempo 单次只支持 0.5–2.0，需链式调用。speed > 1 加快语速。 */
export function buildAtempoChain(speed) {
  const target = Number(speed)
  if (!Number.isFinite(target) || Math.abs(target - 1) < 0.01) return ''
  let remaining = Math.max(0.25, Math.min(4, target))
  const filters = []
  while (remaining > 2.0 + 1e-6) {
    filters.push('atempo=2.0')
    remaining /= 2.0
  }
  while (remaining < 0.5 - 1e-6) {
    filters.push('atempo=0.5')
    remaining /= 0.5
  }
  if (Math.abs(remaining - 1) >= 0.01) {
    filters.push(`atempo=${remaining.toFixed(4)}`)
  }
  return filters.join(',')
}

function buildDubbingChain({ videoDuration, dubDuration, speechSpeed = 1 }) {
  const parts = []
  let expectedDuration = dubDuration

  if (speechSpeed && Math.abs(speechSpeed - 1) >= 0.01) {
    const atempo = buildAtempoChain(speechSpeed)
    if (atempo) {
      parts.push(atempo)
      expectedDuration = dubDuration / speechSpeed
    }
  }

  // 配音比视频长时加速；比视频短时适度放慢，尽量铺满（最低 0.75x）
  if (videoDuration > 0) {
    if (expectedDuration > videoDuration * 1.02) {
      const fitSpeed = Math.min(expectedDuration / videoDuration, 4.0)
      const atempo = buildAtempoChain(fitSpeed)
      if (atempo) {
        parts.push(atempo)
        expectedDuration /= fitSpeed
      }
    } else if (expectedDuration < videoDuration * 0.98) {
      const stretchSpeed = Math.max(0.75, expectedDuration / videoDuration)
      const atempo = buildAtempoChain(stretchSpeed)
      if (atempo) {
        parts.push(atempo)
        expectedDuration /= stretchSpeed
      }
    }
  }

  if (videoDuration > 0) {
    parts.push(`apad=whole_dur=${videoDuration.toFixed(3)}`)
  } else {
    parts.push('apad')
  }

  return `[1:a]${parts.join(',')}[a1]`
}

/** 将音频时长调整到 targetDuration（通过 atempo 变速，不改变音高）。 */
export async function adjustAudioDuration(inputPath, outputPath, targetDuration) {
  const { duration } = await probeMedia(inputPath)
  if (!duration || !targetDuration) {
    await runFfmpeg(['-y', '-i', inputPath, '-c', 'copy', outputPath])
    return duration
  }
  const speed = duration / targetDuration
  if (Math.abs(speed - 1) < 0.03) {
    await runFfmpeg(['-y', '-i', inputPath, '-c', 'copy', outputPath])
    return duration
  }
  const af = buildAtempoChain(speed)
  if (!af) {
    await runFfmpeg(['-y', '-i', inputPath, '-c', 'copy', outputPath])
    return duration
  }
  await runFfmpeg(['-y', '-i', inputPath, '-af', af, outputPath])
  const out = await probeMedia(outputPath)
  return out.duration
}

/** 拼接多段 wav，段间插入短暂静音。 */
export async function concatWavWithGaps(inputPaths, outputPath, gapSec = 0.12) {
  if (!inputPaths.length) throw new Error('没有可拼接的音频')
  if (inputPaths.length === 1) {
    await runFfmpeg(['-y', '-i', inputPaths[0], '-c', 'copy', outputPath])
    return
  }

  const { sampleRate } = await probeMedia(inputPaths[0])
  const sr = sampleRate || 48_000
  const gapCount = inputPaths.length - 1
  const args = ['-y']
  for (const p of inputPaths) args.push('-i', p)
  for (let i = 0; i < gapCount; i++) {
    args.push('-f', 'lavfi', '-t', String(gapSec), '-i', `anullsrc=r=${sr}:cl=mono`)
  }

  const streams = []
  for (let i = 0; i < inputPaths.length; i++) {
    streams.push(`[${i}:a]`)
    if (i < gapCount) streams.push(`[${inputPaths.length + i}:a]`)
  }
  const filter = `${streams.join('')}concat=n=${inputPaths.length + gapCount}:v=0:a=1[out]`
  args.push('-filter_complex', filter, '-map', '[out]', outputPath)
  await runFfmpeg(args)
}

export async function mixDubbingIntoVideo({
  videoPath,
  audioPath,
  outputPath,
  hasOriginalAudio,
  audioMode = 'mix',
  videoDuration = 0,
  speechSpeed = 1,
}) {
  const dub = await probeMedia(audioPath)
  const dubChain = buildDubbingChain({
    videoDuration,
    dubDuration: dub.duration,
    speechSpeed,
  })

  const encodeTail = [
    '-c:v',
    'copy',
    '-c:a',
    'aac',
    '-b:a',
    '192k',
    '-movflags',
    '+faststart',
    outputPath,
  ]

  if (!hasOriginalAudio || audioMode === 'replace') {
    await runFfmpeg([
      '-y',
      '-i',
      videoPath,
      '-i',
      audioPath,
      '-filter_complex',
      dubChain,
      '-map',
      '0:v:0',
      '-map',
      '[a1]',
      ...encodeTail,
    ])
    return
  }

  const padDur = videoDuration > 0 ? videoDuration.toFixed(3) : null
  const mixFilter = padDur
    ? `${dubChain};[0:a]apad=whole_dur=${padDur}[a0p];[a0p][a1]amix=inputs=2:duration=longest:dropout_transition=0,apad=whole_dur=${padDur}[aout]`
    : `${dubChain};[0:a][a1]amix=inputs=2:duration=longest:dropout_transition=0[aout]`

  await runFfmpeg([
    '-y',
    '-i',
    videoPath,
    '-i',
    audioPath,
    '-filter_complex',
    mixFilter,
    '-map',
    '0:v:0',
    '-map',
    '[aout]',
    ...encodeTail,
  ])
}
