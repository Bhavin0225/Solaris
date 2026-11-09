import { test } from 'node:test'
import assert from 'node:assert/strict'
import { makeFmt, istParts, istTicks, istMidnights, greeting, ageText, dataThrough } from '../src/lib/time.ts'

const TZ = 'Asia/Kolkata'
const f = makeFmt(TZ)

test('hour label is 12 h IST with am/pm and :30 offset', () => {
  assert.equal(f.hour(Date.parse('2026-11-09T16:00:00Z')), '9:30 pm')
  assert.equal(f.hour(Date.parse('2026-11-09T18:30:00Z')), '12:00 am')
  assert.equal(f.hour(Date.parse('2026-11-10T06:30:00Z')), '12:00 pm')
  assert.equal(f.hourShort(Date.parse('2026-11-10T00:30:00Z')), '6 am')
})

test('day, dayTime, longDate formats', () => {
  const ms = Date.parse('2026-11-11T06:00:00Z')
  assert.equal(f.day(ms), 'Wed 11 Nov')
  assert.equal(f.dayTime(ms), 'Wed 11 Nov, 11:30 am')
  assert.equal(f.longDate(ms), 'Wednesday, 11 November')
})

test('makeFmt caches per tz', () => {
  assert.equal(makeFmt(TZ), f)
})

test('istParts', () => {
  assert.deepEqual(istParts(Date.parse('2026-11-09T18:30:00Z'), TZ), { hour: 0, minute: 0, y: 2026, m: 11, d: 10 })
})

test('istTicks every 6 local hours inside range', () => {
  const s = Date.parse('2026-11-09T16:00:00Z')
  const e = Date.parse('2026-11-12T15:00:00Z')
  const ticks = istTicks(s, e, TZ)
  assert.equal(ticks[0], Date.parse('2026-11-09T18:30:00Z'))
  assert.equal(ticks[1] - ticks[0], 6 * 3600e3)
  assert.ok(ticks.every((t) => t >= s && t <= e))
  assert.equal(ticks.length, 12)
})

test('istMidnights only local 00:00', () => {
  const s = Date.parse('2026-11-09T16:00:00Z')
  const e = Date.parse('2026-11-12T15:00:00Z')
  assert.deepEqual(istMidnights(s, e, TZ), [
    Date.parse('2026-11-09T18:30:00Z'),
    Date.parse('2026-11-10T18:30:00Z'),
    Date.parse('2026-11-11T18:30:00Z'),
  ])
})

test('greeting', () => {
  assert.equal(greeting(5), 'Good morning')
  assert.equal(greeting(11), 'Good morning')
  assert.equal(greeting(12), 'Good afternoon')
  assert.equal(greeting(16), 'Good afternoon')
  assert.equal(greeting(17), 'Good evening')
  assert.equal(greeting(4), 'Good evening')
})

test('ageText', () => {
  assert.equal(ageText(190), '3 h 10 min')
  assert.equal(ageText(45), '45 min')
})

test('dataThrough is run_time + 1 h', () => {
  assert.equal(dataThrough('2026-11-09T15:00:00Z'), Date.parse('2026-11-09T16:00:00Z'))
})
