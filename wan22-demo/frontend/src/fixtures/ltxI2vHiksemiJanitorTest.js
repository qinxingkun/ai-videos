/**
 * LTX 2.3 · 海康存储「扫地生」老陈 — 默认剧情测试用例（6×5s）
 * I2V / T2V 共用；台词写入 dialogue，画面描述写入 prompt。
 *
 * 固定三人卡司：老陈（唯一保洁服）+ 研发A + 研发B（年轻工程师，禁止保洁服）
 */

const LAB_SETTING =
  '明亮现代科技公司研发实验室，同一间办公室、同一白天白光，连续时间线不换场；桌上有显示器与存储样机；干净科幻办公感'

export const LTX_HIKSEMI_JANITOR_TEST = {
  id: 'ltx-hiksemi-janitor-v4',
  title: '海康存储·扫地生反转',
  description:
    'LTX 2.3 I2V/T2V 6段 × 5s。三人卡司：1保洁老陈 + 2年轻研发；第1段仅两研发出场。',
  engine: 'ltx',
  durationPreset: '30s',
  dialogueMode: false,
  styleSuffix:
    '无厘头职场反差喜剧，人物说话时口型清晰可辨，表情夸张有喜剧感，实验室白光明亮干净，人物身份服装前后一致，动作自然流畅，无水印无烧录对白字幕，画质清晰',
  baseSeed: 100,
  sceneBible: LAB_SETTING,
  character: {
    name: '老陈',
    age: '45',
    gender: '男',
    face: '中年中国男性，淡定扑克脸，严格匹配上传定妆照脸部特征（T2V 无图时以本描述为准）',
    hair: '短发黑发略带灰白',
    clothing: '皱巴巴灰蓝色保洁服（全片唯一穿保洁服的人）；后段脱下外套露出笔挺白衬衫与领带',
    accessories: '拖把、清洁桶；后段海康存储固态硬盘与产品总监胸牌',
    immutable:
      '全程同一张脸，不得换脸换人；表情克制淡定；全片只有他一人穿保洁服拿拖把',
    voice: 'steady calm middle-aged male Mandarin'
  },
  characters: [
    {
      id: 'laochen',
      name: '老陈',
      gender: '男',
      age: '45',
      face: '中年中国男性，淡定扑克脸',
      hair: '短发略带灰白',
      clothing: '灰蓝色皱巴巴保洁服（全片唯一保洁服）；后段白衬衫领带',
      accessories: '拖把与清洁桶',
      role: '保洁/产品总监',
      voice: 'steady calm middle-aged male Mandarin'
    },
    {
      id: 'eng-a',
      name: '研发A',
      gender: '男',
      age: '28',
      face: '年轻中国男性，焦虑表情，圆脸短发',
      hair: '黑色短发整齐',
      clothing: '浅色衬衫或卫衣、深色休闲裤、运动鞋，工牌挂绳；绝不是保洁服',
      accessories: '无拖把无清洁桶',
      role: '年轻研发工程师',
      voice: 'anxious young male Mandarin'
    },
    {
      id: 'eng-b',
      name: '研发B',
      gender: '男',
      age: '26',
      face: '年轻中国男性，瘦削脸，急躁表情',
      hair: '黑色短发稍乱',
      clothing: '深色Polo或黑色T恤、牛仔裤；绝不是保洁服',
      accessories: '无拖把无清洁桶',
      role: '年轻研发工程师',
      voice: 'frustrated young male Mandarin'
    }
  ],
  shots: [
    {
      name: '01_panic',
      storyBeat: '0-5s 仅两名工程师，禁止第三人',
      presentCharacterIds: ['eng-a', 'eng-b'],
      prompt:
        '明亮研发实验室中景：画面里从头到尾只有两名年轻男工程师，一共两个人，没有第三人，没有第四人，没有路人，没有保洁工，没有灰蓝保洁服，没有拖把。两人围着同一台电脑抓狂，屏幕红色报错告警感。研发A穿浅色衬衫/卫衣薅头发焦急开口；研发B穿深色Polo猛敲键盘抱怨。桌上散落硬盘和测试样机。焦虑快节奏，口型清晰，不要烧录对白字幕',
      dialogue:
        '研发A: "这速度卡死了！8K raw 素材都跑不动！"\n研发B: "大容量测试又崩了！这礼拜第八回了！"',
      ambientSound: 'keyboard clatter, stressed office room tone, computer alert beeps'
    },
    {
      name: '02_janitor_pass',
      storyBeat: '5-10s 老陈路过被撵',
      presentCharacterIds: ['laochen', 'eng-a', 'eng-b'],
      prompt:
        '同一实验室恰好三人同框、不要第四人：老陈拖着拖把慢悠悠从旁边路过，保洁服皱巴巴，还挎着清洁桶；他随意瞟一眼屏幕，停下脚步，拖把往地上一靠。两名年轻研发（浅色衬衫与深色Polo，绝非保洁服）不耐烦抬头，研发A摆手让他让路，老陈语气平淡开口回应。全片只有老陈一人穿保洁服拿拖把。中景反差喜剧，口型清晰，拖把拖地摩擦声，不要烧录对白字幕',
      dialogue:
        '研发A: "师傅麻烦让让，这儿正忙呢！"\n老陈: "哦？这问题啊。"',
      ambientSound: 'mop dragging and floor friction, soft lab ambient'
    },
    {
      name: '03_ssd_fix',
      storyBeat: '10-15s 老陈插海康硬盘，测试全过，无台词',
      presentCharacterIds: ['laochen', 'eng-a', 'eng-b'],
      prompt:
        '本段无台词。老陈不多废话，从保洁服口袋摸出一块海康存储固态硬盘（HIKSEMI logo清晰），随手插上电脑，指尖随便点两下鼠标。背景两名年轻工程师（衬衫/Polo，无保洁服）旁观。切屏幕特写：绿色进度条瞬间拉满，传输速度数值疯狂飙升，测试结果全项通过的成功状态。清脆插拔声与极速传输电子音。光影科技感，logo清晰，无对白字幕。画面不超过三人',
      dialogue: '',
      ambientSound: 'crisp USB plug click, whoosh high-speed transfer tone, rising digital meter beeps'
    },
    {
      name: '04_reveal',
      storyBeat: '15-20s 揭身份：产品总监老陈',
      presentCharacterIds: ['laochen', 'eng-a', 'eng-b'],
      prompt:
        '恰好三人、不要第四人。两名年轻研发（衬衫与Polo，无保洁服）瞪大眼睛凑到屏幕前，嘴巴张成O型，缓缓转头看老陈。老陈淡定拔掉硬盘，拍拍衣服上的灰，一把扯下保洁外套——里面穿着笔挺衬衫，胸牌写着产品总监老陈。两人异口同声惊讶发问；老陈整理领带，手持海康存储产品，沉稳开口介绍。倒抽冷气与衣服摩擦声。中景推镜反转揭秘，口型清晰，不要烧录对白字幕',
      dialogue:
        '研发A: "你是？！"\n研发B: "你是？！"\n老陈: "海康存储，高速稳定，大容量兜底。搞不定的，找它就行。"',
      ambientSound: 'gasps, clothing rustle, soft lab tone'
    },
    {
      name: '05_mop_again',
      storyBeat: '20-25s 老陈继续拖地，工程师懵住',
      presentCharacterIds: ['laochen', 'eng-a', 'eng-b'],
      prompt:
        '恰好三人、不要第四人。老陈弯腰拿起拖把和清洁桶，背对着镜头慢悠悠往前走继续拖地；前景两名年轻工程师（衬衫/Polo，绝非保洁服）呆站着面面相觑一脸懵。全景镜头，喜剧留白感，同一实验室，禁止第二名保洁工。无对白字幕',
      dialogue: '',
      ambientSound: 'slow mopping, quiet awkward silence'
    },
    {
      name: '06_brand',
      storyBeat: '25-30s 品牌产品亮光特写收尾（独立 T2V，不接拖地暗场）',
      presentCharacterIds: [],
      forceT2v: true,
      prompt:
        '明亮商业产品广告镜头：干净白色或浅灰摄影棚背景，高键光均匀打亮，无大面积阴影。画面正中海康存储固态硬盘产品超清晰特写，金属机身反射柔光，HIKSEMI logo锐利可读。镜头缓慢微推，产品始终合焦清晰。不要人物、不要拖把、不要虚化黑影、不要剪影、不要暗调。底部可有清晰品牌标语：海康存储 高手藏得深。干净明亮品牌收尾，4k product packshot，无水印无乱码',
      dialogue: '',
      ambientSound: 'soft bright brand stinger, clean silence'
    }
  ]
}

