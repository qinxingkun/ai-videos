export function createCharacter(index = 0) {
  const id = `speaker-${index + 1}`
  return {
    id,
    name: `角色${index + 1}`,
    speakerId: id,
    voiceId: '',
    referenceImageName: '',
    faceTrackId: null
  }
}

export function createUtterance(index = 0, speakerId = 'speaker-1') {
  const startFrame = index * 30
  return {
    id: `utterance-${Date.now()}-${index}`,
    speakerId,
    text: '',
    startFrame,
    endFrame: Math.min(125, startFrame + 30),
    lipSyncPolicy: 'preferred',
    faceTrackId: null
  }
}

export function normalizeCharacters(characters = []) {
  return characters.map((character, index) => {
    const id = String(character.id || character.speakerId || `speaker-${index + 1}`)
    return {
      ...createCharacter(index),
      ...character,
      id,
      speakerId: String(character.speakerId || id)
    }
  })
}

export function validateUtterances(utterances = [], { maxFrame = 125, speakerIds = [] } = {}) {
  if (!utterances.length) return { ok: false, error: '至少需要一条台词' }
  const sorted = utterances
    .map((item, index) => ({ ...item, _index: index }))
    .sort((a, b) => Number(a.startFrame) - Number(b.startFrame))

  for (const item of sorted) {
    const start = Number(item.startFrame)
    const end = Number(item.endFrame)
    if (!String(item.text || '').trim()) return { ok: false, error: `第 ${item._index + 1} 条台词为空` }
    if (!speakerIds.includes(String(item.speakerId))) {
      return { ok: false, error: `第 ${item._index + 1} 条台词未选择有效说话人` }
    }
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > maxFrame || end <= start) {
      return { ok: false, error: `第 ${item._index + 1} 条台词帧范围无效（0–${maxFrame}）` }
    }
  }
  for (let index = 1; index < sorted.length; index += 1) {
    if (Number(sorted[index].startFrame) < Number(sorted[index - 1].endFrame)) {
      return { ok: false, error: `第 ${sorted[index]._index + 1} 条台词与其他台词重叠` }
    }
  }
  return { ok: true, utterances: sorted.map(({ _index, ...item }) => item) }
}

function parseDialogue(dialogue = '') {
  return String(dialogue)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const matched = line.match(/^([^:：]+)[:：]\s*["“]?(.+?)["”]?$/)
      return matched ? { name: matched[1].trim(), text: matched[2].trim() } : { name: '', text: line }
    })
}

export function buildUtterancesFromShots(shots = [], characters = [], { framesPerShot = 125 } = {}) {
  const cast = normalizeCharacters(characters)
  const utterances = []
  shots.forEach((shot, shotIndex) => {
    const lines = parseDialogue(shot.dialogue)
    if (!lines.length) return
    const shotOffset = shotIndex * framesPerShot
    const localStart = Number.isFinite(Number(shot.startFrame)) ? Number(shot.startFrame) : 0
    const localEnd = Number.isFinite(Number(shot.endFrame)) ? Number(shot.endFrame) : framesPerShot
    const span = Math.max(lines.length, localEnd - localStart)
    lines.forEach((line, lineIndex) => {
      const character = cast.find((item) => item.name === line.name) || cast[lineIndex % cast.length]
      const startFrame = shotOffset + localStart + Math.floor((span * lineIndex) / lines.length)
      const endFrame = shotOffset + localStart + Math.floor((span * (lineIndex + 1)) / lines.length)
      utterances.push({
        id: `shot-${shotIndex + 1}-utterance-${lineIndex + 1}`,
        speakerId: character?.speakerId || '',
        text: line.text,
        startFrame,
        endFrame,
        lipSyncPolicy: shot.lipSyncPolicy || 'off',
        faceTrackId: character?.faceTrackId || null
      })
    })
  })
  return utterances
}

/** Merge fresh shot-derived utterances while preserving manual edits by id when possible. */
export function mergeUtterancesFromShots(existing = [], shots = [], characters = [], options = {}) {
  const generated = buildUtterancesFromShots(shots, characters, options)
  if (!existing.length) return generated
  const byId = Object.fromEntries(existing.map((item) => [item.id, item]))
  return generated.map((item) => {
    const prev = byId[item.id]
    if (!prev) return item
    return {
      ...item,
      text: prev.text || item.text,
      speakerId: prev.speakerId || item.speakerId,
      startFrame: Number.isFinite(Number(prev.startFrame)) ? Number(prev.startFrame) : item.startFrame,
      endFrame: Number.isFinite(Number(prev.endFrame)) ? Number(prev.endFrame) : item.endFrame,
      lipSyncPolicy: prev.lipSyncPolicy || item.lipSyncPolicy,
      faceTrackId: prev.faceTrackId || item.faceTrackId
    }
  })
}

export function estimatedMasterMaxFrame(shotCount = 1, framesPerShot = 125) {
  return Math.max(1, Number(shotCount) * Number(framesPerShot))
}

export function toDubCharacters(characters = []) {
  return normalizeCharacters(characters).map((item) => ({
    id: item.id,
    name: item.name,
    speakerId: item.speakerId,
    voiceId: item.voiceId,
    referenceImageName: item.referenceImageName || '',
    ...(item.faceTrackId ? { faceTrackId: item.faceTrackId } : {})
  }))
}
