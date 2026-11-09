// Weather page (/weather, D-35). Temperature, cloud and rain come from Open-Meteo; humidity, sunlight and
// wind speed are our model's P50. Temperature is never a model target, so it stays --ink (D-34).
// Interactive: tap an hour to show it in the hero, tap a day to load its hours into the strip.
import { Activity, Clock, Cloud, CloudMoon, CloudRain, CloudSun, Moon, Sun, Sunrise, Sunset, type LucideIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ApiError, useForecast, useHealth, useSite, useTz, useWeather } from '../api'
import { GlassCard, IconChip, PageHeader, SourceTag, StateBlock, Stagger } from '../components/ui'
import { buildRows, type Row } from '../lib/forecast'
import { sunFraction, sunTimes } from '../lib/sun'
import { TARGETS } from '../lib/targets'
import { istParts, makeFmt } from '../lib/time'
import { CONDITION_LABEL, condition, dayAggregate, type Condition, type WeatherPoint } from '../lib/weather'

const COND_ICON: Record<Condition, LucideIcon> = {
  rain: CloudRain, cloudy: Cloud, partly: CloudSun, 'partly-night': CloudMoon, sunny: Sun, clear: Moon,
}
const COND_ANIM: Record<Condition, string> = {
  rain: 'wx-rain', cloudy: 'wx-cloud', partly: 'wx-cloud', 'partly-night': 'wx-moon', sunny: 'wx-sun', clear: 'wx-moon',
}
const COND_MOOD: Record<Condition, string> = {
  rain: 'wx-mood-rain', cloudy: 'wx-mood-cloudy', partly: 'wx-mood-partly', 'partly-night': 'wx-mood-night',
  sunny: 'wx-mood-sunny', clear: 'wx-mood-night',
}

function CondIcon({ c, size, animate = false }: { c: Condition; size: number; animate?: boolean }) {
  const Icon = COND_ICON[c]
  return (
    <Icon size={size} strokeWidth={size >= 48 ? 1.5 : 1.75} aria-hidden className={`shrink-0 text-ink ${animate ? COND_ANIM[c] : ''}`} />
  )
}

const STATS = ['rh', 'ghi', 'ws10'] as const
const STEP = 68 // hourly cell width 64 px + 4 px gap; the temperature curve uses the same spacing
const dayKey = (ms: number, tz: string) => {
  const { y, m, d } = istParts(ms, tz)
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}
const shortDay = (s: string) => s.split(' ').slice(0, 2).join(' ') // "Wed 11 Nov" -> "Wed 11"
const round1 = (v: number) => Math.round(v * 10) / 10

function dayModelStats(rows: Row[], key: string, tz: string) {
  const day = rows.filter((r) => dayKey(r.t, tz) === key)
  const rh = day.map((r) => r.rh?.p50).filter((v): v is number => v != null)
  const ws = day.map((r) => r.ws10?.p50).filter((v): v is number => v != null)
  return {
    rhAvg: rh.length ? Math.round(rh.reduce((s, v) => s + v, 0) / rh.length) : null,
    wsMax: ws.length ? round1(Math.max(...ws)) : null,
  }
}

