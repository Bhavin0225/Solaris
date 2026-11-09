---
phase: 07-frontend-full-local-site
plan: 03
subsystem: frontend
tags: [typescript, helpers, tdd, node-test, timezone]
requires: []
provides:
  - "frontend/src/lib/time.ts: makeFmt(tz), istParts, istTicks, istMidnights, greeting, ageText, dataThrough"
  - "frontend/src/lib/forecast.ts: buildRows, sliceHours, currentIndex, peakOf (+ Forecast/Row/Cell types)"
  - "frontend/src/lib/weather.ts: condition, CONDITION_LABEL, dayAggregate (+ WeatherPoint/DayAgg types)"
  - "frontend/src/lib/corr.ts: corrSentences"
  - "frontend/src/lib/targets.ts: TARGETS, modelName, isSimulated"
affects: [07-04, 07-05, 07-06]
tech-stack:
  added: []
  patterns: ["node --test with native type stripping, .ts import extensions", "tz always passed in from API display_timezone"]
key-files:
  created:
    - frontend/src/lib/time.ts
    - frontend/src/lib/forecast.ts
    - frontend/src/lib/weather.ts
    - frontend/src/lib/corr.ts
    - frontend/src/lib/targets.ts
    - frontend/tests/time.test.ts
    - frontend/tests/forecast.test.ts
    - frontend/tests/weather.test.ts
    - frontend/tests/corr.test.ts
    - frontend/tests/targets.test.ts
  modified: []
decisions:
  - "istTicks uses the tz offset at range start (computed via Intl, not hard-coded); DST shifts inside a range are not handled (IST has none) - marked as a shortcut comment"
  - "corrSentences takes labels as Record<key,label>; sentence order is matrix order (A = earlier target), e.g. 'Solar and Sunlight rise together (r = 0.99): ...'"
  - "condition() accepts null cloud as well as null precip (both treated as 0)"
metrics:
  duration: "~15 min"
  completed: 2026-11-10
  tasks: 2
  files: 10
---

# Phase 07 Plan 03: Frontend pure helpers Summary

Dependency-free TypeScript helpers for IST formatting/ticks (from API tz, 24 h, :30-correct), equal-length synced forecast rows with null-safe bands, UI-SPEC weather condition and day aggregation, correlation sentences, and the target table, all test-first under `node --test` (23 tests green).

## Tasks

| Task | Name | Commits |
| ---- | ---- | ------- |
| 1 | RED + GREEN time.ts, forecast.ts, targets.ts | 711c2c6 (test), 1cdfc59 (feat) |
| 2 | RED + GREEN weather.ts, corr.ts | 58d0f7e (test), 2dd0df4 (feat) |

## Verification

- `cd frontend && node --test "tests/**/*.test.ts"`: 23 pass, 0 fail
- `npx tsc -b`: clean; tests also typecheck with `--strict --types node`
- `grep "Asia/Kolkata" frontend/src/lib/*.ts`: no matches; `hourCycle` present in time.ts
- Corr real-value case: exactly 4 sentences, order 0.99, 0.84, -0.61, -0.59, first mentions Solar and Sunlight

## Deviations from Plan

- **Test fixture fixes during GREEN (Task 2):** the weather test's day-10 cloud values gave a daytime mean of exactly 70 (cloudy, not partly), and its `is_day` used absolute hour offset rather than local hour of day. Both were fixture mistakes, fixed in the test; the implementation follows the spec. Committed with 2dd0df4.

## TDD Gate Compliance

RED commits (711c2c6, 58d0f7e) precede GREEN commits (1cdfc59, 2dd0df4). No refactor commit needed.

## Known Stubs

None.

## Self-Check: PASSED

All 10 files exist; commits 711c2c6, 1cdfc59, 58d0f7e, 2dd0df4 present in git log.
