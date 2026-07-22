/** LTX 2.3 多角色对话 prompt 构建（含音频/台词） */

import { buildShotPrompt } from './characterBible.js'
import { buildContinuityContext } from './storyContinuity.js'
import {
  DEFAULT_CHARACTERS,
  DEFAULT_DIALOGUE_SHOTS,
  LTX_T2V_TWO_PERSON_DIALOGUE_TEST,
  applyTwoPersonDialogueTestCase,
  applyLongStoryTestCase
} from '../fixtures/ltxT2vTwoPersonDialogueTest.js'
import {
  LTX_I2V_HIKSEMI_JANITOR_TEST,
  LTX_HIKSEMI_JANITOR_TEST,
  applyLtxI2vHiksemiJanitorTestCase,
  applyLtxHiksemiJanitorTestCase
} from '../fixtures/ltxI2vHiksemiJanitorTest.js'

export {
  DEFAULT_CHARACTERS,
  DEFAULT_DIALOGUE_SHOTS,
  LTX_T2V_TWO_PERSON_DIALOGUE_TEST,
  applyTwoPersonDialogueTestCase,
  applyLongStoryTestCase,
  LTX_I2V_HIKSEMI_JANITOR_TEST,
  LTX_HIKSEMI_JANITOR_TEST,
  applyLtxI2vHiksemiJanitorTestCase,
  applyLtxHiksemiJanitorTestCase
}

const SPEAKER_LINE_RE = /^([^:：]+)\s*[:：]\s*["「『]?(.+?)["」』]?\s*$/

/** LTX 画面提示词净化：抑制烧录对白字幕，保留口型与音效描述 */
export function sanitizeLtxVisualPrompt(prompt = '') {
  let p = String(prompt).trim()
  if (!p) return p
  // 弱化「必须把对白烧在画面上」的暗示，但不删除台词内容（台词走 dialogue → speech block）
  p = p.replace(/底部配文字/g, '底部品牌标语区')
  p = p.replace(/\s{2,}/g, ' ').replace(/，{2,}/g, '，').trim()
  return p
}

export const LTX_NO_SUBTITLE_SUFFIX =
  'no burned-in dialogue captions, no karaoke subtitles, no floating speech bubbles; speech is audible Mandarin with clear lip sync, not on-screen caption text'

export const LTX_CAST_IDENTITY_SUFFIX =
  'exactly one janitor in grey-blue cleaning uniform with mop; the other two are young engineers in casual office clothes, never wearing cleaning uniforms, never holding mops; no second janitor; no fourth person'

/** 按分镜 presentCharacterIds 过滤当场出场角色；未指定则用全卡司 */
export function resolvePresentCharacters(characters = [], shot = {}) {
  const ids = shot?.presentCharacterIds
  if (!Array.isArray(ids)) return characters || []
  if (!ids.length) return []
  const set = new Set(ids)
  return (characters || []).filter((c) => set.has(c.id) || set.has(c.name))
}

/** 按当场人数生成人数约束，避免第1段仍注入「必须有保洁」 */
export function buildShotCastIdentitySuffix(characters = []) {
  const n = characters.length
  if (n === 0) {
    return 'no people in frame, product packshot only, empty clean background, no silhouettes'
  }
  if (n === 2) {
    return 'exactly two young male engineers only; total headcount two; no janitor; no cleaning uniform; no mop; no third person; no fourth person; no background extras'
  }
  if (n === 3) {
    return LTX_CAST_IDENTITY_SUFFIX
  }
  return `exactly ${n} people in frame, no background extras, no crowd`
}

/** 解析 "角色名: 台词" 多行文本 */
export function parseDialogueLines(text) {
  if (!text?.trim()) return []
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const m = line.match(SPEAKER_LINE_RE)
      if (!m) return { speaker: '', line: line.replace(/^["「『]|["」』]$/g, '') }
      return { speaker: m[1].trim(), line: m[2].trim() }
    })
}

export function findCharacter(characters, speakerName) {
  if (!speakerName) return null
  return (
    characters.find((c) => c.name === speakerName) ||
    characters.find((c) => speakerName.includes(c.name) || c.name.includes(speakerName))
  )
}

/** 多角色外观 cast 描述（LTX 要求写清每个角色） */
export function buildCastBlock(characters = []) {
  if (!characters.length) return ''
  const descs = characters.map((c) => {
    const parts = [c.name]
    if (c.age || c.gender) parts.push([c.age && `${c.age} years old`, c.gender].filter(Boolean).join(' '))
    if (c.face) parts.push(c.face)
    if (c.hair) parts.push(c.hair)
    if (c.clothing) parts.push(c.clothing)
    return parts.join(', ')
  })
  return ` Characters visible in THIS shot only (${characters.length} people): ${descs.join('; ')}. Do not add any other people.`
}

