---
phase: 03-physics-validation-gate
plan: 03
subsystem: validation
tags: [wind, kaggle, nrmse]
requires: [03-01]
provides: [load_t1, simulate_t1, wind_metrics]
key-files:
  created: [src/swf/validate/kaggle_wind.py, tests/test_validate_wind.py]
requirements-completed: [VAL-03]
completed: 2026-11-03
---

# Phase 3 Plan 03: Wind validator Summary

Pure functions parsing T1.csv strictly and scoring the unchanged production wind chain (standard air) against LV ActivePower, next to the manufacturer curve on identical rows.

## Results on real T1.csv (read-only from main checkout)
- full_year sim 12.12% vs reference 12.94% (n=50530); ref_slice 12.31% vs 13.08% (n=10098); jan_to_ref 12.08% vs 12.90%. Gate pass = True.
- energy_ratio 0.877; availability measured 3.54% (the `ws > 4 and lv <= 0` definition as implemented; RESEARCH quoted ~4.6%, config 3.5%).

## Deviations
None. Tests: 8 in tests/test_validate_wind.py. Full suite: 184 passed, 1 skipped, 21 deselected; ruff clean.

## Self-Check: PASSED
