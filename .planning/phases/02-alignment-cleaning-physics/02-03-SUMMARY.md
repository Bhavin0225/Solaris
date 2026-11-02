---
phase: 02-alignment-cleaning-physics
plan: 03
subsystem: align
tags: [clean, gap-fill, clear-sky-index]
requires: [02-01, 02-08]
provides:
  - swf.align.clean (clean, short_gap_mask, REPORT_COLS)
key-files:
  created:
    - src/swf/align/clean.py
    - tests/test_align_clean.py
metrics:
  completed: 2026-11-03
---

# Phase 2 Plan 03: Cleaning Summary

`clean()` reindexes to a complete hourly UTC index, clips to PHYS_RANGES, night-zeroes radiation, and fills interior gaps of at most `max_gap_h` (met linear, direction via sin/cos, radiation via clear-sky index), returning the frame plus a variable x year report.

## Commits
- e2c4591: clean.py and 12 synthetic-gap tests. Tasks 1 and 2 landed in one commit because the fill logic was written together with the reindex/clip code.

## Deviations from Plan
- Single commit for both tasks (see above).
- The report frame holds every variable x year row. Filtering to non-zero rows (the accepted D-12 refinement) is left to the data_notes writer (plan 02-07).
- Tests place midday and night gaps by UTC hour (site is UTC+5:30); the synthetic clear-sky night has small non-zero values at twilight, so night_zeroed is asserted as a delta against an unmodified baseline.

Full suite passes, ruff clean. No realdata tests added.

## Self-Check: PASSED