/** Smooth line through points (quadratic curves via midpoints). */
function smoothPath(pts: [number, number][]): string {
  if (pts.length < 2) return ''
  let d = `M${pts[0][0]},${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i][0] + pts[i + 1][0]) / 2
    const my = (pts[i][1] + pts[i + 1][1]) / 2
    d += ` Q${pts[i][0]},${pts[i][1]} ${mx},${my}`
  }
  const last = pts[pts.length - 1]
  return `${d} L${last[0]},${last[1]}`
}

function TempCurve({ items, selected }: { items: { p: WeatherPoint; gi: number }[]; selected: number }) {
  const H = 64
  const temps = items.map((x) => x.p.temp)
  const lo = Math.min(...temps)
  const hi = Math.max(...temps)
  const y = (t: number) => (hi === lo ? H / 2 : 10 + (1 - (t - lo) / (hi - lo)) * (H - 30))
  const pts = items.map((x, i) => [i * STEP + 32, y(x.p.temp)] as [number, number])
  return (
    <svg width={items.length * STEP} height={H} aria-hidden className="block overflow-visible">
      {items.map((x, i) =>
        (x.p.precip ?? 0) > 0 ? (
          <rect
            key={`r${x.gi}`}
            x={i * STEP + 22}
            width={20}
            y={H - Math.max(3, Math.min(1, (x.p.precip ?? 0) / 5) * 22)}
            height={Math.max(3, Math.min(1, (x.p.precip ?? 0) / 5) * 22)}
            rx={3}
            fill="var(--hue-rh)"
            opacity={0.45}
          />
        ) : null,
      )}
      <path d={smoothPath(pts)} fill="none" stroke="currentColor" strokeWidth={2} className="text-ink opacity-60" />
      {pts.map(([px, py], i) => (
        <circle
          key={items[i].gi}
          cx={px}
          cy={py}
          r={items[i].gi === selected ? 5 : 3}
          className={items[i].gi === selected ? 'fill-accent' : 'fill-ink opacity-70'}
        />
      ))}
    </svg>
  )
}

function SunArc({ rise, set, frac, fmt }: { rise: number; set: number; frac: number | null; fmt: ReturnType<typeof makeFmt> }) {
  const W = 180
  const R = 70
  const cx = W / 2
  const cy = 80
  const ang = frac == null ? null : Math.PI * (1 - frac)
  return (
    <div className="grid justify-items-center gap-1">
      <svg width={W} height={92} viewBox={`0 0 ${W} 92`} aria-hidden>
        <path d={`M${cx - R},${cy} A${R},${R} 0 0 1 ${cx + R},${cy}`} fill="none" stroke="currentColor" strokeDasharray="4 5" className="text-muted opacity-60" />
        <line x1={cx - R - 8} x2={cx + R + 8} y1={cy} y2={cy} stroke="currentColor" className="text-muted opacity-40" />
        {ang != null && (
          <circle cx={cx + R * Math.cos(ang)} cy={cy - R * Math.sin(ang)} r={8} fill="#F5B53D" stroke="#fff" strokeWidth={2} />
        )}
      </svg>
      <div className="flex w-full justify-between gap-4 text-label text-muted">
        <span className="inline-flex items-center gap-1">
          <Sunrise size={14} strokeWidth={1.75} aria-hidden /> {fmt.hour(rise)}
        </span>
        <span className="inline-flex items-center gap-1">
          {fmt.hour(set)} <Sunset size={14} strokeWidth={1.75} aria-hidden />
        </span>
      </div>
      {frac == null && <span className="text-label text-muted">The sun is down</span>}
    </div>
  )
}

export default function Weather() {
  const site = useSite().data?.site
  const name = site?.name
  const tz = useTz()
  const wq = useWeather()
  const fq = useForecast()
  const [now] = useState(() => Date.now())
  const [selIdx, setSelIdx] = useState<number | null>(null)
  const [selDay, setSelDay] = useState<string | null>(null)

  // same 'Updated' time as the Energy page: last successful refresh, falling back to the forecast run
  const run = useHealth().data?.last_success ?? fq.data?.run_time
  // shortcut: hours with a missing temperature are dropped, so the strip can skip an hour; Open-Meteo rarely nulls temp.
  const points = useMemo(
    () => (wq.data?.points ?? []).filter((p): p is WeatherPoint => p.temp != null),
    [wq.data],
  )
  const rows = useMemo(() => (fq.data ? buildRows(fq.data) : []), [fq.data])
  const allDays = useMemo(() => (tz ? dayAggregate(points, tz) : []), [points, tz])

  let cur = 0
  points.forEach((p, i) => {
    if (Date.parse(p.time) <= now) cur = i
  })
  const fmt = tz ? makeFmt(tz) : undefined
  // the weather window starts at the UTC hour holding IST midnight, so drop any day before today's IST date
  const todayKey = points[cur] && tz ? dayKey(Date.parse(points[cur].time), tz) : undefined
  const days = allDays.filter((d) => todayKey == null || d.dateKey >= todayKey).slice(0, 3)
  const activeDay = selDay ?? todayKey

  // strip: from now for today, the whole IST day for another selected day
  const indexed = points.map((p, gi) => ({ p, gi }))
  const strip =
    !tz || activeDay === todayKey
      ? indexed.slice(cur, cur + 24)
      : indexed.filter((x) => dayKey(Date.parse(x.p.time), tz) === activeDay)
  const ai = selIdx ?? (activeDay === todayKey ? cur : (strip[0]?.gi ?? cur))
  const here = points[ai]
  const hereMs = here ? Date.parse(here.time) : now
  const isNow = ai === cur
  const hereDay = tz && here ? dayKey(hereMs, tz) : undefined
  const hereAgg = allDays.find((d) => d.dateKey === hereDay)
  const hereRow = rows.find((r) => Math.abs(r.t - hereMs) <= 31 * 60e3)

  // sunrise/sunset for the hero's day; the sun dot follows the selected hour
  const sunT = site && here ? sunTimes(hereMs, site.latitude, site.longitude) : null
  const sun = sunT ? { ...sunT, frac: sunFraction(hereMs, sunT.rise, sunT.set) } : null

  const range = days.length
    ? { lo: Math.min(...days.map((d) => d.low)), hi: Math.max(...days.map((d) => d.high)) }
    : { lo: 0, hi: 1 }

  const pickDay = (key: string) => {
    setSelDay(key)
    if (key === todayKey) setSelIdx(null)
    else {
      // jump the hero to that day's midday hour (or its first hour)
      const dayPts = indexed.filter((x) => tz && dayKey(Date.parse(x.p.time), tz) === key)
      const mid = dayPts.find((x) => tz && istParts(Date.parse(x.p.time), tz).hour === 12) ?? dayPts[0]
      setSelIdx(mid ? mid.gi : null)
    }
  }

  const weatherMissing = wq.error instanceof ApiError && wq.error.status === 503
  const c = here ? condition(here.precip, here.cloud, here.is_day) : 'cloudy'

  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title="Weather"
        subtitle={`Next 3 days${name ? ` in ${name}` : ''} · times in IST · tap an hour or a day`}
        secondary={
          fmt && run ? (
            <>
              <Clock size={16} strokeWidth={1.75} aria-hidden />
              Updated {fmt.hour(Date.parse(run))} IST
            </>
          ) : undefined
        }
        primary={{ to: '/', label: 'See energy forecast' }}
      >
        <div className="flex flex-wrap gap-2">
          <SourceTag kind="open-meteo" icon={Cloud} label="Open-Meteo: temperature, cloud, rain" />
          <SourceTag kind="ours" icon={Activity} label="Our forecast: humidity, sunlight, wind speed" />
        </div>
      </PageHeader>

      {/* 1. Hero: shows the selected hour (Now by default), with a mood tint for the sky */}
      <GlassCard ariaLabel="Selected hour weather" className="relative grid gap-6 overflow-hidden p-6! lg:grid-cols-[1fr_auto_auto] lg:p-8!">
        {!weatherMissing && here && <div aria-hidden className={`wx-mood ${COND_MOOD[c]}`} />}
        {weatherMissing ? (
          <StateBlock
            kind="empty"
            title="Weather data missing"
            body="Weather details are not cached yet. They arrive with the next hourly refresh."
          />
        ) : wq.error ? (
          <StateBlock kind="error" onRetry={() => wq.refetch()} />
        ) : !here || !fmt ? (
          <StateBlock kind="loading" />
        ) : (
          <div className="relative flex items-center gap-5">
            <CondIcon c={c} size={64} animate />
            <div className="grid gap-1">
              <span className="text-label font-bold uppercase tracking-[0.08em] text-muted">
                {isNow ? 'Now' : `${shortDay(fmt.day(hereMs))}, ${fmt.hour(hereMs)} IST`}
              </span>
              <p className="m-0 flex items-baseline gap-1 text-ink">
                <span className="text-display font-bold tabular-nums">{Math.round(here.temp)}°</span>
                <span className="text-body text-muted">C</span>
              </p>
              <p className="m-0 text-body font-bold text-ink">{CONDITION_LABEL[c]}</p>
              {hereAgg && (
                <p className="m-0 text-body text-muted">
                  High {Math.round(hereAgg.high)}° · Low {Math.round(hereAgg.low)}°
                </p>
              )}
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <SourceTag kind="open-meteo" />
                {!isNow && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelIdx(null)
                      setSelDay(null)
                    }}
                    className="inline-flex h-7 items-center rounded-full bg-secondary px-3 text-label font-bold text-ink hover:brightness-105"
                  >
                    Back to now
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <ul className="relative m-0 grid list-none content-center gap-3 p-0">
          {STATS.map((key) => {
            const t = TARGETS.find((x) => x.key === key)!
            const v = hereRow?.[key]?.p50
            return (
              <li key={key} className="flex flex-wrap items-center gap-3">
                <IconChip targetKey={key} />
                <span className="min-w-24 text-body text-muted">{t.label}</span>
                <span className="text-body font-bold tabular-nums text-ink">
                  {v == null ? '–' : v.toFixed(t.decimals)} <span className="font-medium text-muted">{t.unit}</span>
                </span>
                <SourceTag kind="ours" />
              </li>
            )
          })}
        </ul>

        {sun && fmt && (
          <div className="relative content-center">
            <SunArc rise={sun.rise} set={sun.set} frac={sun.frac} fmt={fmt} />
          </div>
        )}
      </GlassCard>

      {!weatherMissing && fmt && strip.length > 0 && (
        <>
          {/* 2. Hourly strip with temperature curve and rain bars; tap an hour */}
          <GlassCard ariaLabel="Hourly forecast" className="min-w-0">
            <h2 className="m-0 mb-3 text-body font-bold text-ink">
              {activeDay === todayKey ? 'Next 24 hours' : `Hours on ${shortDay(fmt.day(Date.parse(strip[0].p.time)))}`}
            </h2>
            <div className="overflow-x-auto pb-2">
              <div className="grid gap-1" style={{ width: strip.length * STEP }}>
                <ol className="m-0 flex list-none gap-1 p-0">
                  {strip.map(({ p, gi }) => {
                    const ms = Date.parse(p.time)
                    const hc = condition(p.precip, p.cloud, p.is_day)
                    const sel = gi === ai
                    const label = gi === cur ? 'Now' : fmt.hour(ms)
                    return (
                      <li key={p.time} className="shrink-0">
                        <button
                          type="button"
                          onClick={() => setSelIdx(gi)}
                          aria-pressed={sel}
                          aria-label={`${label}: ${Math.round(p.temp)}°, ${CONDITION_LABEL[hc]}`}
                          className={`grid w-[64px] justify-items-center gap-2 rounded-chip py-2 transition duration-150 hover:-translate-y-0.5 hover:bg-white/30 hover:shadow-[inset_0_1px_0_rgba(255,255,255,.4)] active:scale-95 ${
                            sel ? 'bg-white/25 outline-2 outline-accent' : ''
                          }`}
                        >
                          <span className="text-label text-muted">{label}</span>
                          <CondIcon c={hc} size={20} animate={sel} />
                          <span className="text-body font-bold tabular-nums text-ink">{Math.round(p.temp)}°</span>
                          <span className="h-4 text-label tabular-nums text-muted">
                            {(p.precip ?? 0) > 0 ? `${round1(p.precip!)} mm` : ''}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ol>
                <TempCurve items={strip} selected={ai} />
              </div>
            </div>
            <p className="m-0 mt-2 text-label text-muted">Line: temperature. Blue bars: rain. From Open-Meteo.</p>
          </GlassCard>

          {/* 3. Day cards; tap a day to load its hours */}
          <div className="grid gap-4 lg:grid-cols-3">
            {days.map((d) => {
              const s = tz ? dayModelStats(rows, d.dateKey, tz) : { rhAvg: null, wsMax: null }
              const label = d.dateKey === todayKey ? 'Today' : shortDay(fmt.day(d.firstMs))
              const sel = d.dateKey === activeDay
              const span = range.hi - range.lo || 1
              const left = ((d.low - range.lo) / span) * 100
              const width = Math.max(4, ((d.high - d.low) / span) * 100)
              return (
                <GlassCard
                  key={d.dateKey}
                  ariaLabel={label}
                  className={`p-0! transition duration-200 hover:-translate-y-1 hover:shadow-[0_12px_30px_rgba(4,32,47,.18)] ${sel ? 'outline-2 outline-accent' : ''}`}
                >
                  <button
                    type="button"
                    onClick={() => pickDay(d.dateKey)}
                    aria-pressed={sel}
                    className="grid w-full gap-2 rounded-[inherit] p-4 text-left active:scale-[0.99] lg:p-6"
                  >
                    <h2 className="m-0 text-body font-bold text-ink">{label}</h2>
                    <p className="m-0 flex items-center gap-2 text-body text-ink">
                      <CondIcon c={d.condition} size={20} animate={sel} />
                      {CONDITION_LABEL[d.condition]}
                    </p>
                    <div className="flex items-center gap-3">
                      <span className="w-8 text-body tabular-nums text-muted">{Math.round(d.low)}°</span>
                      <span className="relative h-1.5 flex-1 rounded-full bg-black/10" aria-hidden>
                        <span
                          className="absolute inset-y-0 rounded-full bg-[linear-gradient(90deg,#4F9DFF,#FFB347)]"
                          style={{ left: `${left}%`, width: `${width}%` }}
                        />
                      </span>
                      <span className="w-8 text-right text-body font-bold tabular-nums text-ink">{Math.round(d.high)}°</span>
                    </div>
                    <p className="m-0 text-label tabular-nums text-muted">Rain {round1(d.rainMm)} mm</p>
                    <p className="m-0 text-label text-muted">
                      Humidity {s.rhAvg ?? '–'}% avg · Wind up to {s.wsMax ?? '–'} m/s
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <SourceTag kind="open-meteo" />
                      <SourceTag kind="ours" />
                    </div>
                  </button>
                </GlassCard>
              )
            })}
          </div>
        </>
      )}
    </Stagger>
  )
}
