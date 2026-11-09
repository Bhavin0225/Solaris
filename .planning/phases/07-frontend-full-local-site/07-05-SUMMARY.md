---
phase: 07-frontend-full-local-site
plan: 05
subsystem: frontend
tags: [react, recharts, energy-page, syncId]
requires: [07-04]
provides:
  - "components/ForecastPanel.tsx: ForecastPanel, ForecastChart, plus helpers useIsLg, useNow, fmtNum, chartSentence"
  - "pages/Energy.tsx: header, stale banner, target cards, 72 h chart, daily totals, correlation card"
affects: [07-08]
tech-stack:
  added: []
  patterns:
    - "One buildRows + sliceHours result is passed to every panel; each panel has its own Tooltip (syncId=forecast, default index sync)"
    - "Line/band animation only during the first 700 ms after the chart mounts; off under reduced motion"
    - "useNow() re-reads the clock every minute, so the Now line and current-hour card values move on a page left open"
key-files:
  created:
    - frontend/src/components/ForecastPanel.tsx
  modified:
    - frontend/src/pages/Energy.tsx
decisions:
  - "Chart hues stay CSS var() values on SVG attributes (stroke/fill/fillOpacity), with no getComputedStyle resolution. Chrome accepts var() in presentation attributes, but this was not checked in a browser in this plan"
  - "Midnight 'Wed 11' and 'Now' labels sit on the top panel only, so they are not repeated five times"
  - "Strong correlation cell text uses CSS light-dark(#ffffff, #04202f), because index.css has no corr-text token (it follows color-scheme, which is dark under [data-theme=dark])"
  - "'Updated HH:mm IST' uses health.last_success and falls back to forecast.run_time"
  - "Phone sizes (panel 100/240 px, matrix cell 48 px) come from a matchMedia hook (useIsLg), not CSS, because the Recharts responsive prop needs a numeric height"
metrics:
  duration: "~20 min"
  completed: 2026-11-10
---

# Phase 7 Plan 05: Energy page Summary

The Energy page has five target cards (count-up P50, P10–P90, sparkline, model badge, Simulated energy tag), a synchronized five-panel 72 h Recharts chart on a numeric IST time axis, daily totals with a combined-energy donut (default Tomorrow), and a 5x5 correlation grid with plain-language explanations.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | ForecastPanel and ForecastChart | 46c4dc1 |
| 2 | Energy page sections | 76235be |

## Verification

- `npm run lint` passes with 0 errors. The only warnings are only-export-components (fast refresh) for the helper exports. `npm run build` passes; there is a chunk-size advisory only. `npm test` 23/23 pass.
- ForecastPanel.tsx contains `syncId="forecast"`, `type="number"`, `ReferenceLine`, `Tooltip`, `band` and `sliceHours`, and has no `ResponsiveContainer`.
- Energy.tsx contains useSummary, StaleBanner, SimulatedTag, ModelBadge, MatrixGrid, corrSentences, PieChart, "from Open-Meteo" and "Daily totals". `grep hue | grep -i temp` returns nothing. No "Davanagere" or "Asia/Kolkata" anywhere in frontend/src.
- Live check: `python -m swf serve` on the new build. `/api/forecast/summary?day=today` returned 200, `day=tomorrow` returned a full payload (peak_hour 06:00Z, which displays as 11:30 IST), and `/`, `/api/correlation` and `/api/weather` all answered.

## Deviations from Plan

- Minor, additive: ForecastPanel.tsx also exports `useIsLg`, `useNow`, `fmtNum` and `chartSentence`, which Energy reuses. No shared component in components/ was changed.
- The daily-totals caption reads "Rest of today, from HH:mm IST" or "{Wed 11 Nov}, IST day". The plan only asked for "rest of today".

## Known Stubs

None.

## Not verified

- No visual or hover check in a browser. Still to confirm by eye: cross-panel hover sync (Assumption A5; fallback is `syncMethod="value"`), that var() hues render, and the light-dark() text.

## Self-Check: PASSED

- Files exist: frontend/src/components/ForecastPanel.tsx, frontend/src/pages/Energy.tsx.
- Commits found: 46c4dc1, 76235be.
