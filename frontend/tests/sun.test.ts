import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sunTimes, sunFraction } from '../src/lib/sun.ts'

// Davanagere-like site; values from the config, not hard-coded in src.
const LAT = 14.4644
const LON = 75.9218
const IST = 5.5 * 3600e3

test('sunrise/sunset near 06:20 / 17:55 IST in mid November at 14.5 N', () => {
  const noonIst = Date.parse('2026-11-10T06:30:00Z') // 12:00 IST
  const { rise, set } = sunTimes(noonIst, LAT, LON)
  const riseIst = new Date(rise + IST).toISOString().slice(11, 16)
  const setIst = new Date(set + IST).toISOString().slice(11, 16)
  const mins = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3))
  assert.ok(Math.abs(mins(riseIst) - (6 * 60 + 20)) <= 12, `rise ${riseIst}`)
  assert.ok(Math.abs(mins(setIst) - (17 * 60 + 55)) <= 12, `set ${setIst}`)
  assert.ok(set - rise > 11 * 3600e3 && set - rise < 12 * 3600e3)
})

test('sunFraction is 0..1 by day, null at night', () => {
  const rise = 1000
  const set = 2000
  assert.equal(sunFraction(1500, rise, set), 0.5)
  assert.equal(sunFraction(999, rise, set), null)
  assert.equal(sunFraction(2001, rise, set), null)
})
