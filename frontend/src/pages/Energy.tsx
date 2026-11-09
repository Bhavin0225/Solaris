// Energy page (/): target cards, synchronized 72 h chart, daily totals, correlation (D-33, UI-01..UI-05).
import { Clock, Thermometer } from 'lucide-react'
import { motion } from 'motion/react'
import { useMemo, useState, type ReactNode } from 'react'
import { Cell, Line, LineChart, Pie, PieChart } from 'recharts'
import {
  ApiError, useCorrelation, useForecast, useHealth, useSite, useSummary, useTz, useWeather, type Forecast,
} from '../api'
import { CountUp } from '../components/CountUp'
import { ForecastChart, fmtNum, useIsLg, useNow } from '../components/ForecastPanel'
import { MatrixGrid } from '../components/MatrixGrid'
import { Segmented } from '../components/Segmented'
import {
  GlassCard, IconChip, ModelBadge, PageHeader, SimulatedTag, SourceTag, StaleBanner, Stagger, StateBlock, useItemVariants,
} from '../components/ui'
import { corrSentences } from '../lib/corr'
import { buildRows, currentIndex, type Row } from '../lib/forecast'
import { TARGETS, type Target } from '../lib/targets'
import { greeting, istParts, makeFmt, type Fmt } from '../lib/time'
import { condition, CONDITION_LABEL } from '../lib/weather'

const plain = (t: Target) => t.label.replace(/ \(.*\)$/, '') // "Sunlight (GHI)" -> "Sunlight"

function TempChip({ now }: { now: number }) {
  const w = useWeather().data
  if (!w || w.points.length === 0) return null // hidden while missing (503) or loading
  // Same rule as the forecast: last point at or before now, else the first.
  let p = w.points[0]
  for (const q of w.points) if (Date.parse(q.time) <= now) p = q
  if (p.temp == null) return null
  return (
    // D-34: temperature is Open-Meteo's, never ours, so --ink and never a target colour.
    <span className="inline-flex flex-wrap items-center gap-2 justify-self-start rounded-full bg-secondary py-1 pl-3 pr-1 text-body font-medium text-ink">
      <Thermometer size={16} strokeWidth={1.75} aria-hidden />
      {Math.round(p.temp)} °C · {CONDITION_LABEL[condition(p.precip, p.cloud, p.is_day)]}
      <SourceTag kind="open-meteo" />
    </span>
  )
}

function TargetCard({ t, rows, idx, model }: { t: Target; rows: Row[]; idx: number; model: string }) {
  const c = rows[idx]?.[t.key]
  return (
    <GlassCard className="grid content-start gap-3 last:col-span-2 lg:last:col-span-1">
      <div className="flex items-start justify-between gap-2">
        <IconChip targetKey={t.key} />
        <ModelBadge targetKey={t.key} runtime={model} />
      </div>
      <div className="grid gap-1">
        <p className="m-0 tabular-nums text-heading font-bold text-ink">
          <CountUp value={c?.p50 ?? null} decimals={t.decimals} />
          <span className="ml-1 text-body font-medium text-muted">{t.unit}</span>
        </p>
        <h2 className="m-0 text-body font-bold text-ink">{t.label}</h2>
        <p className="m-0 text-label text-muted">
          P10–P90 {fmtNum(c?.p10, t.decimals)}–{fmtNum(c?.p90, t.decimals)} {t.unit}
        </p>
      </div>
      {t.simulated && (
        <span>
          <SimulatedTag />
        </span>
      )}
      <LineChart data={rows} responsive style={{ width: '100%', height: 40 }} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <Line
          dataKey={(r: Row) => r[t.key]?.p50 ?? null}
          stroke={t.hue}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </GlassCard>
  )
}

function Cards({ fc, now }: { fc: Forecast; now: number }) {
  const rows = useMemo(() => buildRows(fc), [fc])
  const idx = currentIndex(rows, now) // Pitfall 8: stale runs start in the past
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
      {TARGETS.filter((t) => fc.targets[t.key]).map((t) => (
        <TargetCard key={t.key} t={t} rows={rows} idx={idx} model={fc.targets[t.key].model} />
      ))}
    </div>
  )
}

