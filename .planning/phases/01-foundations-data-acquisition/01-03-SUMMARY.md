---
phase: 01-foundations-data-acquisition
plan: 03
subsystem: data-acquisition
tags: [open-meteo, gfs_seamless, era5, httpx]
requires: [01-02, 01-06]
provides:
  - swf.fetch.openmeteo (ENDPOINTS, base_params, year_params, live_params, summarize, pr_accepts_all_leads, fetch_years, fetch_live, run)
  - data/raw/openmeteo/{archive/era5,historical_forecast/gfs_seamless,previous_runs/gfs_seamless,forecast/gfs_seamless} (git-ignored)
  - tests/fixtures/om_live_gfs_seamless.json (+ .meta.json) for the Phase 4 parity test
affects: [01-05]
key-files:
  created: [src/swf/fetch/openmeteo.py, tests/test_openmeteo_fetch.py, tests/fixtures/om_hf_sample.json, tests/fixtures/om_pr_sample.json, tests/fixtures/om_era5_sample.json, tests/fixtures/om_live_gfs_seamless.json, tests/fixtures/om_live_gfs_seamless.meta.json]
key-decisions:
  - "Previous Runs smoke (1 day, 42 names) was ACCEPTED: all-leads mode, one file per year (2024.json, 2025.json)"
  - "Archive always sends models=era5; gfs_seamless for HF, PR, live"
requirements-completed: [DATA-02, DATA-04]
completed: 2026-11-02
---

# Phase 1 Plan 03: Open-Meteo fetch Summary

Stdlib-only Open-Meteo fetchers (ERA5, GFS Historical Forecast, GFS Previous Runs day1-3, live) on the shared cache primitive; all real pulls cached and one live response committed as a fixture.

## Task commits
1. 10038b9 fetchers and request-contract tests
2. Live fixture + 264-row test (see git log "test(01-03)"); the pull itself changes no source (data git-ignored)

## Real pull results
- Smoke mode: **all-leads** (42-name request accepted, no 400); run logged `previous_runs mode: all-leads`.
- Files: ERA5 25, HF 5, PR 2 (+ smoke), live 1 = 33 data requests. Total about 24-25 MB (ERA5 18.0 MB, HF 3.6 MB, PR 3.7 MB incl. smoke, live 28 KB).
- Retries/429/503 during the successful run: none (0 warnings in log).
- Re-run of era5/historical/previous: 32 cache hits, 0 network fetches.
- Every ERA5 sidecar URL has models=era5; every HF/PR/live sidecar URL has models=gfs_seamless.
- Snapped grid / elevation: ERA5 14.5/76.0, 598 m; GFS (HF, PR, live) 14.467949/75.9375, 598 m. NASA uses a different, coarser cell.
- Missingness: HF 2021 shortwave/RH/wind80 22.2% (before 2021-03-23, as expected); HF 2025 0%; PR 2024 wind_speed_80m_previous_day1 12.64% (expected ~13%); ERA5 2001 0%; live 264 rows, 0%.
- `uv run pytest -q`: all pass.

## Deviations from Plan
- **Outage (not a code deviation):** Task 2 was first attempted during an Open-Meteo overload (HTTP 503, then 429 after retries). Nothing was cached or invented; the pull was resumed later from Task 2 after services recovered, with Task 1 left as committed.

## Self-Check: PASSED
