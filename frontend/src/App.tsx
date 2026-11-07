import { useEffect, useState } from 'react'

interface Point {
  time: string
  p10: number | null
  p50: number | null
  p90: number | null
}
interface Target {
  unit: string
  model: string
  points: Point[]
}
interface Forecast {
  run_time: string
  stale: boolean
  age_minutes: number
  display_timezone: string
  targets: Record<string, Target>
}

const fmt = (v: number | null) => (v == null ? '-' : v.toFixed(1))

export default function App() {
  const [data, setData] = useState<Forecast | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/forecast?hours=72')
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail ?? `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error)
    return (
      <p>
        {error}. Refresh the page in a minute.
      </p>
    )
  if (!data) return <p>Loading...</p>

  const tz = data.display_timezone
  const local = (iso: string) => new Date(iso).toLocaleString('en-IN', { timeZone: tz })
  const keys = Object.keys(data.targets)
  const rows = data.targets[keys[0]]?.points ?? []

  return (
    <main>
      <h1>72 h forecast</h1>
      <p>Run time: {local(data.run_time)} ({tz})</p>
      {data.stale && (
        <p role="alert">
          Forecast is stale: last successful refresh {data.age_minutes} min ago
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>Time</th>
            {keys.map((k) => (
              <th key={k}>
                {k} ({data.targets[k].unit}) - {data.targets[k].model}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.time}>
              <td>{local(row.time)}</td>
              {keys.map((k) => {
                const p = data.targets[k].points[i]
                return (
                  <td key={k}>
                    {fmt(p.p50)} ({fmt(p.p10)}-{fmt(p.p90)})
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <footer>
        Weather data by Open-Meteo.com (CC BY 4.0), modified. NASA POWER data courtesy of NASA
        Langley Research Center.
      </footer>
    </main>
  )
}
