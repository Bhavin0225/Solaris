// Scatter drawn on one <canvas> instead of thousands of SVG circles: thousands of SVG nodes made scrolling
// the Performance page stutter (measured ~6x fewer frames). Redraws on resize and on theme change.
import { useEffect, useRef, useState } from 'react'

const kw = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

interface Props {
  points: [number, number][] // [simulated, actual]
  ticks: number[] // round axis ticks from 0 to top
  color: string | string[] // one CSS colour, or one per point
  alpha: number
  height?: number
  label: string
}

const M = { top: 8, right: 22, bottom: 46, left: 68 }

export function ScatterCanvas({ points, ticks, color, alpha, height = 260, label }: Props) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const [width, setWidth] = useState(0)
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme)
  const [hover, setHover] = useState<[number, number] | null>(null)
  const top = ticks[ticks.length - 1]

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)))
    ro.observe(el)
    const mo = new MutationObserver(() => setTheme(document.documentElement.dataset.theme))
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => {
      ro.disconnect()
      mo.disconnect()
    }
  }, [])

  useEffect(() => {
    const c = canvas.current
    if (!c || width === 0) return
    const dpr = window.devicePixelRatio || 1
    c.width = width * dpr
    c.height = height * dpr
    const g = c.getContext('2d')!
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.clearRect(0, 0, width, height)
    const css = getComputedStyle(document.documentElement)
    const v = (name: string) => css.getPropertyValue(name).trim()
    const pw = width - M.left - M.right
    const ph = height - M.top - M.bottom
    const x = (val: number) => M.left + (val / top) * pw
    const y = (val: number) => M.top + ph - (val / top) * ph

    // grid, ticks and axis labels
    g.font = `12px ${v('--font-sans') || 'sans-serif'}`
    g.fillStyle = v('--muted')
    g.strokeStyle = v('--grid')
    g.setLineDash([3, 3])
    g.lineWidth = 1
    for (const t of ticks) {
      g.beginPath()
      g.moveTo(x(t), M.top)
      g.lineTo(x(t), M.top + ph)
      g.moveTo(M.left, y(t))
      g.lineTo(M.left + pw, y(t))
      g.stroke()
      g.textAlign = t === top ? 'right' : 'center' // keep the last label inside the canvas
      g.textBaseline = 'top'
      g.fillText(kw.format(t), t === top ? x(t) + 4 : x(t), M.top + ph + 6)
      g.textAlign = 'right'
      g.textBaseline = 'middle'
      g.fillText(kw.format(t), M.left - 6, y(t))
    }
    g.setLineDash([])
    g.textAlign = 'center'
    g.textBaseline = 'alphabetic'
    g.fillText('Actual (kW)', M.left + pw / 2, height - 3)
    g.save()
    g.translate(14, M.top + ph / 2)
    g.rotate(-Math.PI / 2)
    g.fillText('Simulated (kW)', 0, 0)
    g.restore()

    // points (actual on x, simulated on y)
    g.globalAlpha = alpha
    points.forEach(([sim, act], i) => {
      g.fillStyle = Array.isArray(color) ? color[i] : color
      g.beginPath()
      g.arc(x(act), y(sim), 3.5, 0, Math.PI * 2)
      g.fill()
    })
    g.globalAlpha = 1

    // perfect-match diagonal on top
    g.strokeStyle = v('--ink')
    g.globalAlpha = 0.5
    g.setLineDash([5, 4])
    g.beginPath()
    g.moveTo(x(0), y(0))
    g.lineTo(x(top), y(top))
    g.stroke()
    g.setLineDash([])
    g.globalAlpha = 1

    if (hover) {
      g.strokeStyle = v('--ink')
      g.lineWidth = 2
      g.beginPath()
      g.arc(x(hover[1]), y(hover[0]), 6, 0, Math.PI * 2)
      g.stroke()
    }
  }, [points, ticks, color, alpha, width, height, theme, top, hover])

  // hover: nearest point within 12 px
  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const pw = width - M.left - M.right
    const ph = height - M.top - M.bottom
    const mx = e.clientX - r.left
    const my = e.clientY - r.top
    let best: [number, number] | null = null
    let bd = e.pointerType === 'mouse' ? 144 : 484 // fingers are less precise: 22 px reach on touch
    for (const p of points) {
      const dx = M.left + (p[1] / top) * pw - mx
      const dy = M.top + ph - (p[0] / top) * ph - my
      const d = dx * dx + dy * dy
      if (d < bd) {
        bd = d
        best = p
      }
    }
    setHover(best)
  }

  return (
    <div ref={wrap} className="relative">
      <canvas
        ref={canvas}
        role="img"
        aria-label={label}
        style={{ width: '100%', height, touchAction: 'pan-y' }}
        onPointerMove={(e) => e.pointerType === 'mouse' && onMove(e)}
        onPointerDown={onMove} // touch: tap a dot to see its values, tap empty space to clear
        onPointerLeave={(e) => e.pointerType === 'mouse' && setHover(null)}
      />
      {hover && (
        <div className="popover pointer-events-none absolute right-2 top-2 px-3 py-2 text-label text-ink">
          Actual {kw.format(hover[1])} kW · Simulated {kw.format(hover[0])} kW
        </div>
      )}
    </div>
  )
}
