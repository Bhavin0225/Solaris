---
phase: 06-deep-models-selection-final-evaluation
plan: 07
subsystem: evaluation
tags: [selection, final-evaluation, once-guard, registry, lightgbm]
requires: [06-02, 06-03, 06-04]
provides:
  - "swf.evaluate.final: CANDIDATES, select, select_from_reports, guard, git_sha, build_registry, write_reports, run_final"
  - "swf.models.lgbm.predict_frame / predict_split (serving-path LightGBM predictions, no refit)"
  - "python -m swf evaluate --final"
affects: [06-08]
key-files:
  created: [src/swf/evaluate/final.py, tests/test_final_eval.py]
  modified: [src/swf/models/lgbm.py, src/swf/evaluate/report.py, src/swf/cli.py, tests/test_lgbm_train.py, tests/test_lgbm_real.py, tests/test_cli.py]
requirements-completed: [MODEL-05, MODEL-06, MODEL-07, EVAL-08, EVAL-09, EVAL-10]
metrics:
  completed: 2026-11-09
---

# Phase 6 Plan 07: Selection and once-only final evaluation Summary

`evaluate --final` selects the serving model per target on validation (shared-sample `rmse`, `min_shared_frac`, must beat baseline 3), then opens the test split exactly once and writes `models/deployed/registry.json` last. The code is written and tested on synthetic tmp data only. The command was NOT run on real data.

## What was built

- `select` / `select_from_reports`: validation rows only, `rmse` column (not `rmse_own`), candidates below `min_shared_frac` listed but cannot win, ties follow CANDIDATES order, no winner gives baseline3 with reason "no ML model beat baseline 3 on validation" (D-23).
- `guard`: refuses (exit 1, names the file) when `test_started.json` or `registry.json` exists in `models/deployed/`; no override flag anywhere (D-28).
- `run_final` order: guard, preconditions, selection, `selection_val.json`, `test_started.json` (git SHA and split dates only), test predictors for each candidate, `score_split("test")` merged into leaderboard/breakdown, `write_reports`, `save_registry` last. A crash leaves the marker, so a rerun is refused until the owner deletes it.
- `build_registry`: all MODEL-06 fields per target; top level split_dates, git_sha, final_split, selection_split, baseline3_choice, buckets. NaN metrics are stored as null.
- `write_reports`: prob_metrics.csv, reliability_{val,test}.png, skill_heatmap_test.{csv,png}, wind_cf.{csv,png}, lgbm_gain_importance.{csv,png}, AUTO:final notes block (selection table, D-23 sentences, LSTM/GRU training summary, 3-point reliability caveat, val bands in-sample, W1 skew, D-26 ERA5-vs-live skew). Baseline 3 bands are built in memory only; no baseline3 parquet is rewritten.
- `lgbm.predict_frame/predict_split`: reuse `swf.predict.lgbm.predict_p50` and the stored validation band offsets. Realdata parity test `test_predict_split_val_parity` reproduces the committed val/lightgbm.parquet (atol 1e-3), writing to tmp only.
- `evaluate --final` flag in cli.py, dispatched from `report.run`.

## Deviations from Plan

None of substance. `predict_split` defaults the Phase 5 registry to `models_root/registry.json` so the injected models_root is honoured. `run_final` also checks that the test baseline parquets exist before the marker is written, so a missing `baselines` run cannot burn the marker.

## Verification

- tests/test_final_eval.py (test_select, test_select_reads_no_test, test_once_guard x2 markers, test_crash_leaves_marker, test_registry_fields, test_run_final_order, test_write_reports, test_heatmap, test_wind_cf) pass.
- Realdata test_lgbm_real.py (including parity) passes.
- No `models/deployed/*` and no `data/processed/predictions/test/*` were created (git status clean of both).
- Known nit: ruff import-wrap formatting on one line of final.py (not auto-fixed).

## Next

Plan 06-08 runs `python -m swf evaluate --final` after owner sign-off.
