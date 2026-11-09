// Value matrix (correlation grid, skill heatmap). Every cell prints its number; colour never carries meaning alone.

export interface CellColor { bg: string; opacity: number; text: string }

export function MatrixGrid({
  rowLabels, colLabels, values, colorFor, cellSize = 56, diagonalMuted = false, label,
}: {
  rowLabels: string[]
  colLabels: string[]
  values: (number | null)[][]
  colorFor: (v: number) => CellColor
  cellSize?: number
  diagonalMuted?: boolean
  label: string
}) {
  const cols = `auto repeat(${colLabels.length}, ${cellSize}px)`
  return (
    <div role="table" aria-label={label} className="inline-grid gap-y-0 text-label">
      <div role="row" className="grid" style={{ gridTemplateColumns: cols }}>
        <span role="columnheader" />
        {colLabels.map((c) => (
          <span key={c} role="columnheader" className="pb-1 text-center font-bold text-muted">
            {c}
          </span>
        ))}
      </div>
      {rowLabels.map((r, i) => (
        <div key={r} role="row" className="grid" style={{ gridTemplateColumns: cols }}>
          <span role="rowheader" className="flex items-center pr-2 font-bold text-muted">
            {r}
          </span>
          {colLabels.map((c, j) => {
            const v = values[i]?.[j] ?? null
            const diag = diagonalMuted && i === j
            const col = v == null || diag ? null : colorFor(v)
            const corner = `${i === 0 && j === 0 ? 'rounded-tl-chip' : ''} ${
              i === 0 && j === colLabels.length - 1 ? 'rounded-tr-chip' : ''
            } ${i === rowLabels.length - 1 && j === 0 ? 'rounded-bl-chip' : ''} ${
              i === rowLabels.length - 1 && j === colLabels.length - 1 ? 'rounded-br-chip' : ''
            }`
            return (
              <span
                key={c}
                role="cell"
                className={`relative flex items-center justify-center overflow-hidden border border-grid font-bold ${corner}`}
                style={{ height: cellSize, color: col?.text ?? 'var(--muted)' }}
              >
                {col && <span aria-hidden className="absolute inset-0" style={{ background: col.bg, opacity: col.opacity }} />}
                <span className="relative">{diag ? '1' : v == null ? '–' : v.toFixed(2)}</span>
              </span>
            )
          })}
        </div>
      ))}
    </div>
  )
}
