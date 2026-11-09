// One-line explanations for strong correlations (UI-SPEC correlation card).

const REASONS: Record<string, string> = {
  'ghi|t1_kw': 'solar output is computed from the sunlight reaching the panels.',
  't5_kw|ws10': "the turbine's power curve turns wind speed into kW, steeply between cut-in and rated speed.",
  'ghi|rh': 'humid hours are usually cloudy or at night, when there is little sunlight.',
  'rh|t1_kw': 'the same cloud and night effect, passed through to solar output.',
  'rh|ws10': 'the monsoon brings both stronger winds and moist air.',
}

export interface CorrSentence { a: string; b: string; r: number; text: string }

export function corrSentences(targets: string[], matrix: number[][], labels: Record<string, string>): CorrSentence[] {
  const out: CorrSentence[] = []
  for (let i = 0; i < targets.length; i++) {
    for (let j = i + 1; j < targets.length; j++) {
      const r = matrix[i]?.[j]
      if (r == null || !Number.isFinite(r) || Math.abs(r) < 0.5) continue
      const a = targets[i]
      const b = targets[j]
      const reason = REASONS[[a, b].sort().join('|')]
      const head = `${labels[a] ?? a} and ${labels[b] ?? b} ${r > 0 ? 'rise together' : 'move in opposite directions'} (r = ${r.toFixed(2)})`
      out.push({ a, b, r, text: reason ? `${head}: ${reason}` : head })
    }
  }
  return out.sort((x, y) => Math.abs(y.r) - Math.abs(x.r)).slice(0, 4)
}
