// Live, theme-aware replacements for the old matplotlib PNGs: physics scatters, quantile reliability, wind CF.
import { useReducedMotion } from 'motion/react'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import { useValidation, type CoverageRow, type WindCfRow } from '../api'
import { modelName, TARGETS } from '../lib/targets'
import { GlassCard, StateBlock } from './ui'

const tick = { fontSize: 12, fill: 'var(--muted)' }
const tip = {
  contentStyle: { background: 'var(--popover-fill)', border: '1px solid var(--card-border)', borderRadius: 12, fontSize: 12 },
  labelStyle: { color: 'var(--muted)' },
}
const kw = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

/** Round axis ticks (steps of 1, 2 or 5 x 10^k) from 0 to just above max. */
function niceTicks(max: number, count = 4): number[] {
  const raw = max / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const out: number[] = []
  for (let v = 0; v <= max + step * 0.999; v += step) out.push(Math.round(v))
  return out
}

function Head({ title, caption }: { title: string; caption: string }) {
  return (
    <div className="mb-3 grid gap-1">
      <h3 className="m-0 text-body font-bold text-ink">{title}</h3>
      <p className="m-0 text-label text-muted">{caption}</p>
    </div>
  )
}

const SCATTERS = [
  { key: 'solar_plant_1', title: 'Solar physics vs Kaggle plant 1', hue: 'var(--scatter-solar)',
    caption: 'Simulated vs metered AC power, hourly, daytime. Dots near the diagonal mean the physics chain is right.' },
  { key: 'solar_plant_2', title: 'Solar physics vs Kaggle plant 2', hue: 'var(--scatter-solar)',
    caption: 'The same check on the second plant (not used for tuning).' },
  { key: 'wind', title: 'Wind power curve vs Kaggle turbine', hue: 'var(--hue-t5_kw)',
    caption: 'Power from the configured power curve vs the turbine’s metered output (10-minute data).' },
] as const

