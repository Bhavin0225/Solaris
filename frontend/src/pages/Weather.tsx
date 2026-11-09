// Weather page (/weather, D-35). Temperature, cloud and rain come from Open-Meteo; humidity, sunlight and
// wind speed are our model's P50. Temperature is never a model target, so it stays --ink (D-34).
import { Activity, Clock, Cloud, CloudMoon, CloudRain, CloudSun, Moon, Sun, type LucideIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ApiError, useForecast, useHealth, useSite, useTz, useWeather } from '../api'
import { GlassCard, IconChip, PageHeader, SourceTag, StateBlock, Stagger } from '../components/ui'
import { buildRows, currentIndex, type Row } from '../lib/forecast'
import { TARGETS } from '../lib/targets'
import { istParts, makeFmt } from '../lib/time'
import { CONDITION_LABEL, condition, dayAggregate, type Condition, type WeatherPoint } from '../lib/weather'

const COND_ICON: Record<Condition, LucideIcon> = {
  rain: CloudRain, cloudy: Cloud, partly: CloudSun, 'partly-night': CloudMoon, sunny: Sun, clear: Moon,
}

function CondIcon({ c, size }: { c: Condition; size: number }) {
  const Icon = COND_ICON[c]
  return <Icon size={size} strokeWidth={size >= 48 ? 1.5 : 1.75} aria-hidden className="shrink-0 text-ink" />
}

const STATS = ['rh', 'ghi', 'ws10'] as const
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

export default function Weather() {
  const name = useSite().data?.site.name
  const tz = useTz()
  const wq = useWeather()
  const fq = useForecast()
  const [now] = useState(() => Date.now())

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
  const here = points[cur]
  const strip = points.slice(cur, cur + 24)
  const curRow = rows.length ? rows[currentIndex(rows, now)] : undefined
  const fmt = tz ? makeFmt(tz) : undefined
  // the weather window starts at the UTC hour holding IST midnight, so drop any day before today's IST date
  const todayKey = here && tz ? dayAggregate([here], tz)[0]?.dateKey : undefined
  const days = allDays.filter((d) => todayKey == null || d.dateKey >= todayKey).slice(0, 3)
  const today = days[0]?.dateKey === todayKey ? days[0] : undefined

  const weatherMissing = wq.error instanceof ApiError && wq.error.status === 503

  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title="Weather"
        subtitle={`Next 3 days${name ? ` in ${name}` : ''} · times in IST`}
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

      {/* 1. Hero */}
      <GlassCard ariaLabel="Current weather" className="grid gap-6 p-6! lg:grid-cols-[1fr_auto] lg:p-8!">
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
          (() => {
            const c = condition(here.precip, here.cloud, here.is_day)
            return (
              <div className="flex items-center gap-5">
                <CondIcon c={c} size={64} />
                <div className="grid gap-1">
                  <p className="m-0 flex items-baseline gap-1 text-ink">
                    <span className="text-display font-bold tabular-nums">{Math.round(here.temp)}°</span>
                    <span className="text-body text-muted">C</span>
                  </p>
                  <p className="m-0 text-body font-bold text-ink">{CONDITION_LABEL[c]}</p>
                  {today && (
                    <p className="m-0 text-body text-muted">
                      High {Math.round(today.high)}° · Low {Math.round(today.low)}°
                    </p>
                  )}
                  <div className="mt-1">
                    <SourceTag kind="open-meteo" />
                  </div>
                </div>
              </div>
            )
          })()
        )}

        <ul className="m-0 grid list-none content-center gap-3 p-0">
          {STATS.map((key) => {
            const t = TARGETS.find((x) => x.key === key)!
            const v = curRow?.[key]?.p50
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
      </GlassCard>

      {!weatherMissing && fmt && strip.length > 0 && (
        <>
          {/* 2. Hourly strip */}
          <GlassCard ariaLabel="Next 24 hours" className="min-w-0">
            <h2 className="m-0 mb-3 text-body font-bold text-ink">Next 24 hours</h2>
            <ol className="m-0 flex list-none snap-x snap-mandatory gap-1 overflow-x-auto p-1 pb-2">
              {strip.map((p, i) => {
                const ms = Date.parse(p.time)
                const c = condition(p.precip, p.cloud, p.is_day)
                return (
                  <li
                    key={p.time}
                    aria-label={`${i === 0 ? 'Now' : fmt.hour(ms)}: ${Math.round(p.temp)}°, ${CONDITION_LABEL[c]}`}
                    className={`grid w-16 shrink-0 snap-start justify-items-center gap-2 rounded-chip py-2 ${
                      i === 0 ? 'outline-2 outline-accent' : ''
                    }`}
                  >
                    <span className="text-label text-muted">{i === 0 ? 'Now' : fmt.hour(ms)}</span>
                    <CondIcon c={c} size={20} />
                    <span className="text-body font-bold tabular-nums text-ink">{Math.round(p.temp)}°</span>
                    {(p.precip ?? 0) > 0 && (
                      <span className="text-label tabular-nums text-muted">{round1(p.precip!)} mm</span>
                    )}
                  </li>
                )
              })}
            </ol>
          </GlassCard>

          {/* 3. Day cards */}
          <div className="grid gap-4 lg:grid-cols-3">
            {days.map((d) => {
              const s = tz ? dayModelStats(rows, d.dateKey, tz) : { rhAvg: null, wsMax: null }
              return (
                <GlassCard key={d.dateKey} ariaLabel={d.dateKey === todayKey ? 'Today' : shortDay(fmt.day(d.firstMs))} className="grid gap-2">
                  <h2 className="m-0 text-body font-bold text-ink">{d.dateKey === todayKey ? 'Today' : shortDay(fmt.day(d.firstMs))}</h2>
                  <p className="m-0 flex items-center gap-2 text-body text-ink">
                    <CondIcon c={d.condition} size={20} />
                    {CONDITION_LABEL[d.condition]}
                  </p>
                  <p className="m-0 text-body font-bold tabular-nums text-ink">
                    {Math.round(d.high)}° / {Math.round(d.low)}°
                  </p>
                  <p className="m-0 text-label tabular-nums text-muted">Rain {round1(d.rainMm)} mm</p>
                  <p className="m-0 text-label text-muted">
                    Humidity {s.rhAvg ?? '–'}% avg · Wind up to {s.wsMax ?? '–'} m/s
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <SourceTag kind="open-meteo" />
                    <SourceTag kind="ours" />
                  </div>
                </GlassCard>
              )
            })}
          </div>
        </>
      )}
    </Stagger>
  )
}
