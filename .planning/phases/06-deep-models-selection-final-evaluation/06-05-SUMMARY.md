---
phase: 06-deep-models-selection-final-evaluation
plan: 05
subsystem: modelling
tags: [tft, darts, quantiles, variable-selection, leaderboard]
requires:
  - phase: 06-04
    provides: TFT trainer, train-tft CLI, D-27 timing
provides:
  - TFT val predictions (native P10/P50/P90) and val leaderboard rows for all five targets
  - TFT variable-selection and training-curve figures
  - test_tft realdata test
affects: [06-08 final evaluation, model selection]
key-files:
  created:
    - models/tft/tft.pt
    - models/tft/tft.json
    - reports/evaluation/tft_training_curves.png
    - reports/evaluation/tft_variable_selection.csv
    - reports/evaluation/tft_variable_selection.png
  modified:
    - tests/test_deep_real.py
    - reports/evaluation/leaderboard.csv
    - reports/evaluation/breakdown.csv
    - docs/data_notes.md
key-decisions:
  - "Owner chose full-run after D-27 timing (projected 0.086 h, fits before hard stop)"
requirements-completed: []
duration: ~10 min wall (fit+predict)
completed: 2026-11-09
---

# Phase 6 Plan 05: TFT full run Summary

TFT trained to early stop (best epoch 8, 13 epochs run, patience 5) and scored on val only; it beats baseline 3 on every target and is roughly tied with LSTM and LightGBM.

## Decision and timing (D-27)
Owner decision: **full-run**. timing.json: epoch 9.75 s x 30 = fit 0.081 h, predict 0.0047 h (0.00098 s/origin x 17,400 origins), projected 0.086 h, fits_before_stop true, hard stop 2026-11-11T18:29:59Z (not reached). Exit code 0.

## Val RMSE per target (test split untouched)

| target | baseline3 raw | baseline3 corrected | LightGBM | LSTM | TFT |
|---|---|---|---|---|---|
| t1_kw | 137.3 | 139.1 | 71.64 | 71.36 | **70.53** |
| rh | 12.56 | 11.22 | 7.10 | 8.18 | **7.08** |
| ghi | 155.9 | 155.9 | 83.46 | **83.04** | 84.22 |
| ws10 | 1.446 | 1.698 | 1.141 | 1.137 | **1.124** |
| t5_kw | 580.5 | 697.8 | 479.9 | **464.6** | 466.0 |

(The TFT run printed baseline3 as the raw variant: 137.3 / 11.22 / 155.9 / 1.446 / 580.5; the leaderboard also carries the corrected variant.) Skill vs baseline 3 (leaderboard): t1 0.486, rh 0.369, ghi 0.460, ws10 0.222, t5 0.197. TFT wins 3 of 5 targets on val RMSE versus LSTM and LightGBM, by small margins (differences of 0.1-1.5%, except rh where LSTM is 15% worse); no claim of significance. Selection between models is left to the later selection plan.

## Artifacts
val/tft.parquet (no test/tft.parquet), tft.pt (64 KB) + tft.json committed. Left out of git: models/tft/darts/ (20 MB), tft.pt.ckpt (5 MB), logs/run, logs/timing/hparams.yaml.

## Tests
`pytest -m realdata tests/test_deep_real.py` passes (test_lstm, test_tft); default suite passes.

## Deviations from Plan
None. Task 3 code commit: 6d192e8. Task 1 commit c9668f9.

## Self-Check: PASSED
