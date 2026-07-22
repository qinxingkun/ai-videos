/** 角色圣经：固定外观描述，注入每段 prompt */

export const DEFAULT_CHARACTER = {
  name: '陈默',
  gender: 'male',
  age: '32',
  face: 'square jaw, short stubble, calm observant eyes',
  hair: 'short neat black hair, slightly textured',
  clothing: 'navy blazer over charcoal turtleneck, silver watch',
  accessories: 'silver watch',
  immutable: 'same face throughout, short stubble only, no glasses'
}

/** 生产环境质量底线：这些字段缺失会明显放大长链人设漂移，建议强制填写 */
export const REQUIRED_BIBLE_FIELDS = ['face', 'hair', 'clothing', 'immutable']

/** 校验角色圣经必填字段，返回缺失字段列表（供 UI 提示，不静默跳过） */
export function validateCharacterBible(character = {}) {
  const c = { ...character }
  const missing = REQUIRED_BIBLE_FIELDS.filter((key) => !c[key] || !String(c[key]).trim())
  return { ok: missing.length === 0, missing }
}

/** 防人设漂移通用负向词条：拼入负向提示，抑制"换脸/换装/变成另一个人" */
export const ANTI_DRIFT_NEGATIVE =
  'changing face, different person, morphing identity, inconsistent identity, face swap, different actor, costume change, changing hairstyle, changing eye color'

/** 基于 immutable 描述生成更具体的防漂移负向词（如"同一张脸，只留短胡须"→ 反向约束胡须变化） */
export function buildIdentityNegativeSuffix(character = {}) {
  const c = { ...DEFAULT_CHARACTER, ...character }
  const parts = [ANTI_DRIFT_NEGATIVE]
  if (c.immutable?.trim()) {
    parts.push(`violating: ${c.immutable.trim()}`)
  }
  return parts.join(', ')
}

export function buildCharacterBibleBlock(character = {}) {
  const c = { ...DEFAULT_CHARACTER, ...character }
  const parts = []
  if (c.name) parts.push(c.name)
  if (c.gender || c.age) parts.push([c.age && `${c.age} years old`, c.gender].filter(Boolean).join(' '))
  if (c.face) parts.push(c.face)
  if (c.hair) parts.push(c.hair)
  if (c.clothing) parts.push(c.clothing)
  if (c.accessories) parts.push(c.accessories)
  if (c.immutable) parts.push(c.immutable)
  if (!parts.length) return ''
  return `, character: ${parts.join(', ')}`
}

export function buildShotPrompt({ shotPrompt, character, styleSuffix, sceneSeedOffset = 0 }) {
  const bible = buildCharacterBibleBlock(character)
  const suffix = styleSuffix?.trim()
    ? styleSuffix.startsWith(',')
      ? styleSuffix
      : `, ${styleSuffix}`
    : ''
  return `${shotPrompt.trim()}${bible}${suffix}`
}

/** 同场景共用 seed；T2V 各段略递增避免生成雷同 */
export function resolveSegmentSeed({ baseSeed = 100, segmentIndex, sceneGroup = 0, mode = 't2v' }) {
  const base = (baseSeed ?? 100) + sceneGroup
  if (mode === 'i2v') return base
  return base + segmentIndex * 17
}