/** 将台词转为 LTX 音频格式（引号 + 声线） */
export function buildSpeechBlock(dialogueText, characters = []) {
  const lines = parseDialogueLines(dialogueText)
  if (!lines.length) return ''

  const parts = lines.map(({ speaker, line }, idx) => {
    const char = findCharacter(characters, speaker)
    const label = char?.name || speaker || 'The character'
    const voice = char?.voice || (char?.gender === 'female' ? 'soft female voice' : 'calm male voice')
    const quote = line.replace(/^["「『]|["」』]$/g, '')
    if (idx === 0) {
      return `${label} speaks in a ${voice} in Mandarin: "${quote}"`
    }
    return `then ${label} ${idx > 0 ? 'replies' : 'speaks'} in a ${voice} in Mandarin: "${quote}"`
  })

  return ` ${parts.join('. ')}.`
}

/** LTX T2V 完整 prompt：场景 + 角色 + 叙事衔接 + 台词 + 环境音 + 风格 */
export function buildLTXDialoguePrompt({
  shotPrompt,
  dialogueText,
  characters = [],
  styleSuffix,
  ambientSound = 'soft ambient room tone, natural foley',
  sceneBible,
  continuityBlock = '',
  storyBeatBlock = '',
  castIdentitySuffix
}) {
  const visual = sanitizeLtxVisualPrompt(shotPrompt?.trim() || '')
  const cast = buildCastBlock(characters)
  const scene = sceneBible?.trim()
    ? ` Setting: ${sceneBible.trim()} Same location, continuous timeline, no scene jump.`
    : ''
  const speech = buildSpeechBlock(dialogueText, characters)
  const style = styleSuffix?.trim()
    ? styleSuffix.startsWith(',')
      ? styleSuffix
      : `, ${styleSuffix}`
    : ''
  const identity = castIdentitySuffix || buildShotCastIdentitySuffix(characters)

  let prompt = visual
  if (!prompt.toLowerCase().startsWith('style:')) {
    prompt = `Style: cinematic realistic.${scene}${cast ? ` ${cast.trim()}` : ''} ${continuityBlock}${storyBeatBlock} ${prompt}`
  } else {
    prompt = `${prompt}${scene}${cast}${continuityBlock}${storyBeatBlock}`
  }

  if (ambientSound && !speech.toLowerCase().includes('ambient')) {
    prompt += ` Ambient sound: ${ambientSound}.`
  }
  if (speech) prompt += speech

  return `${prompt.trim()}${style} ${LTX_NO_SUBTITLE_SUFFIX}. ${identity}`.replace(/\s+/g, ' ').trim()
}

export function buildShotPromptWithDialogue({
  shotPrompt,
  dialogueText,
  characters,
  character,
  styleSuffix,
  dialogueMode: _dialogueMode,
  engine,
  mode,
  segmentIndex = 0,
  allShots = [],
  sceneBible = '',
  chained = false,
  ambientSound
}) {
  const fullCast = characters?.length ? characters : character ? [character] : []
  const shotMeta = allShots?.[segmentIndex] || {}
  const cast = resolvePresentCharacters(fullCast, shotMeta)
  const { bridgeBlock, beatBlock } = buildContinuityContext({
    segmentIndex,
    shots: allShots,
    sceneBible,
    totalSegments: allShots.length || 6,
    chained: chained || segmentIndex > 0
  })

  const shotAmbient =
    ambientSound ||
    shotMeta.ambientSound ||
    'soft ambient room tone, natural foley'

  // LTX：按分镜出场角色注入 cast，避免第1段仍带入老陈导致多人
  if (engine === 'ltx') {
    return buildLTXDialoguePrompt({
      shotPrompt,
      dialogueText: dialogueText || '',
      characters: cast,
      styleSuffix,
      sceneBible,
      continuityBlock: bridgeBlock,
      storyBeatBlock: beatBlock,
      ambientSound: shotAmbient,
      castIdentitySuffix: buildShotCastIdentitySuffix(cast)
    })
  }
  const parts = [shotPrompt.trim()]
  if (sceneBible) parts.push(sceneBible)
  if (bridgeBlock) parts.push(bridgeBlock)
  if (beatBlock) parts.push(beatBlock)
  if (cast.length > 1) {
    const castDesc = cast
      .map((c) => [c.name, c.face, c.hair, c.clothing].filter(Boolean).join(', '))
      .join('; ')
    parts.push(`characters: ${castDesc}`)
    const suffix = styleSuffix?.trim()
      ? styleSuffix.startsWith(',')
        ? styleSuffix
        : `, ${styleSuffix}`
      : ''
    return `${parts.join('. ')}${suffix}`
  }
  return buildShotPrompt({ shotPrompt: parts.join('. '), character: cast[0] || character, styleSuffix })
}
