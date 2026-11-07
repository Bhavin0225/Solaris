---
phase: 05-walking-skeleton-lightgbm
plan: 03
subsystem: api
tags: [sqlite, wal, refresh, open-meteo, registry]
requires:
  - phase: 05-01
    provides: swf.predict (baseline, registry, bands), synth helpers
  - phase: 05-02
    provides: models/registry.json
provides:
  - swf.api.db (connect, write_run, read_forecast, read_history, read_meta)
  - swf.api.refresh (origin_for, build_run, refresh)
  - shared fixtures live_raw, live_client, api_env
affects: [05-04, 05-05]
key-files:
  created: [src/swf/api/__init__.py, src/swf/api/db.py, src/swf/api/refresh.py, tests/test_api_db.py, tests/test_api_refresh.py]
  modified: [config/site.yaml, tests/conftest.py, tests/test_openmeteo_fetch.py]
key-decisions:
  - "write_run is one sqlite transaction (forecast + history + meta); only the latest run is kept"
  - "last_success is wall clock at success, not the injected now"
requirements-completed: [API-02, API-03, API-04, API-05]
completed: 2026-11-07
---

# Phase 5 Plan 03: SQLite repository and refresh job Summary

**Atomic SQLite WAL cache plus a refresh job (fetch_live -> serve_features -> registry dispatch -> bands -> DB) that returns False and keeps the cache on any outage, with past_days=8.**

## Accomplishments
- `swf.api.db`: parameterized SQL only, WAL, rollback test and injection-string round-trip test.
- `swf.api.refresh.refresh()` writes 5 x 72 banded rows plus 168 h history per target; baseline3 p50 matches `live_tables` after `enforce`; the lightgbm rh path matches booster residual + b3 (synthetic registry).
- Outage (ConnectError and 503) returns False, retries happen via the injected sleep, previous run and last_success unchanged.
- `config/site.yaml` live past_days 8; spec hash still 3bd1a73d99093287.

## Task Commits
1. SQLite repository: d98d20e
2. Refresh job, past_days=8, fixtures: c9e7a35

## Deviations from Plan

**1. [Rule 1 - plan premise incorrect] 00:xx test**
- Plan said serve_features on the unextended 7-day fixture at origin 2026-11-01T23:00Z raises. It does not: canon labels shift back one hour (interval-start convention), so the fixture starts 2026-10-25T23:00 and the 168 h need is met with zero spare hours.
- Fix: the test asserts that origin passes exactly and origin 22:00 raises (history error), and that the 24 h-extended payload refreshes at now=00:30Z. past_days=8 stays as an extra day of margin, as the plan requires.
- Files: tests/test_api_refresh.py

Formatting used `ruff format --line-length 120` (repo style; no ruff config exists).

## Known Stubs
None.

## Self-Check: PASSED
Full default suite: 329 passed, 30 deselected. Commits d98d20e and c9e7a35 exist; files exist.
