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
}

export function modelName(runtime: string): string {
  return MODEL_NAMES[runtime] ?? runtime.replaceAll('_', ' ')
}

export function isSimulated(key: string): boolean {
  return key === 't1_kw' || key === 't5_kw'
}
