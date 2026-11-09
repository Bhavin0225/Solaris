// About page (/about, D-37, UI-07). Every site/plant value, Kaggle slug and wind number comes from the API.
import { ChevronDown, ChevronRight, TriangleExclamationPoint } from 'lucide-react'
import { motion } from 'motion/react'
import { Fragment, type ReactNode } from 'react'
import { useBuild, usePerformance, useSite, type WindCfRow } from '../api'
import { FigureCard, GlassCard, PageHeader, Stagger, useItemVariants } from '../components/ui'
import { modelName, TARGETS } from '../lib/targets'

const FLOW = [
  'NASA POWER + Open-Meteo',
  'Clean & align (UTC)',
  'Physics (pvlib, power curve)',
  'Features',
  'Baselines · LightGBM · LSTM · TFT',
  'Pick on 2024',
  'Test once on 2025',
  'Hourly API',
  'This site',
]

const link = 'text-ink underline underline-offset-2'
const kaggleUrl = (slug: string) => `https://www.kaggle.com/datasets/${encodeURI(slug)}`
const pct = (v: number | null | undefined) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)

function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={link}>
      {children}
    </a>
  )
}

function KV({ k, v, unit }: { k: string; v: ReactNode; unit?: string }) {
  return (
    <tr className="border-b border-grid last:border-0">
      <th scope="row" className="py-2 pr-4 text-left font-medium text-muted">{k}</th>
      <td className="py-2 text-right tabular-nums text-ink">
        {v} {unit && <span className="text-muted">{unit}</span>}
      </td>
    </tr>
  )
}

function windStory(rows: WindCfRow[], runtime: string | undefined): string | null {
  const served = rows.filter((r) => r.model === runtime)
  const by = (s: string) => served.find((r) => r.season === s)
  const all = by('all'), mon = by('monsoon'), dry = by('dry')
  if (!runtime || !all) return null
  const name = modelName(runtime)
  const parts = [
    `Over the 2025 test year the simulated turbine ran at a capacity factor of ${pct(all.observed_cf)}; the served ${name} model predicted ${pct(all.predicted_cf)}.`,
  ]
  if (mon && dry) {
    parts.push(
      `The monsoon carries the wind: ${pct(mon.observed_cf)} observed vs ${pct(mon.predicted_cf)} predicted, against only ${pct(dry.observed_cf)} vs ${pct(dry.predicted_cf)} in the dry months.`,
      `So most of the annual wind energy arrives in a few months, and the model ${
        (dry.predicted_cf ?? 0) < (dry.observed_cf ?? 0) ? 'under-predicts the calmer dry season' : 'tracks the dry season closely'
      }.`,
    )
  }
  return parts.join(' ')
}

