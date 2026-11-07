---
phase: 05-walking-skeleton-lightgbm
plan: 04
subsystem: api
tags: [fastapi, apscheduler, sqlite, openapi]
requires:
  - phase: 05-03
    provides: swf.api.db, swf.api.refresh
  - phase: 05-02
    provides: models/registry.json
provides:
  - swf.api.main (create_app, app), schemas, summary, run
  - docs/openapi.json
affects: [05-05, 07]
key-files:
  created: [src/swf/api/schemas.py, src/swf/api/summary.py, src/swf/api/main.py, src/swf/api/run.py, docs/openapi.json, tests/test_api_summary.py, tests/test_api_endpoints.py, tests/test_api_perf.py, tests/test_api_scheduler.py, tests/test_api_stale.py, tests/test_served_model.py]
  modified: [tests/conftest.py]
key-decisions:
  - "Summary window computed with ZoneInfo, but all returned timestamps are UTC Z (D-12)"
  - "Refresh function is imported lazily inside the lifespan so importing swf.api.main stays light"
requirements-completed: [API-01, API-02, API-04, API-05, API-06, API-07]
completed: 2026-11-07
---

# Phase 5 Plan 04: FastAPI app Summary

**Six sync endpoints over the SQLite cache with Z-suffixed Pydantic schemas, a next-IST-day summary, a startup + hourly background refresh (max_instances=1, coalesce=True), stale flag after 2 h, static mount last, and a published docs/openapi.json.**

## Accomplishments
- /api/health, /forecast (hours 1..72), /forecast/summary, /history (days 1..7), /metrics (stdlib csv), /site; 503 on an empty cache; 422 on out-of-range params.
- Committed registry serves "baseline3" for all five targets (tests/test_served_model.py, no skips).
- Outage (ConnectError and 503) leaves the cache served with stale true, age_minutes >= 180.
- Import hygiene subprocess test passes; create_app touches no disk.
- Best-of-5 /api/forecast is well under 500 ms.
- `serve` CLI subcommand already existed (cli.py); run.py uses workers=1 and host from the CLI default 127.0.0.1; no 0.0.0.0 anywhere.

## Task Commits
1. Schemas and IST summary: 7bb0321
2. App, endpoints, run.py: 39d9665
3. Scheduler/stale/served-model tests, openapi.json: 414b219

## Deviations from Plan
- Added a shared `seed` fixture to tests/conftest.py (Tasks 2 and 3 both need a seeded DB) instead of a per-file fixture.

## Known Stubs
None.

## Self-Check: PASSED
Full default suite: 352 passed, 30 deselected. Commits exist; files exist. STATE.md and ROADMAP.md untouched.
