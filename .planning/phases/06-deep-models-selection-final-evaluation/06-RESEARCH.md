# Phase 6: Deep Models, Selection & Final Evaluation - Research

**Researched:** 2026-11-07
**Domain:** PyTorch seq2seq + darts TFT on tabular hourly weather/energy series; model selection; frozen final evaluation; registry-driven serving
**Confidence:** MEDIUM-HIGH (codebase and env verified; darts quantile-prediction details verified by signature only, not run)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-15:** Follow the plan order: LSTM/GRU first, then TFT. TFT is kept in scope, time-boxed to the Day-11 hard stop. It is the first item in the cut order only if the time box is missed.
- **D-01 (Phase 4, amended for deep models):** Evaluation uses all hourly origins. Deep-model training MAY subsample origins for speed (stride 3 is the default here).
- **D-03a / D-13:** Official baseline 3 per target = the per-target choice in `config/baseline3_choice.json`. Phase 5 served baseline 3 everywhere; Phase 6 is the first place an ML model can be selected per target.
- **D-07 / D-08:** LightGBM residual over baseline 3 and horizon-bucket structure are the reference for how the deep models must be compared (same leaderboard row format).
- **FEAT-04 / splits:** covariate models train 2021-04 to 2023; validation 2024; test 2025. Purge origins whose 72 h targets cross a split boundary.
- **D-14:** early stopping never sees 2024 rows. For the deep models, the held-out tail is the last part of the 2023 training window, same rule as LightGBM.
- **D-16:** Architecture as in the roadmap: encoder 168 h of past observations, decoder 72 h with known-future covariates, five targets jointly. Plain PyTorch (not darts), so an ONNX export stays possible later.
- **D-17:** Uncertainty for LSTM/GRU uses the same validation-residual bands as LightGBM and baseline 3 (D-09), so the leaderboard compares the same method. No quantile heads.
- **D-18:** Time box: stable by ~Day 10. If unstable by then, report the minimal version honestly (roadmap success criterion 1).
- **D-19:** TFT via darts, multi-target, native P10/P50/P90 outputs, 5 targets. Hard stop Day 11. If it fails or is not finished by the stop, write up the attempt with its training curves.
- **D-20:** TFT is served locally with torch if it wins a target. No ONNX for TFT.
- **D-21:** Per target, the serving model is the one with the lowest validation RMSE that beats the official baseline 3 (PRD 9.4). Selection uses validation only.
- **D-22:** `evaluate --final` runs once on test. Its result is recorded in `models/deployed/registry.json` with the MODEL-06 fields (selected model, runtime, artifact, reason, test metrics, baseline-3 RMSE, band method, feature_spec_hash, split dates, git SHA).
- **D-23:** A target where no ML model beats baseline 3 deploys baseline 3, and the report says so.

### Claude's Discretion
- LSTM/GRU hidden size, layers, learning rate, batch size, dropout and seeds (fixed); small search (no Optuna sweeps).
- TFT hyper-parameters within the time box (at most 3-4 trials).
- Exact figure layout and file names under `reports/evaluation/`.
- Whether GRU is run alongside LSTM. Default: LSTM first; GRU only if time allows.

### Deferred Ideas (OUT OF SCOPE)
- ONNX export and torch-free serving image (v2 cloud deployment).
- Cloud hosting, keep-alive, seed snapshot (v2).
- Front-end redesign and weather tab (Phase 7).
- Optuna-style hyper-parameter sweeps (PRD anti-feature).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODEL-02 | LSTM/GRU seq2seq, plain PyTorch, GPU | Sequence builder from existing `hist` + `assemble` (below); residual-on-b3 design; env verified (torch 2.15.0+cu134, CUDA True, RTX 4060 8 GB) |
| MODEL-03 | TFT (darts) P10/P50/P90, 5 targets | darts 0.48.1 API verified by introspection; list-of-series predict; `predict_likelihood_parameters` |
| MODEL-05 | Selection on val; test once; b3 fallback | Pure `select()` over val leaderboard; once-guard = refuse if deployed registry exists |
| MODEL-06 | `models/deployed/registry.json` fields | Extend Phase 5 registry contract (schema below); git SHA via `git rev-parse HEAD` |
| MODEL-07 | Gain importance + TFT variable selection | `Booster.feature_importance("gain")` on the 15 text boosters; `TFTExplainer.explain().get_feature_importances()` |
| EVAL-08 | coverage, width, pinball, reliability | New `swf.evaluate.prob` over long-format frames (p10/p50/p90 columns already exist) |
| EVAL-09 | skill heatmap target x horizon x season | `breakdown.csv` already has `skill_vs_baseline3` by exact horizon x season |
| EVAL-10 | wind capacity factor, monsoon vs dry | `breakdown` season rows + a small capacity-factor table from t5_kw / `s.wind.rated_kw` |
</phase_requirements>

