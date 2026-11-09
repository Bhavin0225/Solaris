// Forecast rows: one equal-length array shared by all panels (Recharts syncId needs equal ticks).

export interface Point { time: string; p10: number | null; p50: number | null; p90: number | null }
export interface Forecast {
  run_time: string
  stale: boolean
  age_minutes: number
  display_timezone: string
  targets: Record<string, { unit: string; model: string; points: Point[] }>
}
export interface Cell { p50: number | null; p10: number | null; p90: number | null; band: [number, number] | null }
export type Row = { t: number } & Record<string, Cell>

export function buildRows(fc: Forecast): Row[] {
  const entries = Object.entries(fc.targets)
  if (entries.length === 0) return []
  const n = Math.min(...entries.map(([, v]) => v.points.length))
  const rows: Row[] = []
  for (let i = 0; i < n; i++) {
    const row = { t: Date.parse(entries[0][1].points[i].time) } as Row
    for (const [key, v] of entries) {
      const { p10, p50, p90 } = v.points[i]
      row[key] = { p50, p10, p90, band: p10 == null || p90 == null ? null : [p10, p90] }
    }
    rows.push(row)
  }
  return rows
}

export function sliceHours(rows: Row[], hours: number): Row[] {
  return hours >= rows.length ? rows : rows.slice(0, hours)
}

export function currentIndex(rows: Row[], nowMs: number): number {
  let idx = 0
  for (let i = 0; i < rows.length; i++) if (rows[i].t <= nowMs) idx = i
  return idx
}

export function peakOf(rows: Row[], key: string): { t: number; p50: number } | null {
  let best: { t: number; p50: number } | null = null
  for (const r of rows) {
    const v = r[key]?.p50
    if (v != null && (best === null || v > best.p50)) best = { t: r.t, p50: v }
  }
  return best
}
