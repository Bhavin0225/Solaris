---
phase: 07-frontend-full-local-site
plan: 08
subsystem: frontend
tags: [visual-verification, owner-review, performance, polish]
requires: [07-05, 07-06, 07-07]
requirements-completed: [UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09]
metrics:
  completed: 2026-11-10
---

# Phase 7 Plan 08: Visual verification, owner review and sign-off Summary

The full local site ("Solaris") was checked in the browser at 1440x900 and 375x812, light and dark, against the reference video, then refined over several owner review rounds. **Owner approved on 2026-11-10 ("Approve").**

## Functional checks (Playwright, against `python -m swf serve`)
- All 4 pages render with no console errors; at 375 px `scrollWidth <= viewport` on every page, bottom nav visible, sidebar hidden.
- Hover on one Energy panel highlights the same hour on all five (6 active dots).
- ModelBadge click lands on `/performance#target-{key}` with the section in view; reloading a page URL returns the SPA (no 404).
- Stale check on a temp copy of `data/app.db` served on port 8001: "Stale" pill and stale banner shown; the real DB untouched.
- Scroll performance under 6x CPU throttle: ~415-470 frames / 3 s on every page.

## Fixes and owner-requested changes (all committed separately, revertible)
- Layout: page-wide horizontal overflow on phones fixed (single-column grids use `minmax(0,1fr)`); weather "Today" card and Updated time fixed; donut and Now label fixes; header pills on one line.
- Owner feedback: 12-hour am/pm clock everywhere; translucent glass scrollbar (the native dark scrollbar showed as a black column); frosted sidebar hover pill; greeting "Hello" late at night.
- Weather page made interactive: tap an hour / a day, temperature curve with rain bars, animated icons (reduced-motion aware), range bars, mood tint, sunrise/sunset with sun arc (tested sunrise equation).
- Performance: main-models leaderboard with Show all, grouped by target with a header row per target and a highlighted serving row; round axis ticks; full-width heatmap; sticky jump-to menu.
- The matplotlib PNG figures were replaced by live charts: physics scatters (new `/api/validation`, fixed-seed 1,500-point samples written by `python -m swf validate`), quantile reliability (`rel_q10/50/90` added to `/api/performance` coverage rows), wind capacity factor. Scatter colours restored to the original matplotlib colours (blue; viridis density for wind) at the owner's request.
- Performance regression found and fixed: SVG scatters added ~4,200 nodes and scroll fell to 72 frames / 3 s; scatters now draw on one `<canvas>` each (454 frames, ~1,060 nodes), with mouse hover and tap-to-inspect on touch.
- Visuals: glossier chart panels; blurred aerial wind + solar landscape photo behind the glass (Unsplash, stored locally, owner pick); solid Settings panel; theme switch without thumb artefacts or a gap; Daily totals mini charts; About in two columns.
- Server sends `Cache-Control: no-cache` for the page shell so browsers pick up new builds.
- Site named "Solaris".

## Verification
- `pytest` full suite green; frontend `npm run lint` (0 errors), `npm run build`, `npm test` (25 pass).
- `swf.api` import hygiene intact (no torch/darts/matplotlib/lightgbm/swf.evaluate).
- `evaluate --final` not re-run; no retraining. `python -m swf validate` re-run only to write the scatter samples; metrics and PNGs unchanged.

## Known limitations / not done
- The optional "Simulated 1 MW plant / 3.6 MW turbine" label wording and phone-specific leaderboard cards were offered and not taken.
- Bundle is ~950 kB (build warning only); fine for local use.