## Summary

Everything the phase needs is installed and the codebase already provides most pieces. `.venv` has torch 2.15.0+cu134 (CUDA available, RTX 4060 Laptop 8 GB), darts 0.48.1, pytorch-lightning 2.6.6; `pyproject.toml` `[train]` extra already pins them, so **no new packages** [VERIFIED: .venv import + pyproject]. The existing `evaluate` machinery (long format, `align_models`, `leaderboard_rows`, `breakdown`) already scores any model that writes the long format, so the LSTM and TFT only need to write `val/<model>.parquet` and they appear on the leaderboard.

Three real design gaps need planner attention. (1) There is no sequence builder: `origin_table` stores lag columns, not raw series. A 168 h encoder window must be gathered from the same `hist` frame (`history_frame(history_input(era5))`) that `origin_table` is built from, and the decoder tensor can be gotten from `assemble(..., horizons=1..72, cov=...)` (it already does the lead-matched D-02 covariate mapping). (2) Serving: the runtime interface `predict_p50(entry, X, b3, target, models_root)` is per-target with a one-row tabular `X`; a joint 5-target sequence model needs the 168 h history and all five b3 series, and TFT needs native quantiles instead of residual bands. `build_run` in `swf/api/refresh.py` must change (small). (3) `evaluate --final` needs test predictions for every candidate model, but no LightGBM test predictions exist and `lgbm.run` only predicts val inside training, so a `predict_split` is needed (reuse the registry runtime).

**Primary recommendation:** Build one `swf.models.seq` module (window builder + LSTM train + `predict_split`), one `swf.models.tft` module, one `swf.evaluate.final` module (select on val, score test once, write deployed registry + figures), and extend the runtime whitelist with `lstm` and `tft`. Make the LSTM predict the residual over baseline 3 (b3 as a decoder input and added back), matching LightGBM so the comparison is like for like.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Training (LSTM, TFT, LightGBM importance) | Offline CLI (`swf.models.*`) | GPU | Never in the serving process |
| Selection + final evaluation + registry write | Offline CLI (`swf.evaluate.final`) | -- | Reads val predictions and test predictions, writes `models/deployed/registry.json` |
| Runtime inference | API/Backend (`swf.predict.{lstm,tft}`, lazy torch/darts import) | -- | Whitelisted dispatch from registry |
| Bands (LSTM/LGBM/b3 residual quantiles; TFT native) | Offline (computed on val) | API (applies stored offsets) | D-09/D-17 |
| Figures | Offline (`reports/evaluation/*.png`) | Frontend (Phase 7 shows them) | matplotlib only in evaluate/train env |

## Standard Stack

Nothing new to install. [VERIFIED: pyproject.toml, .venv]

| Library | Version | Purpose |
|---------|---------|---------|
| torch | 2.15.0+cu134 | LSTM/GRU, TFT backend; `torch.cuda.is_available()` is True |
| darts | 0.48.1 | `TFTModel`, `QuantileRegression`, `TFTExplainer` |
| pytorch-lightning | 2.6.6 | darts trainer; `pl_trainer_kwargs` for GPU and EarlyStopping |
| lightgbm | 4.7.0 | gain importance from existing text boosters |
| matplotlib | (train extra) | figures; imported lazily only in evaluate/train modules |

### Package Legitimacy Audit
All packages are already installed and pinned in the committed lock; none are new in this phase. No slopcheck run needed. Packages removed: none. Flagged: none.

## Architecture Patterns

### Data flow
```
ERA5 hist (history_input -> history_frame)  --168 h gather-->  encoder tensor [N,168,Ce]
truth_frame (NASA + energy_sim)             --72 h gather--->  targets    [N,72,5]
covariate_table(hf | pr_d{1,2,3}) + target_table + b3_table
      -- assemble(origins, 1..72, cov=hf or {1,2,3: pr_dk}) --> decoder tensor [N,72,Cd]
encoder + decoder --> LSTM seq2seq (residual over b3) --> p50 [N,72,5]
p50 + val residual offsets (bucket quantiles) --> p10/p90   (D-17)
p50/p10/p90 --> make_long(...) --> val/<model>.parquet --> existing evaluate leaderboard
evaluate --final: select(val leaderboard) -> predict test for all candidates -> score once
      -> models/deployed/registry.json + reports/evaluation/* figures
```

