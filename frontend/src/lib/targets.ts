// The five targets in display order (UI-SPEC target table).

export interface Target {
  key: string
  label: string
  short: string
  unit: string
  decimals: number
  simulated: boolean
  hue: string
}

const t = (key: string, label: string, short: string, unit: string, decimals: number, simulated: boolean): Target => ({
  key, label, short, unit, decimals, simulated, hue: `var(--hue-${key})`,
})

export const TARGETS: Target[] = [
  t('t1_kw', 'Solar output', 'Solar', 'kW', 0, true),
  t('t5_kw', 'Wind output', 'Wind', 'kW', 0, true),
  t('ghi', 'Sunlight (GHI)', 'Sun', 'W/m²', 0, false),
  t('rh', 'Humidity', 'RH', '%', 0, false),
  t('ws10', 'Wind speed (10 m)', 'WS', 'm/s', 1, false),
]

const MODEL_NAMES: Record<string, string> = {
  tft: 'TFT',
  baseline3: 'Baseline 3',
  lightgbm: 'LightGBM',
  lstm: 'LSTM',
  gru: 'GRU',
  persistence: 'Persistence',
  climatology: 'Climatology',
  baseline3_raw: 'Baseline 3 (raw)',
  baseline3_corrected: 'Baseline 3 (bias-corrected)',
  baseline3_stitched_raw: 'Baseline 3 (stitched, raw)',
  baseline3_stitched_corrected: 'Baseline 3 (stitched, corrected)',
}

/** Models shown in the short leaderboard; the baseline-3 variants appear under "Show all". */
export const MAIN_MODELS = ['tft', 'lightgbm', 'lstm', 'gru', 'baseline3', 'persistence', 'climatology']

export function modelName(runtime: string): string {
  return MODEL_NAMES[runtime] ?? runtime.replaceAll('_', ' ')
}

export function isSimulated(key: string): boolean {
  return key === 't1_kw' || key === 't5_kw'
}
