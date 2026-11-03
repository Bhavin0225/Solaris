# Phase 4: Features, Splits, Baselines & Evaluation Harness - Research

**Researched:** 2026-11-03
**Domain:** leak-free time-series feature pipeline, chronological splits, NWP+physics baseline, evaluation harness (pandas/numpy/pvlib only)
**Confidence:** HIGH on data facts and reuse points (measured in this session); MEDIUM on layout/sizing recommendations (design choices)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Splits:** weather-only models train 2001–2023; covariate models train 2021-04 to 2023 (GFS history). Validation is 2024 and test is 2025. Purge origins whose 72 h targets cross a split boundary, and log the date ranges (FEAT-04, PROJECT Key Decisions).
- **Single NWP model:** GFS (`gfs_seamless`) for covariates, baseline 3 and the live site. Training covariates come from the Historical Forecast data (stitched, short-lead); val/test baseline 3 uses lead-matched Previous Runs, with the stitched variant reported alongside (EVAL-03).
- **History and truth:** lag and rolling history features come from ERA5 in training and from Open-Meteo `past_days` at serving. NASA POWER is the target truth (FEAT-03).
- **Baselines:** persistence takes the value at t, or the same hour yesterday for solar. Climatology is the hour-of-day × month mean over the training years (EVAL-01/02).
- **Daytime scoring:** solar is scored on daytime only (midpoint zenith < 85°) (EVAL-05).
- **Correction:** GHI is NOT corrected. `config/site.yaml` `align.skip: {ghi: ...}` covers this, and `config/bias_correction.json` holds rh, ws10 and ws_hub only (Phase 2 decision, d32ec9d).
- **Solar plant loss:** `loss_pct` stays 14 (Phase 3 D-L1). Simulated energy labels come from `data/interim/energy_sim.parquet` as built in Phase 2.
- **D-01:** Issue a 72 h forecast at every hour (hourly origins) for both training and evaluation samples. Deep models (Phase 6) may subsample origins for training speed, but evaluation always uses all hourly origins.
- **D-02:** Lead mapping for lead-matched GFS (baseline 3 and val/test covariates): horizon h uses Previous Runs `previous_day{k}` with k = ceil(h/24).
- **D-03:** Baseline 3 is reported both ways. Official row ("baseline 3") = GFS through `apply_correction()` (rh, ws10, ws_hub; GHI unchanged) then the physics chain. Second row "baseline 3 (raw GFS)" skips the correction. Skill scores and the Phase 6 "ML beats baseline 3" claim use the corrected row.
- **D-04:** Re-use the ERA5→NASA coefficients as they are for GFS. No separate GFS→NASA fit. Measure and report remaining GFS-vs-NASA bias after correction on validation (2024), per variable and lead day.

### Claude's Discretion
- Covariate skew: train covariate models on stitched Historical Forecast GFS (2021-04 to 2023) and quantify the stitched-vs-lead-matched gap on 2024 in the report. Lead age as a feature is optional; propose only if research shows a material gap.
- nRMSE normalisation: kW targets by capacity (solar AC cap from config, wind 3600 kW rated); GHI, RH, wind speed by the mean of actuals over the scored sample. State the normalisation in metrics output.
- Season: monsoon = June–September (UTC months); dry = the rest.
- Shared sample index: skill computed on the intersection of samples where every compared model has a prediction.
- Horizon breakdown buckets: 1, 6, 24, 48, 72 h (EVAL-06). Bucket edges are the planner's choice and must be stated.

### Deferred Ideas (OUT OF SCOPE)
None. ML training (LightGBM, LSTM/GRU, TFT) is NOT in this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FEAT-01 | One causal builder `swf.features`, `FEATURE_SPEC` hash stored/checked | §FEATURE_SPEC; two-axis builder design |
| FEAT-02 | Feature list | §Feature Catalogue (concrete names, counts) |
| FEAT-03 | ERA5 history in training, OM past_days at serving | §History pipeline (history frame = enforce(physics(correct(canon)))) |
| FEAT-04 | Chronological splits, purge, logged ranges | §Splits and purge rule (exact counts) |
| FEAT-05 | Truncation/perturbation leakage test | §Leakage test design |
| FEAT-06 | Train/serve parity on committed raw OM fixture | §Parity test; `tests/fixtures/om_live_gfs_seamless.json` already suffices |
| EVAL-01 | Persistence baseline | §Baselines |
| EVAL-02 | Climatology baseline | §Baselines |
| EVAL-03 | Baseline 3 lead-matched + stitched | §Lead mapping, §Baseline 3 |
| EVAL-04 | Common long prediction format | §Long format and storage |
| EVAL-05 | MAE/RMSE/nRMSE/skill, shared index, daytime solar | §Metrics |
| EVAL-06 | Breakdown by horizon/season/target | §Metrics, §Breakdowns |
| EVAL-07 | `reports/evaluation/leaderboard.csv` + plots | §Module layout, §Outputs |
</phase_requirements>

## Summary

Everything the phase needs is already in the repo: canonical hourly UTC parquets, the correction function, the physics chain, solar geometry helpers, the AUTO-block writer and the CLI pattern. No new dependencies are required. The serving image is torch- and sklearn-free, so `swf.features` and `swf.evaluate` (metrics) must stay numpy/pandas/pvlib-only; matplotlib is imported lazily (plots only), as `swf.validate.plots` already does. Total work is: (1) a two-axis feature builder, (2) split/purge logic, (3) three baselines written in the long format, (4) a metrics/leaderboard module, (5) four test files.