### Recommended structure
```
config/deep.yaml                 # DeepCfg pydantic model (like LgbmCfg): lstm + tft sections, seed, stride, es tail
src/swf/models/seq.py            # window builder, LSTM/GRU module, train loop, predict_split, run (train-lstm)
src/swf/models/tft.py            # darts TFT train + predict_split + explainer (train-tft)
src/swf/models/importance.py     # LightGBM gain importance (or put in evaluate/final)
src/swf/evaluate/prob.py         # coverage/width/pinball/reliability (numpy)
src/swf/evaluate/final.py        # select(), score test once, registry, figures
src/swf/predict/lstm.py, tft.py  # lazy-import runtimes
models/lstm/, models/tft/        # artifacts + JSON sidecars
```
CLI: `train-lstm`, `train-tft`, and `evaluate --final` (add the flag to the existing `evaluate` subparser; `swf.evaluate.report.run` dispatches to `final.run` when set).

### Pattern 1: sequence windows from existing tables
- **Encoder:** `hist = history_frame(history_input(raw_era5, s, source="era5"), s, curve, coefs)` (as `lgbm.run` does). `pos = hist.index.get_indexer(origins)`; `idx = pos[:,None] + np.arange(-167, 1)`; `hist[TARGETS].to_numpy()[idx]` gives `[N,168,5]`. Add `csi_hist`-style or calendar channels only if needed; calendar for the encoder can come from `target_table(hist.index)` gathered the same way. NaNs (interpolated cells are masked to NaN): normalise, `nan_to_num` to 0, and append a mask channel per target. Normalisation stats come from fit origins only, stored in the sidecar.
- **Decoder:** `assemble(otab, ttab, origins, range(1,73), cov=cov_tc | cov_val_dict | cov_test_dict, cfg=cfg)` already applies `lead_k` for dict covariates (D-02). Select `COVARIATE_COLS + CALENDAR_COLS + GEOMETRY_COLS` (24 cols) and reshape to `[N,72,24]`. Because the frame also repeats ~76 history columns per row, call it via `iter_features(..., chunk=2000)` and keep only the needed columns, or memory spikes (24k origins x 72 x ~110 x 4 B is ~0.76 GB).
- **b3 inputs/target:** train b3 = `b3_table(hf, s, curve, coefs or None)` per `choice[t]` (stitched, same as LightGBM residual `tgt_y`); val/test b3 = the existing `baseline3_<choice>` long parquet reshaped `[N,72]` (this is what `lgbm.run` does and keeps val/test lead-matched). Decoder input adds the five b3 series (normalised); output = `b3 + out * resid_std` where `resid_std` is per-target train std of `truth - b3`.
- **Targets:** `truth_frame(interim)` gathered by `grid(origins, 1..72)` times, as in `lgbm.tgt_y`. Loss: masked MSE on normalised residuals (ignore NaN truth), summed over five targets. t1_kw/ghi night zeros stay in training (physics clip handles them via `enforce`).
- **Origins:** `split_fit_es(origins_for("train_covariate"), es_tail_start, 72)` reuses D-14 verbatim; train with `origins[::3]` (D-01 amendment), evaluate on every hourly val/test origin.
- **Model:** encoder `nn.LSTM(in, 128, num_layers=2, dropout=0.2, batch_first=True)`; decoder `nn.LSTM` initialised from encoder `(h,c)`, per-step input = decoder features, linear head to 5. One config switch `rnn: lstm|gru` costs nothing. Start: hidden 128, lr 1e-3 AdamW, batch 128, grad-clip 1.0, patience 8, max ~40 epochs. Approx 6-8k windows at stride 3: seconds per epoch on the 4060. Fixed seed; `torch.use_deterministic_algorithms(True, warn_only=True)` and `CUBLAS_WORKSPACE_CONFIG=:4096:8`.
- **Bands:** `residual_offsets(Y, p50, hv, mask, buckets)` from `swf.predict.bands` on val, `band_frame` after, exactly like `lgbm.run`. Copy the daytime mask handling for t1_kw/ghi.
- **Artifact:** `torch.save(state_dict)` + sidecar JSON (`artifact_meta("covariate")`, normalisation stats, column order, hyper-params, seed, epochs). Load with `torch.load(..., weights_only=True)`.

