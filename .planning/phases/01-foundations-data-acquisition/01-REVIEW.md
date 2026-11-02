---
phase: 01-foundations-data-acquisition
reviewed: 2026-11-02T00:00:00Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - config/plant.yaml
  - config/site.yaml
  - pyproject.toml
  - src/swf/__init__.py
  - src/swf/__main__.py
  - src/swf/cli.py
  - src/swf/core/__init__.py
  - src/swf/core/geometry.py
  - src/swf/core/paths.py
  - src/swf/core/settings.py
  - src/swf/coverage/__init__.py
  - src/swf/coverage/probe.py
  - src/swf/coverage/report.py
  - src/swf/fetch/__init__.py
  - src/swf/fetch/cache.py
  - src/swf/fetch/kaggle.py
  - src/swf/fetch/nasa.py
  - src/swf/fetch/openmeteo.py
  - src/swf/fetch/parse.py
  - tests/conftest.py
  - tests/test_cache_atomic.py
  - tests/test_cache_meta.py
  - tests/test_cli.py
  - tests/test_config.py
  - tests/test_coverage.py
  - tests/test_geometry.py
  - tests/test_gpu.py
  - tests/test_kaggle.py
  - tests/test_nasa_fetch.py
  - tests/test_openmeteo_fetch.py
  - tests/test_packaging.py
  - tests/test_parse.py
findings:
  critical: 0
  warning: 6
  info: 3
  total: 9
status: issues_found
---

# Phase 1: Code Review Report

**Depth:** standard. Source files in src/ were read in full. Tests were only partly read (test_cache_atomic.py and test_gpu.py in full; the rest skimmed by size only).

## Summary

No blockers. The core guarantees hold:
- UTC is forced on both APIs (`time-standard=UTC`, `timezone=GMT`).
- The -999 sentinel is masked to NaN in parse.py and counted as missing in summaries.
- Cache writes are atomic, with the sidecar replaced last as the commit marker.
- Retries cover only 429/5xx and transport errors.
- Path parts are regex-validated.
- The kaggle subprocess uses an argv list (no shell) and never reads credentials.

The weak spots are in robustness and silent-misalignment edges.

## Warnings

### WR-01: NASA frame built from positional lists, so parameters can silently misalign
**File:** `src/swf/fetch/parse.py:14-15`
**Issue:** The index comes from the first parameter's keys, and every column is `list(v.values())`. If any parameter has a different key order or length, pandas either raises an unclear error or, with equal lengths but a different order, silently assigns values to the wrong timestamps. This is the one place where raw data becomes the modelling frame.
**Fix:** Align on the keys:
```python
df = pd.DataFrame(params)            # dict of dicts aligns on the key index
df.index = pd.to_datetime(df.index, format="%Y%m%d%H", utc=True)
```

### WR-02: Sentinel check uses `assert`
**File:** `src/swf/fetch/parse.py:17`
**Issue:** The post-mask guard disappears under `python -O`. Also, `df.min() > -900` is hard-coded and ignores `fill`. NaN-only columns compare False, so an all-missing column fails the assert.
**Fix:** Raise `ValueError` explicitly. Check `(df == fill).any().any()` and `df.min().dropna() > -900`.

### WR-03: Division by zero in the summarizers on an empty payload
**File:** `src/swf/fetch/nasa.py:45`, `src/swf/fetch/openmeteo.py:78`
**Issue:** `rows == 0` raises `ZeroDivisionError`. `summarize` runs before anything is written, so nothing is cached. The error is not an `httpx.HTTPError`, so `run()` crashes with a traceback instead of returning 1. The same applies to `KeyError` or `JSONDecodeError` on a 200 response with an error body.
**Fix:** Guard with `rows or 1`, or raise a clear `ValueError`. Catch `(httpx.HTTPError, ValueError, KeyError)` in the `run()` functions.

### WR-04: No timeout on the kaggle subprocess
**File:** `src/swf/fetch/kaggle.py:54`
**Issue:** `runner(...)` has no `timeout=`, so a hung CLI (auth prompt or network stall) blocks `swf data` forever.
**Fix:** Pass `timeout=1800`. Handle `subprocess.TimeoutExpired` and `OSError` by returning False.

### WR-05: Data and sidecar are not replaced as one unit on `--force`
**File:** `src/swf/fetch/cache.py:94-95`
**Issue:** `os.replace(tmp, dest)` happens first, then the sidecar. A crash between the two leaves new data with the old sidecar. `is_cached` is True, so the file is never refetched, and the stale sha256, rows and pct_missing describe different bytes. Only the coverage integrity pass catches it, and only if it is run.
**Fix:** On `force`, delete the old sidecar before replacing the data. A crash then leaves "not cached" and the file is refetched.

### WR-06: Retry ignores `Retry-After` and no timeout is set on retried 429s
**File:** `src/swf/fetch/cache.py:62-69`
**Issue:** The backoff is 2/4/8/16/32 s and the 6 attempts total roughly 62 s. An Open-Meteo minute or hourly limit hit (HTTP 429) can outlast that. A daily-limit 429 is retried pointlessly and then raises.
**Fix:** Honour the `Retry-After` header, or raise `max`/attempts for 429. Fail fast when the reason says the daily limit was exceeded.

## Info

### IN-01: Smoke call repeats every run in split-lead mode
**File:** `src/swf/fetch/openmeteo.py:92-107`, `src/swf/fetch/openmeteo.py:174-176`
**Issue:** A 400 response is never cached, so when the all-leads smoke call is rejected it is re-issued on each run until all years are cached. This is only a wasted call, not a correctness bug.

### IN-02: `write_auto_block` writes non-atomically
**File:** `src/swf/coverage/report.py:201-203`
**Issue:** An interrupted write truncates docs/data_notes.md, which contains hand-written text outside the markers. Write to a temp file and `os.replace`.

### IN-03: GPU test is not excluded from the default run
**File:** `tests/test_gpu.py`, `pyproject.toml` addopts
**Issue:** Only `-m 'not network'` is applied. The gpu test is skipped via `importorskip` when torch is absent, but fails in a torch-CPU environment. Add `and not gpu` to addopts if CPU-only CI is ever used.

---

_Reviewed: 2026-11-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