Measured facts that change planning (all from `data/interim/`, this session):
- GFS Historical Forecast is NaN until **2021-03-22 23:00 UTC** (rh/ws first valid), GHI NaN until 2021-03 as well; "2021-04" for covariate training is therefore correct and needs no clipping logic beyond `dropna`.
- Previous Runs (PR) coverage: day1/2/3 10 m variables valid from **2024-01-19/20/21 ~11:00 UTC**; `ws_hub` (needs 80 m) valid only from **~2024-02-16/17/18**; 2025 is complete (only the last hour NaN). So val-year baseline 3 for wind kW has no predictions for roughly the first 7 weeks of 2024; the shared-index rule handles this and the report must state it.
- **Baseline 3 is a weak bar, and the correction hurts wind.** On 2025 (RMSE vs NASA truth, hourly, all rows; solar/GHI daytime-only): GFS-corrected stitched gives ws10 1.41 m/s, wind kW 653; raw gives 1.19 and 618. Lead-matched d1 corrected 1.61 / 744 vs raw 1.29 / 652. RH improves slightly with correction (10.9 vs 11.7). Naive 24 h persistence gets ws10 1.22, wind kW 608, solar kW (daytime) 55 vs baseline 3 solar 132 (corrected d1 132, raw 131). D-03 stays as locked (official row = corrected), but the leaderboard and report must show both rows and be honest that the corrected row is not the better one for wind. This is the "remaining GFS-vs-NASA bias" evidence behind D-04.
- Stitched vs lead-matched gap is material for wind (653 → 744/753/792 kW for d1/d2/d3 corrected) and small for solar and RH. Lead age as a feature would be **constant in training** (HF is fixed short-lead), so it cannot be learned. Recommendation: do NOT add it; quantify the gap in the report only.

**Primary recommendation:** build features on two axes (an origin-indexed history table and a target-time-indexed covariate/geometry/calendar table) joined by integer gather for `(origin, h)`; compute baseline 3 once per lead k on the target-time axis and expand to the long format by lookup; store long predictions as one zstd parquet per `(split, model)` under gitignored `data/processed/predictions/`; commit only the leaderboard and breakdown CSVs and plots.

## Architectural Responsibility Map

This is an offline Python data pipeline (no browser/CDN tier). Tiers mapped to the repo's layers:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Feature builder (`swf.features`) | Shared library (train + serve) | — | Phase 5 FastAPI imports the same code; must be torch/sklearn-free |
| History frame (correct → physics → enforce) | Shared library | — | Same function for ERA5 (train) and OM past_days (serve) |
| Splits / purge | Offline pipeline | Shared library (pure functions) | Used by trainers and eval; pure so tests are cheap |
| Baselines + long-format writer | Offline pipeline (`swf.evaluate`) | Shared (baseline 3 reused by Phase 5 live serving) | Baseline 3 chain = what the site serves |
| Metrics / leaderboard / plots | Offline pipeline | — | Reports only; plots lazy-import matplotlib |
| Config (`config/features.yaml`) | Config layer | — | Phase 3 pattern, `extra=forbid` |
| Artifact spec hash | Shared library | Phase 5/6 model artifacts | Checked at load |

## Standard Stack

### Core (all already in `pyproject.toml`; versions verified from the venv this session)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.6 | tables, UTC index, rolling/shift | project stack; copy-on-write: never chained-assign |
| numpy | 2.5.4 | integer gather for `(origin, h)` expansion, metrics | project stack |
| pyarrow | 26.0.0 | parquet I/O (zstd) | project stack |
| pvlib | 0.16.1 | zenith/azimuth/clear-sky via `swf.physics.common` | reuse, do not reimplement |
| pydantic | 2.14.2 | `FeaturesCfg` model (`extra=forbid`) | Phase 3 pattern |
| pytest | 9.2 | tests; `realdata` marker for parquet-backed tests | existing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| matplotlib | 3.11.2 (train extra, installed) | leaderboard bar/horizon plots | lazy import inside plot functions only |
| hashlib / json (stdlib) | — | FEATURE_SPEC hash | canonical JSON, sha256 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hand-written metrics (numpy) | scikit-learn metrics | sklearn is NOT in the serving image and `swf.evaluate.metrics` may be imported from it; numpy is 10 lines |
| tsfresh / featuretools / sktime | custom shifts | heavy, would hide the causal axis that the leakage test must prove |

**Installation:** none. `uv sync --extra train` already provides everything. Do not add packages.

## Package Legitimacy Audit

No new external packages are installed by this phase. All libraries above are existing locked dependencies (`uv.lock`).

**Packages removed due to slopcheck [SLOP] verdict:** none (n/a)
**Packages flagged as suspicious [SUS]:** none (n/a)

## Architecture Patterns

### System Architecture Diagram

```
 data/interim (cached, gitignored)                      config/*.yaml
  era5 ─┐                                                 features.yaml (new)
  nasa ─┼─ energy_sim (truth kW)                          site/plant/bias_correction
  gfs_hf│ gfs_pr_d1..d3
        v
 [truth frame y_true: t1_kw,rh,ghi,ws10,t5_kw]   (NASA / energy_sim)  ------------------+
        |                                                                               |
 [history_frame(canon)] = enforce(physics(apply_correction(canon)))                    |
   ERA5 (train/val/test) | OM past_days via openmeteo_canon (serve)                      |
        v                                                                               |
 ORIGIN AXIS table  (row = origin label t, labels <= t only)                           |
   lag0..lag168, roll6/24 mean/std, csi_hist            ---+                            |
 TARGET AXIS table (row = target label T)                  |  gather by (t, h): T=t+h   |
   calendar sin/cos, monsoon, geometry, clear-sky,         +--> X[(t,h)] + horizon      |
   covariates (GFS corrected; stitched=HF | lead k=PR_dk) -+      |                     |
        |                                                         v                     |
        |                                              trainers (Phase 5/6)             |
        v                                                         |                     |
 splits.py: origin ∈ [start, end-72h] per split ──────────────────┘                     |
        |                                                                               |
 baselines: persistence(y_true) | climatology(train yrs) | baseline3 {k=ceil(h/24)} x   |
            {corrected,raw} x {lead-matched, stitched}                                  |
        v                                                                               v
 long format  issue_time,horizon,target_time,target,model,y_true,p10,p50,p90  <-- joined to y_true
        v
 data/processed/predictions/{split}/{model}.parquet (gitignored)
        v
 metrics (shared index, daytime mask, nRMSE norm) -> reports/evaluation/{leaderboard,breakdown_*}.csv + png
        v
 docs/data_notes.md  AUTO:features / AUTO:evaluation blocks
```