export default function About() {
  const site = useSite().data
  const build = useBuild().data
  const perf = usePerformance().data
  const name = site?.site.name
  const kaggle = build?.kaggle
  const story = perf ? windStory(perf.wind_cf, build?.models.t5_kw) : null
  const item = useItemVariants()

  return (
    <Stagger className="grid max-w-[72ch] gap-6">
      <PageHeader
        title="About this project"
        subtitle={`Bhavin's final-year project: 72-hour solar, wind and weather forecasts${name ? ` for ${name}` : ''}.`}
        primary={{ to: '/performance', label: 'See model accuracy' }}
      />

      {/* 4 is the focal point, but the reading order follows the spec */}
      <GlassCard ariaLabel="What it forecasts" className="grid gap-3">
        <h2 className="m-0 text-body font-bold text-ink">What it forecasts</h2>
        <p className="m-0 text-body text-muted">
          Five linked quantities, every hour for the next 72 hours, each with a P10–P90 range around the P50 (middle)
          forecast:
        </p>
        <ul className="m-0 grid gap-1 pl-5 text-body text-ink">
          {TARGETS.map((t) => (
            <li key={t.key}>
              {t.label} <span className="text-muted">({t.unit})</span>
            </li>
          ))}
        </ul>
      </GlassCard>

      <GlassCard ariaLabel="Site and plant" className="grid gap-3">
        <h2 className="m-0 text-body font-bold text-ink">Site and plant</h2>
        {site ? (
          <table className="w-full border-collapse text-body">
            <tbody>
              <KV k="Site" v={site.site.name} />
              <KV k="Latitude" v={site.site.latitude.toFixed(4)} unit="°" />
              <KV k="Longitude" v={site.site.longitude.toFixed(4)} unit="°" />
              <KV k="Elevation" v={site.site.elevation_m} unit="m" />
              <KV k="Timezone" v={site.site.display_timezone} />
              <KV k="Solar DC capacity" v={site.solar.dc_kwp} unit="kWp" />
              <KV k="Solar AC capacity" v={(site.solar.dc_kwp / site.solar.dc_ac_ratio).toFixed(0)} unit="kW" />
              <KV k="Panel tilt" v={site.solar.tilt_deg} unit="°" />
              <KV k="Panel azimuth (180 = south)" v={site.solar.azimuth_pvlib_deg} unit="°" />
              <KV k="Turbine rated power" v={site.wind.rated_kw} unit="kW" />
              <KV k="Hub height" v={site.wind.hub_height_m} unit="m" />
              <KV k="Cut-in / rated / cut-out" v={`${site.wind.cut_in_ms} / ${site.wind.rated_ms} / ${site.wind.cut_out_ms}`} unit="m/s" />
            </tbody>
          </table>
        ) : (
          <p className="m-0 text-body text-muted">Loading site details…</p>
        )}
      </GlassCard>

      <GlassCard ariaLabel="Methodology" className="grid gap-3">
        <h2 className="m-0 text-body font-bold text-ink">How it works</h2>
        <ol className="m-0 flex list-none flex-col items-start gap-1 p-0 lg:flex-row lg:flex-wrap lg:items-center">
          {FLOW.map((step, i) => (
            <Fragment key={step}>
              <li className="rounded-full bg-secondary px-3 py-1.5 text-label font-bold text-ink">{step}</li>
              {i < FLOW.length - 1 && (
                <li aria-hidden className="text-muted">
                  <ChevronRight size={16} strokeWidth={1.75} className="hidden lg:block" />
                  <ChevronDown size={16} strokeWidth={1.75} className="ml-4 lg:hidden" />
                </li>
              )}
            </Fragment>
          ))}
        </ol>
      </GlassCard>

      <motion.div
        role="note"
        variants={item}
        className="flex items-start gap-3 rounded-card bg-warning-bg p-4 text-body text-warning-ink lg:p-6"
      >
        <TriangleExclamationPoint size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
        <p className="m-0">
          <strong>Solar and wind output are simulated.</strong> Physics models turn the weather into the power a plant
          of this size would produce; there is no metered plant at {name ?? 'this site'}. The physics was checked
          against real plant data from Kaggle (see Performance › Physics validation).
        </p>
      </motion.div>

      <FigureCard
        name="wind_cf"
        title="Wind capacity factor by season"
        caption={story ?? 'Observed vs predicted capacity factor, test year 2025.'}
        alt="Bar chart of observed and predicted wind capacity factor for the whole year, the monsoon and the dry season"
      />

      <GlassCard ariaLabel="Data and credits" className="grid gap-3">
        <h2 className="m-0 text-body font-bold text-ink">Data and credits</h2>
        <ul className="m-0 grid gap-2 pl-5 text-body text-ink">
          <li>
            <Ext href="https://power.larc.nasa.gov/">NASA POWER</Ext> (NASA Langley Research Center): hourly history
            used for training.
          </li>
          <li>
            <Ext href="https://open-meteo.com/">Weather data by Open-Meteo.com</Ext>, licensed{' '}
            <Ext href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</Ext>; modified: resampled and combined
            with physics models.
          </li>
          {kaggle && (
            <>
              <li>
                Solar plant data: <Ext href={kaggleUrl(kaggle.solar_slug)}>{kaggle.solar_slug}</Ext> (Kaggle)
              </li>
              <li>
                Wind turbine SCADA data: <Ext href={kaggleUrl(kaggle.wind_slug)}>{kaggle.wind_slug}</Ext> (Kaggle)
              </li>
            </>
          )}
        </ul>
      </GlassCard>
    </Stagger>
  )
}
