---
phase: 05-walking-skeleton-lightgbm
plan: 02
subsystem: models
tags: [lightgbm, residual, baseline3, bands, registry, leaderboard]
requires:
  - phase: 05-01
    provides: LgbmCfg, swf.predict bands/registry/lgbm runtime
provides:
  - swf.models.lgbm (split_fit_es, to_grid, fit_bucket, save_bucket, run)
  - 15 text boosters + sidecars under models/lightgbm/, models/registry.json
  - val/lightgbm.parquet and lightgbm val rows on the leaderboard
affects: [05-03, 05-04, 06]
key-files:
  created: [src/swf/models/__init__.py, src/swf/models/lgbm.py, tests/test_lgbm_train.py, tests/test_lgbm_real.py, models/registry.json, models/lightgbm/]
  modified: [docs/data_notes.md, reports/evaluation/leaderboard.csv, reports/evaluation/breakdown.csv, reports/evaluation/rmse_by_horizon_val.png, reports/evaluation/skill_val.png]
key-decisions:
  - "Registry pins baseline3 for all five targets (D-13); LightGBM kept as candidate for Phase 6 (MODEL-05)"
requirements-completed: [MODEL-01, MODEL-04]
duration: 40min
completed: 2026-11-07
---

# Phase 5 Plan 02: LightGBM training Summary

**15 residual-on-baseline-3 LightGBM boosters (5 targets x 3 horizon buckets, hourly origins, early stopping on a purged 2023-H2 tail) with val residual-quantile bands; LightGBM beats baseline 3 on validation RMSE for every target, but the registry still serves baseline3 (D-13).**

## Results (val 2024, shared sample)

| target | lightgbm RMSE | baseline3 RMSE | skill vs b3 | daytime [p10,p90] coverage |
|---|---|---|---|---|
| t1_kw | 71.64 | 137.3 | 0.478 | 0.800 |
| rh | 7.102 | 11.22 | 0.367 | 0.800 |
| ghi | 83.46 | 155.9 | 0.465 | 0.800 |
| ws10 | 1.141 | 1.446 | 0.211 | 0.800 |
| t5_kw | 479.9 | 580.5 | 0.173 | 0.800 |

Coverage is in-sample on val by construction (all within [0.70, 0.90]); honest check is test in Phase 6. best_iteration per booster, n_train_rows and n_es_rows are in docs/data_notes.md ("LightGBM training (Phase 5)"). Early-stopping rows are > 0 for every booster. No LightGBM test file exists. The training run takes about 3 minutes.

## Task Commits
1. Task 1 training module + synthetic tests: fd822fb (style pass follow-up commit)
2. Task 2 real run, leaderboard, registry, realdata test, data notes: a85fd15

## Deviations from Plan
- [Rule 1 - Bug] The issue_time alignment assert compared tz-aware Timestamps (object array from `grid`) with naive datetime64 and always failed; changed to a `pd.DatetimeIndex` comparison. Fixed before the first successful run.
- Residual-identity check in the synthetic test is trivial (arithmetic identity); the substantive check is that predict_p50 equals b3 + booster.predict.

## Known Stubs
None.

## Self-Check: PASSED
Default suite 316 passed (30 realdata deselected); `pytest -m realdata tests/test_lgbm_real.py` 4 passed. registry.json has 5 `"runtime": "baseline3"`, 0 lightgbm; 15 .txt + 15 .json boosters; 5 lightgbm val rows in leaderboard.csv.
