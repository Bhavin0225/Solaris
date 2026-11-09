---
phase: 06-deep-models-selection-final-evaluation
plan: 03
subsystem: deep model (LSTM/GRU)
tags: [lstm, pytorch, residual-on-b3, gpu]
requires: [06-01]
provides: [swf.predict.lstm, swf.models.seq, train-lstm, models/lstm, val/lstm.parquet]
affects: [06-04, 06-06]
key-files:
  created: [src/swf/predict/lstm.py, src/swf/models/seq.py, tests/test_deep_real.py, models/lstm/lstm.pt, models/lstm/lstm.json]
  modified: [src/swf/predict/registry.py, src/swf/cli.py, tests/synth.py, tests/test_deep_seq.py, tests/test_cli.py, reports/evaluation/leaderboard.csv, reports/evaluation/breakdown.csv]
requirements: [MODEL-02]
completed: 2026-11-09
---

# Phase 6 Plan 03: LSTM/GRU residual seq2seq Summary

Plain-PyTorch 2-layer LSTM seq2seq (168 h encoder, 72 h decoder, 5 joint targets) predicting the residual over baseline 3, trained on the GPU in 34 s; status stable, on the val leaderboard for all five targets.

## Commits
- bc724ec: lazy-torch runtime (weights_only=True), RUNTIMES whitelist lstm/gru, synth.write_tiny_lstm, runtime tests
- ad5181b: trainer (windows, fit_norm, train, save, predict_split, run), train-lstm CLI, trainer tests
- e3e053d: real GPU run artifacts, leaderboard/breakdown val rows, tests/test_deep_real.py

## Sidecar (models/lstm/lstm.json)
- status: **stable**, reason: "" (ended by early stopping, all losses finite)
- best_epoch 3, epochs_run 11, wall 34.4 s, n_fit 6544 origins (stride 3), n_es 1448
- best ES loss (2023-H2 tail, standardised residual MSE): 0.4100; train loss falls to 0.15 by epoch 11, so the net overfits fast (early stop at epoch 3 is doing real work)
- Deadline (2026-11-10T18:29:59Z) was not hit; no D-18 stop, no NaN.

## Val RMSE (shared scored mask, leaderboard.csv)
| target | baseline3 | lightgbm | lstm |
|---|---|---|---|
| t1_kw | 137.33 | 71.64 | 71.36 |
| rh | 11.22 | 7.10 | 8.18 |
| ghi | 155.91 | 83.46 | 83.04 |
| ws10 | 1.446 | 1.141 | 1.137 |
| t5_kw | 580.5 | 479.9 | 464.6 |

LSTM beats baseline 3 on all five and edges LightGBM on four (not rh). Differences from LightGBM are small; selection is Phase 6 plan work, not decided here.

## HP runs
Single run, config/deep.yaml unchanged (hidden 128, layers 2, dropout 0.2, lr 1e-3): best_epoch 3, best es_loss 0.4100. The optional extra HP runs and GRU were skipped (stable result on the first run; no tuning on val/test). GRU remains available via `lstm.rnn: gru`.

## Deviations
- [Rule 1 - Bug] predict_p50 referenced `meta` on the cached path (UnboundLocalError on the 2nd target); the cache now stores (array, targets). Caught by test_predict_p50_cached.
- [Rule 1 - Bug] windows() returned a read-only y view; now a copied array.
- Realdata test asserts leaderboard has a val lstm row for each target (5 rows, grep gate = 5).

## Notes
- train-lstm never names the final-holdout split and never touches the registry; no lstm.parquet exists outside val/.
- Bands: val residual quantiles by horizon bucket stored in sidecar band_offsets (D-17).
- evaluate --split val also refreshed val plots and docs/data_notes.md notes block (committed).
- Full default suite and realdata (deep + lgbm) pass. STATE.md / ROADMAP.md untouched.

## Self-Check: PASSED
