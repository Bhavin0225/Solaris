// Typed API layer. Mirrors src/swf/api/schemas.py; every time is an ISO UTC string with Z.
// Relative /api URLs only (same origin; Vite proxy in dev). Display tz always comes from the API.
import { useQuery } from '@tanstack/react-query'

export interface Point { time: string; p10: number | null; p50: number | null; p90: number | null }
export interface TargetForecast { unit: string; model: string; points: Point[] }
export interface Forecast {
  run_time: string; stale: boolean; age_minutes: number; display_timezone: string
  targets: Record<string, TargetForecast>
}
export interface Health {
  status: 'ok' | 'stale' | 'empty'; last_success: string | null; run_time: string | null
  stale: boolean; age_minutes: number | null
}
export interface Summary {
  window_start: string; window_end: string; display_timezone: string; n_hours: number
  solar_kwh: number; wind_kwh: number; peak_hour: string | null; mean_rh: number | null
  max_wind: number | null; run_time: string; stale: boolean
}
export interface MetricsRow {
  split: string; target: string; model: string; norm_kind: string | null; feature_spec_hash: string | null
  n_own: number | null; n_shared: number | null; rmse_own: number | null; shared_frac: number | null
  mae: number | null; rmse: number | null; mbe: number | null; nrmse_pct: number | null; norm: number | null
  skill_vs_baseline3: number | null; skill_vs_persistence: number | null
}
export interface Metrics { rows: MetricsRow[] }
export interface WeatherPoint { time: string; temp: number | null; cloud: number | null; precip: number | null; is_day: boolean }
export interface Weather { display_timezone: string; run_time: string; points: WeatherPoint[] }
export interface Correlation { targets: string[]; matrix: number[][]; period_start: string; period_end: string; n: number }
export interface CoverageRow { target: string; model: string; n: number; coverage: number | null; width: number | null; pinball: number | null }
export interface HorizonRow {
  target: string; model: string; horizon: number; n: number; rmse: number | null; mae: number | null
  nrmse_pct: number | null; skill_vs_baseline3: number | null
}
export interface HeatmapRow { target: string; model: string; season: string; horizon: number; skill_vs_baseline3: number | null }
export interface WindCfRow {
  season: string; model: string; n: number; observed_cf: number | null; predicted_cf: number | null; rmse_cf: number | null
}
export interface Performance { coverage: CoverageRow[]; horizon: HorizonRow[]; heatmap: HeatmapRow[]; wind_cf: WindCfRow[] }
export interface BuildInfo {
  git_sha: string | null; registry_git_sha: string | null; schema_version: number | null; final_split: string | null
  models: Record<string, string>; data_through: string | null; kaggle: { solar_slug: string; wind_slug: string }
}
export interface SiteInfo {
  site: { name: string; latitude: number; longitude: number; elevation_m: number; display_timezone: string }
  solar: {
    dc_kwp: number; tilt_deg: number; azimuth_pvlib_deg: number; dc_ac_ratio: number; eta_inv_nom: number
    gamma_pdc: number; loss_pct: number; transposition: string; albedo: number
  }
  wind: {
    rated_kw: number; hub_height_m: number; availability_loss: number; cut_in_ms: number; rated_ms: number
    cut_out_ms: number; power_curve_csv: string
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new ApiError(r.status, typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
  }
  return r.json() as Promise<T>
}

const MIN5 = 5 * 60e3
// 503 = server has nothing cached yet (empty state): poll faster until it arrives.
const poll = (q: { state: { error: Error | null } }) => (q.state.error instanceof ApiError && q.state.error.status === 503 ? 30e3 : MIN5)
const fixed = { staleTime: Infinity } as const

export const useForecast = () =>
  useQuery({ queryKey: ['forecast'], queryFn: () => getJson<Forecast>('/api/forecast?hours=72'), refetchInterval: poll })
export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: () => getJson<Health>('/api/health'), refetchInterval: poll })
export const useSummary = (day: 'today' | 'tomorrow') =>
  useQuery({
    queryKey: ['summary', day],
    queryFn: () => getJson<Summary>(`/api/forecast/summary?day=${day}`),
    refetchInterval: poll,
  })
export const useWeather = () =>
  useQuery({ queryKey: ['weather'], queryFn: () => getJson<Weather>('/api/weather'), refetchInterval: poll })
export const useMetrics = () => useQuery({ queryKey: ['metrics'], queryFn: () => getJson<Metrics>('/api/metrics'), ...fixed })
export const usePerformance = () =>
  useQuery({ queryKey: ['performance'], queryFn: () => getJson<Performance>('/api/performance'), ...fixed })
export const useCorrelation = () =>
  useQuery({ queryKey: ['correlation'], queryFn: () => getJson<Correlation>('/api/correlation'), ...fixed })
export const useSite = () => useQuery({ queryKey: ['site'], queryFn: () => getJson<SiteInfo>('/api/site'), ...fixed })
export const useBuild = () => useQuery({ queryKey: ['build'], queryFn: () => getJson<BuildInfo>('/api/build'), ...fixed })

// Display timezone from the site config; undefined until /api/site answers.
export const useTz = (): string | undefined => useSite().data?.site.display_timezone
