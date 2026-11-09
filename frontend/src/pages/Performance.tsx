// Performance page (/performance): the honest test-year results. Every number comes from the API.
import { TriangleExclamationPoint } from 'lucide-react'
import { useReducedMotion } from 'motion/react'
import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, Rectangle, ReferenceLine, ResponsiveContainer, Tooltip, XAxis,
  YAxis, type BarShapeProps,
} from 'recharts'
import { useBuild, useForecast, useMetrics, usePerformance, type MetricsRow } from '../api'
import { CountUp } from '../components/CountUp'
import { MatrixGrid } from '../components/MatrixGrid'
import { Ring } from '../components/Ring'
import { Segmented } from '../components/Segmented'
import { FigureCard, GlassCard, IconChip, ModelBadge, PageHeader, StateBlock, Stagger } from '../components/ui'
import { modelName, TARGETS } from '../lib/targets'

const NOMINAL = 0.8 // a P10-P90 band should hold the truth 80% of the time
const LESS_RELIABLE = new Set(['ws10', 't5_kw'])
const f1 = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const num = (v: number | null | undefined) => (v == null ? '–' : f1.format(v))
const signedPct = (s: number | null | undefined) => (s == null ? '–' : `${s > 0 ? '+' : ''}${f1.format(s * 100)}%`)
const pct0 = (c: number | null | undefined) => (c == null ? '–' : `${Math.round(c * 100)}`)
const tick = { fontSize: 12, fill: 'var(--muted)' }
const HORIZONS = [1, 6, 24, 48, 72]
const SEG_LABEL: Record<string, string> = { t1_kw: 'Solar', t5_kw: 'Wind', ghi: 'Sunlight', rh: 'Humidity', ws10: 'Wind speed' }
const SEASONS = [
  { value: 'all', label: 'All year' },
  { value: 'monsoon', label: 'Monsoon' },
  { value: 'dry', label: 'Dry' },
] as const
type Season = (typeof SEASONS)[number]['value']
const signColor = (s: number | null | undefined) =>
  s == null || s === 0 ? 'text-muted' : s > 0 ? 'text-positive' : 'text-negative'
// Literal allowlist (T-07-19); the server allowlist is the real control.
const FIGURES = [
  {
    name: 'solar_plant_1_scatter',
    title: 'Solar physics vs Kaggle plant 1',
    caption: 'Simulated vs metered AC power, hourly. Points near the diagonal mean the physics chain is right.',
    alt: 'Scatter of simulated against metered solar AC power for Kaggle plant 1, clustered along the diagonal',
  },
  {
    name: 'solar_plant_2_scatter',
    title: 'Solar physics vs Kaggle plant 2',
    caption: 'The same check on the second plant.',
    alt: 'Scatter of simulated against metered solar AC power for Kaggle plant 2',
  },
  {
    name: 'wind_scatter',
    title: 'Wind power curve vs Kaggle turbine',
    caption: 'Power from the configured power curve vs the turbine’s metered output.',
    alt: 'Scatter of power-curve wind output against metered turbine output',
  },
  {
    name: 'reliability_test',
    title: 'Quantile reliability (test 2025)',
    caption: 'How often the truth fell below each forecast quantile; the diagonal is perfect calibration.',
    alt: 'Reliability diagram of observed against nominal quantile frequency per target on the 2025 test year',
  },
]