### Recommended Project Structure
```
config/features.yaml           # horizons, lags, windows, splits, buckets, season months, covariate cols, baseline names
src/swf/features/
  __init__.py
  spec.py          # FEATURE_SPEC dict, spec_hash(), assert_spec(hash) -> raises on mismatch
  history.py       # history_frame(canon, s, coefs, curve) -> 5 target columns (shared train/serve)
  build.py         # origin_table(history), target_table(index, cov), assemble(origins, horizons, ...)
  covariates.py    # stitched(gfs_hf) and lead_matched(pr_d1..3, h) assemblers (D-02)
  splits.py        # SplitCfg, origins_for(split, kind), log_splits()
src/swf/evaluate/
  __init__.py
  longfmt.py       # LONG_COLS, validate_long(), write/read parquet
  baselines.py     # persistence, climatology, baseline3 variants -> long frames
  metrics.py       # metrics(), skill(), shared_index(), day mask, norms
  report.py        # leaderboard + breakdowns + plots + AUTO block, run(args)
tests/test_features_*.py, test_splits.py, test_evaluate_*.py
```
CLI additions in `src/swf/cli.py`: `features` (build + log splits + AUTO:features), `baselines` (write predictions), `evaluate` (leaderboard + breakdowns). Handlers `run(args) -> int` via `_run("swf.<pkg>.run", args)`; keep the `swf.features` entry in a `run` module or `swf.features.__init__`-free `swf.features.cli`-style module to preserve lazy import.