### Pattern 2: TFT via darts (D-19)
- `TFTModel(input_chunk_length=168, output_chunk_length=72, hidden_size=64, lstm_layers=1, num_attention_heads=4, dropout=0.1, batch_size=128, add_relative_index=False, likelihood=QuantileRegression([0.1,0.5,0.9]), random_state=42, pl_trainer_kwargs={"accelerator":"gpu","devices":1,"callbacks":[EarlyStopping("val_loss", patience=5)],"enable_progress_bar":False})`. Signature verified [VERIFIED: introspection]. Multi-target = a 5-component `TimeSeries`; `future_covariates` is mandatory. Normalise manually (store mean/std in sidecar) rather than a darts `Scaler`, so serving can invert it without pickled transformers.
- Training series = truth (5 comp, NASA + energy_sim) over the fit span; `future_covariates` = hf-stitched covariates + calendar + geometry + the five b3 series (b3 as a covariate is how TFT gets the physics prior; target is raw, not residual). `fit(..., val_series=<ES tail with 168 h of context>, val_future_covariates=..., stride=3, max_samples_per_ts=...)`; `fit` has `stride`, `max_samples_per_ts`, `load_best` parameters [VERIFIED]. Fit span must end >= 72 h before `es_tail_start` (reuse `split_fit_es` bounds) so D-14 holds.
- Prediction at val/test origins: covariates are lead-matched per origin so there is no single covariate series. Build per-origin lists: `series=[TimeSeries(target[o-167:o])...]`, `future_covariates=[TimeSeries(cov rows o-167..o+72)...]` where the past part (<= o) uses hf-stitched values and the future part uses `assemble`'s lead-matched rows. One `model.predict(n=72, series=list, future_covariates=list, predict_likelihood_parameters=True, batch_size=512)` call. Output component names are `<comp>_q0.10`, `_q0.50`, `_q0.90` (verify on a tiny model first). `np.sort` across quantiles, un-normalise, `enforce`. Encoder target series at inference comes from `hist` (ERA5 chain, what serving has) while training used truth: a train/serve skew; measure it with one A/B on val if time allows, otherwise document.
- Variable selection (MODEL-07): `TFTExplainer(model, background_series=[...], background_future_covariates=[...]).explain()` returns `TFTExplainabilityResult`; `.get_feature_importances()` gives encoder/decoder DataFrames; plot as bar chart. [VERIFIED: introspection; Context7 darts TFT notebook]
- Budget: <= 3-4 trials (hidden 32/64, dropout, lr). Log per-epoch train/val loss (Lightning logger CSV) for the Day-11 write-up regardless of outcome. Save with `model.save()` (darts pickle + ckpt, trusted local artifact only) under `models/tft/`.
- darts is slow on many series; if prediction time on ~8.7k val + ~8.7k test origins is excessive, evaluating TFT on every 3rd hourly origin violates D-01/EVAL shared index (the leaderboard requires >= 50 % shared fraction per target, `min_shared_frac`), so prefer full origins and cap batch work; decide by timing a 500-origin trial first.

