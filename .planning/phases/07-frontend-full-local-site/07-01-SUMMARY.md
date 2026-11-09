---
phase: 07-frontend-full-local-site
plan: 01
subsystem: api
tags: [fastapi, read-only-endpoints, spa]
requires: []
provides:
  - "GET /api/forecast/summary?day=today|tomorrow"
  - "GET /api/weather, /api/correlation, /api/performance, /api/build, /api/figures/{name}"
  - "SPA fallback static mount (client routes reload to index.html)"
  - "swf.fetch.openmeteo.live_path"
affects: [07-02, 07-04, 07-05, 07-06, 07-07, 07-08]
tech-stack:
  added: []
  patterns: ["paths injected via create_app kwargs; all disk reads inside handlers", "dict allowlist for served files", "lazy imports of pvlib/httpx inside handlers for import hygiene"]
key-files:
  created: [src/swf/api/extras.py, tests/test_api_extras.py]
  modified: [src/swf/api/main.py, src/swf/api/schemas.py, src/swf/api/summary.py, src/swf/fetch/openmeteo.py, tests/test_api_summary.py, docs/openapi.json]
decisions:
  - "Weather window starts at the UTC hour label containing IST midnight (18:00Z), so the Today card includes the 00:00-00:30 IST slice"
  - "Correlation cached per app only on success; FileNotFoundError -> 503"
  - "/api/build reads registry inside the handler; missing/invalid registry -> models {} and None fields (200)"
metrics:
  duration: ~40min
  completed: 2026-11-10
---

# Phase 07 Plan 01: Backend read-only endpoints for the site Summary

Six small read-only FastAPI endpoints plus a `day` param on the summary and an SPA fallback mount, all serving existing files on disk (cached live Open-Meteo JSON, interim parquet, reports CSV/PNG, registry). No new network calls, no retraining.

## What was built

- `ist_day_window(now, tz, day="tomorrow")`: "today" runs from floor(now) UTC to the next IST midnight; `/api/forecast/summary?day=` validated as a Literal (bad value -> 422).
- `live_path(s, root, now)` in `fetch/openmeteo.py`, used by both `fetch_live` and `/api/weather`.
- `src/swf/api/extras.py`: `FIGURES` allowlist, `git_short_sha` (cached, fixed argv, 5 s timeout, failure -> None), `resolve_registry`, `read_csv_rows` (now also used by `/api/metrics`), `weather_points`, `correlation`, `SPAStatic`.
- `/api/weather`: temp/cloud/precip/is_day from IST midnight to run_time + 72 h; 503 when no run or no file.
- `/api/correlation`: 5x5 Pearson for t1_kw, t5_kw, ghi, rh, ws10 (real data: t1-ghi 0.99, t1-rh -0.61).
- `/api/performance`: test coverage, horizon rows (int horizons, season all), heatmap, wind_cf.
- `/api/build`: short git SHA, registry SHA/version/final_split, per-target runtime, data_through = run_time + 1 h (D-44), Kaggle slugs (D-46).
- `/api/figures/{name}`: dict lookup only, 404 for unknown names, traversal attempts, or missing files.
- Live smoke on real data: weather, correlation, performance, build, figures/wind_cf, /performance (SPA) and summary?day=today all return 200.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | f05b3dc | test(07-01): add failing tests for new read-only endpoints and summary day window |
| 2 | 5c1c4b2 | feat(07-01): summary day param, build info, figure allowlist, SPA fallback |
| 3 | c07f2e7 | feat(07-01): weather, correlation and performance endpoints |
| fix | 4289e26 | docs(07-01): regenerate published OpenAPI schema for the new endpoints |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Regenerated docs/openapi.json**
- **Found during:** Task 3 full-suite run
- **Issue:** `tests/test_api_scheduler.py::test_openapi_published` compares the published schema with the live one; the new endpoints made it fail.
- **Fix:** Regenerated with the command in the test docstring.
- **Files modified:** docs/openapi.json
- **Commit:** 4289e26

**2. [Lint] Task 2 was committed with two ruff findings (missing `check=False`, import order); fixed in the Task 3 commit.**

## TDD Gate Compliance

RED `test(07-01)` f05b3dc precedes GREEN `feat(07-01)` 5c1c4b2 and c07f2e7.

## Known Stubs

None.

## Self-Check: PASSED

- Files exist: src/swf/api/extras.py, tests/test_api_extras.py
- Commits f05b3dc, 5c1c4b2, c07f2e7, 4289e26 present in git log
- Full default pytest suite: only failure was test_openapi_published, fixed in 4289e26 and re-run green with all API tests
