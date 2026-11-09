// Small shared building blocks (UI-SPEC "Shared components").
import {
  ArrowUpRight, Cloud, Droplets, Fan, SolarPanel, SunMedium, TriangleExclamationPoint, Wind, Activity,
  type LucideIcon,
} from 'lucide-react'
import { motion, useReducedMotion, type Variants } from 'motion/react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useSite, useTz } from '../api'
import { modelName, TARGETS } from '../lib/targets'
import { ageText, makeFmt } from '../lib/time'

const EASE_OUT = [0.22, 1, 0.36, 1] as const

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 12, filter: 'blur(6px)' },
  visible: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.36, ease: EASE_OUT } },
}
const reducedItem: Variants = { hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.12 } } }

/** Any motion child of Stagger that should take part in the card entrance. */
export function useItemVariants(): Variants {
  return useReducedMotion() ? reducedItem : itemVariants
}

// shortcut: plain staggerChildren, so a page with > 8 items runs slightly past 0.8 s; cap per item if a page gets long.
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{ hidden: {}, visible: { transition: reduce ? {} : { staggerChildren: 0.05, delayChildren: 0.06 } } }}
    >
      {children}
    </motion.div>
  )
}

export function GlassCard({
  variant = 'card', className = '', children, id, ariaLabel,
}: { variant?: 'card' | 'chart'; className?: string; children: ReactNode; id?: string; ariaLabel?: string }) {
  return (
    <motion.section
      id={id}
      aria-label={ariaLabel}
      variants={useItemVariants()}
      className={`${variant === 'chart' ? 'card-chart' : 'card'} p-4 lg:p-6 ${className}`}
    >
      {children}
    </motion.section>
  )
}

const ICONS: Record<string, LucideIcon> = { t1_kw: SolarPanel, t5_kw: Fan, ghi: SunMedium, rh: Droplets, ws10: Wind }

export function TargetIcon({ targetKey, size = 16, className }: { targetKey: string; size?: number; className?: string }) {
  const Icon = ICONS[targetKey] ?? SunMedium
  return <Icon size={size} strokeWidth={1.75} aria-hidden className={className} />
}

export function IconChip({ targetKey }: { targetKey: string }) {
  return (
    <span
      className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--chip)]"
      style={{ color: TARGETS.find((t) => t.key === targetKey)?.hue }}
    >
      <TargetIcon targetKey={targetKey} />
    </span>
  )
}

const tagBase = 'inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-label'

export function ModelBadge({ targetKey, runtime }: { targetKey: string; runtime: string }) {
  const name = modelName(runtime)
  return (
    <Link
      to={`/performance#target-${targetKey}`}
      aria-label={`Served by ${name}. See its scores`}
      className={`${tagBase} bg-secondary font-bold text-ink hover:brightness-95`}
    >
      {name}
      <ArrowUpRight size={12} strokeWidth={1.75} aria-hidden />
    </Link>
  )
}

export function SimulatedTag() {
  const name = useSite().data?.site.name
  return (
    <span
      className={`${tagBase} border border-dashed border-muted font-medium text-muted`}
      title={`Computed by physics from forecast weather; there is no metered plant at ${name ?? 'this site'}.`}
    >
      Simulated energy
    </span>
  )
}

export function SourceTag({ kind, label, icon }: { kind: 'open-meteo' | 'ours'; label?: string; icon?: LucideIcon }) {
  const Icon = icon ?? (kind === 'open-meteo' ? Cloud : Activity)
  return (
    <span className={`${tagBase} bg-secondary font-medium text-muted`}>
      <Icon size={12} strokeWidth={1.75} aria-hidden />
      {label ?? (kind === 'open-meteo' ? 'from Open-Meteo' : 'Our forecast')}
    </span>
  )
}

export function StatusPill({ stale }: { stale: boolean | undefined }) {
  if (stale === undefined) return null
  return (
    <span
      className={`${tagBase} h-5 font-bold ${stale ? 'bg-warning-bg text-warning-ink' : 'bg-white/15 text-on-sidebar'}`}
    >
      <span aria-hidden className={`size-1.5 rounded-full ${stale ? 'bg-warning-ink' : 'bg-positive'}`} />
      {stale ? 'Stale' : 'Live'}
    </span>
  )
}