### Pattern 3: selection, final evaluation, registry (MODEL-05/06)
1. `select(leaderboard_val, baseline3_rmse)` is a pure function over val rows only: for each target, among `{lightgbm, lstm, tft}` with `rmse < baseline3 rmse`, pick the lowest val RMSE; otherwise `baseline3` with reason "no ML model beat baseline 3 on validation" (D-23). Unit-test that it never touches the test directory.
2. Once-guard: `evaluate --final` exits non-zero if `models/deployed/registry.json` exists (message names the file; `--force` is NOT offered; the owner deletes the file deliberately). Write selection first (`models/deployed/selection_val.json` optional), then test predictions, then the registry atomically (`save_registry` already writes atomically via `os.replace`).
3. Test predictions for every candidate go through the same runtime modules the API uses: `lgbm.predict_p50` with `assemble(..., cov=cov_test_dict)`; sequence/TFT `predict_split("test")`; b3 from `test/baseline3_<choice>.parquet`; bands from the VAL offsets stored in the registry draft (no refit on test). Write `test/<model>.parquet` via `make_long/validate_long/write_long`, then reuse `score_split("test", ...)` and `_merge` so test rows land in `leaderboard.csv`/`breakdown.csv` with the other models.
4. Registry per target (extends `swf.predict.registry` contract; keep `schema_version` field, bump to 2): `selected`, `runtime`, `artifacts`, `reason`, `bands` (keyed by runtime; TFT entry `{"method": "native_quantiles"}`), `val_rmse`, plus new `test_metrics` (`rmse, mae, nrmse_pct, coverage, pinball`), `baseline3_test_rmse`, `band_method`, `split_dates` (from `cfg.splits`), `git_sha`; top level keeps `feature_spec_hash`. `git_sha` via `subprocess.run(["git","rev-parse","HEAD"])`; record `"+dirty"` if the tree is dirty. No timestamps (deterministic-output convention).
5. Serving switch: `refresh.refresh` defaults to `models_root / "registry.json"`; change to prefer `models_root/"deployed"/"registry.json"` and fall back to `models/registry.json` when absent, so the Phase 5 skeleton keeps working until `--final` has run. Update the `_REMEDY` text.
6. `build_run` changes (the one serving-side change): after `serve_features`, compute the encoder window (new `serve_sequence(raw, ...)` in `swf.features.build`, built from the same `hist` already computed inside `serve_features`; live `past_days: 8` gives >= 192 h, enough for 168) and pass it plus the five live b3 series on `X.attrs`. Runtimes `lstm`/`tft` compute the joint forecast once per origin and cache it (keyed on `X.attrs["origin"]` or `id(X)`) because `build_run` calls `predict_p50` once per target. For TFT add an optional `predict_quantiles(...)` that returns p10/p90, and have `build_run` use it when the runtime defines it (else the residual-offset `band_frame` path).
7. Add `"lstm": "swf.predict.lstm", "tft": "swf.predict.tft"` to `RUNTIMES` in `registry.py`. Import hygiene test (`test_predict_registry.py` subprocess pattern) must show a registry selecting only baseline3/lightgbm imports neither torch nor darts, and importing `swf.predict.registry` imports none of the new modules.

### Pattern 4: evaluation figures
- **EVAL-08** `swf.evaluate.prob`: per model/target on the shared scored mask (use `align_models`/`scored_mask` on p50, then index p10/p90 from the long frame; daytime mask for t1_kw/ghi): coverage = mean(p10 <= y <= p90), mean width = mean(p90 - p10), pinball loss averaged over q in {0.1, 0.5, 0.9}, and reliability points. With only three quantiles the reliability diagram has three points per model (nominal 0.1/0.5/0.9 vs empirical fraction y <= p_q); say so on the figure. Write `prob_metrics.csv` and `reliability_<split>.png`.
- **EVAL-09** heatmap from `breakdown.csv` (`skill_vs_baseline3` by target x exact horizon in {1,6,24,48,72} x season): one axes per target, rows = season, columns = horizon, for the selected model (or each ML model). Phase 4 explicitly chose exact horizons "no buckets" (`config/features.yaml`); the requirement text says "horizon bucket", so either keep exact horizons and state it (recommended: zero new metric code) or add a small bucket aggregation. See assumption A2.
- **EVAL-10**: monsoon vs dry rows already exist in `breakdown`. Add a capacity-factor table for t5_kw: observed mean CF = mean(y)/`s.wind.rated_kw`, predicted CF per model, and RMSE in CF units by season; report honestly (t5_kw ML skill vs baseline 3 is the smallest, 0.17 for LightGBM on val).
- **MODEL-07** LightGBM gain: `lgb.Booster(model_file=...).feature_importance("gain")` for the 15 text boosters (paths from the registry `artifacts`), sum gain per feature per target across buckets, normalise to 100 %, bar chart top ~15 per target. Feature names come from the sidecar `feature_columns`.
- All figures: existing `plots()` conventions (`Agg`, `dpi=120`, `metadata={"Software": None}` for deterministic PNGs), matplotlib imported inside the function.

### Anti-Patterns
- Importing torch/darts/matplotlib/`swf.evaluate` at module scope in `swf.predict.*` or `swf.api.*` (hygiene test fails).
- Pickling PyTorch models for the LSTM (use `state_dict` + `weights_only=True`).
- Re-fitting bands, normalisation, or choosing hyper-parameters using 2025 data; test rows are read only inside `evaluate --final`.
- DataLoader `num_workers>0` on Windows; pass `dataloader_kwargs={"num_workers":0}` to darts if overriding.
- Using `val` encoder/covariate data that crosses D-14 for early stopping.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lead-matched decoder covariates | A new lead mapper | `assemble(..., cov=dict)` + `lead_k` | D-02 already tested |
| Purged ES tail | New split logic | `split_fit_es` from `swf.models.lgbm` | D-14 identical rule |
| Bands for LSTM | Quantile heads | `residual_offsets` + `band_frame` | D-17 |
| Leaderboard rows, skill, seasons | New metric code | `align_models`, `leaderboard_rows`, `breakdown`, `score_split`, `_merge` | Same sample rules, `min_shared_frac` guard |
| Long format IO | Custom parquet | `make_long`, `validate_long`, `write_long` | Contract |
| Atomic registry write | Plain `open` | `save_registry` (os.replace) | Existing contract; extend fields only |
| TFT quantile sampling | Monte-Carlo samples | `predict_likelihood_parameters=True` | Direct quantiles, deterministic |
| TFT variable selection | Hooking internals | `TFTExplainer` | Official API |
| Early stopping | Custom loop for TFT | Lightning `EarlyStopping` callback via `pl_trainer_kwargs` | Standard |

