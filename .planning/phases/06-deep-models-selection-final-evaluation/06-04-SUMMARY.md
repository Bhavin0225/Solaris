---
phase: 06-deep-models-selection-final-evaluation
plan: 04
subsystem: deep model (TFT)
tags: [tft, darts, quantiles, hard-stop, timing]
requires: [06-01, 06-03]
provides: [swf.predict.tft, swf.models.tft, train-tft]
affects: [06-05, 06-06]
key-files:
  created: [src/swf/predict/tft.py, src/swf/models/tft.py, tests/test_tft.py]
  modified: [src/swf/predict/registry.py, src/swf/cli.py, tests/synth.py, tests/test_cli.py]
requirements: [MODEL-03, MODEL-07]
completed: 2026-11-09
---

# Phase 6 Plan 04: TFT code Summary

darts TFT code path (code and tests only, no GPU run): per-origin D-26 series, lazy darts runtime with native P10/P50/P90, `train-tft` with `--timing-only` / full / `--stop`, wall-clock hard-stop callback (exit 3), two-term timing projection, variable-selection and training-curve outputs.

## Commits
- 1651529: lazy darts runtime (origin_inputs, quantiles, predict_quantiles), `tft` in RUNTIMES, synth helpers, runtime tests
- 1058d96: trainer, CLI, trainer tests

## Research assumption A1 (recorded)
darts 0.48.1 quantile output components are `<target>_q0.100`, `<target>_q0.500`, `<target>_q0.900` (three decimals, not `q0.10`), ordered target-major (all of t1_kw's three, then rh, ...). The runtime raises a ValueError listing actual names on mismatch. Explainer `get_feature_importances()` returns a list of DataFrames per block (one per target component); explain() concatenates and averages them.

## Real-data check (no training)
`_inputs()` on the real interim data builds in about 27 s: 6406 fit origins (stride 3, 138 dropped for NaN label or future covariate), 1448 ES origins, 500 timing origins, n_origins = 17400 (val + test counts only).

## Deviations
- [Rule 1] darts logs `train_loss` per step only; with the default `log_every_n_steps=50` the CSV had no train_loss. make_model sets `log_every_n_steps=1`; curves() averages per epoch.
- [Rule 1] The fit-only callback is stored in the model's hyper-parameters and pickled by darts, and darts safe loading rejects it. The callback class is published at module level with a plain-data `__getstate__`; `scrub(model)` strips callbacks/logger before `model.save` so the served `tft.pt` loads under safe loading (tested with a tiny save/load). The best-epoch checkpoint reload uses `trusted=True` on the checkpoint written seconds earlier by the same process.
- [Rule 2] darts keeps last-epoch weights, so the full run enables `save_checkpoints` and reloads the best (val_loss) checkpoint (`fit(best=True)`).
- Fit/ES origin selection (split_fit_es, stride) lives in `_inputs()` rather than inside `fit()`; `fit()` takes the prepared series. `run()` also accepts `dcfg=`/`inputs=` so tests drive the real code path with tiny synthetic inputs.
- Training rows drop only on NaN labels or future covariates; NaN history/past-covariate cells become the training mean.

## Notes and risks for plan 06-05
- Timing times the in-memory (GPU) model, but `predict_split` loads via `_load(..., map_location="cpu")`; if darts predicts on CPU after load, the real predict term may exceed the timing.json projection. Check the first val chunk speed.
- The timing epoch includes trainer setup overhead (conservative).
- Hard stop tested with an injected clock (halts after epoch 0 of 5, exit 3, AUTO tft block written, no tft.pt).
- Import hygiene verified: `swf.predict.tft`, `swf.predict.registry`, `swf.api.main` import neither darts nor torch. No `predict_split("test")` or test long-file read in swf.models.tft.
- Full default pytest passes. STATE.md / ROADMAP.md untouched.

## Self-Check: PASSED
