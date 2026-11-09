// Coverage ring: share of hours inside the P10-P90 band, with an --ink tick at the nominal share.
import { motion, useReducedMotion } from 'motion/react'

const SIZE = 64
const STROKE = 6
const R = (SIZE - STROKE) / 2
const C = 2 * Math.PI * R
const MID = SIZE / 2

export function Ring({ value, nominal, hue, label }: { value: number | null; nominal: number; hue: string; label: string }) {
  const reduce = useReducedMotion()
  const frac = Math.min(Math.max(value ?? 0, 0), 1)
  const a = nominal * 2 * Math.PI // clockwise from 12 o'clock
  const tick = (r: number) => ({ x: MID + r * Math.sin(a), y: MID - r * Math.cos(a) })
  const t0 = tick(R - STROKE / 2 - 2)
  const t1 = tick(R + STROKE / 2 + 1)
  const pct = value == null ? '–' : `${Math.round(value * 100)}%`
  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label={`${label} band coverage ${pct}, target ${Math.round(nominal * 100)}%`}
    >
      <circle cx={MID} cy={MID} r={R} fill="none" stroke="var(--axis)" strokeWidth={STROKE} />
      <motion.circle
        cx={MID}
        cy={MID}
        r={R}
        fill="none"
        stroke={hue}
        strokeWidth={STROKE}
        strokeLinecap="round"
        strokeDasharray={C}
        transform={`rotate(-90 ${MID} ${MID})`}
        initial={reduce ? false : { strokeDashoffset: C }}
        animate={{ strokeDashoffset: C * (1 - frac) }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      />
      <line x1={t0.x} y1={t0.y} x2={t1.x} y2={t1.y} stroke="var(--ink)" strokeWidth={2} />
      <text x={MID} y={MID} textAnchor="middle" dominantBaseline="central" fontSize={14} fontWeight={700} fill="var(--ink)">
        {pct}
      </text>
    </svg>
  )
}
