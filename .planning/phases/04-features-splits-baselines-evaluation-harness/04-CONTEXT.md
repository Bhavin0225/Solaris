# Phase 4: Features, Splits, Baselines & Evaluation Harness - Context

**Gathered:** 2026-11-03
**Status:** Ready for planning

<domain>
## Phase Boundary

The phase builds one causal feature pipeline, shared by training and serving, and a chronological split that is provably leak-free. It also delivers the evaluation harness: the common long prediction format, metrics, breakdowns and a leaderboard. The leaderboard scores all three baselines (persistence, climatology, baseline 3 = GFS → physics) for all five targets, so every later ML claim has a bar to beat. ML model training (LightGBM, LSTM/GRU, TFT) is NOT in this phase.

Requirements: FEAT-01..06, EVAL-01..07 (ROADMAP Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (already locked, do not re-decide)
- **Splits:** weather-only models train 2001–2023; covariate models train 2021-04 to 2023 (GFS history). Validation is 2024 and test is 2025. Purge origins whose 72 h targets cross a split boundary, and log the date ranges (FEAT-04, PROJECT Key Decisions).
- **Single NWP model:** GFS (`gfs_seamless`) for covariates, baseline 3 and the live site. Training covariates come from the Historical Forecast data (stitched, short-lead); val/test baseline 3 uses lead-matched Previous Runs, with the stitched variant reported alongside (EVAL-03).
- **History and truth:** lag and rolling history features come from ERA5 in training and from Open-Meteo `past_days` at serving. NASA POWER is the target truth (FEAT-03).
- **Baselines:** persistence takes the value at t, or the same hour yesterday for solar. Climatology is the hour-of-day × month mean over the training years (EVAL-01/02).
- **Daytime scoring:** solar is scored on daytime only (midpoint zenith < 85°) (EVAL-05).
- **Correction:** GHI is NOT corrected. `config/site.yaml` `align.skip: {ghi: ...}` covers this, and `config/bias_correction.json` holds rh, ws10 and ws_hub only (Phase 2 decision, d32ec9d).
- **Solar plant loss:** `loss_pct` stays 14 (Phase 3 D-L1). Simulated energy labels come from `data/interim/energy_sim.parquet` as built in Phase 2.

### Forecast origins
- **D-01:** Issue a 72 h forecast at **every hour** (hourly origins) for both training and evaluation samples. This matches the live site's hourly refresh and gives about 8,760 origins per year, so val/test metrics are tight. Deep models (Phase 6) may subsample origins for training speed, but evaluation always uses all hourly origins.
- **D-02:** Lead mapping for lead-matched GFS (baseline 3 and val/test covariates): horizon h uses Previous Runs `previous_day{k}` with **k = ceil(h/24)**. So h 1–24 uses day1, h 25–48 uses day2 and h 49–72 uses day3. This is deliberately simple and slightly pessimistic for the earliest horizons, and it mirrors what the live site actually has available.

### Baseline 3 correction
- **D-03:** Baseline 3 is **reported both ways**. The official leaderboard row ("baseline 3") passes GFS weather through `swf.align.consistency.apply_correction()` with the committed coefficients (rh, ws10, ws_hub; GHI unchanged), then runs the physics chain. This gives it the same inputs the ML pipeline sees. A second row, "baseline 3 (raw GFS)", skips the correction so the report can state what the correction is worth. Skill scores and the Phase 6 "ML beats baseline 3" claim use the **corrected** row.
- **D-03a (amends D-03, 2026-11-03, after research):**
  - **Finding:** research measured that the ERA5-fitted correction makes GFS *worse* for wind. 2025 lead-matched day1 RMSE: ws10 1.61 m/s corrected vs 1.29 raw; wind kW 744 vs 652. Solar is roughly unchanged (132 vs 131 kW) and RH is slightly better.
  - **Rule:** the **official** baseline-3 bar is chosen **per target** as whichever of {corrected, raw GFS} has the lower RMSE on **validation (2024)**. The choice is made once, recorded in a committed file and frozen before any test (2025) scoring.
  - **Reporting:** both rows, plus the stitched variants, stay on the leaderboard. The report states the selection rule and the per-target choice.
  - **Use:** skill scores and the Phase 6 "ML beats baseline 3" claim use the official (per-target best) row.
- **D-04:** **Re-use the ERA5→NASA coefficients as they are** for GFS. Do not fit a separate GFS→NASA correction. Measure and report the remaining GFS-vs-NASA bias after correction on validation (2024), per variable and lead day, as the documented train/serve and source skew.

### Plan-check decisions (user, 2026-11-03)
- **D-05 (GTI dropped, errata vs PRD §8):** GTI (`global_tilted_irradiance`) is NOT a covariate. CANON_COLS (frozen in Phase 2) has no GTI column, and GTI is GHI/DNI/DHI transposed onto the panel tilt — information already carried by the GHI/DNI/DHI covariates plus solar geometry (and computed by the physics chain). Record the deviation and reason in `docs/data_notes.md` (hand-written, outside AUTO blocks) so the viva has the answer.
- **D-06 (purge only, no 168 h embargo):** keep origin t iff start ≤ t and t+72 h ≤ split end. No extra 168 h embargo (deviation from research PITFALLS): lag/rolling history features are inputs, not labels — reading late-2023 weather to forecast early-2024 is exactly what the live site does — and no training target leaks into val/test. Record the reasoning in the report.

### Claude's Discretion (defaults; the researcher/planner may refine with evidence)
- **Covariate skew:** train covariate models on stitched Historical Forecast GFS (2021-04 to 2023) and quantify the stitched-vs-lead-matched gap on 2024 in the report. Adding lead age as a feature is optional; propose it only if research shows a material gap.
- **nRMSE normalisation:**
  - kW targets: normalise by capacity (solar AC cap from config, wind 3600 kW rated).
  - GHI, RH and wind speed: normalise by the mean of actuals over the scored sample.
  - State the normalisation in metrics output (EVAL-05).
- **Season definition:** monsoon = June–September (UTC months); dry = the remaining months.
- **Shared sample index:** skill vs baseline 3 and vs persistence is computed on the intersection of samples where every compared model has a prediction.
- **Horizon breakdown buckets:** 1, 6, 24, 48, 72 h, per EVAL-06. Bucket edges are the planner's choice and must be stated.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec and requirements
- `docs/PRD.md` — source of truth. Read the feature, split, baseline and evaluation sections. `.planning/research/SUMMARY.md` errata override it where they conflict.
- `.planning/research/SUMMARY.md` — errata and pitfalls, including the train/serve skew notes for Open-Meteo stitched vs lead-matched data.
- `.planning/REQUIREMENTS.md` — FEAT-01..06 and EVAL-01..07 (EVAL-08..10 belong to Phase 6).
- `.planning/ROADMAP.md` §Phase 4 — success criteria 1–5.
- `.planning/PROJECT.md` Key Decisions table — dual training window, lead-matched baseline 3, single NWP model GFS.

### Data and prior-phase results
- `docs/data_notes.md` — coverage (D1–D3), timestamp offsets, cleaning, NASA vs ERA5 consistency and correction decision, physics chain, physics validation (Phase 3).
- `config/bias_correction.json` — committed ERA5→NASA coefficients (rh, ws10, ws_hub).
- `config/site.yaml`, `config/plant.yaml` — site and plant values, the `align` section, `align.skip`.
- `.planning/phases/02-alignment-cleaning-physics/02-VERIFICATION.md` and `.planning/phases/03-physics-validation-gate/03-VERIFICATION.md` — what is shipped and verified.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `swf.align.adapters.load_source` / `swf.align.clean.clean` turn sources into the canonical `CANON_COLS` hourly UTC frame. The interim parquets already exist: `data/interim/weather_{nasa,era5,gfs_hf,gfs_pr_d1,gfs_pr_d2,gfs_pr_d3}.parquet` and `energy_sim.parquet`.
- `swf.align.consistency.apply_correction(df, coefs, s)` is the single train/serve correction function. `load_coefs` reads `config/bias_correction.json`.
- `swf.physics.simulate` (solar via `swf.physics.solar` / `ac_from_poa`, wind via `swf.physics.wind.simulate_wind`) plus `swf.physics.constraints.enforce` form the physics chain for baseline 3, reused unchanged.
- `swf.physics.common` provides midpoint solar position, night mask and clear-sky. These serve the solar geometry and clear-sky-index features and the daytime mask.
- `swf.validate.metrics.error_stats` is the existing nRMSE/MAE/RMSE helper (Phase 3). Extend or reuse it rather than duplicating.
- `swf.coverage.report.write_auto_block(path, block, name=...)` and `_table` write the AUTO blocks in `docs/data_notes.md`.

### Established Patterns
- CLI: subcommands in `src/swf/cli.py` dispatch via `_run("swf.<pkg>.run", args)`, and handlers are `run(args) -> int`.
- Config: pydantic models with `extra=forbid`. New config sections get their own yaml and model (Phase 3 `config/validation.yaml` pattern) rather than new keys in site.yaml or plant.yaml.
- Determinism: committed outputs are byte-identical on rerun, with no timestamps in artifacts.
- Tests: synthetic builders in `tests/synth.py`. `@pytest.mark.realdata` tests are deselected by default and run with `-o addopts=""`.
- All timestamps are UTC internally, with no tz_convert in pipeline logic.

### Integration Points
- New `swf.features` package, shared by Phase 5 (LightGBM, serving) and Phase 6 (deep models). Its `FEATURE_SPEC` hash is stored in every artifact.
- New evaluation package writes `reports/evaluation/leaderboard.csv` and the common long prediction format (`issue_time, horizon, target_time, target, model, y_true, p10, p50, p90`). Phase 5/6 models write the same format.

</code_context>

<specifics>
## Specific Ideas

- The leaderboard keeps two baseline-3 rows (corrected = official, raw GFS = reference), so the viva can show the correction's value honestly.
- The GFS-after-correction bias table on 2024 (per variable × lead day) is a report figure, not just a log line.

</specifics>

<deferred>
## Deferred Ideas

None. Discussion stayed within phase scope. (Covariate skew and scoring conventions were left to Claude's discretion with the defaults above, not deferred.)

</deferred>

---

*Phase: 04-features-splits-baselines-evaluation-harness*
*Context gathered: 2026-11-03*
