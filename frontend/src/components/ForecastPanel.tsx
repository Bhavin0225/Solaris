// 72 h forecast chart: one Recharts panel per target, all sharing ONE rows slice and syncId (UI-01).
import { useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, Tooltip, XAxis, YAxis, type TooltipContentProps } from 'recharts'
import { buildRows, peakOf, sliceHours, type Forecast, type Row } from '../lib/forecast'
import { TARGETS, type Target } from '../lib/targets'
import { istMidnights, istTicks, makeFmt, type Fmt } from '../lib/time'
import { Segmented } from './Segmented'
import { GlassCard, ModelBadge, SimulatedTag, TargetIcon } from './ui'

const LG = '(min-width: 1024px)'
const subscribe = (cb: () => void) => {
  const m = window.matchMedia(LG)
  m.addEventListener('change', cb)
  return () => m.removeEventListener('change', cb)
}
/** True at the single `lg` breakpoint (>= 1024 px). */
export function useIsLg(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(LG).matches)
}

/** Wall clock in ms, re-read every minute so the "Now" line and current hour move on a long-open page. */
export function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60e3)
    return () => clearInterval(id)
  }, [])
  return now
}

const nf = new Map<number, Intl.NumberFormat>()
export function fmtNum(v: number | null | undefined, decimals: number): string {
  if (v == null || !Number.isFinite(v)) return '–'
  let f = nf.get(decimals)
  if (!f) {
    f = new Intl.NumberFormat('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    nf.set(decimals, f)
  }
  return f.format(v)
}

function PanelTip({ active, payload, target, fmt }: TooltipContentProps<number, string> & { target: Target; fmt: Fmt }) {
  const row = payload?.[0]?.payload as Row | undefined
  if (!active || !row) return null
  const c = row[target.key]
  return (
    <div className="popover grid gap-1 rounded-chip px-3 py-2 text-label">
      <span className="text-muted">{fmt.dayTime(row.t)} IST</span>
      <span className="flex items-center gap-2 text-ink">
        <span aria-hidden className="size-2 rounded-full" style={{ background: target.hue }} />
        {target.label}
        <span className="text-body font-bold">
          {fmtNum(c?.p50, target.decimals)} {target.unit}
        </span>
      </span>
      <span className="text-muted">
        P10–P90 {fmtNum(c?.p10, target.decimals)}–{fmtNum(c?.p90, target.decimals)}
      </span>
    </div>
  )
}

export function ForecastPanel({
  rows, target, height, showX, showY, showLabels, ticks, midnights, nowMs, fmt, animate,
}: {
  rows: Row[]
  target: Target
  height: number
  showX: boolean
  showY: boolean
  showLabels: boolean
  ticks: number[]
  midnights: number[]
  nowMs: number | null
  fmt: Fmt
  animate: boolean
}) {
  const k = target.key
  const label = (value: string) => (showLabels ? { value, position: 'insideTopLeft' as const, fontSize: 12, fill: 'var(--muted)' } : undefined)
  return (
    <ComposedChart
      data={rows}
      syncId="forecast"
      responsive
      style={{ width: '100%', height }}
      margin={{ top: showLabels ? 16 : 4, right: 8, bottom: 0, left: showY ? 0 : 8 }}
    >
      <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--grid)" />
      <XAxis
        dataKey="t"
        type="number"
        scale="time"
        domain={['dataMin', 'dataMax']}
        ticks={ticks}
        tickFormatter={(t: number) => fmt.hourShort(t)}
        hide={!showX}
        tick={{ fontSize: 12, fill: 'var(--muted)' }}
        stroke="var(--grid)"
      />
      <YAxis hide={!showY} tickCount={4} width={44} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: 'var(--muted)' }} />
      {midnights.map((m) => (
        <ReferenceLine key={m} x={m} stroke="var(--grid)" strokeWidth={1} label={label(fmt.day(m).split(' ').slice(0, 2).join(' '))} />
      ))}
      {nowMs != null && (
        <ReferenceLine
          x={nowMs}
          stroke="var(--accent)"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          label={showLabels ? { value: 'Now', position: 'insideTopLeft', fontSize: 12, fill: 'var(--accent)' } : undefined}
        />
      )}
      <Area
        dataKey={(r: Row) => r[k]?.band ?? null}
        stroke="none"
        fill={target.hue}
        fillOpacity="var(--band-opacity)"
        isAnimationActive={animate}
        animationDuration={600}
        animationEasing="ease-out"
        activeDot={false}
      />
      <Line
        dataKey={(r: Row) => r[k]?.p50 ?? null}
        stroke={target.hue}
        strokeWidth={2}
        dot={false}
        activeDot={{ r: 4, fill: target.hue, stroke: 'var(--card)', strokeWidth: 2 }}
        isAnimationActive={animate}
        animationDuration={600}
        animationEasing="ease-out"
      />
      {/* Every synced panel needs its own Tooltip to show the cursor and active dot (Pitfall 6). */}
      <Tooltip
        content={(p) => <PanelTip {...(p as TooltipContentProps<number, string>)} target={target} fmt={fmt} />}
        cursor={{ stroke: 'var(--grid)' }}
        isAnimationActive={false}
      />
    </ComposedChart>
  )
}