/** The three physics-validation scatters, drawn from a fixed sample of the real points. */
export function PhysicsScatters() {
  const q = useValidation()
  const reduce = useReducedMotion()
  if (q.isPending) return <GlassCard><StateBlock kind="loading" /></GlassCard>
  if (q.error || !q.data) {
    return (
      <GlassCard>
        <StateBlock kind="empty" title="Validation points missing" body="Run python -m swf validate to build them." />
      </GlassCard>
    )
  }
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {SCATTERS.map((sc) => {
        const s = q.data.series[sc.key]
        if (!s) return null
        const data = s.points.map(([sim, act]) => ({ act, sim }))
        const ticks = niceTicks(s.cap_kw)
        const top = ticks[ticks.length - 1]
        return (
          <GlassCard key={sc.key} variant="chart" ariaLabel={sc.title}>
            <Head title={sc.title} caption={sc.caption} />
            <ResponsiveContainer width="100%" height={260}>
              <ScatterChart margin={{ top: 8, right: 12, bottom: 20, left: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis
                  type="number" dataKey="act" name="Actual" domain={[0, top]} ticks={ticks} tick={tick}
                  tickFormatter={(v: number) => kw.format(Math.max(0, v))} axisLine={{ stroke: 'var(--axis)' }} tickLine={false}
                  label={{ value: 'Actual (kW)', position: 'insideBottom', offset: -12, fontSize: 12, fill: 'var(--muted)' }}
                />
                <YAxis
                  type="number" dataKey="sim" name="Simulated" domain={[0, top]} ticks={ticks} tick={tick} width={68}
                  tickFormatter={(v: number) => kw.format(Math.max(0, v))} axisLine={false} tickLine={false}
                  label={{ value: 'Simulated (kW)', angle: -90, position: 'insideLeft', offset: 0, dy: 40, fontSize: 12, fill: 'var(--muted)' }}
                />
                <ReferenceLine
                  segment={[{ x: 0, y: 0 }, { x: top, y: top }]}
                  stroke="var(--ink)" strokeOpacity={0.5} strokeDasharray="5 4"
                />
                <Tooltip {...tip} cursor={{ strokeDasharray: '3 3' }} formatter={(v) => `${kw.format(v as number)} kW`} />
                <Scatter data={data} fill={sc.hue} fillOpacity={0.35} shape="circle" isAnimationActive={!reduce} />
              </ScatterChart>
            </ResponsiveContainer>
            <p className="m-0 mt-1 text-label text-muted">
              {kw.format(s.points.length)} of {kw.format(s.n_total)} points shown · dashed line = perfect match
            </p>
          </GlassCard>
        )
      })}
    </div>
  )
}

/** Quantile reliability for the served model: observed share below each quantile vs the nominal level. */
export function ReliabilityCard({ coverage, served }: { coverage: CoverageRow[]; served: (key: string) => string }) {
  const reduce = useReducedMotion()
  const levels = [0.1, 0.5, 0.9]
  const data = levels.map((lvl) => {
    const row: Record<string, number | null> = { lvl, ideal: lvl }
    for (const t of TARGETS) {
      const r = coverage.find((c) => c.target === t.key && c.model === served(t.key))
      row[t.key] = r ? (lvl === 0.1 ? r.rel_q10 : lvl === 0.5 ? r.rel_q50 : r.rel_q90) : null
    }
    return row
  })
  return (
    <GlassCard variant="chart" ariaLabel="Quantile reliability">
      <Head
        title="Quantile reliability (test 2025)"
        caption="How often the true value fell below each forecast quantile (P10, P50, P90). On the dashed diagonal = perfectly calibrated."
      />
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
          <XAxis
            dataKey="lvl" type="number" domain={[0, 1]} ticks={[0, 0.1, 0.5, 0.9, 1]} tick={tick}
            tickFormatter={(v: number) => (v === 0.1 ? 'P10' : v === 0.5 ? 'P50' : v === 0.9 ? 'P90' : `${v}`)}
            axisLine={{ stroke: 'var(--axis)' }} tickLine={false}
            label={{ value: 'Forecast quantile', position: 'insideBottom', offset: -12, fontSize: 12, fill: 'var(--muted)' }}
          />
          <YAxis
            type="number" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tick={tick} width={44}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`} axisLine={false} tickLine={false}
          />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--ink)" strokeOpacity={0.5} strokeDasharray="5 4" />
          <Tooltip {...tip} labelFormatter={(v) => `Nominal ${Math.round((v as number) * 100)}%`} formatter={(v) => `${Math.round((v as number) * 100)}% below`} />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
          {TARGETS.map((t) => (
            <Line
              key={t.key} name={t.short} dataKey={t.key} stroke={t.hue} strokeWidth={2}
              dot={{ r: 4, fill: t.hue, strokeWidth: 0 }} isAnimationActive={!reduce}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </GlassCard>
  )
}

const SEASON_LABEL: Record<string, string> = { all: 'Whole year', monsoon: 'Monsoon', dry: 'Dry season' }

/** Wind capacity factor by season: observed vs the served model vs baseline 3. */
export function WindCfChart({ rows, servedModel, caption }: { rows: WindCfRow[]; servedModel: string; caption: string }) {
  const reduce = useReducedMotion()
  const data = ['all', 'monsoon', 'dry'].map((season) => {
    const m = (model: string) => rows.find((r) => r.season === season && r.model === model)
    const srv = m(servedModel)
    return {
      season: SEASON_LABEL[season],
      observed: srv?.observed_cf ?? m('baseline3')?.observed_cf ?? null,
      served: srv?.predicted_cf ?? null,
      baseline: m('baseline3')?.predicted_cf ?? null,
    }
  })
  const pct = (v: unknown) => (v == null ? '–' : `${Math.round((v as number) * 1000) / 10}%`)
  return (
    <GlassCard variant="chart" ariaLabel="Wind capacity factor by season">
      <Head title="Wind capacity factor by season" caption={caption} />
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barGap={4}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--grid)" />
          <XAxis dataKey="season" tick={tick} axisLine={{ stroke: 'var(--axis)' }} tickLine={false} />
          <YAxis tick={tick} width={44} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
          <Tooltip {...tip} formatter={(v) => pct(v)} cursor={{ fill: 'var(--grid)' }} />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <Bar name="Observed (simulated truth)" dataKey="observed" fill="var(--ink)" fillOpacity={0.7} radius={[6, 6, 0, 0]} isAnimationActive={!reduce} />
          <Bar name={`${modelName(servedModel)} forecast`} dataKey="served" fill="var(--hue-t5_kw)" radius={[6, 6, 0, 0]} isAnimationActive={!reduce} />
          <Bar name="Baseline 3" dataKey="baseline" fill="var(--hue-baseline)" radius={[6, 6, 0, 0]} isAnimationActive={!reduce} />
        </BarChart>
      </ResponsiveContainer>
    </GlassCard>
  )
}