/** @deprecated 使用 LTX_HIKSEMI_JANITOR_TEST */
export const LTX_I2V_HIKSEMI_JANITOR_TEST = LTX_HIKSEMI_JANITOR_TEST

function setTarget(target, key, val) {
  const r = target[key]
  if (r != null && typeof r === 'object' && 'value' in r) r.value = val
  else target[key] = val
}

/**
 * 将海康「扫地生」用例写入 MultiShotEditor 的 reactive 状态。
 * @param {{ mode?: 'i2v' | 't2v' }} [opts] I2V 用 chain+anchor；T2V 用 production
 */
export function applyLtxHiksemiJanitorTestCase(target, { mode = 'i2v' } = {}) {
  const t = LTX_HIKSEMI_JANITOR_TEST

  setTarget(target, 'dialogueMode', false)
  setTarget(target, 'styleSuffix', t.styleSuffix)
  setTarget(target, 'baseSeed', t.baseSeed)
  setTarget(target, 'sceneBible', t.sceneBible)
  setTarget(target, 'continuityMode', mode === 'i2v' ? 'chain+anchor' : 'production')
  if (target.durationPreset != null) setTarget(target, 'durationPreset', t.durationPreset)
  if (target.productionSeg1I2v != null) setTarget(target, 'productionSeg1I2v', false)
  if (target.dubbingEnabled != null) setTarget(target, 'dubbingEnabled', false)

  if (target.character && typeof target.character === 'object') {
    Object.assign(target.character, t.character)
  }

  const castList = target.characters
  const castMapped = t.characters.map((c, index) => ({
    ...c,
    speakerId: c.speakerId || c.id || `speaker-${index + 1}`,
    voiceId: c.voiceId || '',
    voice: c.voice || ''
  }))
  if (castList && typeof castList.splice === 'function') {
    castList.splice(0, castList.length, ...castMapped)
  }

  const shotList = target.shots
  const mapped = t.shots.map((s) => ({
    name: s.name,
    prompt: s.prompt,
    dialogue: s.dialogue || '',
    storyBeat: s.storyBeat,
    startFrame: null,
    endFrame: null,
    lipSyncPolicy: 'off',
    ambientSound: s.ambientSound || '',
    forceT2v: !!s.forceT2v,
    presentCharacterIds: Array.isArray(s.presentCharacterIds) ? [...s.presentCharacterIds] : undefined
  }))
  if (shotList && typeof shotList.splice === 'function') {
    shotList.splice(0, shotList.length, ...mapped)
  } else {
    target.shots = mapped
  }

  return t
}

/** @deprecated 使用 applyLtxHiksemiJanitorTestCase */
export function applyLtxI2vHiksemiJanitorTestCase(target, opts) {
  return applyLtxHiksemiJanitorTestCase(target, opts ?? { mode: 'i2v' })
}