## Common Pitfalls

1. **Train/serve covariate skew (stitched vs lead-matched).** Training uses stitched `hf`; val/test use `pr_d{k}`. This is documented in Phase 4 (W1). Report the stitched-vs-lead gap per model; do not hide it. For TFT the encoder part of val covariates uses hf (past) and the decoder part uses lead-matched values.
2. **Prediction origin sample mismatch.** Previous-Runs 10 m variables only start ~2024-01-19, so the val shared index starts there; a model that predicts every origin is fine, `align_models` + `scored_mask` handle it. A model predicting a subset of origins can fail `min_shared_frac`.
3. **NaN in encoder/decoder.** `history_input` re-masks interpolated cells to NaN. Count NaNs before training; use a mask channel; never let NaN reach the loss (a single NaN silently kills an epoch). Mask NaN truth in the loss.
4. **Overlapping windows leak across ES boundary.** Fit origins must satisfy `origin + 72 h < es_tail_start` (the `split_fit_es` rule). For TFT, `val_series` starts 168 h before the tail but its first target time is the tail start.
5. **Quantile crossing / physical bounds in TFT.** Sort across quantiles, then `enforce` each; `band_frame`'s min/max trick is for residual bands only.
6. **Joint-model runtime called per target.** `build_run` loops targets; recomputing the joint forecast five times wastes time and risks inconsistency; cache per origin.
7. **darts pickle/ckpt load.** `TFTModel.load` unpickles; acceptable for locally trained trusted artifacts only. Keep `models/tft/` out of untrusted inputs; record this in the sidecar notes.
8. **Windows + CUDA determinism.** Fixed seeds, `num_workers=0`, deterministic algorithms with `warn_only=True`; the LSTM cuDNN path may still differ by ~1e-6; assert metric tolerance, not bit equality, in tests.
9. **Selection leakage.** The decision must be computed from val rows before any test file is read; unit-test it with a monkeypatched `read_long` that raises on `split="test"`.
10. **Registry spec hash.** `load_registry` calls `assert_spec`; the deployed registry must be written by `save_registry` so the hash matches. Features code must not change after training (spec hash 3bd1a73d99093287) or all artifacts must be retrained.
11. **TFT memory with 8.7k+ TimeSeries.** Building ~17k `TimeSeries` objects (val + test) takes tens of seconds and a few GB if carelessly copied; build lazily per chunk of 1000 origins and predict per chunk.

## Code Examples

### Window gather (sketch)
```python
# encoder [N,168,5] from the same hist used by origin_table
pos = hist.index.get_indexer(origins)
enc = hist[list(TARGETS)].to_numpy(np.float32)[pos[:, None] + np.arange(-167, 1)]
# decoder [N,72,24]: lead-matched via assemble
cols = COVARIATE_COLS + CALENDAR_COLS + GEOMETRY_COLS
parts = [f[cols].to_numpy(np.float32).reshape(-1, 72, len(cols))
         for f in iter_features(otab, ttab, origins, range(1, 73), cov=cov, cfg=cfg)]
```

### TFT quantile prediction (sketch; verify component names on a tiny run)
```python
# Source: darts 0.48.1 TFTModel.predict signature (introspected); Context7 /unit8co/darts
pred = model.predict(n=72, series=series_list, future_covariates=cov_list,
                     predict_likelihood_parameters=True, batch_size=512)
```

### Once-guard
```python
dep = MODELS_DIR / "deployed" / "registry.json"
if dep.exists():
    print(f"{dep} exists: test was already evaluated once (D-22). Delete it deliberately to redo.")
    return 1
```

## State of the Art

