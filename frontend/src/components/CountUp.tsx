// Animated number: 0 -> value in 800 ms on mount, old -> new in 400 ms later; reduced motion shows the value at once.
import { animate, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'

export function CountUp({ value, decimals = 0, className }: { value: number | null; decimals?: number; className?: string }) {
  const reduce = useReducedMotion()
  const fmt = useMemo(
    () => new Intl.NumberFormat('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }),
    [decimals],
  )
  const [shown, setShown] = useState(0)
  const last = useRef<number | null>(null) // last displayed value; null until the first frame

  useEffect(() => {
    if (value == null || reduce) return
    const first = last.current == null
    const c = animate(last.current ?? 0, value, {
      duration: first ? 0.8 : 0.4,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        last.current = v
        setShown(v)
      },
    })
    return () => c.stop()
  }, [value, reduce])

  return <span className={className}>{value == null ? '–' : fmt.format(reduce ? value : shown)}</span>
}
