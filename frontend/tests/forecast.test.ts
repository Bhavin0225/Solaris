import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildRows, sliceHours, currentIndex, peakOf } from '../src/lib/forecast.ts'

const t0 = Date.parse('2026-11-09T16:00:00Z')
const iso = (i: number) => new Date(t0 + i * 3600e3).toISOString()
const pts = (n: number, fn: (i: number) => number | null) =>
  Array.from({ length: n }, (_, i) => ({ time: iso(i), p10: fn(i), p50: fn(i), p90: fn(i) }))

const fc = {
  run_time: '2026-11-09T15:00:00Z',
  stale: false,
  age_minutes: 5,
  display_timezone: 'Asia/Kolkata',
  targets: {
    t1_kw: { unit: 'kW', model: 'tft', points: pts(72, (i) => i) },
    ghi: { unit: 'W/m²', model: 'tft', points: pts(70, () => 1) },
  },
}

test('buildRows truncates to shortest series and shapes cells', () => {
  const rows = buildRows(fc)
  assert.equal(rows.length, 70)
  assert.equal(rows[0].t, t0)
  assert.deepEqual(rows[3].t1_kw, { p50: 3, p10: 3, p90: 3, band: [3, 3] })
})

test('band null when a quantile is null', () => {
  const f2 = { ...fc, targets: { rh: { unit: '%', model: 'x', points: [{ time: iso(0), p10: null, p50: 4, p90: 6 }] } } }
  assert.equal(buildRows(f2)[0].rh.band, null)
  assert.equal(buildRows(f2)[0].rh.p50, 4)
})

test('sliceHours', () => {
  const rows = buildRows({ ...fc, targets: { t1_kw: fc.targets.t1_kw } })
  assert.equal(sliceHours(rows, 24).length, 24)
  assert.equal(sliceHours(rows, 72), rows)
})

test('currentIndex', () => {
  const rows = buildRows(fc)
  assert.equal(currentIndex(rows, t0 - 1), 0)
  assert.equal(currentIndex(rows, t0 + 2.5 * 3600e3), 2)
  assert.equal(currentIndex(rows, t0 + 1e12), rows.length - 1)
})

test('peakOf', () => {
  const rows = buildRows(fc)
  assert.deepEqual(peakOf(rows, 't1_kw'), { t: t0 + 69 * 3600e3, p50: 69 })
  const nulls = buildRows({ ...fc, targets: { rh: { unit: '%', model: 'x', points: pts(3, () => null) } } })
  assert.equal(peakOf(nulls, 'rh'), null)
})