| Old | Current | Impact |
|-----|---------|--------|
| pytorch-forecasting TFT | darts 0.48.1 TFT | Project decision; multi-target native |
| `pvwatts_ac` etc. | already handled in Phase 2-5 | n/a |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | darts `predict(..., predict_likelihood_parameters=True)` yields components named `<comp>_q0.10/0.50/0.90` for a 5-component series (inferred from darts docs, not run) | Pattern 2 | Parsing code adjustment; trivial |
| A2 | EVAL-09 "horizon bucket" is satisfied by the existing exact horizons {1,6,24,48,72} (Phase 4 stated choice); the user may want 1-6/7-24/25-72 buckets | Pattern 4 | Small extra aggregation if user wants buckets; needs confirmation |
| A3 | LSTM residual-over-b3 design (b3 as decoder input) is acceptable; CONTEXT only says compare like LightGBM (D-07) | Pattern 1 | If a non-residual LSTM is wanted, drop b3 add-back |
| A4 | TFT target = raw (not residual), b3 supplied as a future covariate | Pattern 2 | TFT could underperform LSTM purely by formulation; honest note in report |
| A5 | Hyper-parameter starting values (hidden 128, lr 1e-3, etc.) are reasonable defaults | Pattern 1 | Needs the small search anyway |
| A6 | TFT epoch time and 17k-origin predict time are acceptable on the 4060 within the Day-11 box (unmeasured) | Pattern 2 | May force a smaller TFT or the documented stop; time a 500-origin trial first |
| A7 | `truth_frame` has few/no NaN (not checked this session) | Pitfall 3 | Mask handling already planned |

## Open Questions (RESOLVED)

1. **TFT series: truth vs hist for the encoder target (RESOLVED in part by this research).** Train on `truth` (matches scoring), infer with `hist` (what serving has). RESOLVED: D-26 in 06-CONTEXT.md — TFT encoder uses the same ERA5-based history in training and serving; no A/B.
2. **Where do test predictions of LightGBM come from? (RESOLVED)** From a new `predict_split("test")` that reuses `swf.predict.lgbm.predict_p50` and the stored val offsets; no retraining.
3. **Once-guard form (RESOLVED by D-22 intent)** Refuse when `models/deployed/registry.json` exists; no override flag.
4. **GRU alongside LSTM** is Claude's discretion (default LSTM only); a config switch is enough. RESOLVED: 06-CONTEXT.md Claude's Discretion (LSTM first, GRU if time).
5. **Do the live-served deep models need `past_days` > 8?** No: 8 days = 192 h >= 168 h encoder (+ lag-168 margin already satisfied by `serve_features`). RESOLVED.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv | all | yes | 3.12 | -- |
| torch + CUDA | LSTM, TFT | yes | 2.15.0+cu134, CUDA True | CPU (slow) |
| GPU | training | yes | RTX 4060 Laptop, 8188 MiB | -- |
| darts | TFT | yes | 0.48.1 | cut TFT |
| pytorch-lightning | TFT | yes | 2.6.6 | -- |
| data/interim parquet (era5, nasa, hf, pr_d1-3) | all | yes | hf 2021-01..2025-12, pr_d* 2024-01..2025-12 | -- |
| Baseline test/val parquet | scoring | yes | present | -- |
| LightGBM test predictions | final eval | no | -- | create via predict_split |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2 (`addopts = -q -m 'not network and not realdata'`) |
| Config | `pyproject.toml` (markers `gpu`, `realdata` exist) |
| Quick run | `.venv/Scripts/python -m pytest tests/test_deep_seq.py tests/test_final_eval.py -x` |
| Full suite | `.venv/Scripts/python -m pytest` (316 passing before this phase; also run `-m realdata` for the real runs) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-02 | Window builder shapes, no look-ahead (encoder ends at origin, decoder uses lead-matched cov); one synthetic train step lowers loss; checkpoint round-trips with `weights_only=True` | unit | `pytest tests/test_deep_seq.py -x` | Wave 0 |
| MODEL-02 | Real LSTM run writes `val/lstm.parquet` valid long format, 5 targets, all val origins | realdata/gpu | `pytest -m "realdata" tests/test_deep_real.py::test_lstm` | Wave 0 |
| MODEL-02 | Serving window parity: `serve_sequence` equals training gather at same origin | unit | `pytest tests/test_deep_seq.py::test_serve_parity -x` | Wave 0 |
| MODEL-03 | TFT tiny synthetic fit + quantile predict shape, sorted quantiles | unit (gpu opt) | `pytest tests/test_tft.py -x` | Wave 0 |
| MODEL-03 | Real TFT writes `val/tft.parquet` with native p10/p50/p90, or training-curve write-up exists | realdata | `pytest -m realdata tests/test_deep_real.py::test_tft` | Wave 0 |
| MODEL-05 | `select()` picks lowest val RMSE < b3, else baseline3; never reads test | unit | `pytest tests/test_final_eval.py::test_select -x` | Wave 0 |
| MODEL-05 | `--final` refuses when deployed registry exists | unit | `pytest tests/test_final_eval.py::test_once_guard -x` | Wave 0 |
| MODEL-06 | Registry has all fields, hash matches, `load_registry` accepts, runtime in whitelist, artifacts exist | unit/realdata | `pytest tests/test_final_eval.py::test_registry_fields -x` | Wave 0 |
| MODEL-06 | Import hygiene: baseline3/lightgbm-only registry imports no torch/darts; `swf.predict.registry` imports neither | unit | `pytest tests/test_predict_registry.py -x` | extend |
| MODEL-07 | Gain importance sums to 100 % per target, names from sidecar; TFT importance DataFrame plotted | unit/realdata | `pytest tests/test_final_eval.py::test_importance -x` | Wave 0 |
| EVAL-08 | coverage/width/pinball on a hand-computed tiny frame; reliability points | unit | `pytest tests/test_evaluate_prob.py -x` | Wave 0 |
| EVAL-09 | heatmap CSV/PNG written, cells equal `breakdown.csv` skill values | unit | `pytest tests/test_final_eval.py::test_heatmap -x` | Wave 0 |
| EVAL-10 | capacity-factor table: mean CF = mean(y)/rated; monsoon vs dry rows present | unit | `pytest tests/test_final_eval.py::test_wind_cf -x` | Wave 0 |
| API | Refresh with a deployed registry of lstm runtime (tiny synthetic artifact) writes DB rows; default registry path prefers `deployed/` with fallback | unit | `pytest tests/test_api_refresh.py -x` | extend |