export function StaleBanner({ ageMinutes, lastSuccess }: { ageMinutes: number | null; lastSuccess: string | null }) {
  const tz = useTz()
  const at = lastSuccess && tz ? `${makeFmt(tz).hour(Date.parse(lastSuccess))} IST` : 'an unknown time'
  return (
    <motion.div
      role="status"
      variants={useItemVariants()}
      className="flex items-start gap-3 rounded-card bg-warning-bg p-4 text-body text-warning-ink"
    >
      <TriangleExclamationPoint size={18} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
      <p>
        This forecast may be out of date. The last successful refresh was{' '}
        {ageMinutes == null ? 'a while' : ageText(ageMinutes)} ago, at {at}. You are seeing the last good forecast;
        the server retries every hour.
      </p>
    </motion.div>
  )
}

const COPY = {
  empty: {
    title: 'No forecast yet',
    body: 'The server is fetching its first forecast, which takes about a minute after start-up. This page checks again every 30 seconds.',
  },
  error: {
    title: "Can't reach the forecast server",
    body: 'Start it with python -m swf serve (port 8000). This page reconnects on its own, or press Try again.',
  },
}

export function StateBlock({
  kind, onRetry, title, body, rows = 3,
}: { kind: 'loading' | 'empty' | 'error'; onRetry?: () => void; title?: string; body?: string; rows?: number }) {
  if (kind === 'loading') {
    return (
      <div aria-busy="true" aria-label="Loading" className="grid gap-3">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="skeleton h-6" style={{ width: `${100 - i * 15}%` }} />
        ))}
      </div>
    )
  }
  const c = COPY[kind]
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className="grid max-w-[72ch] justify-items-start gap-2 py-4">
      <h2 className="text-body font-bold text-ink">{title ?? c.title}</h2>
      <p className="text-body text-muted">{body ?? c.body}</p>
      {kind === 'error' && onRetry && (
        <motion.button
          type="button"
          whileTap={{ scale: 0.97 }}
          onClick={onRetry}
          className="mt-2 inline-flex h-11 items-center rounded-full bg-secondary px-4 text-body font-bold text-ink lg:h-9"
        >
          Try again
        </motion.button>
      )}
    </div>
  )
}

export function FigureCard({ name, title, caption, alt }: { name: string; title: string; caption: string; alt: string }) {
  const src = `/api/figures/${name}`
  const [failed, setFailed] = useState(false)
  return (
    <motion.figure variants={useItemVariants()} className="card m-0 grid gap-3 p-4 lg:p-6">
      <figcaption className="grid gap-1">
        <span className="text-body font-bold text-ink">{title}</span>
        <span className="text-label text-muted">{caption}</span>
      </figcaption>
      {failed ? (
        <p className="paper m-0 text-label text-muted">Figure not found: {name}</p>
      ) : (
        <a href={src} target="_blank" rel="noopener noreferrer" className="paper block">
          <img
            src={src}
            alt={alt}
            loading="lazy"
            className="block h-auto w-full rounded-chip"
            onError={() => setFailed(true)}
          />
        </a>
      )}
    </motion.figure>
  )
}

export function PageHeader({
  title, subtitle, secondary, primary, children,
}: {
  title: string
  subtitle?: ReactNode
  secondary?: ReactNode
  primary?: { to: string; label: string }
  children?: ReactNode
}) {
  return (
    <motion.header variants={useItemVariants()} className="flex flex-wrap items-start justify-between gap-4">
      <div className="grid min-w-0 gap-3">
        <h1 className="m-0 text-heading font-bold text-ink">{title}</h1>
        {subtitle && <p className="m-0 text-body text-muted-glass">{subtitle}</p>}
        {children}
      </div>
      {(secondary || primary) && (
        <div className="flex w-full flex-wrap gap-2 lg:w-auto">
          {secondary && (
            <span className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-full bg-secondary px-4 text-body font-bold text-ink lg:h-9 lg:flex-none">
              {secondary}
            </span>
          )}
          {primary && (
            <Link
              to={primary.to}
              className="inline-flex h-11 flex-1 items-center justify-center rounded-full bg-primary px-4 text-body font-bold text-on-primary lg:h-9 lg:flex-none"
            >
              {primary.label}
            </Link>
          )}
        </div>
      )}
    </motion.header>
  )
}
