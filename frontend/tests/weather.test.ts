import { test } from 'node:test'
import assert from 'node:assert/strict'
import { condition, CONDITION_LABEL, dayAggregate } from '../src/lib/weather.ts'

test('condition thresholds', () => {
  assert.equal(condition(0.5, 0, true), 'rain')
  assert.equal(condition(0.4, 70, true), 'cloudy')
  assert.equal(condition(0, 30, true), 'partly')
  assert.equal(condition(null, 30, false), 'partly-night')
  assert.equal(condition(0, 29, true), 'sunny')
  assert.equal(condition(null, null as unknown as number, false), 'clear')
})

test('CONDITION_LABEL', () => {
  assert.deepEqual(CONDITION_LABEL, {
    rain: 'Rain', cloudy: 'Cloudy', partly: 'Partly cloudy', 'partly-night': 'Partly cloudy', sunny: 'Sunny', clear: 'Clear',
  })
})

const t0 = Date.parse('2026-11-09T18:30:00Z') // IST midnight, 10 Nov
const pt = (h: number, o: Partial<{ temp: number; cloud: number; precip: number | null; is_day: boolean }>) => ({
  time: new Date(t0 + h * 3600e3).toISOString(),
  temp: 20, cloud: 0, precip: 0, is_day: (h + 24) % 24 >= 6 && (h + 24) % 24 < 18, ...o,
})

test('dayAggregate groups by local date', () => {
  const points = [
    pt(-1, { temp: 99, cloud: 100 }), // 9 Nov 23:00 local, night only
    pt(1, { temp: 15 }),
    pt(10, { temp: 30, cloud: 80 }),
    pt(12, { temp: 28, cloud: 40, precip: 0.2 }), // daytime mean cloud 60 -> partly
    pt(26, { temp: 22, precip: 1.0 }), // 11 Nov 02:00 night rain
    pt(36, { temp: 25, cloud: 10, precip: 0.6 }), // 11 Nov 12:00 day rain
  ]
  const days = dayAggregate(points, 'Asia/Kolkata')
  assert.deepEqual(days.map((d) => d.dateKey), ['2026-11-09', '2026-11-10', '2026-11-11'])
  assert.equal(days[0].condition, 'cloudy') // no daytime hours: mean of all, day icon set
  assert.deepEqual(
    { firstMs: days[1].firstMs, high: days[1].high, low: days[1].low, condition: days[1].condition },
    { firstMs: t0 + 3600e3, high: 30, low: 15, condition: 'partly' },
  )
  assert.ok(Math.abs(days[1].rainMm - 0.2) < 1e-9)
  assert.equal(days[2].condition, 'rain')
  assert.ok(Math.abs(days[2].rainMm - 1.6) < 1e-9)
})

test('night-only clear day uses sunny, not clear', () => {
  const days = dayAggregate([pt(1, { cloud: 0 })], 'Asia/Kolkata')
  assert.equal(days[0].condition, 'sunny')
})
