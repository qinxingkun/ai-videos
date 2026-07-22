/** 多分镜剧情连贯：场景圣经 + 段间叙事衔接 */

export function buildSceneBibleBlock(sceneBible) {
  const text = sceneBible?.trim()
  if (!text) return ''
  return ` Setting: ${text} Same location, continuous timeline, no scene jump, no time skip.`
}

export function summarizeShot(shot) {
  if (!shot) return ''
  const parts = []
  if (shot.storyBeat?.trim()) parts.push(shot.storyBeat.trim())
  else if (shot.prompt?.trim()) parts.push(shot.prompt.trim().slice(0, 100))
  if (shot.dialogue?.trim()) {
    const lines = shot.dialogue
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length) parts.push(`They said: ${lines.join('; ')}`)
  }
  return parts.join('. ')
}

/**
 * 注入「紧接上一段」的叙事桥接（LTX 对时序/因果描述敏感）
 */
export function buildNarrativeBridge({ segmentIndex, shots = [], totalSegments, chained = false }) {
  if (segmentIndex <= 0 || !shots.length) return ''

  const total = totalSegments ?? shots.length
  const prev = shots[segmentIndex - 1]
  const prevSummary = summarizeShot(prev)
  const parts = [
    `Continuity: Shot ${segmentIndex + 1} of ${total} in one uninterrupted scene.`,
    `Immediately continues from the previous moment: ${prevSummary}.`,
    'Same characters, same costumes, same weather and lighting as previous shot.'
  ]
  if (chained) {
    parts.push(
      'The clip starts mid-action with immediate visible motion — no frozen opening, no static pose hold, no replay of the previous ending frame.',
      'First 8–12 frames must already show continuous motion from the reference pose; do not hold or morph slowly into action.',
      'Dialogue and speech should finish within the first 3.5 seconds; leave the last 0.5 seconds as natural pause or breath with no new words starting.'
    )
  } else if (segmentIndex > 0) {
    parts.push(
      'New distinct camera angle advancing the story — do not repeat the exact same composition, pose, or action from the previous shot.'
    )
  }
  return ` ${parts.join(' ')}`
}

export function buildStoryBeatBlock(shot) {
  const beat = shot?.storyBeat?.trim()
  if (!beat) return ''
  return ` Story beat: ${beat}.`
}

export function buildContinuityContext({ segmentIndex, shots, sceneBible, totalSegments, chained = false }) {
  return {
    sceneBlock: buildSceneBibleBlock(sceneBible),
    bridgeBlock: buildNarrativeBridge({ segmentIndex, shots, totalSegments, chained }),
    beatBlock: buildStoryBeatBlock(shots[segmentIndex])
  }
}