function Kpi({ title, value, unit, sub, tag }: { title: string; value: ReactNode; unit: string; sub?: string; tag?: boolean }) {
  return (
    <GlassCard className="grid content-start gap-2">
      <h3 className="m-0 text-label font-bold text-muted">{title}</h3>
      <p className="m-0 tabular-nums text-heading font-bold text-ink">
        {value}
        <span className="ml-1 text-body font-medium text-muted">{unit}</span>
      </p>
      {sub && <p className="m-0 text-label text-muted">{sub}</p>}
      {tag && (
        <span>
          <SimulatedTag />
        </span>
      )}
    </GlassCard>
  )
}

const SOLAR = TARGETS[0]
const WIND = TARGETS[1]

function DailyTotals({ fc, fmt }: { fc: Forecast | undefined; fmt: Fmt }) {
  const [day, setDay] = useState<'today' | 'tomorrow'>('tomorrow')
  const q = useSummary(day)
  const s = q.data
  const rows = useMemo(() => (fc ? buildRows(fc) : []), [fc])
  const variants = useItemVariants()

  let body
  if (q.isPending) body = <GlassCard><StateBlock kind="loading" /></GlassCard>
  else if (q.error) {
    body = (
      <GlassCard>
        {q.error instanceof ApiError && q.error.status === 503 ? (
          <StateBlock kind="empty" />
        ) : (
          <StateBlock kind="error" onRetry={() => q.refetch()} />
        )}
      </GlassCard>
    )
  } else if (s) {
    const peakMs = s.peak_hour ? Date.parse(s.peak_hour) : null
    const peakKw = peakMs == null ? null : (rows.find((r) => r.t === peakMs)?.t1_kw?.p50 ?? null)
    const total = s.solar_kwh + s.wind_kwh
    const pct = (v: number) => (total > 0 ? Math.round((v / total) * 100) : 0)
    const parts = [
      { t: SOLAR, name: 'Solar', v: s.solar_kwh },
      { t: WIND, name: 'Wind', v: s.wind_kwh },
    ]
    body = (
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="grid grid-cols-2 gap-4 lg:col-span-2 lg:grid-cols-3">
          <Kpi title="Solar energy" value={fmtNum(s.solar_kwh, 0)} unit="kWh" tag />
          <Kpi title="Wind energy" value={fmtNum(s.wind_kwh, 0)} unit="kWh" tag />
          <Kpi
            title="Peak solar hour"
            value={peakMs == null ? '–' : fmt.hour(peakMs)}
            unit="IST"
            sub={`${fmtNum(peakKw, 0)} kW at peak`}
          />
        </div>
        <GlassCard className="grid gap-3" ariaLabel={`Combined energy ${fmtNum(total, 0)} kWh`}>
          <h3 className="m-0 text-label font-bold text-muted">Combined energy</h3>
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative size-44 shrink-0">
              <PieChart responsive style={{ width: '100%', height: '100%' }}>
                <Pie
                  data={parts}
                  dataKey="v"
                  nameKey="name"
                  innerRadius="80%"
                  outerRadius="100%"
                  startAngle={90}
                  endAngle={-270}
                  paddingAngle={total > 0 && s.solar_kwh > 0 && s.wind_kwh > 0 ? 3 : 0}
                  stroke="none"
                  animationDuration={800}
                  animationEasing="ease-out"
                >
                  {parts.map((p) => (
                    <Cell key={p.name} fill={p.t.hue} />
                  ))}
                </Pie>
              </PieChart>
              <div className="pointer-events-none absolute inset-0 grid place-content-center text-center">
                <CountUp value={total} className="tabular-nums text-heading font-bold text-ink" />
                <span className="text-label text-muted">kWh</span>
              </div>
            </div>
            <ul className="m-0 grid list-none gap-2 p-0 text-label">
              {parts.map((p) => (
                <li key={p.name} className="flex items-center gap-2 text-ink">
                  <span aria-hidden className="size-2 rounded-full" style={{ background: p.t.hue }} />
                  <span className="font-bold">{p.name}</span>
                  <span className="tabular-nums">{fmtNum(p.v, 0)} kWh</span>
                  <span className="tabular-nums text-muted">{pct(p.v)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </GlassCard>
      </div>
    )
  }

  const caption = s
    ? day === 'today'
      ? `Rest of today, from ${fmt.hour(Date.parse(s.window_start))} IST`
      : `${fmt.day(Date.parse(s.window_start) + 3600e3)}, IST day`
    : day === 'today' ? 'Rest of today' : 'Tomorrow'
  return (
    <section className="grid gap-4" aria-label="Daily totals">
      <motion.div variants={variants} className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 text-body font-bold text-ink">Daily totals</h2>
        <Segmented
          options={[{ value: 'today', label: 'Today' }, { value: 'tomorrow', label: 'Tomorrow' }]}
          value={day}
          onChange={setDay}
          label="Day"
          size="sm"
        />
        <span className="text-label text-muted-glass">{caption}</span>
      </motion.div>
      {body}
    </section>
  )
}

function CorrelationCard() {
  const c = useCorrelation().data
  const lg = useIsLg()
  if (!c) return null // static extra; nothing to show until it loads
  const byKey = new Map(TARGETS.map((t) => [t.key, t]))
  const short = c.targets.map((k) => byKey.get(k)?.short ?? k)
  const labels = Object.fromEntries(TARGETS.map((t) => [t.key, plain(t)]))
  const sentences = corrSentences(c.targets, c.matrix, labels)
  const span = `${c.period_start.slice(0, 4)}–${c.period_end.slice(0, 4)}`
  return (
    <GlassCard variant="chart" className="grid gap-4" ariaLabel="How the five targets move together">
      <div className="grid gap-1">
        <h2 className="m-0 text-body font-bold text-ink">How the five targets move together</h2>
        <p className="m-0 text-label text-muted">Pearson correlation of hourly values, {span}. Darker = stronger.</p>
      </div>
      <div className="flex flex-wrap items-start gap-6">
        <div className="max-w-full overflow-x-auto">
          <MatrixGrid
            rowLabels={short}
            colLabels={short}
            values={c.matrix}
            cellSize={lg ? 56 : 48}
            diagonalMuted
            label={`Correlation matrix, ${span}`}
            colorFor={(r) => ({
              bg: r >= 0 ? 'var(--corr-pos)' : 'var(--corr-neg)',
              opacity: Math.abs(r) * 0.85,
              text: Math.abs(r) > 0.5 ? 'light-dark(#ffffff, #04202f)' : 'var(--ink)',
            })}
          />
        </div>
        {sentences.length > 0 && (
          <ul className="m-0 grid max-w-[60ch] flex-1 basis-72 list-disc gap-2 pl-5 text-body text-ink">
            {sentences.map((s) => (
              <li key={`${s.a}-${s.b}`}>{s.text}</li>
            ))}
          </ul>
        )}
      </div>
    </GlassCard>
  )
}

export default function Energy() {
  const name = useSite().data?.site.name
  const tz = useTz()
  const fq = useForecast()
  const health = useHealth().data
  const now = useNow()
  const [greetAt] = useState(() => Date.now()) // greeting fixed per page visit
  const fmt = tz ? makeFmt(tz) : null
  const fc = fq.data
  const updated = health?.last_success ?? fc?.run_time ?? null

  let main
  if (fq.isPending || !fmt || !tz) {
    main = (
      <GlassCard>
        <StateBlock kind="loading" rows={4} />
      </GlassCard>
    )
  } else if (fq.error) {
    main = (
      <GlassCard>
        {fq.error instanceof ApiError && fq.error.status === 503 ? (
          <StateBlock kind="empty" />
        ) : (
          <StateBlock kind="error" onRetry={() => fq.refetch()} />
        )}
      </GlassCard>
    )
  } else {
    main = (
      <>
        <Cards fc={fq.data} now={now} />
        <ForecastChart forecast={fq.data} tz={tz} />
      </>
    )
  }

  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title={tz && name ? `${greeting(istParts(greetAt, tz).hour)}, ${name}` : 'Energy forecast'}
        subtitle={`${fmt ? `${fmt.longDate(greetAt)} · ` : ''}72-hour forecast, refreshed every hour`}
        secondary={
          fmt && updated ? (
            <>
              <Clock size={16} strokeWidth={1.75} aria-hidden />
              Updated {fmt.hour(Date.parse(updated))} IST
            </>
          ) : undefined
        }
        primary={{ to: '/performance', label: 'See model accuracy' }}
      >
        <TempChip now={now} />
      </PageHeader>
      {fc?.stale && <StaleBanner ageMinutes={health?.age_minutes ?? fc.age_minutes} lastSuccess={health?.last_success ?? null} />}
      {main}
      {fmt && <DailyTotals fc={fc} fmt={fmt} />}
      <CorrelationCard />
    </Stagger>
  )
}
