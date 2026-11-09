// Glass shell: sidebar (desktop), top bar with settings, bottom nav (phone), provenance footer (UI-08).
import { ChartColumn, CloudSun, Info, MapPin, Moon, Settings, Sun, SunMedium, Zap, type LucideIcon } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { NavLink } from 'react-router-dom'
import { useBuild, useHealth, useSite, useTz } from '../api'
import { modelName } from '../lib/targets'
import { makeFmt } from '../lib/time'
import { Segmented } from './Segmented'
import { StatusPill } from './ui'

interface NavItem { to: string; label: string; icon: LucideIcon }
const GROUPS: { label: string; items: NavItem[] }[] = [
  { label: 'Forecast', items: [{ to: '/', label: 'Energy', icon: Zap }, { to: '/weather', label: 'Weather', icon: CloudSun }] },
  { label: 'Results', items: [{ to: '/performance', label: 'Performance', icon: ChartColumn }] },
  { label: 'Project', items: [{ to: '/about', label: 'About', icon: Info }] },
]
const ALL_ITEMS = GROUPS.flatMap((g) => g.items)

const ACTIVE_PILL =
  'bg-[linear-gradient(180deg,var(--accent-from),var(--accent))] text-on-accent shadow-[inset_0_1px_0_rgba(255,255,255,.5),0_4px_14px_rgba(30,180,240,.45)]'

function Sidebar() {
  const site = useSite().data?.site
  const health = useHealth().data
  return (
    <aside className="glass-sidebar sheen sticky top-4 hidden h-[calc(100dvh-32px)] flex-col gap-6 overflow-y-auto p-4 lg:flex">
      <div className="flex items-center gap-3">
        <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-white/85 text-[#0f1e2e]">
          <SunMedium size={20} strokeWidth={1.75} aria-hidden />
        </span>
        <div className="grid min-w-0">
          <span className="text-body font-bold text-on-sidebar">Solar &amp; Wind Forecast</span>
          <span className="truncate text-label text-on-sidebar-muted">{site ? `${site.name} · 72 h` : '72 h'}</span>
        </div>
      </div>
      <nav aria-label="Primary" className="grid gap-5">
        {GROUPS.map((g) => (
          <div key={g.label} className="grid gap-1">
            <span className="px-3 pb-1 text-label font-bold uppercase tracking-[0.08em] text-on-sidebar-muted">{g.label}</span>
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.to === '/'}
                className={({ isActive }) =>
                  `flex h-10 items-center gap-3 rounded-full px-3 text-body transition-colors duration-150 ${
                    isActive ? `${ACTIVE_PILL} font-bold` : 'text-on-sidebar hover:bg-white/12'
                  }`
                }
              >
                <it.icon size={18} strokeWidth={1.75} aria-hidden />
                <span className="flex-1">{it.label}</span>
                {it.to === '/' && <StatusPill stale={health?.stale} />}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  )
}

function useMinute(): number {
  const [m, setM] = useState(() => Math.floor(Date.now() / 60e3))
  useEffect(() => {
    const id = setInterval(() => setM(Math.floor(Date.now() / 60e3)), 10e3)
    return () => clearInterval(id)
  }, [])
  return m * 60e3
}

function readTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function SettingsPopover({ onClose, gear }: { onClose: () => void; gear: RefObject<HTMLButtonElement | null> }) {
  const ref = useRef<HTMLDivElement>(null)
  const [theme, setTheme] = useState(readTheme)

  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node
      if (!ref.current?.contains(t) && !gear.current?.contains(t)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [onClose, gear])

  const choose = (t: 'light' | 'dark') => {
    setTheme(t)
    document.documentElement.dataset.theme = t
    try {
      localStorage.setItem('swf-theme', t) // storage can throw (privacy mode); the choice still applies this session
    } catch {
      /* ignore */
    }
  }

  return (
    <motion.div
      ref={ref}
      role="dialog"
      aria-label="Settings"
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1, transition: { duration: 0.16, ease: [0.22, 1, 0.36, 1] } }}
      exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.12 } }}
      style={{ transformOrigin: 'top right' }}
      className="popover absolute right-0 top-full z-50 mt-2 grid w-60 gap-3 p-4 text-ink"
    >
      <span className="text-label font-bold uppercase tracking-[0.08em] text-muted">Appearance</span>
      <Segmented
        label="Theme"
        value={theme}
        onChange={choose}
        options={[
          { value: 'light', label: 'Light', icon: Sun },
          { value: 'dark', label: 'Dark', icon: Moon },
        ]}
      />
      <p className="m-0 text-label text-muted">Animations follow your system's reduce-motion setting.</p>
    </motion.div>
  )
}

