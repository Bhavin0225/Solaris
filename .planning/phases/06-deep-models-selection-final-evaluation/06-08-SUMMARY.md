---
phase: 06-deep-models-selection-final-evaluation
plan: 08
subsystem: evaluation
tags: [final-evaluation, test-once, registry, tft]
requires: [06-05, 06-06, 06-07]
provides:
  - "models/deployed/registry.json (TFT served for all five targets, D-30)"
  - "test-split leaderboard, breakdown, prob metrics, heatmap, wind CF, reliability and gain figures"
affects: [07, 08]
key-files:
  created: [models/deployed/registry.json, models/deployed/selection_val.json, models/deployed/test_started.json]
  modified: [src/swf/evaluate/final.py, src/swf/features/build.py, src/swf/models/lgbm.py, src/swf/models/seq.py, tests/test_final_real.py, reports/evaluation/leaderboard.csv, reports/evaluation/breakdown.csv, docs/data_notes.md]
requirements-completed: [MODEL-05, MODEL-06, MODEL-07, EVAL-08, EVAL-09, EVAL-10]
metrics:
  completed: 2026-11-09
---

# Phase 6 Plan 08: Single test evaluation Summary

`evaluate --final` ran on real data and the test split (2025) is now opened. Owner decision D-30 (made on validation numbers before the run): TFT is the only served ML model, with baseline 3 as the fallback. TFT beat baseline 3 on validation for all five targets, so TFT is served everywhere. No target falls back to baseline 3 (D-23 not triggered).

## Run history (honest record)

1. First run crashed after writing `test_started.json`: `ValueError: target_table: 1 requested times missing, first 2025-12-31 23:00:00+00:00`. Cause: the target-time table was built on the history index, which ends one hour before the last forecast target. Fix d3da54d: `swf.features.build.target_index` extends the index by `horizon_max`. Validation parity of LightGBM, LSTM and TFT was re-checked after the fix.
2. The owner deliberately deleted `models/deployed/test_started.json` once (recovery rule from the plan). The second run completed with exit 0.
3. Nothing was retrained or retuned after the test split was opened.

Once-guard state: `test_started.json` and `registry.json` are both present, so `evaluate --final` refuses to run again. Recovery is only by a deliberate owner deletion of `test_started.json`.

## Test results (2025, selected = TFT)

| target | val RMSE TFT | val RMSE b3 | test RMSE TFT | test RMSE b3 | test skill vs b3 | test nRMSE % | test P10-P90 coverage |
|---|---|---|---|---|---|---|---|
| t1_kw (solar kW) | 70.53 | 137.3 | 63.61 | 132.19 | 0.519 | 7.95 | 0.806 |
| ghi (W/m²) | 84.22 | 155.9 | 72.39 | 148.82 | 0.514 | 16.20 | 0.791 |
| rh (%) | 7.078 | 11.22 | 6.522 | 11.41 | 0.428 | 9.41 | 0.743 |
| ws10 (m/s) | 1.124 | 1.446 | 1.157 | 1.381 | 0.162 | 25.61 | 0.662 |
| t5_kw (wind kW) | 466.0 | 580.5 | 552.47 | 689.96 | 0.199 | 15.35 | 0.684 |

TFT beats baseline 3 on test for every target. No target selected on validation does worse than baseline 3 on test.

Wind capacity factor (test, TFT vs observed): all 0.319 vs 0.328, monsoon 0.522 vs 0.467, dry 0.216 vs 0.257 (RMSE CF 0.153, best of all models; baseline 3 0.192).

## Known limitation (owner decision 2026-11-09: report, do not fix)

TFT P10-P90 intervals are too narrow on wind: test coverage 0.662 (ws10) and 0.684 (t5_kw) against the nominal 0.80. They were already narrow on validation (0.695 / 0.718). rh is also below nominal (0.743). Solar and GHI are close to 0.80. No post-test recalibration was done, because fitting on what the test showed would no longer be an honest test result. Wind speed has the weakest skill (0.162) of the five targets.

## Fixes made in this plan

- `run_final` reads the git SHA once. The real run read it again after rewriting tracked report files, so the stored registry says `d3da54d...+dirty` while the marker says `d3da54d...`. Both refer to the same commit; the realdata test accepts that one suffix.
- `tests/test_final_real.py::test_registry_fields_real` iterated artifact dict keys instead of paths; fixed to `.values()`.

## Verification

- `pytest -m realdata tests/test_final_real.py`: 5 passed.
- Default suite `pytest -q`: passed.
- `evaluate --final` was not run a third time.

## Figures

reports/evaluation: leaderboard.csv, breakdown.csv, prob_metrics.csv, reliability_val.png, reliability_test.png, skill_heatmap_test.{csv,png} (exact horizons 1/6/24/48/72 h, D-24), wind_cf.{csv,png}, lgbm_gain_importance.{csv,png}; final notes in docs/data_notes.md (AUTO:final).
