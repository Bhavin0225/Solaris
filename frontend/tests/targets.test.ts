import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TARGETS, modelName, isSimulated } from '../src/lib/targets.ts'

test('TARGETS order and table', () => {
  assert.deepEqual(TARGETS.map((t) => t.key), ['t1_kw', 't5_kw', 'ghi', 'rh', 'ws10'])
  assert.deepEqual(TARGETS.map((t) => t.label), ['Solar output', 'Wind output', 'Sunlight (GHI)', 'Humidity', 'Wind speed (10 m)'])
  assert.deepEqual(TARGETS.map((t) => t.short), ['Solar', 'Wind', 'Sun', 'RH', 'WS'])
  assert.deepEqual(TARGETS.map((t) => t.unit), ['kW', 'kW', 'W/m²', '%', 'm/s'])
  assert.deepEqual(TARGETS.map((t) => t.decimals), [0, 0, 0, 0, 1])
  assert.equal(TARGETS[2].hue, 'var(--hue-ghi)')
  assert.deepEqual(TARGETS.map((t) => t.simulated), [true, true, false, false, false])
})

test('modelName', () => {
  const m = { tft: 'TFT', baseline3: 'Baseline 3', lightgbm: 'LightGBM', lstm: 'LSTM', gru: 'GRU', persistence: 'Persistence', climatology: 'Climatology' }
  for (const [k, v] of Object.entries(m)) assert.equal(modelName(k), v)
  assert.equal(modelName('foo_bar'), 'foo bar')
})

test('isSimulated', () => {
  assert.equal(isSimulated('t1_kw'), true)
  assert.equal(isSimulated('t5_kw'), true)
  assert.equal(isSimulated('ghi'), false)
})
