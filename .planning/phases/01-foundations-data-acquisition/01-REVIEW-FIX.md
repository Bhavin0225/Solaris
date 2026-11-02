---
phase: 01-foundations-data-acquisition
fixed_at: 2026-11-02T00:00:00Z
review_path: .planning/phases/01-foundations-data-acquisition/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-11-02
**Source review:** .planning/phases/01-foundations-data-acquisition/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

Full `uv run pytest -q` passes. Work was done in the main tree, not a worktree (clean tree, no concurrent session).

## Fixed Issues

### WR-01: NASA frame built from positional lists
**Files modified:** `src/swf/fetch/parse.py`, `tests/test_parse.py`
**Commit:** f7613a5
**Applied fix:** Build the frame from the dict of dicts so columns align on timestamp keys. Test with reordered keys added.

### WR-02: Sentinel check uses `assert`
**Files modified:** `src/swf/fetch/parse.py`, `tests/test_parse.py`
**Commit:** b743a6c
**Applied fix:** Explicit `ValueError`; `min().dropna()` so all-missing columns pass. Tests added for all-missing and a surviving -950 value.

### WR-03: Division by zero on empty payload
**Files modified:** `src/swf/fetch/nasa.py`, `src/swf/fetch/openmeteo.py`, `tests/test_nasa_fetch.py`, `tests/test_openmeteo_fetch.py`
**Commit:** 59d0b66
**Applied fix:** Both summarizers raise `ValueError` on zero rows. Both `run()` functions now also catch `ValueError` and `KeyError` (JSONDecodeError is a ValueError; NASA also catches StopIteration) and return 1.

### WR-04: No timeout on kaggle subprocess
**Files modified:** `src/swf/fetch/kaggle.py`, `tests/test_kaggle.py`
**Commit:** b574906
**Applied fix:** `timeout=1800`; `TimeoutExpired`/`OSError` log and return False. Existing kwargs assertion updated; timeout test added.

### WR-05: Data and sidecar not replaced as one unit
**Files modified:** `src/swf/fetch/cache.py`, `tests/test_cache_atomic.py`
**Commit:** c42e5ab (shared with WR-06, both are in cache.py)
**Applied fix:** The old sidecar is deleted before the data is replaced on a re-fetch. `is_cached` also now requires the sidecar sha256 to match the data bytes (a malformed sidecar counts as a miss). Tests: sha mismatch is not a hit; a crash during `--force` leaves the file not cached.

### WR-06: Retry ignores Retry-After
**Files modified:** `src/swf/fetch/cache.py`, `tests/test_cache_atomic.py`
**Commit:** c42e5ab
**Applied fix:** Custom tenacity wait uses `max(backoff, Retry-After)` capped at 300 s. A 429 whose body mentions "daily" is no longer retried. Tests added for both.

---

_Fixed: 2026-11-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
