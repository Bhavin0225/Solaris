---
phase: 08-reproducibility-viva-readiness
plan: 02
subsystem: evaluate
tags: [evaluate, reproducibility, fresh-clone]
requires: []
provides:
  - "`swf evaluate` never overwrites committed ML rows on a partial split; SKIPPED list; own-sample MISMATCH guard (exit 2)"
  - "stored Phase 6 test-year outputs rebuilt via final.write_reports, gated on models/deployed/test_started.json"
affects: [08-04, 08-05]
key-files:
  modified:
    - src/swf/evaluate/report.py
    - tests/test_evaluate_report.py
decisions:
  - "Both tasks touched the same two files and were committed together (a358988)"
metrics:
  completed: 2026-11-10
---

# Phase 8 Plan 02: evaluate on a fresh clone Summary

`swf evaluate` now re-scores every model that has a prediction file, writes a split to leaderboard/breakdown only when no committed model is missing, checks `n_own`/`rmse_own` of partial splits against the committed rows (exit 2 + MISMATCH on difference), prints a SKIPPED list naming only absent ML models, never calls `run_final`, and rebuilds test-year tables/figures from the stored run when `test_started.json`, `selection_val.json` and `registry.json` exist.

## Commits
- a358988: feat(08-02) report.py + 5 new tests (fresh-clone byte identity, own-sample mismatch, never run_final, stored rebuild called / skipped)

## Owner-laptop check (real data)
- `uv run python -m swf evaluate` exit 0; all reports/evaluation CSVs and all PNGs byte-identical (git status of reports/ and config/ empty).
- PNG table: rmse_by_horizon_val, skill_val, gfs_bias_val, reliability_val, reliability_test, skill_heatmap_test, wind_cf, lgbm_gain_importance: all byte-identical.
- docs/data_notes.md differed, then restored with `git checkout`. Besides the expected `git sha:` line, the AUTO:evaluation block gained 13 test-split rows for lightgbm/lstm/tft (the committed block predates the test ML rows, which only `--final` added to the CSV) and one rounding flip (t5_kw baseline3_corrected nrmse 21.25 vs 21.24, in-memory value vs CSV-rounded). Finding, not a code bug: the CSVs match; the committed notes block is just older than the CSV.
- `tft_training_curves.png`, `tft_variable_selection.*` come from `train-tft`; validation scatters from `validate` (in the `data` chain). evaluate does not rebuild them.

## Deviations from Plan
None in code. Tests were written together with the code rather than strictly RED-first.

## Self-Check: PASSED (commit a358988 exists; report.py and test file present)