### Pattern 1: Two-axis feature builder (the causal guarantee by construction)
**What:** History features live on the origin axis and are computed with trailing windows on an hourly-complete frame (`shift(k)`, `rolling(w, min_periods=w)` closed at the row's own label). Everything that depends on the forecast time T=t+h (calendar, geometry, covariates) lives on the target axis and is fetched by index offset. A row for `(t, h)` is `origin_tab[t] ⊕ target_tab[t+h] ⊕ h`.
**Why:** The pitfall (PITFALLS C4) is computing `lag_k` on a target-aligned frame, which leaks when h > k. On the origin axis, lag k at row t is by construction `x[t-k]`. The leakage test then only has to prove that origin-axis columns never read labels > t.
**Example:**
```python
# Source: this research (pandas 3 API, no chained assignment)
def origin_table(hist: pd.DataFrame, spec) -> pd.DataFrame:
    parts = {}
    for c in spec.targets:                      # t1_kw, rh, ghi, ws10, t5_kw
        x = hist[c]
        for k in (0, *spec.lags):               # lag0 = value at origin label
            parts[f"{c}_lag{k}"] = x.shift(k)
        for w in spec.windows:                  # 6, 24; trailing, includes label t
            r = x.rolling(w, min_periods=w)
            parts[f"{c}_roll{w}_mean"], parts[f"{c}_roll{w}_std"] = r.mean(), r.std()
    return pd.DataFrame(parts, index=hist.index).astype("float32")

def gather(origin_tab, target_tab, origins, h):
    # origins: DatetimeIndex; h: int array. Integer positions on a shared hourly index.
    oi = origin_tab.index.get_indexer(origins)
    ti = oi + h                                  # valid because the index is gap-free hourly
```
The shared hourly index must be gap-free (guaranteed by `clean()` which reindexes to a full hourly range and `validate_canon`); assert `index.freq`/monotone equal-step at build time.

### Pattern 2: Single `history_frame` for ERA5 (train) and Open-Meteo `past_days` (serve)
The five target-space history columns are `rh`, `ghi`, `ws10` (corrected canonical columns, GHI uncorrected) and `t1_kw`, `t5_kw` = `simulate(apply_correction(canon))` then `enforce`. Same function, different input frame. At serving the input is `openmeteo_canon(raw, s)` of the live JSON (same adapter, same −1 h radiation/instant shift as training) followed by `clean(...)`. Because history is physics-of-ERA5, NOT NASA-derived, lag features and `y_true` come from different sources by design (FEAT-03); `y_true` always comes from the truth frame (NASA weather columns + `energy_sim.parquet`).

### Pattern 3: Lead-matched covariate assembly (D-02)
For origin t and horizon h, with k = ceil(h/24): covariate row = `gfs_pr_d{k}.loc[t+h]`. Because PR files are indexed by **valid time**, this is a pure target-axis lookup: build `cov_k = corrected(gfs_pr_dk)` for k=1,2,3 once; for horizon h pick table k(h) at target time. Stitched variant = `corrected(gfs_hf)` at target time, independent of h. Causality note: `previous_day{k}` at valid time T is "the value predicted 24·k h before T" [CITED: open-meteo.com/en/docs/previous-runs-api], i.e. issued at about T−24k ≥ t−24+... : with k=ceil(h/24), issue time T−24k = t+h−24k ∈ (t−24, t], so it is available at origin t; for h=1 it is 23 h stale (the D-02 "pessimistic" case). The docs do not name the run cycle, so the exact issue instant is approximate; state this in the report.

### Anti-Patterns to Avoid
- **Lags on the target axis** (`shift(k)` of a frame indexed by target time): leaks whenever h > k.
- **`rolling(center=True)` or windows ending at T:** leak.
- **Interpolating the history tail with future neighbours.** `clean._fill_gaps` linearly interpolates gaps ≤ 3 h using the right-hand neighbour. Features must be built from the already-cleaned frame and the truncation test must start from that cleaned frame (ERA5 has 0% missing, so no effect today). At serving, a trailing gap simply stays NaN; models/LightGBM handle NaN.
- **Fitting scalers/climatology on all years.** Climatology uses training years only (2001–2023).
- **Raw `dayofyear`.** Only sin/cos(2π·doy/365.25) and the monsoon flag.
- **Hard-coding capacities, coordinates, lags in code.** Lags/windows/horizons/cov columns come from `config/features.yaml`; capacities from `ac_cap_kw(s)` and `s.wind.rated_kw`.

## Feature Catalogue (FEAT-02)

Time convention (state in the spec and docs): **origin label t = last fully observed hourly label**; history rows with label ≤ t are usable; targets are labels t+1…t+72. Radiation is labelled at interval start (canonical), so the live site issues at wall-clock t+1 h (plus data latency). `issue_time` in the long format = t.

| Group | Columns | Count | Axis |
|-------|---------|-------|------|
| History lags | `{target}_lag{k}`, k ∈ {0,1,2,3,4,5,6,12,24,48,168} for 5 targets | 55 | origin |
| Rolling | `{target}_roll{6,24}_{mean,std}` | 20 | origin |
| Clear-sky index (history) | `csi_hist` = ghi_lag0 / clearsky_ghi(t) (0 when zenith ≥ 85) | 1 | origin |
| Calendar | `hour_sin/cos`, `doy_sin/cos`, `monsoon` (UTC month 6–9) at target time | 5 | target |
| Geometry | `zenith`, `azimuth_sin/cos`, `clearsky_ghi` at target midpoint | 4 | target |
| Covariates (corrected GFS) | `ghi,dni,dhi,temp,rh,pressure,ws10,ws_hub,precip,cloud` + `wd10_sin/cos`, `wd_hub_sin/cos`, `csi_cov` | 15 | target |
| Horizon | `horizon` | 1 | — |

- `lag0` is an addition to the listed t−1…6,12,24,48,168: persistence uses the value at t and omitting it would make the model strictly worse than its own baseline [ASSUMED: planner may confirm; adding does not violate FEAT-02].
- Weather-only feature set = history + calendar + geometry + horizon (≈85 cols). Covariate set adds the 15 covariate cols (≈100 cols). `FEATURE_SPEC` defines both named sets.
- `global_tilted_irradiance` is NOT in the canonical frame (CANON_COLS has 12 columns, GTI dropped in Phase 2); PRD's GTI covariate is dropped. Say so in the spec [VERIFIED: `swf.align.canon.CANON_COLS`].
- Covariates are `apply_correction(GFS)`: the ML pipeline sees corrected rh/ws10/ws_hub (D-03 "same inputs the ML pipeline sees"), ghi/dni/dhi uncorrected.
- Dtype float32 for all feature columns; `monsoon` stored as float32 0/1 for LightGBM simplicity.
- Direction: sin/cos only, never raw degrees; hub direction `wd_hub` is 80 m (OM) / 50 m (NASA proxy) per the adapter.

### FEATURE_SPEC hash (FEAT-01)
`spec.py` holds a plain dict: `spec_version` (int, bump by hand when computation logic changes), `time_convention`, `targets`, `lags`, `windows`, `covariate_cols`, `geometry_cols`, `calendar_cols`, `horizons` (1..72), ordered column lists for both named sets, and `dtype`. `spec_hash() = sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")))[:16]`. Artifacts (Phase 5/6) store `{"feature_spec_hash", "feature_columns", "feature_set"}`; `assert_spec(artifact_hash)` raises `ValueError` listing the diff at load. A **golden-hash unit test** (constant committed in the test) forces a conscious update when the spec changes. Config values that affect the spec (lags, windows) are read into the spec from `features.yaml`, so editing yaml changes the hash. Logic changes with identical params (e.g. different correction) are covered only by `spec_version` (human discipline; note in pitfalls).

## Splits and purge rule (FEAT-04)

Config (`features.yaml`): `val: 2024`, `test: 2025`, `train_weather_only: [2001-01-01, 2023-12-31 23:00]`, `train_covariate: [2021-04-01, 2023-12-31 23:00]`. Rule, one function `origins_for(split)`:

`origin t is kept iff start ≤ t and t + 72 h ≤ end` (all 72 targets lie inside the same split), and for training additionally `t ≥ start + 168 h` only for the *weather-only train start* (history warm-up; val/test have earlier history available so no warm-up loss there).

Counts (hourly origins; 72 horizons; per target):

| Split | Origin range (UTC) | Origins | Rows (×72) | ×5 targets |
|-------|--------------------|---------|------------|-----------|
| train weather-only | 2001-01-08 00:00 → 2023-12-28 23:00 | 201,384 | 14.50 M | 72.5 M |
| train covariate | 2021-04-01 00:00 → 2023-12-28 23:00 | 24,048 | 1.73 M | 8.66 M |
| val 2024 (leap) | 2024-01-01 00:00 → 2024-12-28 23:00 | 8,712 | 627,264 | 3.14 M |
| test 2025 | 2025-01-01 00:00 → 2025-12-28 23:00 | 8,688 | 625,536 | 3.13 M |

(Computed by hand from calendar arithmetic; planner's test should assert these numbers.) The last 72 origins of each split are dropped (0.8%): this is the purge. No extra 168 h embargo is needed: lag windows only read *past observed* history, and a val origin reading train-period history is exactly what serving does; the embargo in PITFALLS C4 matters only if training targets could overlap val history, which the `t+72 ≤ end` rule already excludes [reasoned; MEDIUM].

Memory (15.6 GB RAM machine, measured): the weather-only training set is 14.5 M rows × ~85 float32 cols ≈ 4.9 GB per target if fully materialised, too heavy to hold five at once. Recommendation: the builder returns **lazy chunks** (`iter_chunks(origins, horizons, n_origins=2000)`), and the trainer subsamples origins by a stride (e.g. every 6th origin → 33.6 k origins × 72 ≈ 2.4 M rows ≈ 0.8 GB) or draws random horizons per origin. D-01 allows deep-model subsampling; LightGBM subsampling is Phase 5's call. Val/test fit easily (630 k rows × 100 × 4 B ≈ 250 MB).

LightGBM direct multi-horizon: with the horizon-as-feature framing (PRD 9.2 and REQUIREMENTS), one model per target sees all 72 horizons; the origin×h gather above is exactly its input. No per-horizon models needed in Phase 4.

`log_splits()` prints and writes the table above (ranges, origin counts, first/last origin, purge count) into an `AUTO:features` block in `docs/data_notes.md`.

## Baselines

All baselines emit the long format for `val` and `test` (and `train` is not required). Truth series `y_true` for target T: NASA weather columns (`rh`, `ghi`, `ws10`) and `energy_sim` (`t1_kw`, `t5_kw`) from `data/interim/` [VERIFIED: `swf.physics.constraints.TARGET_COLS`; `energy_sim.parquet` is `simulate(NASA weather)` + `enforce`, 2001-01-01..2025-12-31, 219,144 rows, no NaN].

| Model name | Definition for origin t, horizon h, target time T=t+h |
|-----------|--------------------------------------------------------|
| `persistence` | non-solar targets: `y[t]`. Solar kW: `y[T − 24·ceil(h/24)]` (same hour of day, most recent observed day, ≤ t). The same-hour rule is applied to `t1_kw` only (GHI too would arguably be fair; recommend applying it to `ghi` as well, since flat `y[t]` for a nighttime-zero variable is a strawman — [ASSUMED], planner/user to confirm). Computed on the truth series (the strongest, most favourable persistence; the site's version would use ERA5/OM history — state this) |
| `climatology` | mean of truth over (UTC month, UTC hour) across 2001–2023, looked up at T. One 12×24 table per target. Same table for all models and splits (a baseline, not a trained covariate model) |
| `baseline3` (official) | lead-matched: `chain(corrected(gfs_pr_d{k}))[T]`, k = ceil(h/24) |
| `baseline3_raw` | same without `apply_correction` |
| `baseline3_stitched` | `chain(corrected(gfs_hf))[T]` (h-independent) |
| `baseline3_stitched_raw` | `chain(gfs_hf)[T]` |

`chain` = for rh, ghi, ws10: the GFS canonical column directly; for t1_kw, t5_kw: `simulate(df, s, curve)` (which already ends in `enforce`), then `enforce` on the assembled frame so rh ∈ [0,100], ghi ≥ 0 and night = 0 [VERIFIED: `swf.physics.simulate.simulate`, `constraints.enforce`]. Run the chain on the whole PR/HF table once per variant (≤ 44 k rows, seconds), then expand to the long format by lookup, never per origin.

Notes:
- Correction only touches rh, ws10, ws_hub (coefficients file has no ghi key, so `apply_correction` skips ghi and does not call `is_night`) [VERIFIED: `config/bias_correction.json` keys per Phase 2; `apply_correction` code].
- Corrected ws10 feeds Faiman cell temperature in the solar chain, as in `simulate_solar`.
- NaN predictions (PR before 2024-01-19..21 for 10 m vars, before ~2024-02-16..18 for hub wind, last hour 2025-12-31 23:00) stay NaN and drop out via the shared index. Do not gap-fill baseline inputs beyond what `clean()` already did.
- The D-04 table: bias = mean(corrected GFS − NASA truth) per variable (rh, ws10, ws_hub, plus ghi uncorrected) × lead day (d1, d2, d3, stitched) on 2024 (and 2025 as a second column), written to `reports/evaluation/gfs_bias_2024.csv` plus a figure. Also write the stitched-vs-lead-matched RMSE gap table (the "covariate skew" quantification).

## Long prediction format and storage (EVAL-04)

Columns exactly: `issue_time` (datetime64[ns, UTC]), `horizon` (int16), `target_time` (datetime64[ns, UTC]), `target` (category: `t1_kw, rh, ghi, ws10, t5_kw`), `model` (category), `y_true` (float32), `p10`, `p50`, `p90` (float32; point models set p50 = prediction, p10/p90 NaN). `validate_long()` asserts: columns/dtypes, `target_time == issue_time + horizon h`, horizon ∈ 1..72, no duplicate `(issue_time, horizon, target, model)`, `y_true` equals the truth lookup, issue_time inside the split's purged origin set.

Storage: `data/processed/predictions/{split}/{model}.parquet` (zstd, gitignored under `data/`). One model-split ≈ 3.1 M rows ≈ 60–100 MB. Reading with `pyarrow` + `filters` or a column subset keeps memory small. No further partitioning needed; evaluation loads one target at a time (630 k rows). Phase 5/6 models write the same path pattern; the leaderboard globs `*/*.parquet`. Committed outputs (CSV/PNG, no timestamps) are byte-deterministic; sort rows and fix float formatting (`float_format="%.6g"`).

## Metrics (EVAL-05/06)

New numpy-only `swf.evaluate.metrics`; keep `swf.validate.metrics.error_stats` untouched (Phase 3 tests depend on its keys `rmse_kw`, `mae_kw`, `mbe_pct`, `nrmse_pct`; it also hard-codes `_kw` names) and reuse its logic in a generic function:

- `metrics(y, p, norm) -> {n, mae, rmse, mbe, nrmse_pct, norm, norm_kind}` on complete pairs.
- Norms: `t1_kw` → `ac_cap_kw(s)` (=800 kW), `t5_kw` → `s.wind.rated_kw` (3600), `rh/ghi/ws10` → mean of `y_true` over the **scored common sample for that (target, split)**, computed once and reused for every slice and model, so slices and models are comparable [recommended refinement of the CONTEXT default; the norm and its kind are written to every row].
- Daytime mask: `solar_position(target_time_index, s)["zenith"] < 85` evaluated at the **target time** midpoint (`swf.physics.common` already adds 30 min). Apply to `t1_kw`; recommend also `ghi` (same reason: nighttime is a deterministic zero) [ASSUMED for ghi; CONTEXT only names solar].
- Skill: `1 − RMSE_model / RMSE_ref` on the shared index; refs: `baseline3` (official corrected, lead-matched) and `persistence`. Shared index = rows (issue_time, horizon, target) where **every model in the comparison set** has a finite prediction and y_true is finite. Report both `n_own` (own index) and `n_shared`; leaderboard RMSE/MAE/nRMSE columns on the shared index; also `rmse_own_index` for transparency. Because PR is missing early 2024, the shared index for wind starts ~Feb 2024.
- Season: monsoon = target-time UTC months 6–9, dry otherwise (season attached by **target time**; state it).
- Horizons: exact values {1, 6, 24, 48, 72} plus "all" (≈8.7 k samples each per target on val, adequate). Also define in config the four buckets for Phase 6's EVAL-09 heatmap: 1–6, 7–24, 25–48, 49–72 (edges stated).
- Breakdown table (`breakdown.csv`): rows = (split, target, model, horizon ∈ {1,6,24,48,72,all}, season ∈ {monsoon, dry, all}) with n, mae, rmse, nrmse_pct, skill_vs_baseline3, skill_vs_persistence. Leaderboard (`leaderboard.csv`): (split, target, model) aggregated over all horizons, same columns. Leaderboard rows for both `val` and `test`; baselines have no tuning so scoring them on test now does not compromise "test evaluated once" for ML models, provided Phase 6 selection uses val only.
- Plots (lazy matplotlib): RMSE-by-horizon lines per target (all baselines), skill bars; saved to `reports/evaluation/`.

Wind and probabilistic items (capacity factor, coverage, pinball, reliability) are EVAL-08..10, Phase 6; the p10/p90 columns just have to exist.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Source → canonical frame | new parsers | `swf.align.adapters.openmeteo_canon` / `load_source` | single −1 h label shift logic, validated |
| Gap policy / physical clipping | new cleaner | `swf.align.clean.clean` | same policy train and serve |
| ERA5/GFS → NASA space | new scaling | `swf.align.consistency.apply_correction` + `load_coefs` | the one train/serve function |
| kW from weather | new PV/wind formulas | `swf.physics.simulate.simulate` + `constraints.enforce` | Phase 3 validated |
| Sun position, night, clear-sky | own astronomy | `swf.physics.common.solar_position / is_night / clearsky` | midpoint convention already handled |
| AUTO doc blocks | string splice | `swf.coverage.report.write_auto_block`, `_table` | idempotent |
| CLI wiring | custom main | `cli.py` `_run` pattern | lazy imports |
| Config models | dict access | pydantic `extra=forbid` + yaml (`load_features_cfg`) | Phase 3 pattern |
| Spec hash | pickle/repr hash | canonical JSON sha256 | stable across Python versions |

**Key insight:** this phase is mostly composition. New logic is limited to index arithmetic (origin/target axes), the lead mapping, and metric aggregation; each of those has a cheap unit test.

## Common Pitfalls

### Pitfall 1: target-axis lags (C4)
**What goes wrong:** `shift(k)` on a table indexed by target time leaks for h > k. **Avoid:** two-axis design. **Detect:** the perturbation test (randomise history after t, history columns must not change).

### Pitfall 2: timezone-naive or wrong-offset joins
**What goes wrong:** `get_indexer` on mismatched tz or non-hourly labels silently gives −1. **Avoid:** assert tz-aware UTC, hourly gap-free index before gather; raise if any indexer is −1 (instead of NaN). Never `tz_convert` in pipeline logic.

### Pitfall 3: PR coverage gaps reading as zero error
**What goes wrong:** NaN baseline predictions dropped per model make models look different-sample. **Avoid:** shared index; log `n_shared` vs `n_own`; fail the leaderboard if `n_shared` < 50% of the split rows for a target.

### Pitfall 4: correction hurts, and nobody says so
**What goes wrong:** the official baseline-3 row (corrected) is worse than raw for ws10 and wind kW (measured above), so "ML beats baseline 3" could be vacuous. **Avoid:** always print both rows; the report states it; skill is vs the corrected row per D-03 and ALSO vs raw/persistence columns so the claim is robust.

### Pitfall 5: baseline 3 weaker than persistence
**What goes wrong:** at h≈24 daytime solar persistence RMSE is 55 kW vs 132 kW for baseline 3. This is real (NASA truth is itself a coarse product; GFS and NASA disagree), not a bug. **Avoid:** verify with a physics sanity test (baseline 3 on NASA weather itself reproduces `energy_sim` exactly) before trusting numbers. That identity test is the cheapest proof that the chain is wired correctly.

### Pitfall 6: spec hash drifting silently
Logic changes (e.g. correction coefficients) don't change the hash. Mitigate: include `bias_correction.json` sha256 and `energy`-chain parameters (loss_pct, dc_ac_ratio) in the spec hash input; golden-hash test.

### Pitfall 7: pandas 3 behaviour
Copy-on-write: build new frames, don't assign into slices. Default `str` dtype: keep `target`/`model` as `category` explicitly before writing parquet. `rolling().std()` uses ddof=1 (state it; same code both paths so parity holds).

### Pitfall 8: determinism
Committed CSV/PNG: sort, fixed float format, `matplotlib.use("Agg")`, no timestamps/metadata (`metadata={"Software": None}` for PNG).

## Code Examples

### Lead-matched covariates / baseline-3 lookup
```python
# Source: this research; D-02, PR files are indexed by valid time
def lead_k(h):                       # vectorised
    return -(-h // 24)               # ceil(h/24)

def baseline3_long(pred_by_k, origins, horizons):
    # pred_by_k: {1: DataFrame(5 target cols, index=valid time), 2: ..., 3: ...}
    out = []
    for k in (1, 2, 3):
        hs = horizons[lead_k(horizons) == k]
        T = origins.values[:, None] + (hs * 3600 * 10**9).astype("timedelta64[ns]")[None, :]
        ...  # reindex pred_by_k[k] at T.ravel(); stack into long rows
```

### Leakage test (truncation + perturbation)
```python
# Source: this research
def test_no_future_in_history_features(hist, spec):
    full = origin_table(hist, spec)
    for t in rng_origins:                              # e.g. 25 random origins incl. month/year edges
        trunc = origin_table(hist.loc[:t], spec).loc[t]          # data after t removed
        assert_series_equal(full.loc[t], trunc, check_names=False)
        pert = hist.copy(); pert.loc[pert.index > t] = rng.normal(size=...) * 1e6
        assert_series_equal(origin_table(pert, spec).loc[t], full.loc[t], check_names=False)
```
For target-axis columns the allowed exception is exactly the row at `t+h`: perturb covariates at times ≠ t+h (and everything after t+h) and assert the assembled row for `(t,h)` is unchanged; perturb the covariate at t+h and assert the covariate columns DO change (proves the test is sensitive).

### Parity test
```python
# Source: this research; fixture already committed: tests/fixtures/om_live_gfs_seamless.json (264 h, 14 vars)
raw = (fixtures_dir / "om_live_gfs_seamless.json").read_bytes()
canon = clean(openmeteo_canon(raw, s), s, source="live")[0]
hist = history_frame(canon, s, coefs, curve)
batch = assemble(hist, cov, origins=all_valid_origins, horizons=range(1, 73))      # "training" call
one = assemble(hist.loc[:t].iloc[-W:], cov.loc[: t + 72h], origins=[t], horizons=range(1, 73))  # "serving" call
pd.testing.assert_frame_equal(batch.xs(t), one, check_exact=True)
assert list(one.columns) == FEATURE_SPEC["sets"]["covariate"]
```
Window W: at least 168 + 1 hours of history (the live fixture: past_days=7 gives exactly 7 full days before today; the latest valid origin is today's last completed hour, e.g. 2026-11-02T12:00, and t−168 = 2026-10-26T12:00 is inside the file). The fixture has labels 2026-10-26T00:00 → 2026-11-05T23:00; choose origins whose t+72 ≤ 2026-11-05T23:00 and t−168 ≥ 2026-10-26T00:00, i.e. t ∈ [2026-11-02T00:00, 2026-11-02T23:00]. Also assert the serving window length requirement (≥169 h) raises a clear error when violated. A second cheap check: write the same JSON bytes as a year file into a tmp raw cache and run `load_source("era5", ...)` to prove the training loader and the serving adapter produce the same canon frame (use the existing cache helpers; skip if awkward).

## State of the Art / Project-specific changes

| Old (PRD) | Current (errata/CONTEXT) | Impact |
|-----------|--------------------------|--------|
| Single NWP "Open-Meteo best_match" | GFS `gfs_seamless` everywhere | covariate train window starts 2021-04 |
| Baseline 3 on stitched forecast | lead-matched PR primary, stitched alongside | val gaps early 2024; D-02 mapping |
| `pvwatts_ac` | `pvlib.inverter.pvwatts` | already handled in Phase 3 |
| GTI covariate | dropped (not canonical) | 14→ no GTI column |
| Raw day-of-year | sin/cos + monsoon flag | lesson from PRD §8 |

## Runtime State Inventory
Not a rename/refactor phase: omitted. (New artifacts only: `data/processed/` and `reports/evaluation/`.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Add `lag0` (value at origin) beyond the listed lags | Feature Catalogue | None functionally; user may prefer literal list |
| A2 | Apply the daytime mask and same-hour-yesterday persistence to `ghi` as well as `t1_kw` | Baselines, Metrics | Leaderboard GHI numbers differ from a literal reading of EVAL-05; user may want solar kW only |
| A3 | Persistence is computed on the NASA truth series, not ERA5-derived history | Baselines | Persistence bar slightly stronger than what the live site could compute |
| A4 | No 168 h embargo beyond the `t+72 ≤ split end` rule | Splits | If the user wants PITFALLS' embargo literally, drop 168 more origins before each val/test start (cheap to add as config) |
| A5 | `previous_day{k}` run cycle/issue instant is approximate (docs don't name it) | Pattern 3 | Report wording only |
| A6 | Exact-horizon (not bucket) rows for {1,6,24,48,72}; buckets 1–6/7–24/25–48/49–72 defined for Phase 6 | Metrics | Planner's choice per CONTEXT |
| A7 | Do not add lead age as a feature (constant in training) | Summary | If user wants it, covariate models need PR-based training data which exists only for 2024–2025 (val/test) |

## Open Questions

1. **Does the corrected row become the official bar even though raw is better for wind?**
   - What we know: measured above; D-03 locks corrected as official, reports both.
   - Resolution: RESOLVED by D-03/D-04 (keep corrected official, show raw next to it, state the finding). Surface the finding to the user in the plan summary.
2. **Origin convention for the live site** (last completed label vs current hour).
   - What we know: radiation labelled at interval start; the hour labelled t is complete only at t+1 h.
   - Recommendation: lock "origin = last fully observed label" in `FEATURE_SPEC.time_convention`; Phase 5 must feed the same.
3. **GHI daytime mask / same-hour persistence for GHI (A2).** Not decided by CONTEXT. Recommend yes for both; planner may confirm with the user, or default to yes and document.
4. **Hub-wind early-2024 gap** (~7 weeks): RESOLVED as handled by the shared index; no data fetch needed (never re-download).
5. **Covariate-model validation covariates** (stitched or lead-matched at val/test): Phase 5 decision. Phase 4 provides both assemblers; recommend lead-matched for val/test (it is what serving sees) with stitched reported alongside.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv (`.venv`) | all | ✓ | 3.12 | — |
| pandas / pyarrow / pvlib | features, eval | ✓ | 3.0.6 / 26.0.0 / 0.16.1 | — |
| matplotlib | plots | ✓ (train extra) | 3.11.2 | skip plots if absent (lazy import) |
| `data/interim/*.parquet` (9 files) | everything | ✓ | built Phase 2 | `python -m swf build-weather && python -m swf simulate-energy` |
| `config/bias_correction.json` | correction | ✓ | committed | — |
| Network | — | not needed | — | Phase 4 is fully offline |
| RAM | chunked builder | ✓ | 15.6 GB | chunk size parameter |

No missing dependencies. Geometry cost: `solar_position` + `clearsky` for all 219 k hours ≈ 7 s each, computed once per build.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (default `-m 'not network and not realdata'`) |
| Quick run command | `.venv/Scripts/python.exe -m pytest tests/test_features_*.py tests/test_splits.py tests/test_evaluate_*.py -x` |
| Full suite command | `.venv/Scripts/python.exe -m pytest` (and `-o addopts="" -m realdata` for parquet-backed checks) |

Synthetic frames come from `tests/synth.py::canon_frame` so default tests are offline and fast; parquet-backed identity and leaderboard checks use `@pytest.mark.realdata`.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FEAT-01 | golden spec hash; `assert_spec` raises on mismatch; hash changes when a lag param changes | unit | `pytest tests/test_features_spec.py -x` | ❌ Wave 0 |
| FEAT-02 | column names/counts/order match spec; no raw `doy`/degree columns; sin²+cos²=1; monsoon flag months | unit | `pytest tests/test_features_build.py -x` | ❌ Wave 0 |
| FEAT-03 | `history_frame` same output when fed ERA5 frame vs same data via serving adapter; kW columns equal `enforce(simulate(correct))` | unit | `pytest tests/test_features_history.py -x` | ❌ Wave 0 |
| FEAT-04 | origin counts per split (201,384 / 24,048 / 8,712 / 8,688), no target crosses boundary, ranges logged | unit | `pytest tests/test_splits.py -x` | ❌ Wave 0 |
| FEAT-05 | truncation + perturbation + sensitivity check (covariate at t+h does change) | unit | `pytest tests/test_features_leakage.py -x` | ❌ Wave 0 |
| FEAT-06 | batch vs single-origin identical on committed OM live JSON; short-window raises | unit | `pytest tests/test_features_parity.py -x` | ❌ Wave 0 (fixture exists) |
| EVAL-01 | persistence value at t / same-hour-yesterday for solar, hand-computed small case | unit | `pytest tests/test_evaluate_baselines.py::test_persistence -x` | ❌ Wave 0 |
| EVAL-02 | climatology equals groupby mean, uses only train years | unit | `... ::test_climatology` | ❌ Wave 0 |
| EVAL-03 | lead map k=ceil(h/24) at h=1,24,25,48,49,72; baseline3 on NASA weather reproduces `energy_sim` (identity); corrected vs raw differ only in rh/ws; NaN PR rows stay NaN | unit + realdata | `... ::test_lead_map`, `::test_identity` | ❌ Wave 0 |
| EVAL-04 | `validate_long` rejects bad columns/dup keys/target_time mismatch/wrong y_true | unit | `pytest tests/test_evaluate_longfmt.py -x` | ❌ Wave 0 |
| EVAL-05 | metrics by hand; skill on shared index (drop rows where any model NaN); daytime mask drops night rows; norms (800, 3600, mean) | unit | `pytest tests/test_evaluate_metrics.py -x` | ❌ Wave 0 |
| EVAL-06 | breakdown has horizons {1,6,24,48,72,all}, seasons, targets; monsoon months 6–9 | unit | `... ::test_breakdown` | ❌ Wave 0 |
| EVAL-07 | `leaderboard.csv` has 6 baseline model rows × 5 targets × {val,test}; deterministic bytes on rerun | realdata | `pytest -o addopts="" -m realdata tests/test_evaluate_report.py` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the quick command above (< 30 s, synthetic data).
- **Per wave merge:** full default suite.
- **Phase gate:** full suite plus the `realdata` set green before `/gsd:verify-work`; run `python -m swf features`, `baselines`, `evaluate` twice and diff `reports/evaluation/*.csv` (determinism).

### Wave 0 Gaps
- [ ] test files listed above (all new); extend `tests/synth.py` with a helper that builds a synthetic `hist` frame (5 target columns) and a fake PR trio.
- [ ] `config/features.yaml` + pydantic `FeaturesCfg` + `load_features_cfg` in `swf.core.settings`.
- No framework install needed.

## Security Domain

`security_enforcement` is not set to false; applicable surface is small (offline batch code, no network, no user input).

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2/V3/V4 Auth, session, access | no | — |
| V5 Input validation | yes | pydantic config (`extra=forbid`); `validate_long`; fail loud on index/tz/hourly violations; the serving path (Phase 5) feeds untrusted Open-Meteo JSON, so the window-length and NaN checks in the builder are the boundary |
| V6 Cryptography | no (sha256 is an integrity fingerprint, not a secret) | stdlib hashlib |

| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Corrupt/NaN upstream JSON poisoning features | Tampering | `openmeteo_canon` + `clean` + builder asserts; NaN tolerated, never silently zero-filled |
| Stale/incompatible model artifact | Tampering | `assert_spec` at load |
| Path traversal in model/split names | Tampering | name regex like `fetch.cache.safe_part` for `model` used in file paths |

## Sources

### Primary (HIGH confidence)
- Repo code read this session: `swf/align/{adapters,canon,clean,consistency}.py`, `swf/physics/{common,solar,wind,constraints,simulate}.py`, `swf/validate/metrics.py`, `swf/core/{settings,paths}.py`, `swf/cli.py`, `swf/coverage/report.py`, `tests/fixtures/*`, `pyproject.toml`.
- Measured read-only from `data/interim/*.parquet`: coverage, NaN months, baseline RMSE numbers quoted above.
- Open-Meteo Previous Runs docs https://open-meteo.com/en/docs/previous-runs-api (fetched 2026-11-03): `_previous_dayN` = value predicted N×24 h before valid time; run cycle not named; GFS 2 m temperature back to March 2021.
- `docs/data_notes.md` (coverage, correction decision), `.planning/research/PITFALLS.md` C1, C4, C5.

### Secondary (MEDIUM)
- PRD §7.5, §8, §9 (errata override).

### Tertiary (LOW)
- none

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, no new packages, versions read from the venv.
- Architecture: MEDIUM-HIGH, two-axis design is a recommendation, but it follows directly from the leakage definition and was checked against the repo's index conventions.
- Pitfalls: HIGH for the data-driven ones (correction hurts wind; PR gaps), MEDIUM for the rest.

**Research date:** 2026-11-03
**Valid until:** 2026-12-03 (data and code stable; re-check only if interim parquets are rebuilt)

## Wave structure sketch (for the planner)

- **Wave 0 (foundation, sequential):** `config/features.yaml` + `FeaturesCfg`; `spec.py` (FEATURE_SPEC + hash + golden test); `splits.py` (+ counts test); `evaluate/longfmt.py`; `evaluate/metrics.py` (+ tests); synth helpers.
- **Wave 1 (parallel):** (a) `history.py` + `build.py` + `covariates.py`; (b) `evaluate/baselines.py` (persistence, climatology, baseline 3 four variants, identity test).
- **Wave 2 (parallel):** (a) leakage + parity tests and fixing what they find; (b) `evaluate/report.py`: leaderboard, breakdowns, D-04 bias table, plots, AUTO blocks.
- **Wave 3:** CLI wiring (`features`, `baselines`, `evaluate`), real-data run, determinism rerun diff, `data_notes.md` AUTO:features / AUTO:evaluation, full pytest.
Never cut: baseline 3 (all four variants can shrink to two if time is short: official + raw), the leakage and parity tests, the leaderboard.