function TopBar() {
  const site = useSite().data?.site
  const tz = useTz()
  const now = useMinute()
  const [open, setOpen] = useState(false)
  const gear = useRef<HTMLButtonElement>(null)
  const close = useCallback(() => {
    setOpen(false)
    gear.current?.focus()
  }, [])

  return (
    <header className="glass-bar relative z-40 flex h-14 items-center justify-between gap-3 px-4 lg:h-16 lg:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <MapPin size={16} strokeWidth={1.75} aria-hidden className="shrink-0" />
        <span className="truncate text-body font-bold">{site?.name ?? ''}</span>
        {tz && (
          <span className="hidden text-body text-on-sidebar-muted lg:inline">{makeFmt(tz).dayTime(now)} IST</span>
        )}
      </div>
      <div className="relative">
        <motion.button
          ref={gear}
          type="button"
          aria-label="Settings"
          aria-expanded={open}
          aria-haspopup="dialog"
          whileTap={{ scale: 0.97 }}
          onClick={() => (open ? close() : setOpen(true))}
          className="inline-flex size-11 items-center justify-center rounded-full border border-white/25 bg-white/15 text-on-sidebar hover:bg-white/25 lg:size-10"
        >
          <Settings size={18} strokeWidth={1.75} aria-hidden />
        </motion.button>
        <AnimatePresence>{open && <SettingsPopover onClose={close} gear={gear} />}</AnimatePresence>
      </div>
    </header>
  )
}

function BottomNav() {
  return (
    <nav
      aria-label="Primary"
      className="glass-bar fixed inset-x-2 bottom-2 z-40 grid grid-cols-4 lg:hidden"
      style={{ height: 'calc(64px + env(safe-area-inset-bottom))', paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {ALL_ITEMS.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          end={it.to === '/'}
          className="flex min-w-11 flex-col items-center justify-center gap-1 text-label text-on-sidebar"
        >
          {({ isActive }) => (
            <>
              <span
                className={`inline-flex h-7 w-12 items-center justify-center rounded-full ${isActive ? ACTIVE_PILL : ''}`}
              >
                <it.icon size={20} strokeWidth={1.75} aria-hidden />
              </span>
              <span className={isActive ? 'font-bold' : ''}>{it.label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

const ext = 'underline decoration-1 underline-offset-2 hover:text-ink'

function Footer() {
  const b = useBuild().data
  const tz = useTz()
  const models = b ? [...new Set(Object.values(b.models).map(modelName))].join(', ') : ''
  const through = b?.data_through && tz ? `${makeFmt(tz).dayTime(Date.parse(b.data_through))} IST` : '–'
  const items: ReactNode[] = [
    `Model ${models || '–'}`,
    `registry v${b?.schema_version ?? '–'}`,
    `Data through ${through}`,
    `Build ${b?.git_sha ? b.git_sha.slice(0, 7) : 'unknown'}`,
    <a key="om" href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer" className={ext}>
      Weather data by Open-Meteo.com (CC BY 4.0)
    </a>,
    <a key="nasa" href="https://power.larc.nasa.gov/" target="_blank" rel="noopener noreferrer" className={ext}>
      NASA POWER
    </a>,
  ]
  return (
    <footer className="mt-12 text-label text-muted-glass">
      {items.map((it, i) => (
        <span key={i}>
          {i > 0 && ' · '}
          {it}
        </span>
      ))}
    </footer>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh p-2 pb-24 lg:grid lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-4 lg:p-4">
      <Sidebar />
      {/* minmax(0,1fr): wide charts/toggles must scroll inside their card, never widen the page */}
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-2 lg:gap-4">
        <TopBar />
        <div className="glass-panel sheen min-w-0 p-4 lg:p-8">
          <main className="min-w-0">{children}</main>
          <Footer />
        </div>
      </div>
      <BottomNav />
    </div>
  )
}
