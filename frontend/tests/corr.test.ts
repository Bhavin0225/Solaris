import { test } from 'node:test'
import assert from 'node:assert/strict'
import { corrSentences } from '../src/lib/corr.ts'

const keys = ['t1_kw', 't5_kw', 'ghi', 'rh', 'ws10']
const labels = { t1_kw: 'Solar', t5_kw: 'Wind', ghi: 'Sunlight', rh: 'Humidity', ws10: 'Wind speed' }
// real values: t1-ghi 0.99, t5-ws10 0.84, t1-rh -0.61, ghi-rh -0.59, others <= 0.24
const M = [
  [1, 0.1, 0.99, -0.61, 0.2],
  [0.1, 1, 0.05, 0.24, 0.84],
  [0.99, 0.05, 1, -0.59, 0.15],
  [-0.61, 0.24, -0.59, 1, -0.2],
  [0.2, 0.84, 0.15, -0.2, 1],
]

test('real values give 4 sentences strongest first', () => {
  const s = corrSentences(keys, M, labels)
  assert.equal(s.length, 4)
  assert.deepEqual(s.map((x) => x.r), [0.99, 0.84, -0.61, -0.59])
  assert.match(s[0].text, /Sunlight/)
  assert.match(s[0].text, /Solar/)
  assert.equal(s[0].text, 'Solar and Sunlight rise together (r = 0.99): solar output is computed from the sunlight reaching the panels.')
  assert.equal(s[2].text, 'Solar and Humidity move in opposite directions (r = -0.61): the same cloud and night effect, passed through to solar output.')
  assert.ok(s[1].text.endsWith("the turbine's power curve turns wind speed into kW, steeply between cut-in and rated speed."))
})

test('pairs without a reason end after the r clause; max 4', () => {
  const all = keys.map((_, i) => keys.map((_, j) => (i === j ? 1 : 0.5)))
  const s = corrSentences(keys, all, labels)
  assert.equal(s.length, 4)
  const noReason = corrSentences(['t1_kw', 't5_kw'], [[1, 0.5], [0.5, 1]], labels)
  assert.equal(noReason[0].text, 'Solar and Wind rise together (r = 0.50)')
  assert.equal(corrSentences(['t1_kw', 't5_kw'], [[1, 0.49], [0.49, 1]], labels).length, 0)
})
