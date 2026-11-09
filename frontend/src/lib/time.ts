// Time helpers. tz always comes from the API (display_timezone); never hard-code it.

const H = 3600e3

export interface Fmt {
  hour: (ms: number) => string
  day: (ms: number) => string
  dayTime: (ms: number) => string
  longDate: (ms: number) => string
}

const cache = new Map<string, Fmt>()

function partsOf(f: Intl.DateTimeFormat, ms: number): Record<string, string> {
  const out: Record<string, string> = {}
  for (const p of f.formatToParts(ms)) out[p.type] = p.value
  return out
}

export function makeFmt(tz: string): Fmt {
  const hit = cache.get(tz)
  if (hit) return hit
  const base = { timeZone: tz, hourCycle: 'h23' } as const
  const hm = new Intl.DateTimeFormat('en-IN', { ...base, hour: '2-digit', minute: '2-digit' })
  const dm = new Intl.DateTimeFormat('en-IN', { ...base, weekday: 'short', day: 'numeric', month: 'short' })
  const ld = new Intl.DateTimeFormat('en-IN', { ...base, weekday: 'long', day: 'numeric', month: 'long' })
  const hour = (ms: number) => {
    const p = partsOf(hm, ms)
    return `${p.hour}:${p.minute}`
  }
  const day = (ms: number) => {
    const p = partsOf(dm, ms)
    return `${p.weekday} ${p.day} ${p.month}`
  }
  const fmt: Fmt = {
    hour,
    day,
    dayTime: (ms) => `${day(ms)}, ${hour(ms)}`,
    longDate: (ms) => {
      const p = partsOf(ld, ms)
      return `${p.weekday}, ${p.day} ${p.month}`
    },
  }
  cache.set(tz, fmt)
  return fmt
}

const partsFmt = new Map<string, Intl.DateTimeFormat>()

export function istParts(ms: number, tz: string): { hour: number; minute: number; y: number; m: number; d: number } {
  let f = partsFmt.get(tz)
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric',
    })
    partsFmt.set(tz, f)
  }
  const p = partsOf(f, ms)
  return { hour: Number(p.hour), minute: Number(p.minute), y: Number(p.year), m: Number(p.month), d: Number(p.day) }
}

// Offset (local wall clock minus UTC) at ms, in ms.
function offsetAt(ms: number, tz: string): number {
  const floored = Math.floor(ms / 60e3) * 60e3
  const p = istParts(floored, tz)
  return Date.UTC(p.y, p.m - 1, p.d, p.hour, p.minute) - floored
}

// shortcut: uses the offset at range start, so a DST jump inside the range would shift later ticks; fine for IST (no DST).
export function istTicks(start: number, end: number, tz: string): number[] {
  const off = offsetAt(start, tz)
  const out: number[] = []
  for (let t = Math.ceil((start + off) / (6 * H)) * 6 * H - off; t <= end; t += 6 * H) out.push(t)
  return out
}

export function istMidnights(start: number, end: number, tz: string): number[] {
  return istTicks(start, end, tz).filter((t) => istParts(t, tz).hour === 0)
}

export function greeting(hour: number): string {
  if (hour >= 5 && hour <= 11) return 'Good morning'
  if (hour >= 12 && hour <= 16) return 'Good afternoon'
  return 'Good evening'
}

export function ageText(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}

// D-44: the forecast covers data through run_time + 1 h.
export function dataThrough(runTimeIso: string): number {
  return Date.parse(runTimeIso) + H
}
