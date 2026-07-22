/**
 * LTX 2.3 · T2V · 双人对话 — 标准测试用例（都市日间咖啡馆）
 */

export const LTX_T2V_TWO_PERSON_DIALOGUE_TEST = {
  id: 'ltx-t2v-two-person-dialogue-v3',
  title: '双人对话测试·咖啡馆谈判',
  description:
    'LTX 2.3 T2V 6段 × 5s，同一场景连续时间线。陈默 + 周晴，晴朗午后咖啡馆谈项目合作。',
  engine: 'ltx',
  mode: 't2v',
  dialogueMode: true,
  continuityMode: 'production',
  productionSeg1I2v: false,
  styleSuffix:
    'contemporary urban drama, soft daylight through large glass windows, clean color grade, shallow depth of field, photorealistic, 4k, consistent look every shot',
  baseSeed: 42,
  sceneBible:
    'Bright sunny afternoon inside the same modern downtown cafe. Only 陈默 and 周晴. Continuous real-time timeline in one location. Soft daylight, wooden tables, espresso machine in soft background, city street visible through glass. No weather change, no night scene, no location change.',
  characters: [
    {
      id: 'A',
      name: '陈默',
      gender: 'male',
      age: '32',
      voice: 'steady low male voice',
      face: 'square jaw, short stubble, calm observant eyes',
      hair: 'short neat black hair, slightly textured',
      clothing: 'navy blazer over charcoal turtleneck, silver watch',
      role: '创业者'
    },
    {
      id: 'B',
      name: '周晴',
      gender: 'female',
      age: '29',
      voice: 'clear confident female voice',
      face: 'oval face, light freckles, sharp intelligent eyes',
      hair: 'shoulder-length straight black hair with side part',
      clothing: 'cream knit sweater, beige trench coat draped on chair, thin gold necklace',
      role: '投资人'
    }
  ],
  shots: [
    {
      name: '01_establish',
      storyBeat: 'Two professionals sit across a cafe table; polite but measured opening',
      prompt:
        'Wide establishing two-shot at a wooden cafe table by the window, 陈默 and 周晴 sit opposite each other, soft afternoon sunlight, coffee cups on the table',
      dialogue:
        '陈默: "谢谢你抽空见我。"\n周晴: "说吧，你的方案我看过了。"'
    },
    {
      name: '02_chen_pitch',
      storyBeat: '陈默 outlines why the product matters now',
      prompt:
        'Close medium on 陈默 at the same cafe table, he leans forward slightly, daylight on his face, laptop closed beside his cup',
      dialogue: '陈默: "市场窗口只有六个月，再晚就没了。"'
    },
    {
      name: '03_zhou_pushback',
      storyBeat: '周晴 challenges the risk and timeline',
      prompt:
        'Close medium on 周晴 at the same cafe table, she taps a tablet screen once, same sunny window light behind her',
      dialogue: '周晴: "团队呢？你现在只有五个人。"'
    },
    {
      name: '04_exchange',
      storyBeat: '陈默 answers staffing; 周晴 asks about the valuation',
      prompt:
        'Over-the-shoulder from behind 周晴 toward 陈默 at the same cafe table, he slides a thin printed one-pager across the table',
      dialogue:
        '陈默: "核心工程都在，扩招我有名单。"\n周晴: "那估值怎么算？"'
    },
    {
      name: '05_closer',
      storyBeat: 'Negotiation tightens; both more engaged',
      prompt:
        'Medium two-shot at the same cafe table, both lean in a little closer, steam rises from fresh coffee, city traffic soft-blurred outside',
      dialogue:
        '陈默: "按现在流水，八千万不算高。"\n周晴: "我最多谈到六千五。"'
    },
    {
      name: '06_handshake',
      storyBeat: 'They reach a tentative agreement and seal it with a handshake',
      prompt:
        'Wide two-shot at the same cafe table, 陈默 and 周晴 shake hands across the table, slight smiles, continuous sunny afternoon light, no nightfall',
      dialogue:
        '陈默: "六千五可以，条款我今晚发你。"\n周晴: "好。合作愉快。"'
    }
  ]
}

export const DEFAULT_CHARACTERS = LTX_T2V_TWO_PERSON_DIALOGUE_TEST.characters
export const DEFAULT_DIALOGUE_SHOTS = LTX_T2V_TWO_PERSON_DIALOGUE_TEST.shots

export function applyTwoPersonDialogueTestCase(target) {
  const t = LTX_T2V_TWO_PERSON_DIALOGUE_TEST

  function set(key, val) {
    const r = target[key]
    if (r != null && typeof r === 'object' && 'value' in r) r.value = val
    else target[key] = val
  }

  set('dialogueMode', t.dialogueMode)
  set('styleSuffix', t.styleSuffix)
  set('baseSeed', t.baseSeed)
  set('sceneBible', t.sceneBible)
  if (target.continuityMode != null) set('continuityMode', t.continuityMode)
  if (target.productionSeg1I2v != null) set('productionSeg1I2v', false)

  const chars = target.characters
  if (chars && typeof chars.splice === 'function') {
    chars.splice(0, chars.length, ...t.characters.map((c) => ({ ...c })))
  } else {
    target.characters = t.characters.map((c) => ({ ...c }))
  }

  const shotList = target.shots
  const mapped = t.shots.map((s) => ({
    name: s.name,
    prompt: s.prompt,
    dialogue: s.dialogue,
    storyBeat: s.storyBeat
  }))
  if (shotList && typeof shotList.splice === 'function') {
    shotList.splice(0, shotList.length, ...mapped)
  } else {
    target.shots = mapped
  }

  return t
}

/** 长剧情测试用例（LTX/Wan 默认无配音台词；Wan 可再开配音） */
export function applyLongStoryTestCase(target, { engine = 'ltx', withDialogue = false } = {}) {
  const t = applyTwoPersonDialogueTestCase(target)
  function set(key, val) {
    const r = target[key]
    if (r != null && typeof r === 'object' && 'value' in r) r.value = val
    else target[key] = val
  }
  set('dialogueMode', engine === 'wan' ? withDialogue : false)
  set('continuityMode', 'production')
  set('productionSeg1I2v', false)
  if (!withDialogue || engine !== 'wan') {
    const shotList = target.shots
    if (shotList && typeof shotList.splice === 'function') {
      for (const s of shotList) s.dialogue = ''
    }
  }
  return { ...t, engine, withDialogue: engine === 'wan' && withDialogue }
}
