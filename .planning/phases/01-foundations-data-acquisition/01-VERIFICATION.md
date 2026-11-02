---
phase: 01-foundations-data-acquisition
verified: 2026-11-02T18:00:00Z
status: passed
score: 5/5 roadmap success criteria verified
overrides_applied: 0
gaps: []
---

# Phase 1: Foundations & Data Acquisition Verification Report

**Phase Goal:** Working GPU environment and every raw data source cached on disk, with coverage facts known well enough to lock D1-D3.
**Status:** passed. Re-verification: No (initial).

## Success Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | uv env from pinned pyproject/uv.lock, CUDA True, pytest passes, config-driven | VERIFIED | `uv run pytest -q` all pass (74 tests, 100%). `uv run python -m swf check-gpu` prints `torch 2.15.0+cu134 cuda 13.4 device NVIDIA GeForce RTX 4060 Laptop GPU`. `pyproject.toml`, `uv.lock`, `config/site.yaml`, `config/plant.yaml`, `src/swf/core/settings.py` exist. |
| 2 | NASA 2001-2025 cached, re-run makes no network calls, log has URL/status/rows/% missing, no -999 survives parsing | VERIFIED | 25 `data/raw/nasa/<yr>.json` plus `.meta.json` (url, http_status 200, rows, pct_missing per column, sha256, retrieved_utc, `time-standard=UTC`). `nasa_to_frame` run on all 25 years: 219,144 rows (matches 25 yrs x hourly), min > -900 in all columns. Raw JSON stays verbatim (-999 present in raw by design, D-14). Cache-skip covered by `test_fetch_years_cache`. |
| 3 | Open-Meteo HF, Previous Runs, ERA5, live forecast cached with URL and retrieval date | VERIFIED | `data/raw/openmeteo/`: `archive/era5` 2001-2025 (25), `historical_forecast/gfs_seamless` 2021-2025 (5), `previous_runs/gfs_seamless` 2024-2025 (+ smoke), `forecast/gfs_seamless/20261102T16.json` with `past_days=7&forecast_days=4`. Every sidecar has url and retrieved_utc. |
| 4 | `docs/data_notes.md` coverage report plus D1-D3 recorded | VERIFIED | AUTO coverage block (grid, inventory, NASA % missing, ERA5 start/data-through, HF and PR per-year/lead gaps, 80/120 m wind); NWP choice (D-06); sections "Decision D1", "D2", "D3" with lead mapping rule; errata list; NASA radiation tail latency noted. |
| 5 | Kaggle files in `data/raw/kaggle/` | VERIFIED | All 5 files present; row counts (wc minus header) match data_notes: 68778 / 3182 / 67698 / 3259 / 50530. |

## Requirements Coverage

All 10 IDs are claimed by plans and are Complete in REQUIREMENTS.md; no orphans.

| Req | Plan | Status |
|---|---|---|
| SETUP-01, SETUP-02, SETUP-04 | 01-01 | SATISFIED (pytest + check-gpu run) |
| SETUP-03, SETUP-04 | 01-06 | SATISFIED (config yamls + pydantic settings) |
| SETUP-05 | 01-04 | SATISFIED (files present, kaggle.py) |
| DATA-01, DATA-03, DATA-04 | 01-02 | SATISFIED (nasa.py, parse.py, sidecars) |
| DATA-02, DATA-04 | 01-03 | SATISFIED (openmeteo.py, sidecars) |
| DATA-05 | 01-05, 01-07 | SATISFIED (coverage package, data_notes AUTO block) |

## Anti-Patterns / Review

01-REVIEW.md: 0 critical, 6 warnings (WR-01..06: positional-list NASA frame, assert-based sentinel check, empty-payload division, kaggle subprocess timeout, non-atomic --force, Retry-After). None breaks a must-have. The assert in `parse.py` is redundant with the `mask` and the verified outcome holds; recommend fixing WR-01/02/05 before Phase 2 relies on `nasa_to_frame`.

## Human Verification

None required.

## Notes

- Did not re-run the "second fetch makes no network" check live (no network allowed); relied on the cache test and sidecar presence.
- Wiring beyond existence for the fetch/coverage modules was checked via passing tests, not read line by line.
