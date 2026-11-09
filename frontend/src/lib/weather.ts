// Weather condition rule and daily aggregation (UI-SPEC thresholds). Icons are mapped in components.
import { istParts } from './time.ts'

export type Condition = 'rain' | 'cloudy' | 'partly' | 'partly-night' | 'sunny' | 'clear'

export interface WeatherPoint { time: string; temp: number; cloud: number; precip: number | null; is_day: boolean }

export const CONDITION_LABEL: Record<Condition, string> = {
  rain: 'Rain',
  cloudy: 'Cloudy',
  partly: 'Partly cloudy',
  'partly-night': 'Partly cloudy',
  sunny: 'Sunny',
  clear: 'Clear',
}

export function condition(precip: number | null, cloud: number | null, isDay: boolean): Condition {
  if ((precip ?? 0) >= 0.5) return 'rain'
  const c = cloud ?? 0
  if (c >= 70) return 'cloudy'
  if (c >= 30) return isDay ? 'partly' : 'partly-night'
  return isDay ? 'sunny' : 'clear'
}

export interface DayAgg { dateKey: string; firstMs: number; high: number; low: number; rainMm: number; condition: Condition }

export function dayAggregate(points: WeatherPoint[], tz: string): DayAgg[] {
  const groups = new Map<string, { ms: number; p: WeatherPoint }[]>()
  for (const p of points) {
    const ms = Date.parse(p.time)
    const { y, m, d } = istParts(ms, tz)
    const key = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const g = groups.get(key)
    if (g) g.push({ ms, p })
    else groups.set(key, [{ ms, p }])
  }
  return [...groups].map(([dateKey, g]) => {
    const temps = g.map((x) => x.p.temp)
    const day = g.filter((x) => x.p.is_day)
    const pool = day.length ? day : g
    const meanCloud = pool.reduce((s, x) => s + (x.p.cloud ?? 0), 0) / pool.length
    const rainy = day.some((x) => condition(x.p.precip, x.p.cloud, true) === 'rain')
    return {
      dateKey,
      firstMs: g[0].ms,
      high: Math.max(...temps),
      low: Math.min(...temps),
      rainMm: g.reduce((s, x) => s + (x.p.precip ?? 0), 0),
      // day cards always use the daytime icon set
      condition: rainy ? 'rain' : condition(0, meanCloud, true),
    }
  })
}
