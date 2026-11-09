// Performance page (/performance): the honest test-year results. Every number comes from the API.
import { TriangleExclamationPoint } from 'lucide-react'
import { useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import {
  Bar, BarChart, LabelList, Rectangle, ReferenceLine, ResponsiveContainer, XAxis, YAxis, type BarShapeProps,
} from 'recharts'
import { useBuild, useForecast, useMetrics, usePerformance, type MetricsRow } from '../api'
import { CountUp } from '../components/CountUp'
import { Ring } from '../components/Ring'
import { GlassCard, IconChip, ModelBadge, PageHeader, StateBlock, Stagger } from '../components/ui'
import { TARGETS } from '../lib/targets'

const NOMINAL = 0.8 // a P10-P90 band should hold the truth 80% of the time
const LESS_RELIABLE = new Set(['ws10', 't5_kw'])
const f1 = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const num = (v: number | null | undefined) => (v == null ? '–' : f1.format(v))
const signedPct = (s: number | null | undefined) => (s == null ? '–' : `${s > 0 ? '+' : ''}${f1.format(s * 100)}%`)
const pct0 = (c: number | null | undefined) => (c == null ? '–' : `${Math.round(c * 100)}`)
const tick = { fontSize: 12, fill: 'var(--muted)' }

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
  const metrics = useMetrics()
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
    </Stagger>
  )
}
