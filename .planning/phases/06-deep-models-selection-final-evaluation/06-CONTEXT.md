# Phase 6: Deep Models, Selection & Final Evaluation - Context

**Gathered:** 2026-11-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Train the deep models (LSTM/GRU seq2seq, then TFT) on the GPU, add them to the validation leaderboard, select one serving model per target on validation, evaluate the selection on test exactly once, and write the evaluation figures and registry. LightGBM and the serving path already exist (Phase 5). The front-end redesign is Phase 7.

Requirements: MODEL-02, MODEL-03, MODEL-05, MODEL-06, MODEL-07, EVAL-08, EVAL-09, EVAL-10 (ROADMAP Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Order and scope (user, 2026-11-08)
- **D-15:** Follow the plan order: LSTM/GRU first, then TFT. TFT is kept in scope, time-boxed to the Day-11 hard stop. It is the first item in the cut order only if the time box is missed.

### Locked earlier (do not re-decide)
- **D-01 (Phase 4, amended for deep models):** Evaluation uses all hourly origins. Deep-model training MAY subsample origins for speed (stride 3 is the default here).
- **D-03a / D-13:** Official baseline 3 per target = the per-target choice in `config/baseline3_choice.json`. Phase 5 served baseline 3 everywhere; Phase 6 is the first place an ML model can be selected per target.
- **D-07 / D-08:** LightGBM residual over baseline 3 and horizon-bucket structure are the reference for how the deep models must be compared (same leaderboard row format).
- **FEAT-04 / splits:** covariate models train 2021-04 to 2023; validation 2024; test 2025. Purge origins whose 72 h targets cross a split boundary.
- **D-14:** early stopping never sees 2024 rows. For the deep models, the held-out tail is the last part of the 2023 training window, same rule as LightGBM.

### LSTM/GRU
- **D-16:** Architecture as in the roadmap: encoder 168 h of past observations, decoder 72 h with known-future covariates, five targets jointly. Plain PyTorch (not darts), so an ONNX export stays possible later.
- **D-17:** Uncertainty for LSTM/GRU uses the same validation-residual bands as LightGBM and baseline 3 (D-09), so the leaderboard compares the same method. No quantile heads.
- **D-18:** Time box: stable by ~Day 10. If unstable by then, report the minimal version honestly (roadmap success criterion 1).

### TFT (kept)
- **D-19:** TFT via darts, multi-target, native P10/P50/P90 outputs, 5 targets. Hard stop Day 11. If it fails or is not finished by the stop, write up the attempt with its training curves (roadmap success criterion 2).
- **D-20:** TFT is served locally with torch if it wins a target (roadmap). No ONNX for TFT.

### Selection and final evaluation
- **D-21:** Per target, the serving model is the one with the lowest validation RMSE that beats the official baseline 3 (PRD 9.4). Selection uses validation only.
- **D-22:** `evaluate --final` runs once on test. Its result is recorded in `models/deployed/registry.json` with the fields in MODEL-06 and the roadmap (selected model, runtime, artifact, reason, test metrics, baseline-3 RMSE, band method, feature_spec_hash, split dates, git SHA).
- **D-23:** A target where no ML model beats baseline 3 deploys baseline 3, and the report says so.

### Resolved after research (owner delegated to Claude, 2026-11-08)
- **D-24 (heatmap buckets):** EVAL-09 uses the Phase 4 exact horizons {1, 6, 24, 48, 72} h, as already in `breakdown.csv`. The figure caption states this.
- **D-25 (LSTM target):** LSTM predicts the residual over the official baseline 3, with b3 as a decoder input and added back at output (mirrors D-07).
- **D-26 (TFT target and encoder):** TFT predicts raw targets with b3 as a future covariate. Its encoder input is the reanalysis-style history, not truth: ERA5 archive in training and Open-Meteo `past_days` at serving (the FEAT-03 source pair), built by the same code path. This avoids the truth-vs-history skew, but leaves an accepted ERA5-vs-live source skew, which the final notes must state next to the Phase 4 W1 skew.
- **D-27 (TFT time check):** before full val/test prediction, time a TFT fit and a 500-origin predict. If the projection breaks the Day-11 stop, reduce origins (stride) or stop and write up per D-19.
- **D-28 (once-guard):** `evaluate --final` refuses to run if `models/deployed/registry.json` exists. No override flag.
- **D-29 (serving switch):** refresh prefers `models/deployed/registry.json` and falls back to `models/registry.json` until `--final` has run.

### Claude's Discretion
- LSTM/GRU hidden size, layers, learning rate, batch size, dropout and seeds (fixed); the search size is small (no Optuna mega-sweeps, per the PRD anti-feature list).
- TFT hyper-parameters within the time box (at most 3-4 trials, per the research).
- Exact figure layout and file names under `reports/evaluation/`.
- Whether GRU is run alongside LSTM. Default: LSTM first; GRU only if time allows.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec and requirements
- `docs/PRD.md` §9.2 (model ladder), §9.3 (evaluation), §9.4 (selection rule)
- `.planning/research/SUMMARY.md` — deep-model risks (torch on Windows, darts pins), TFT decision
- `.planning/REQUIREMENTS.md` — MODEL-02, MODEL-03, MODEL-05, MODEL-06, MODEL-07, EVAL-08..10
- `.planning/ROADMAP.md` §Phase 6 — success criteria 1-5, cut order

### Prior phases
- `.planning/phases/04-features-splits-baselines-evaluation-harness/04-CONTEXT.md` — D-01..D-06
- `.planning/phases/05-walking-skeleton-lightgbm/05-CONTEXT.md` — D-07..D-14
- `.planning/phases/05-walking-skeleton-lightgbm/05-02-SUMMARY.md` — LightGBM training pattern, registry shape, val leaderboard row
- `config/baseline3_choice.json`, `config/features.yaml`, `config/lgbm.yaml`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `swf.features` (build, spec, history, splits): shared feature builder, FEATURE_SPEC hash stored in every artifact.
- `swf.evaluate` (baselines, longfmt make_long/validate_long/write_long, metrics, report): leaderboard and the common long prediction format. Deep models write the same format.
- `swf.predict` (bands, registry, runtime dispatch by whitelisted module name): add `torch` / `darts` runtimes to the whitelist, lazily imported.
- `swf.models.lgbm`: training pattern (origins, buckets, early stopping on held-out tail, sidecar JSON, text artifacts).
- `config/lgbm.yaml` + `LgbmCfg` pattern: new `config/deep.yaml` with its own pydantic model.

### Established Patterns
- Fixed seeds, deterministic artifacts, no timestamps in committed outputs.
- Import hygiene: `swf.api` and `swf.predict` never import torch, darts, matplotlib or `swf.evaluate` at module load.
- Realdata tests marked `realdata`, deselected by default.
- Windows: DataLoader num_workers=0 (research pitfall).

### Integration Points
- New `swf.models.deep` (LSTM/GRU, TFT training) and `evaluate --final`.
- `models/deployed/registry.json` replaces the Phase 5 `models/registry.json` as the serving registry.
- Served by the existing FastAPI app via the registry (no API change expected).

</code_context>

<specifics>
## Specific Ideas

- The user wants the full ladder shown in order: baseline 3, LightGBM, LSTM/GRU, TFT, all on the same leaderboard.
- Honest reporting matters more than a winning model: if no deep model beats baseline 3 on a target, say so.

</specifics>

<deferred>
## Deferred Ideas

- ONNX export and torch-free serving image (v2 cloud deployment).
- Cloud hosting, keep-alive, seed snapshot (v2).
- Front-end redesign and weather tab (Phase 7; weather tab needs a scope decision on cloud cover and rain).
- Optuna-style hyper-parameter sweeps (PRD anti-feature).

### Reviewed Todos (not folded)
None.

</deferred>

---

*Phase: 06-deep-models-selection-final-evaluation*
*Context gathered: 2026-11-08*
</content>
