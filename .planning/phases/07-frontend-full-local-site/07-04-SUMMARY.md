---
phase: 07-frontend-full-local-site
plan: 04
subsystem: frontend
tags: [react, motion, react-router, react-query, glass-shell]
requires: [07-01, 07-02, 07-03]
provides:
  - "frontend/src/api.ts: TS types for every endpoint, ApiError, hooks useForecast/useHealth/useSummary/useWeather/useMetrics/usePerformance/useCorrelation/useSite/useBuild/useTz"
  - "frontend/src/components/ui.tsx: GlassCard, Stagger, useItemVariants, IconChip, TargetIcon, ModelBadge, SimulatedTag, SourceTag, StatusPill, StaleBanner, StateBlock, FigureCard, PageHeader"
  - "Segmented, CountUp, MatrixGrid components"
  - "Shell (sidebar, top bar + settings theme popover, bottom nav, footer) and routed App with blur page transition"
  - "pages/{Energy,Weather,Performance,About}.tsx with headers"
affects: [07-05, 07-06, 07-07, 07-08]
tech-stack:
  added: []
  patterns:
    - "Motion children of Stagger call useItemVariants() (opacity/y/blur, opacity-only under reduced motion)"
    - "refetchInterval function: 30 s while last error is ApiError 503, else 5 min"
    - "Site name and display tz only from /api/site; components degrade to neutral copy until it loads"
key-files:
  created:
    - frontend/src/api.ts
    - frontend/src/components/ui.tsx
    - frontend/src/components/Segmented.tsx
    - frontend/src/components/CountUp.tsx
    - frontend/src/components/MatrixGrid.tsx
    - frontend/src/components/Shell.tsx
    - frontend/src/pages/Energy.tsx
    - frontend/src/pages/Weather.tsx
    - frontend/src/pages/Performance.tsx
    - frontend/src/pages/About.tsx
  modified:
    - frontend/src/App.tsx
decisions:
  - "PageHeader API: title, subtitle, secondary (status pill content, not a button), primary {to,label}, children (slot under the subtitle for the Energy temperature chip)"
  - "Top bar shows site.name only (config has no state field); the UI-SPEC 'Davanagere, Karnataka' literal is not reproduced"
  - "Footer data-through uses build.data_through as returned by /api/build (backend already applies D-44)"
  - "CountUp drives a React state per frame (no direct DOM writes) so it is StrictMode-safe"
metrics:
  duration: "~25 min"
  completed: 2026-11-10
---

# Phase 7 Plan 04: Glass shell and shared components Summary

Typed API layer with react-query hooks, the shared UI primitives (cards, badges, banners, state blocks, figure card, segmented toggle, count-up, matrix grid), and the glass shell with a sidebar, settings theme popover, bottom nav, provenance footer and an AnimatePresence blur transition across the four routes.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | api.ts and shared primitives | 4d58f60 |
| 2 | Shell, routes with page transition, page headers | c73f294 |

## Verification

- `npm run lint` exit 0 (one warning: `useItemVariants` hook exported from ui.tsx, fast-refresh only), `npm run build` exit 0, `npm test` 23/23 pass.
- `grep -rn "Asia/Kolkata\|Davanagere\|14.4\|75.9" frontend/src` empty; `grep -rn dangerouslySetInnerHTML frontend/src` empty; api.ts has no absolute URLs.
- `localStorage` appears once in Shell.tsx, inside the try block.
- Smoke: `python -m swf serve`, `curl /about` returned HTML with `<div id="root">`; `/api/build` and `/api/site` answer.

## Deviations from Plan

**1. [Rule 3 - Blocking] Removed unused `frontend/src/assets/react.svg`**
- The Vite template SVG path data matched the `14.4` grep gate. It was not imported anywhere. Deleted in c73f294.

**2. [Rule 1 - Bug] FigureCard error state uses React state**, not DOM insertion, so a missing figure renders "Figure not found: {name}" on the paper surface without fighting React's reconciler.

**3. Minor:** Energy and Weather headers also show the "Updated HH:mm IST" secondary pill from the UI-SPEC (cheap, uses forecast/weather run_time). Stagger uses plain staggerChildren without the 8th-item delay cap (shortcut comment in ui.tsx).

## Known Stubs

- Page bodies are headers only by design; sections land in 07-05 (Energy), 07-06 (Weather, Performance), 07-07 (About).
- ModelBadge links to `/performance#target-{key}`; scrolling to that hash is left to the Performance page (07-06), React Router does not scroll to hashes itself.

## Threat Flags

None. All mitigations from the plan's register are in place (no dangerouslySetInnerHTML, try/catch storage, relative fetches, rel="noopener noreferrer" on every target=_blank).

## Self-Check: PASSED

- Files exist: all 10 created files and App.tsx.
- Commits found: 4d58f60, c73f294.
