---
phase: 01-foundations-data-acquisition
plan: 02
subsystem: data-acquisition
tags: [httpx, tenacity, nasa-power, cache]
requires: [01-01, 01-06]
provides:
  - swf.fetch.cache (fetch_to_cache, is_cached, make_client, safe_part, RETRY_STATUS)
  - swf.fetch.nasa (build_params, build_params_range, summarize, fetch_years, run)
  - swf.fetch.parse.nasa_to_frame
  - data/raw/nasa/{2001..2025}.json + .meta.json (git-ignored)
affects: [01-03, 01-05]
key-files:
  created: [src/swf/fetch/cache.py, src/swf/fetch/nasa.py, src/swf/fetch/parse.py, tests/fixtures/nasa_sample.json, tests/test_cache_atomic.py, tests/test_cache_meta.py, tests/test_nasa_fetch.py, tests/test_parse.py]
key-decisions:
  - "Sidecar written last via os.replace as the commit marker; cache hit requires both files"
  - "ALLSKY_KT missingness (~48%) is structural (night), not a data fault"
requirements-completed: [DATA-01, DATA-03, DATA-04]
completed: 2026-11-02
---

# Phase 1 Plan 02: NASA fetch and cache Summary

One tested cached-fetch primitive (verbatim bytes, atomic write, sidecar, tenacity backoff, structured log) plus the NASA POWER fetcher and a sentinel-aware parser; the real 2001-2025 pull is on disk.

## Task commits
1. b0ef349 cached-fetch primitive
2. 65604f2 NASA fetcher, summarize, parse
3. Real pull: no source changes (data git-ignored)

## Real pull results
- 25 files + 25 sidecars, 56.7 MB total, wall time 1m49s.
- Second run: 25 `cache hit` lines, 0 `fetch {` lines (no network).
- 2024: 8784 rows, parse leaves 0 sentinels, index tz UTC. ALLSKY_KT 48.04% missing (structural, night).
- No year has any non-KT column with missing values.
- `uv run pytest -q`: 44 passed.

## Deviations from Plan
None. (Fixture created after `tests/fixtures/` dir was made, which did not yet exist.)

## Self-Check: PASSED