function CardHead({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="grid gap-1">
        <h2 className="m-0 text-body font-bold text-ink">{title}</h2>
        {subtitle && <p className="m-0 text-label text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

function SkillBadge({ skill }: { skill: number | null | undefined }) {
  if (skill == null) return null
  const win = skill > 0
  return (
    <span
      className={`inline-flex h-6 items-center whitespace-nowrap rounded-full px-2.5 text-label font-bold ${
        win ? 'bg-positive/12 text-[#0B6B49] dark:text-[#6EE7B7]' : 'bg-negative/12 text-[#B42318] dark:text-[#FCA5A5]'
      }`}
    >
      {win ? 'Beats baseline' : 'Baseline wins'}
    </span>
  )
}

export default function Performance() {
  const reduce = useReducedMotion()
  const location = useLocation()
  const [hTarget, setHTarget] = useState('t1_kw')
  const [season, setSeason] = useState<Season>('all')
  const metrics = useMetrics()
  const loaded = metrics.data != null

  // The router does not scroll to #target-{key}; do it once the sections exist (Pitfall 7).
  useEffect(() => {
    if (location.hash && loaded) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: 'start' })
  }, [location.hash, loaded])

  const perf = usePerformance().data
  const build = useBuild().data
  const fc = useForecast().data
  const served = (key: string): string | undefined => build?.models[key] ?? fc?.targets[key]?.model
  const test = (metrics.data?.rows ?? []).filter((r) => r.split === 'test')
  const row = (key: string, model: string | undefined): MetricsRow | undefined =>
    test.find((r) => r.target === key && r.model === model)
  const cov = (key: string) => perf?.coverage.find((c) => c.target === key && c.model === served(key))?.coverage ?? null

  const header = (
    <PageHeader
      title="Model performance"
      subtitle="Test year 2025, scored once. Skill = how much lower the RMSE is than baseline 3 (Open-Meteo + physics)."
      secondary="Test split · 2025"
      primary={{ to: '/about', label: 'Read the method' }}
    />
  )

  if (metrics.isPending || metrics.error) {
    return (
      <Stagger className="grid gap-6">
        {header}
        <GlassCard>
          {metrics.error ? <StateBlock kind="error" onRetry={() => metrics.refetch()} /> : <StateBlock kind="loading" rows={5} />}
        </GlassCard>
      </Stagger>
    )
  }

  if (test.length === 0) {
    return (
      <Stagger className="grid gap-6">
        {header}
        <GlassCard>
          <StateBlock
            kind="empty"
            title="No evaluation results found"
            body="Run python -m swf evaluate to create reports/evaluation/leaderboard.csv, then reload."
          />
        </GlassCard>
      </Stagger>
    )
  }

  const hServed = served(hTarget)
  const hHue = TARGETS.find((t) => t.key === hTarget)?.hue
  const hRow = (model: string | undefined, h: number) =>
    perf?.horizon.find((r) => r.target === hTarget && r.model === model && r.horizon === h)?.nrmse_pct ?? null
  const horizon = HORIZONS.map((h) => ({ h: `${h} h`, served: hRow(hServed, h), base: hRow('baseline3', h) }))

  // Leaderboard: TARGETS order; served row first, the rest by RMSE ascending (nulls last).
  const board = TARGETS.map((t) => {
    const runtime = served(t.key)
    const rows = test
      .filter((r) => r.target === t.key)
      .sort((a, b) => Number(b.model === runtime) - Number(a.model === runtime) || (a.rmse ?? Infinity) - (b.rmse ?? Infinity))
    return { t, runtime, rows }
  })

  const heat = TARGETS.map((t) =>
    HORIZONS.map(
      (h) =>
        perf?.heatmap.find((r) => r.target === t.key && r.model === served(t.key) && r.season === season && r.horizon === h)
          ?.skill_vs_baseline3 ?? null,
    ),
  )

  const bars = TARGETS.map((t) => ({ label: t.label, hue: t.hue, skill: row(t.key, served(t.key))?.skill_vs_baseline3 ?? null }))
    .map((b) => ({ ...b, value: b.skill == null ? null : b.skill * 100 }))

  return (
    <Stagger className="grid gap-6">
      {header}

      {/* 1. Skill cards: each is the #target-{key} anchor for ModelBadge links. */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
        {TARGETS.map((t, i) => {
          const runtime = served(t.key)
          const s = row(t.key, runtime)
          const b3 = row(t.key, 'baseline3')
          const skill = s?.skill_vs_baseline3
          return (
            <GlassCard
              key={t.key}
              id={`target-${t.key}`}
              ariaLabel={`${t.label} skill`}
              className={`grid scroll-mt-4 content-start gap-3 ${i === TARGETS.length - 1 ? 'col-span-2 lg:col-span-1' : ''}`}
            >
              <div className="flex items-start justify-between gap-2">
                <IconChip targetKey={t.key} />
                <SkillBadge skill={skill} />
              </div>
              <p className="m-0 text-heading font-bold text-ink">
                {skill != null && skill > 0 ? '+' : ''}
                <CountUp value={skill == null ? null : skill * 100} decimals={1} />
                {skill != null && '%'}
              </p>
              <div className="grid gap-1">
                <span className="text-body font-bold text-ink">{t.label}</span>
                <span className="text-label text-muted">
                  RMSE {num(s?.rmse)} vs {num(b3?.rmse)} {t.unit}
                </span>
              </div>
              {runtime && (
                <div>
                  <ModelBadge targetKey={t.key} runtime={runtime} />
                </div>
              )}
            </GlassCard>
          )
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* 2. Skill vs baseline bars */}
        <GlassCard variant="chart" className="lg:col-span-2">
          <CardHead
            title="Skill vs baseline 3"
            subtitle="Served model, test year. Right of zero = lower RMSE than Open-Meteo + physics."
          />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 8 }}>
              <XAxis
                type="number"
                domain={[(m: number) => Math.min(0, m * 1.2), (m: number) => Math.max(0, m * 1.2)]}
                tickFormatter={(v: number) => `${Math.round(v)}%`}
                tick={tick}
                axisLine={{ stroke: 'var(--axis)' }}
                tickLine={false}
              />
              <YAxis type="category" dataKey="label" width={128} tick={tick} axisLine={false} tickLine={false} />
              <ReferenceLine x={0} stroke="var(--ink)" strokeOpacity={0.3} />
              <Bar
                dataKey="value"
                barSize={18}
                radius={4}
                isAnimationActive={!reduce}
                animationDuration={600}
                animationEasing="ease-out"
                shape={(p: BarShapeProps) => <Rectangle {...p} fill={(p.payload as { hue: string }).hue} />}
              >
                <LabelList
                  dataKey="skill"
                  position="right"
                  formatter={(v) => signedPct(v as number | null)}
                  style={{ fontSize: 12, fontWeight: 700, fill: 'var(--ink)' }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>

        {/* 3. Band coverage (D-36 wind flag, D-45 humidity note) */}
        <GlassCard variant="chart">
          <CardHead title="P10–P90 coverage" subtitle="Share of hours where the true value fell inside the band. Target: 80%." />
          <div className="grid grid-cols-3 gap-x-2 gap-y-4">
            {TARGETS.map((t) => (
              <div key={t.key} className="grid justify-items-center gap-1 text-center">
                <Ring value={cov(t.key)} nominal={NOMINAL} hue={t.hue} label={t.label} />
                <span className="text-label font-bold text-ink">{t.short}</span>
                {LESS_RELIABLE.has(t.key) && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-warning-bg px-2 py-0.5 text-label font-bold text-warning-ink">
                    <TriangleExclamationPoint size={12} strokeWidth={1.75} aria-hidden />
                    Less reliable
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-2 text-label text-muted">
            <p className="m-0">
              Wind bands are too narrow: they caught the true value {pct0(cov('ws10'))}% and {pct0(cov('t5_kw'))}% of the
              time instead of {Math.round(NOMINAL * 100)}%. Reported as a limitation, not corrected.
            </p>
            {(cov('rh') ?? 1) < NOMINAL && (
              <p className="m-0">
                Humidity bands caught the true value {pct0(cov('rh'))}% of the time, a little under the{' '}
                {Math.round(NOMINAL * 100)}% target.
              </p>
            )}
          </div>
        </GlassCard>
      </div>

      {/* 4. Error by horizon */}
      <GlassCard variant="chart">
        <CardHead
          title="Error by horizon"
          subtitle="nRMSE % at 1, 6, 24, 48 and 72 hours ahead, test year. Lower is better."
          right={
            <div className="flex flex-wrap items-center gap-4 text-label text-muted">
              <span className="inline-flex items-center gap-1.5">
                <svg width="20" height="4" aria-hidden>
                  <line x1="0" y1="2" x2="20" y2="2" stroke={hHue} strokeWidth="2" />
                </svg>
                {hServed ? modelName(hServed) : 'Served model'}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <svg width="20" height="4" aria-hidden>
                  <line x1="0" y1="2" x2="20" y2="2" stroke="var(--hue-baseline)" strokeWidth="2" strokeDasharray="4 4" />
                </svg>
                Baseline 3
              </span>
            </div>
          }
        />
        <div className="mb-4">
          <Segmented
            label="Target"
            size="sm"
            scrollable
            value={hTarget}
            onChange={setHTarget}
            options={TARGETS.map((t) => ({ value: t.key, label: SEG_LABEL[t.key] ?? t.short }))}
          />
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={horizon} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--grid)" />
            <XAxis dataKey="h" tick={tick} axisLine={{ stroke: 'var(--axis)' }} tickLine={false} />
            <YAxis tick={tick} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip
              formatter={(v) => `${num(v as number | null)}%`}
              contentStyle={{
                background: 'var(--popover-fill)', border: '1px solid var(--card-border)', borderRadius: 12, fontSize: 12,
              }}
              labelStyle={{ color: 'var(--muted)' }}
            />
            <Line
              name={hServed ? modelName(hServed) : 'Served model'}
              dataKey="served"
              stroke={hHue}
              strokeWidth={2}
              dot={{ r: 3, fill: hHue, strokeWidth: 0 }}
              isAnimationActive={!reduce}
            />
            <Line
              name="Baseline 3"
              dataKey="base"
              stroke="var(--hue-baseline)"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={{ r: 3, fill: 'var(--hue-baseline)', strokeWidth: 0 }}
              isAnimationActive={!reduce}
            />
          </LineChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* 5. Leaderboard: every test row (D-47) */}
      <GlassCard>
        <CardHead title="Leaderboard" subtitle="Every model scored on the 2025 test year, grouped by target, lowest RMSE first." />
        <div className="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:px-0">
          <table className="w-full min-w-[640px] border-collapse text-body">
            <thead>
              <tr className="text-label text-muted">
                <th scope="col" className="sticky left-0 bg-[var(--card-chart)] py-2 pr-3 text-left font-bold">Target</th>
                <th scope="col" className="py-2 pr-3 text-left font-bold">Model</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold">RMSE</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold">MAE</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold">nRMSE %</th>
                <th scope="col" className="py-2 pl-3 text-right font-bold">Skill vs baseline 3</th>
              </tr>
            </thead>
            <tbody>
              {board.map(({ t, runtime, rows }) => (
                <Fragment key={t.key}>
                  {rows.map((r, i) => (
                    <tr key={r.model} className="border-t border-grid">
                      <th
                        scope="row"
                        className="sticky left-0 bg-[var(--card-chart)] py-2 pr-3 text-left font-bold text-ink whitespace-nowrap"
                      >
                        {i === 0 ? `${t.label} (${t.unit})` : <span className="sr-only">{t.label}</span>}
                      </th>
                      <td className="py-2 pr-3 whitespace-nowrap text-ink">
                        {modelName(r.model)}
                        {r.model === runtime && (
                          <span className="ml-2 inline-flex h-5 items-center rounded-full bg-primary px-2 text-label font-bold text-on-primary">
                            Serving
                          </span>
                        )}
                      </td>
                      <td className="py-2 pl-3 text-right text-ink">{num(r.rmse)}</td>
                      <td className="py-2 pl-3 text-right text-ink">{num(r.mae)}</td>
                      <td className="py-2 pl-3 text-right text-ink">{num(r.nrmse_pct)}</td>
                      <td className={`py-2 pl-3 text-right font-bold ${signColor(r.skill_vs_baseline3)}`}>
                        {signedPct(r.skill_vs_baseline3)}
                      </td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* 6. Skill heatmap, served model */}
      <GlassCard variant="chart">
        <CardHead
          title="Skill by horizon and season"
          subtitle="Served model vs baseline 3, test year."
          right={<Segmented label="Season" size="sm" value={season} onChange={setSeason} options={[...SEASONS]} />}
        />
        <div className="overflow-x-auto">
          <MatrixGrid
            label="Skill vs baseline 3 by target and horizon"
            rowLabels={TARGETS.map((t) => t.short)}
            colLabels={HORIZONS.map((h) => `${h} h`)}
            values={heat}
            format={(v) => signedPct(v)}
            colorFor={(v) => {
              const opacity = Math.min(Math.abs(v) / 0.5, 1) * 0.85
              return { bg: v >= 0 ? 'var(--positive)' : 'var(--negative)', opacity, text: opacity > 0.45 ? 'var(--on-primary)' : 'var(--ink)' }
            }}
          />
        </div>
        <p className="m-0 mt-3 text-label text-muted">Green = beats baseline 3, red = worse.</p>
      </GlassCard>

      {/* 7. Physics validation */}
      <div className="grid gap-4">
        <div className="grid gap-1">
          <h2 className="m-0 text-body font-bold text-ink">Physics validation</h2>
          <p className="m-0 text-label text-muted-glass">
            Solar and wind output are simulated; these plots check the physics against real Kaggle plant data.
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {FIGURES.map((f) => (
            <FigureCard key={f.name} {...f} />
          ))}
        </div>
      </div>
    </Stagger>
  )
}