### Sampling Rate
- Per task commit: the quick run above for the touched module.
- Per wave merge: `pytest` default suite.
- Phase gate: full default suite green plus `pytest -m realdata` for the Phase 6 real tests before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_deep_seq.py`, `tests/test_tft.py`, `tests/test_final_eval.py`, `tests/test_evaluate_prob.py`, `tests/test_deep_real.py`
- [ ] `config/deep.yaml` + `DeepCfg`/`load_deep_cfg` in `swf.core.settings`
- [ ] Synthetic helpers in `tests/synth.py` for tiny hist/cov tables

## Security Domain

Local single-user app; ASVS mostly N/A. Applicable controls:

| ASVS Category | Applies | Control |
|---------------|---------|---------|
| V5 Input validation | yes | Registry runtime names checked against fixed `RUNTIMES` whitelist before `importlib`; artifact paths via `artifact_path` (no traversal) |
| V10 Malicious code / deserialization | yes | LSTM: `torch.load(weights_only=True)`; TFT: darts pickle only from local trained artifacts, noted in sidecar; LightGBM text boosters |
| V6 Cryptography | no | -- |

| Threat | STRIDE | Mitigation |
|--------|--------|------------|
| Tampered registry points to arbitrary module | Tampering/EoP | Whitelist (exists) |
| Malicious pickle in `models/tft/` | EoP | Trusted local artifacts only; do not load from outside `models/` |

## Sources

### Primary (HIGH)
- Codebase read this session: `swf.features.{build,spec,splits,history}`, `swf.evaluate.{report,longfmt,metrics}`, `swf.models.lgbm`, `swf.predict.{registry,lgbm,bands,baseline}`, `swf.api.refresh`, `swf.cli`, `pyproject.toml`, `config/{lgbm,features,baseline3_choice}`.
- `.venv` introspection: torch 2.15.0+cu134 CUDA True, darts 0.48.1, pytorch-lightning 2.6.6; `TFTModel.__init__/fit/predict` signatures; `TFTExplainer`, `TFTExplainabilityResult.get_feature_importances`.
- Context7 `/unit8co/darts` (TFT notebook: QuantileRegression, future covariates mandatory, explainer, list-of-series predict).
- `.planning/phases/05-*/05-0{1,2}-SUMMARY.md`, `06-CONTEXT.md`, `CLAUDE.md`.

### Secondary / Tertiary
- None. Time and quantile-component-name claims are unverified (A1, A6).

## Metadata

**Confidence:** Standard stack HIGH (installed, verified); Architecture MEDIUM-HIGH (serving interface change is a design judgement); Pitfalls MEDIUM (TFT specifics not run).
**Research date:** 2026-11-07
**Valid until:** 2026-11-16 (viva) -- stack is pinned, no drift expected.
