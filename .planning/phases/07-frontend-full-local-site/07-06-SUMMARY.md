---
phase: 07-frontend-full-local-site
plan: 06
subsystem: frontend
tags: [performance, recharts, leaderboard, coverage, heatmap]
requires: [07-01 read-only endpoints, 07-04 shell + shared components]
provides: [Performance page (UI-06), ModelBadge anchor destination (UI-05), Ring component]
affects: [frontend/src/components/MatrixGrid.tsx (additive format prop)]
tech-stack:
  added: []
  patterns: [Recharts Bar `shape` instead of deprecated Cell, hash scroll effect after data load]
key-files:
  created: [frontend/src/components/Ring.tsx]
  modified: [frontend/src/pages/Performance.tsx, frontend/src/components/MatrixGrid.tsx]
decisions:
  - "Served runtime per target = /api/build models[key], fallback /api/forecast targets[key].model"
  - "Nominal coverage 0.80 is a code constant (definition of a P10-P90 band); all observed coverage values come from the API"
  - "Humidity note is shown only when rh coverage < 80%, so it never states something false"
metrics:
  duration: ~25 min
  completed: 2026-11-10
---

# Phase 07 Plan 06: Performance page Summary

The Performance page now shows the full honest test-year results from the API: skill cards anchored at `#target-{key}`, skill-vs-baseline-3 bars, P10–P90 coverage rings with the wind "Less reliable" flag and humidity note, error by horizon (served vs dashed baseline 3), the full leaderboard with the served row pinned, a season-toggled skill heatmap, and the four validation/reliability figures.

## Tasks

| # | Task | Commit |
|---|------|--------|
| 1 | Ring, skill cards, skill bars, coverage card | c80d096 |
| 2 | Error by horizon, leaderboard, heatmap, figures, hash scroll | fa58a61 |

## Verification

- `npm run lint` (warnings only, none in Performance/Ring), `npm run build`, `npm test` (23 pass): green.
- Grep for hard-coded coverage numbers (0.66/0.68/0.74/66%/68%/74%) in Performance.tsx: none.
- Live API: `/api/figures/reliability_test`, `solar_plant_1_scatter`, `solar_plant_2_scatter`, `wind_scatter` all return 200; `/api/build` serves tft for all five; coverage rows match the plan's figures.

## Deviations from Plan

**1. [Rule 3 - Blocking] MatrixGrid `format` prop (shared component, additive)**
- MatrixGrid hard-printed `v.toFixed(2)`; the heatmap needs signed %. Added optional `format?: (v) => string`, default `v.toFixed(2)`, so the correlation grid is unchanged. Commit fa58a61.

**2. Recharts `Cell` replaced by Bar `shape`**
- `Cell` is deprecated in Recharts 3.10 (removed in 4.0). Per-target bar hue is set via `shape={(p) => <Rectangle {...p} fill={hue} />}`. Same visual result.

## Notes

- Heatmap cell text switches to `--on-primary` when fill opacity > 0.45 for contrast in both themes.
- Leaderboard first column is sticky with an opaque `--card-chart` background; non-first rows of a group carry an sr-only target label.
- Visual check in a browser was not done (no browser tool in this run); a `python -m swf serve` started for verification is still running on :8000.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: frontend/src/components/Ring.tsx, frontend/src/pages/Performance.tsx
- FOUND commits: c80d096, fa58a61
