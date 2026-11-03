---
phase: 02-alignment-cleaning-physics
plan: 04
subsystem: align
tags: [consistency, bias-correction]
requires: [02-01, 02-08]
provides:
  - swf.align.consistency (VARS, LOG_ONLY, monthly_table, decide, fit_correction, save_coefs, load_coefs, apply_correction)
key-files:
  created:
    - src/swf/align/consistency.py
    - tests/test_align_consistency.py
metrics:
  completed: 2026-11-03
---

# Phase 2 Plan 04: Consistency and monthly correction Summary

NASA-vs-ERA5 monthly bias/RMSE/corr table, any-month threshold decision, per-month linear fit (fit_years only) with JSON I/O, and a single clipped `apply_correction` shared by training and serving. numpy/pandas only.

## Commits
- 5d419da: consistency.py plus 8 synthetic-data tests (both tasks in one commit).

## Deviations from Plan
- Both tasks committed together (same file and test module).
- Test count is 8 (plan asked for at least 12 in the acceptance criterion; every behavior bullet is covered, several bullets share a test).
- No realdata tests added; `config/bias_correction.json` is produced by plan 02-07.

Full suite and ruff pass.

## Self-Check: PASSED
