/**
 * 镜头语法/雷同度校验：轻量启发式检测，避免连续分镜景别雷同
 * （放大"剪辑硬切感"问题），不涉及模型推理，仅做提示，不阻断生成。
 */

const SHOT_TYPE_PATTERNS = [
  { id: 'close', re: /\b(close[- ]?up|close medium|tight shot|macro)\b/i },
  { id: 'medium', re: /\bmedium (shot|two-shot)\b/i },
  { id: 'wide', re: /\b(wide( shot)?|establishing|long shot)\b/i },
  { id: 'over-shoulder', re: /\bover[- ]the[- ]shoulder\b/i },
  { id: 'insert', re: /\b(insert|close on hands|detail shot)\b/i },
  { id: 'pov', re: /\bpoint[- ]of[- ]view|pov\b/i }
]

/** 从一句分镜描述中猜测景别类别；识别不出时归为 'unspecified' */
export function detectShotType(prompt = '') {
  const text = String(prompt || '')
  for (const { id, re } of SHOT_TYPE_PATTERNS) {
    if (re.test(text)) return id
  }
  return 'unspecified'
}

/**
 * 检测连续 N 段（默认 3）景别雷同，返回警告列表（1-based 段号区间）。
 * 只在能识别出具体景别时才计入雷同（避免对 'unspecified' 误报）。
 */
export function detectRepeatedShotGrammar(shots = [], { runLength = 3 } = {}) {
  const types = shots.map((s) => detectShotType(s?.prompt ?? s?.[1] ?? ''))
  const warnings = []
  let runStart = 0
  for (let i = 1; i <= types.length; i++) {
    const same = i < types.length && types[i] === types[runStart] && types[runStart] !== 'unspecified'
    if (!same) {
      const runLen = i - runStart
      if (runLen >= runLength && types[runStart] !== 'unspecified') {
        warnings.push({
          from: runStart + 1,
          to: i,
          shotType: types[runStart],
          message: `第 ${runStart + 1}–${i} 段连续使用相同景别（${types[runStart]}），建议变化景别避免剪辑硬切感`
        })
      }
      runStart = i
    }
  }
  return warnings
}
