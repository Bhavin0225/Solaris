---
phase: 07-frontend-full-local-site
plan: 02
subsystem: frontend
tags: [tailwind4, design-tokens, theme, providers]
requires: []
provides:
  - "frontend/src/index.css design system (tokens + glass classes, light/dark)"
  - "index.html pre-paint theme script (swf-theme)"
  - "main.tsx provider tree: QueryClientProvider > BrowserRouter > MotionConfig reducedMotion=user"
  - "npm test script (node --test)"
affects: [07-03, 07-04, 07-05, 07-06, 07-07, 07-08]
tech-stack:
  added: [tailwindcss 4.3.5, "@tailwindcss/vite 4.3.5", recharts 3.10.1, motion 14.11.1, lucide-react 1.70.0, "@tanstack/react-query 5.107.1", react-router-dom 7.18.5, "@fontsource-variable/plus-jakarta-sans 5.3.0"]
  patterns: ["@theme inline maps Tailwind colours to per-theme CSS vars (bg-card, text-ink, stroke-t1_kw ...)", "glass classes as @layer components"]
key-files:
  created: []
  modified: [frontend/vite.config.ts, frontend/index.html, frontend/src/main.tsx, frontend/package.json, frontend/src/index.css]
decisions:
  - "@theme inline so colour utilities read the live CSS var and switch with data-theme"
  - "Cards/chart cards carry no backdrop-filter (Pitfall 4), overriding the UI-SPEC card blur column per the plan"
  - "Theme script only accepts 'dark'; any other stored value yields light (T-07-08)"
metrics:
  duration: "~10 min"
  completed: 2026-11-10
---

# Phase 7 Plan 02: Frontend foundation Summary

Tailwind 4 via `@tailwindcss/vite`, the full UI-SPEC token set and glass classes for light and dark, a try/catch pre-paint theme script, and the QueryClient/Router/MotionConfig provider tree.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Owner npm legitimacy gate | owner replied "Approve all" in main session 2026-11-10; install done there (6edee52), `npm ls` re-verified all 8 at pinned versions |
| 2 | Tailwind plugin, theme script, providers, test script | 28cb6f2 |
| 3 | index.css design system | e520598 |

## Verification

- `npm ls` shows all 8 packages at pinned versions; no tailwind.config.* / postcss.config.*.
- `npm run build` and `npm run lint` exit 0.
- `backdrop-filter` appears only in glass-sidebar, glass-bar, glass-panel, popover (plus the `@supports` query and a comment); old `#aa3bff` / `--accent-bg` tokens gone.

## Deviations from Plan

- Added `--text-label/body/heading/display` and named radii (`--radius-chip/card/shell`) to `@theme` so later plans can use `text-heading`, `rounded-card` directly. Minor, no behaviour change.
- `npm test` script exists but `frontend/tests/` does not yet; later plans add test files.

## Known Stubs

None. App.tsx is still the Phase 5 page (replaced in 07-04 per plan); it may look unstyled against the new CSS until then.

## Self-Check: PASSED

- Files exist: frontend/src/index.css, frontend/index.html, frontend/src/main.tsx, frontend/vite.config.ts
- Commits found: 28cb6f2, e520598
