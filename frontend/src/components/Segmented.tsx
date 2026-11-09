// Segmented toggle: ARIA radiogroup with roving focus and a sliding thumb (layoutId).
import type { LucideIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { useId, useRef, type KeyboardEvent } from 'react'

export interface SegOption<T extends string> { value: T; label: string; icon?: LucideIcon }

export function Segmented<T extends string>({
  options, value, onChange, label, size = 'md', scrollable = false,
}: {
  options: SegOption<T>[]
  value: T
  onChange: (v: T) => void
  label: string
  size?: 'sm' | 'md'
  scrollable?: boolean
}) {
  const thumbId = useId()
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const idx = Math.max(0, options.findIndex((o) => o.value === value))

  const onKey = (e: KeyboardEvent) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]
    let next = step === undefined ? -1 : (idx + step + options.length) % options.length
    if (e.key === 'Home') next = 0
    if (e.key === 'End') next = options.length - 1
    if (next < 0) return
    e.preventDefault()
    onChange(options[next].value)
    refs.current[next]?.focus()
  }

  const h = size === 'sm' ? 'h-11 lg:h-8' : 'h-11 lg:h-9'
  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKey}
      className={`inline-flex max-w-full gap-1 rounded-full bg-secondary p-1 ${
        scrollable ? 'overflow-x-auto [scrollbar-width:none]' : ''
      }`}
    >
      {options.map((o, i) => {
        const on = i === idx
        const Icon = o.icon
        return (
          <motion.button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el
            }}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={on ? 0 : -1}
            whileTap={{ scale: 0.97 }}
            onClick={() => onChange(o.value)}
            className={`relative inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-3 text-body font-bold ${h} ${
              on ? 'text-on-primary' : 'text-ink hover:bg-white/30'
            }`}
          >
            {on && (
              <motion.span
                layoutId={thumbId}
                transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
                className="absolute inset-0 rounded-full bg-primary"
              />
            )}
            <span className="relative inline-flex items-center gap-1.5">
              {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden />}
              {o.label}
            </span>
          </motion.button>
        )
      })}
    </div>
  )
}