export function chartSentence(rows: Row[], t: Target, hours: number, fmt: Fmt): string {
  const pk = peakOf(rows, t.key)
  const peak = pk ? `, peak ${fmtNum(pk.p50, t.decimals)} ${t.unit} at ${fmt.hour(pk.t)} IST` : ''
  return `${t.label} forecast, next ${hours} hours${peak}`
}

type Hours = '24' | '48' | '72'
const HOURS = [
  { value: '24' as Hours, label: '24h' },
  { value: '48' as Hours, label: '48h' },
  { value: '72' as Hours, label: '72h' },
]
const SHORT: Record<string, string> = { t1_kw: 'Solar', t5_kw: 'Wind', ghi: 'Sunlight', rh: 'Humidity', ws10: 'Wind speed' }
const VIEWS = [{ value: 'all', label: 'All' }, ...TARGETS.map((t) => ({ value: t.key, label: SHORT[t.key] }))]

export function ForecastChart({ forecast, tz }: { forecast: Forecast; tz: string }) {
  const [hours, setHours] = useState<Hours>('72')
  const [view, setView] = useState('all')
  const lg = useIsLg()
  const now = useNow()
  const reduce = useReducedMotion()
  // Line/band mount animation on first render only; toggles and resizes redraw instantly.
  const [first, setFirst] = useState(true)
  useEffect(() => {
    const id = setTimeout(() => setFirst(false), 700)
    return () => clearTimeout(id)
  }, [])
  const animate = first && !reduce

  const fmt = makeFmt(tz)
  const all = useMemo(() => buildRows(forecast), [forecast])
  const rows = useMemo(() => sliceHours(all, Number(hours)), [all, hours])
  const start = rows[0]?.t ?? 0
  const end = rows.at(-1)?.t ?? 0
  const ticks = useMemo(() => istTicks(start, end, tz), [start, end, tz])
  const midnights = useMemo(() => istMidnights(start, end, tz), [start, end, tz])
  const nowMs = rows.length ? Math.min(Math.max(now, start), end) : null

  const shown = view === 'all' ? TARGETS.filter((t) => forecast.targets[t.key]) : TARGETS.filter((t) => t.key === view)
  const single = view !== 'all'
  const common = { rows, ticks, midnights, nowMs, fmt, animate }

  return (
    <GlassCard variant="chart" ariaLabel="72-hour forecast" className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="m-0 text-body font-bold text-ink">72-hour forecast</h2>
          <p className="m-0 text-label text-muted">Middle line is the P50; shaded band is P10–P90 · times in IST</p>
        </div>
        <div className="flex max-w-full flex-wrap gap-2">
          <Segmented options={HOURS} value={hours} onChange={setHours} label="Forecast length" size="sm" />
          <Segmented options={VIEWS} value={view} onChange={setView} label="Target" size="sm" scrollable />
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="m-0 text-body text-muted">No forecast points.</p>
      ) : (
        <div className="grid gap-2">
          {shown.map((t, i) => (
            <div key={t.key} className="grid gap-1">
              <div className="flex flex-wrap items-center gap-2 text-label">
                <span style={{ color: t.hue }} className="inline-flex">
                  <TargetIcon targetKey={t.key} />
                </span>
                <span className="font-bold text-ink">{t.label}</span>
                <span className="text-muted">{t.unit}</span>
                <ModelBadge targetKey={t.key} runtime={forecast.targets[t.key]?.model ?? ''} />
                {t.simulated && <SimulatedTag />}
              </div>
              <div role="img" aria-label={chartSentence(rows, t, Number(hours), fmt)}>
                <ForecastPanel
                  {...common}
                  target={t}
                  height={single ? (lg ? 320 : 240) : lg ? 120 : 100}
                  showX={i === shown.length - 1}
                  showY={single}
                  showLabels={i === 0}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  )
}
