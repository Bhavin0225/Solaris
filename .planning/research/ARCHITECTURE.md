# Architecture Research

**Domain:** ML weather/energy forecasting system (offline training pipeline + online serving API + SPA), single site, 5 coupled targets, 72 h hourly
**Researched:** 2026-11-01
**Confidence:** MEDIUM-HIGH (structure and patterns: HIGH from PRD plus well-known practice; Open-Meteo lead-time semantics: HIGH, verified on official docs; Darts TFT details: MEDIUM, Context7 snippets; deployment-tier behaviour such as free-tier sleep: MEDIUM, from general knowledge, verify on the chosen host)

## Standard Architecture

Production forecasting systems (energy, NWP post-processing) all split into two programs that share one library: an **offline batch pipeline** (slow, reproducible, GPU, writes artifacts) and an **online inference service** (fast, tiny, read-only on artifacts, writes only a forecast cache). The thing that keeps them honest is a **shared pure-function core** (config, time handling, canonical weather schema, physics, feature builder, predictor interface). Everything else is glue.

### System Overview

```
 EXTERNAL                 OFFLINE (laptop + GPU, `make data/train/evaluate`)
┌──────────┐   ┌─────────────────────────────────────────────────────────────────────┐
│NASA POWER│──▶│ fetch ─▶ raw cache ─▶ align/clean ─▶ physics sim ─▶ validate(Kaggle)│
│Open-Meteo│──▶│ (httpx,   data/raw    (canonical     (T1,T5 truth)   gate, tune loss │
│ (3 APIs) │   │  backoff)             UTC frame)          │                          │
│Kaggle CSV│──▶│                                           ▼                          │
└──────────┘   │        features (SHARED) ─▶ splits ─▶ train {baselines, LGBM, LSTM, TFT}
               │                                           │                          │
               │              predictions.parquet (common long format)                │
               │                                           ▼                          │
               │            evaluate ─▶ leaderboard ─▶ select (§9.4) ─▶ registry.json │
               └───────────────────────────────────────────┬─────────────────────────┘
                                                           │ artifacts (git / image)
          SHARED CORE  swf.core / swf.physics / swf.features / swf.predict
                                                           │
               ONLINE (small container, 1 uvicorn worker)  ▼
┌──────────┐   ┌─────────────────────────────────────────────────────────────────────┐
│Open-Meteo│──▶│ APScheduler hourly ─▶ fetch fcst(+past) ─▶ canonicalise (+bias corr)│
│ forecast │   │        │                                        │                    │
└──────────┘   │        │         features (SAME code) ◀─────────┘                    │
               │        ▼                    │                                        │
               │  registry-dispatched Predictor ─▶ clip (physical) ─▶ SQLite upsert   │
               │                                                        │             │
               │  FastAPI  /api/* ◀──────── read latest run ◀───────────┘             │
               └──────────────┬──────────────────────────────────────────────────────┘
                              │ JSON (UTC ISO-8601), OpenAPI
                       ┌──────▼───────┐
                       │ React SPA    │  static host; UTC→IST only here
                       └──────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `swf.core` | Config loading (`site.yaml`, `plant.yaml`), UTC time helpers, canonical column names/units/ranges, paths, logging | pydantic models over YAML; one `Settings` object; a `CANON_COLS` constant |
| `swf.fetch` | HTTP to NASA/Open-Meteo, disk cache keyed by (api, params, range), retry/backoff, `-999`→NaN, structured fetch log | httpx + tenacity-style loop; raw JSON stored verbatim; no parsing logic beyond adapters |
| `swf.align` (adapters) | Source-specific JSON → **canonical hourly UTC DataFrame**. Only place that knows NASA vs Open-Meteo quirks (timestamp label shift, radiation = preceding-hour mean, wind heights, units) | `nasa_to_canonical()`, `openmeteo_to_canonical()`, shift offset read from config (result of the P2 timestamp test) |
| `swf.clean` | Reindex, gap-fill ≤3 h, clip to physical ranges, night GHI=0, % missing report | pure `DataFrame -> DataFrame` |
| `swf.physics` | Canonical weather → T1/T5 kW (pvlib chain, hub extrapolation, air density, power curve, availability). Used for **training truth (NASA)**, **baseline 3 (Open-Meteo)**, and **serving fallback** | pure functions + config; no I/O |
| `swf.validate` | Kaggle calibration of loss %, power curve build, nRMSE gates, scatter plots, `metrics.json`. Offline only | reads `data/raw/kaggle`, writes `reports/validation`, writes `config/power_curve.csv` and tuned loss into config |
| `swf.features` | **The single feature builder** + `FEATURE_SPEC` (ordered names, dtypes, hash). Offline vectorised over many issue times; online called with one | pure functions, causal only |
| `swf.datasets` | Splits, direct-row builder, seq2seq window index, scalers | offline only (imports features) |
| `swf.models` | Training code + **Predictor implementations** with one interface: `Baseline3`, `Persistence`, `Climatology`, `LGBM`, `Seq2Seq`, `TFT` | `predict(features) -> long DataFrame` |
| `swf.evaluate` | Model-agnostic metrics over `predictions.parquet`; leaderboard; §9.4 selection; writes registry | groupby on common long format |
| `swf.predict` | Registry loader + `Predictor` protocol + physical-constraint clipping. The **only** model-facing module the API imports | lazy imports so torch is optional |
| `swf.api` | FastAPI app, scheduler job, SQLite repository, Pydantic response schemas, stale logic | 1 process, 1 worker |
| `frontend/` | Dashboard, performance, about; fetches `/api/*`; IST conversion; stale banner | Vite + React + TS + Tailwind + Recharts; types generated from OpenAPI |

## Recommended Project Structure

PRD §12 layout is right; adjust to enforce the dependency direction (below).

```
config/                 site.yaml  plant.yaml  power_curve.csv  features.yaml(optional)
src/swf/
├── core/               settings.py  timeutil.py  schema.py(CANON_COLS, ranges)  logging.py
├── fetch/              nasa.py  openmeteo.py  cache.py        # I/O only
├── align/              adapters.py  clean.py  bias.py         # NASA/OM -> canonical; OM->NASA-space correction
├── physics/            solar.py  wind.py  convert.py          # canonical -> T1,T5
├── features/           build.py  spec.py                      # SHARED train+serve
├── datasets/           splits.py  direct.py  windows.py
├── models/             base.py(Predictor)  baselines.py  lgbm.py  seq2seq.py  tft.py
├── evaluate/           metrics.py  leaderboard.py  select.py
├── validate/           kaggle.py
├── predict/            registry.py  runtime.py  clip.py       # serving-side model access
├── api/                main.py  scheduler.py  repo.py(sqlite)  schemas.py
└── cli.py              # `python -m swf.cli fetch|build|simulate|validate|dataset|train|evaluate|export|serve`
data/{raw,interim,processed}   # git-ignored, + processed/manifest.json (hashes)
models/
├── runs/<run_id>/<model>/<target>/   # training outputs (git-ignored)
└── deployed/                         # committed, small; what the image ships
    ├── registry.json
    └── <model>/<target>/{model.txt|model.onnx|state.pt, meta.json}
reports/{validation,evaluation}/   leaderboard.csv + leaderboard.json (API/FE)
tests/                 (incl. test_leakage.py, test_train_serve_parity.py, fixtures/om_sample.json)
frontend/  Makefile  Dockerfile  docs/data_notes.md
```

### Structure Rationale

- **Dependency direction (enforce by review, optionally `import-linter`):** `core ← fetch/align ← physics ← features ← {datasets, models} ← evaluate`; `api` imports only `core, fetch.openmeteo, align, physics, features, predict`. `api` must never import `datasets, evaluate, validate, models.train`, or kaggle/matplotlib/torch at module load. This keeps the serving image small and guarantees the serving path uses the same functions the training path does.
- **`align/adapters` as the single quirk-holder:** all NASA/Open-Meteo differences (label offset, units, heights) are resolved once into the canonical schema, so features/physics/models are source-agnostic.
- **`predict/` split from `models/`:** training code can import torch/darts/pytorch-forecasting freely; serving code imports only the runtime classes it needs.
- **`models/deployed/` committed:** LightGBM artifacts are MBs; committing selected artifacts makes `docker build` self-contained and the deploy reproducible from a clean clone (P10 acceptance).

## Architectural Patterns

### Pattern 1: One feature function, two call sites (kills train/serve skew in code)

**What:** A single causal feature builder works on a canonical hourly frame indexed by UTC and a list of issue times. Training calls it with thousands of issue times (vectorised via `shift`/`rolling`); serving calls it with `[latest_complete_hour]`. No second implementation, no notebook-only features.

**When to use:** Always here. This is the main defence against code skew.

**Trade-offs:** Forces features to be expressible on a trailing window of ≤ ~8 days (fine: max lag 168 h). Vectorised-over-all-times is slightly less natural than per-row, but the parity test makes it safe.

```python
# swf/features/build.py  (sketch)
def per_timestamp_features(canon: pd.DataFrame, cfg) -> pd.DataFrame:
    """Causal: row t uses data <= t only. Lags, rolling (closed right), calendar sin/cos,
    solar zenith/azimuth/clear-sky (pvlib, deterministic from time+config), dir sin/cos."""

def future_covariates(nwp: pd.DataFrame, cfg) -> pd.DataFrame:
    """Open-Meteo vars indexed by *target* time (known future)."""

def make_direct_rows(base, fut, issue_times, horizons, cfg) -> pd.DataFrame:
    """row=(issue t, horizon h): base[t] + fut[t+h] + h + baseline3_pred[t+h]. Returns columns == FEATURE_SPEC.names"""

# training:  make_direct_rows(base, fut, issue_times=train_grid, horizons=range(1,73))
# serving :  make_direct_rows(base, fut, issue_times=[now_hour],  horizons=range(1,73))
```

Guard-rails (all cheap, all required):
1. `FEATURE_SPEC` = ordered column list + dtypes; `feature_spec_hash` stored in every model's `meta.json`; `predict.registry` refuses to load if hash != code's hash.
2. **Truncation-invariance leakage test:** build features on the full frame, then on the frame truncated at issue time t; row t must be identical (excluding the declared known-future columns). This is stronger than "no column uses a shift(-k)" and satisfies PRD §13.
3. **Train/serve parity test:** a committed fixture of a raw Open-Meteo response; run it through the *serving path*, and through the *training path* (adapter → dataset builder) for the same issue time; assert equal feature vectors.

### Pattern 2: Canonical frame + source adapters (handles NASA-train vs Open-Meteo-serve)

**What:** Define `CANON_COLS` once (e.g. `ghi, dni, dhi, temp, rh, pressure, ws10, ws_hub, wd10, wd_hub, precip, cloud`, UTC, hourly, interval convention fixed, e.g. "mean over the preceding hour labelled at the end"). Adapters convert each source into it. The NASA label shift is a config value found by the P2 cross-correlation test.

**The skew problem, precisely.** There are three separate skews, and they need different answers:

| Skew | Cause | Handling |
|------|-------|----------|
| **A. Lag/history inputs** | Training lags come from NASA; at serve time the only "recent history" available is Open-Meteo `past_days` (NWP analysis-like values), because NASA lags by days to months | (1) Compute/learn **OM→NASA-space correction** per variable (hour-of-day × month linear or quantile map) on the 2022+ overlap (§7.4). (2) Apply the *same* correction function to OM data in both the training dataset (for the OM-era portion) and serving. (3) Stage-2 fine-tune/eval on the OM era with lags computed from OM-derived history. Measure skew first; only build what the numbers justify. |
| **B. Known-future covariates** | Training 2001–2021 has no archived NWP forecasts; Historical Forecast API starts ~2022 (docs: "from 2022 onward"); ERA5 is a reanalysis (too clean, optimistic) | Stage 1 (long history): ERA5 as covariate proxy (+ optional noise/bias injection), plus lags from NASA. Stage 2 (2022 → N−1): true Open-Meteo historical-forecast covariates. Report stage-1-only vs stage-2 on val. With train ending 2023, only ~2 y are true-NWP: expect LightGBM to need the residual formulation (below). |
| **C. Lead-time mismatch** | Historical Forecast API **stitches the first hours of each run into one continuous series** (per official docs), i.e. short-lead values; at serve time horizons 24–72 h use *long-lead* forecasts that are less accurate. Training on short-lead covariates makes the model over-trust covariates at long horizons | Use **Previous Runs API** (`*_previous_day1..7`; archived mostly from Jan 2024) to build lead-matched covariates for 2024+ (val/test years). At minimum use it for the **baseline-3 evaluation** so the benchmark is honest at 24/48/72 h. Document as a known limitation if the training set stays on stitched data. |

**Residual formulation (recommended for LightGBM/direct models):** include `baseline3_pred[t+h]` (OM → physics) as a feature and train on the residual `y − baseline3` (or let trees see it as a feature and keep raw target; try both, 1 line of config). It starts the model at the benchmark, makes "beats baseline 3" achievable, and shrinks the skew surface to a correction.

**Trade-offs:** Added bias module (small). Without it, the honest framing is "measure the skew (§7.4) and report the live-vs-offline accuracy gap".

### Pattern 3: Common prediction contract (model-agnostic evaluation)

**What:** Every model, including baselines and seq2seq/TFT after reshaping, emits the same long table:
`issue_time, horizon, target_time, target, model, y_true, p10, p50, p90` → `data/processed/predictions/<split>_<model>.parquet`. `evaluate` is a pure groupby over this table (by horizon, season, target; solar daytime mask by zenith < 85°). The §9.4 selection is a function of the leaderboard.

**Why:** Deep and tree models have different native layouts; this contract is the only place they meet. Adding a model = write one adapter to the long format. Evaluate on a **shared issue-time grid** (e.g. 00/06/12/18 UTC, test year) independent of each model's training stride, so models are compared on identical samples.

### Pattern 4: Registry-dispatched Predictor with baseline-3 as a first-class model

**What:** `Predictor.predict(features) -> long DataFrame`. `Baseline3Predictor` (OM forecast → `swf.physics`) implements the same interface, so "deploy baseline 3 for this target" (§9.4) is a registry entry, not a code branch. Serving iterates the 5 targets, resolves each target's selected predictor from `registry.json`, runs it, clips to physical limits, stores.

**Uncertainty:** make **empirical residual quantiles by horizon bucket (from the validation set)** the universal band mechanism (works for baseline 3, LightGBM, LSTM, stored in the registry/`meta.json`). TFT supplies native P10/P50/P90. Optionally LightGBM `objective=quantile` ×3 if time allows. Calibration check: P10–P90 coverage ≈ 80% on test.

### Pattern 5: Idempotent stage CLI instead of an orchestrator

**What:** Each stage is `read parquet → pure function → write parquet`, skip if output newer than inputs/config hash. `Makefile` targets call `python -m swf.cli <stage>`. No Airflow/Prefect/MLflow/DVC for a 15-day solo project. Lineage = `data/processed/manifest.json` (input hashes, split dates, feature_spec_hash, git SHA) copied into each model's `meta.json`.

## Data Layouts for Modelling

### Direct multi-horizon (LightGBM) = long table

- Row = (issue time t, horizon h∈1..72). Columns: base features at t (lags, rolling, calendar, geometry), known-future covariates at t+h, `h`, `baseline3_pred[t+h]`. Label: `y_target[t+h]` (one model per target).
- **Size control:** 23 y × 8760 × 72 ≈ 14.5 M rows/target. Subsample **issue times at a stride of 3 h** (≈4.8 M rows, float32, ~1.5 GB with ~80 columns) or train on stride 6 first; use the pre-bucket fallback (h 1–6, 7–24, 25–72) if one-model-with-horizon-feature under-fits short horizons. Drop rows whose input window or label touches a >3 h gap.
- Solar: train on all hours but evaluate daytime; or train only where clear-sky GHI > 0 and predict 0 elsewhere (physical constraint anyway).
- LightGBM handles NaN natively; no scaling needed.

### Seq2seq (LSTM/GRU)

- One aligned hourly float32 array `A[time, features]` per split + a **window-start index array**; a `Dataset.__getitem__(i)` slices views, so there is no 168×N duplication.
  - `X_enc = A[s-168:s, past_feats]` (all 5 targets, past covariates, calendar, geometry)
  - `X_dec = A[s:s+72, future_feats]` (known-future OM covariates, calendar, zenith, clear-sky, h index)
  - `Y = A[s:s+72, target_cols]` → `[72, 5]`
- Index only windows with no gap/NaN in the 240 h span; stride 1–3 for training, the shared 6-hourly grid for evaluation. Scalers (per-column mean/std, fit on train only) saved in the model's `meta.json`. Loss: MSE/Huber on scaled targets; weight daytime for T1/T3; optionally add the physics-consistency clip at output.
- Decoder inputs are **known-future only** (never decoder-side target lags); that is the leakage line the test must also cover.

### TFT

- Same windows, framed for the library. Darts `TFTModel` natively supports a multivariate target series with `past_covariates` (observed only in the past), `future_covariates` (known into the horizon) and `QuantileRegression` likelihood (verified via Context7, MEDIUM); `input_chunk_length=168, output_chunk_length=72`. Pragmatic choice for the deadline: **Darts** (one `TimeSeries` per split; the Darts API owns window building, scaling and sample-based quantile prediction with `num_samples>1`). Pytorch-forecasting is more flexible but needs long-format `TimeSeriesDataSet` plumbing and has more setup risk. TFT is the first thing to cut if the schedule slips.
- Convert TFT quantile output to the Pattern 3 long format so evaluation is unchanged.

## Model Registry Format

JSON file plus folders; skip MLflow.

```jsonc
// models/deployed/registry.json
{
  "schema_version": 1,
  "created_utc": "2026-11-12T09:00:00Z",
  "git_sha": "abc123",
  "feature_spec_hash": "sha1:...",          // must equal code's FEATURE_SPEC hash at load
  "data_manifest": "sha1:...",
  "split": {"train": ["2001-01-01","2023-12-31"], "val": ["2024-01-01","2024-12-31"], "test": ["2025-01-01","2025-12-31"]},
  "targets": {
    "T3_ghi": {
      "selected": "lightgbm",
      "runtime": "lightgbm",                  // lightgbm | onnx | torch | baseline3
      "artifact": "lightgbm/T3_ghi/",         // contains model.txt + meta.json
      "reason": "lowest test RMSE and skill_vs_b3 > 0",
      "test": {"rmse": 61.2, "nrmse": 0.071, "skill_vs_b3": 0.12, "coverage_p10_p90": 0.79},
      "baseline3_rmse": 69.5,
      "bands": {"method": "empirical_residual", "by_horizon_bucket": {"1-6": [-20,22], "7-24": [-45,50], "25-72": [-80,85]}}
    },
    "T5_wind_kw": {"selected": "baseline3", "runtime": "baseline3", "reason": "no ML model beat baseline 3 (§9.4)", "...": "..."}
  },
  "candidates": { "...": "all leaderboard rows kept for the report" }
}
```
`meta.json` per artifact: ordered `feature_names`, `feature_spec_hash`, horizons, scaler params (deep), library versions, seed, training date range, config hash. Selection is computed by `evaluate/select.py` from validation-based candidate ranking and test confirmation per PRD §9.4 (**choose candidates on val, report/confirm on test once** to avoid test-set selection bias; if the guide wants literal "lowest test RMSE", state it in the report). `make promote` copies the winners from `models/runs/<id>/` to `models/deployed/`.

## Data Flow

### Offline flow (one-directional, files between stages)

```
fetch_nasa/fetch_openmeteo ─▶ data/raw/{nasa,openmeteo/<api>}/*.json   (immutable)
   ─▶ adapters+clean ─▶ interim/weather_nasa.parquet, weather_era5.parquet, weather_om_hist.parquet (canonical, UTC)
   ─▶ physics(NASA) ─▶ interim/energy_sim.parquet (T1,T5)  ◀─ loss%, power_curve ◀─ validate(Kaggle)   [gate]
   ─▶ source-consistency (NASA vs ERA5/OM) ─▶ docs/data_notes.md, align/bias params
   ─▶ features(SHARED) + splits ─▶ processed/{train,val,test}.parquet (+ window index)
   ─▶ models train ─▶ models/runs/<id>/…  and predictions/<split>_<model>.parquet
   ─▶ evaluate ─▶ reports/evaluation/leaderboard.{csv,json}+plots ─▶ select ─▶ registry.json ─▶ promote
```

### Serving flow (hourly)

```
APScheduler(cron minute=5)  [+ run once at startup if cache empty or older than 60 min]
  1. GET Open-Meteo forecast: timezone=GMT, wind_speed_unit=ms, past_days=7..8, forecast_days=4
     (forecast_days=3 starts at 00:00 UTC *today* and would give < 72 h ahead; slice [now+1h, now+72h])
  2. openmeteo_to_canonical ─▶ bias/space correction (same fn as training)
  3. issue_time = latest complete hour; features.make_direct_rows(...) / seq windows (SAME code)
  4. per target: registry.resolve(target).predict(X) ─▶ bands ─▶ physical clipping
  5. SQLite: BEGIN; upsert runs row + 5×72 forecast rows; COMMIT   (idempotent key: run_time, target_time, target)
  6. Failure at step 1: keep last good run, mark runs.status='failed'; API returns stale=true, age_minutes
```

### Request flow

```
Browser ─▶ GET /api/forecast?hours=72 ─▶ repo.latest_run() ─▶ 360 rows by index ─▶ pydantic ─▶ JSON
         (stale = now - run_time > 90 min or last refresh failed)   ← no model/fetch in request path
/api/metrics, /api/site: baked JSON/YAML read at startup (no compute)   /api/history: `history` table filled each refresh from OM past hours (+physics for T1/T5)
```

### Key Data Flows

1. **Target truth vs input stream:** targets are NASA-space (T2–T4 raw, T1/T5 simulated from NASA). Inputs at serve time are Open-Meteo only. The bias layer and (optional) stage-2 fine-tune bridge them.
2. **Physics is reused three times:** NASA→T1/T5 (labels), OM→T1/T5 (baseline 3 and a feature), registry fallback (served). One implementation, one config, one set of unit tests.
3. **Frontend contract:** FastAPI's OpenAPI → `openapi-typescript` types; `schemas.py` frozen early so the SPA can be built against a mock.

## Packaging for a Small Deployed Container

- **Split dependencies in `pyproject.toml`:** `[project] dependencies` = serving core (fastapi, uvicorn, apscheduler, httpx, pandas, numpy, pyyaml, pydantic, pvlib, lightgbm); `[project.optional-dependencies] train` = pyarrow, matplotlib, torch (CUDA), darts/pytorch-forecasting, scikit-learn, pytest-extras; `deep-serve` = onnxruntime or CPU torch. Image installs core only (~400–600 MB, no torch). Avoid pyarrow in serving (SQLite + in-memory frames only).
- **LightGBM** → `Booster.save_model('model.txt')`; loaded with `lgb.Booster(model_file=...)` (no sklearn needed). 3–10 MB per model.
- **Deep models only if they win a target.** Export to **ONNX** and serve with `onnxruntime` (~15 MB, low RAM) for the LSTM; TFT→ONNX is awkward (Darts/pytorch-forecasting), so if TFT wins, serve with the CPU-only torch wheel (`--index-url https://download.pytorch.org/whl/cpu`) and check RAM against the host tier (free tiers are often 512 MB: torch import is heavy). Honest expectation: LightGBM/baseline 3 win most targets, so build the torch-free image first and add the `deep-serve` build arg only if needed. Scalers and normalisation go into `meta.json`/ONNX, never recomputed at serve time.
- **Bake into image:** `config/`, `models/deployed/`, `reports/evaluation/leaderboard.json`, validation PNGs (or copy PNGs into `frontend/public/reports` at build), no `data/raw`, no Kaggle, no notebooks. `.dockerignore` enforces it.
- **Runtime:** `uvicorn --workers 1` (multiple workers = duplicate schedulers), SQLite in WAL mode on a writable path (ephemeral on most free hosts: fine, since the cache regenerates on startup). Mount a volume only if you want history to persist across deploys.
- **Free-tier sleep caveat:** in-process APScheduler does not run while the container sleeps. Mitigations: refresh-on-read when the latest run is older than 60 min (serve stale immediately with `stale:true`, refresh in a background task); an external pinger (UptimeRobot / GitHub Actions cron) hitting `/api/health`; run-at-startup refresh. Verify the actual host's idle behaviour.
- **Frontend:** static build on Vercel/Netlify; `VITE_API_URL`; backend CORS allows only that origin.

## Build Order and Parallelism (solo, 15 days, ~1 Nov to ~15 Nov)

### Dependency graph

```
core/config ──▶ fetch ──▶ adapters/clean ──▶ physics ──▶ [validate Kaggle]──┐(gate: loss %, power curve)
                              │                 │                           │
                              │                 └──▶ energy_sim ◀───────────┘
                              ▼                          ▼
                    source-consistency (NASA vs ERA5/OM, timestamp test)
                              ▼
        FEATURES (shared) + splits + predictions contract + evaluate harness
                 │                   │                         │
      baselines (b1,b2,b3)       LightGBM              LSTM ─▶ TFT          (GPU, long-running)
                 └───────────────────┴───────────┬────────────┘
                                         leaderboard ─▶ registry ─▶ promote
 Walking skeleton (parallel):  fetch OM live ─▶ adapters ─▶ physics ─▶ Baseline3 ─▶ SQLite ─▶ FastAPI ─▶ React
```

### Suggested order

| Days | Work | Notes |
|------|------|-------|
| 1 | P0 setup; `core`, config, Makefile/CLI skeleton; **start NASA + Open-Meteo (historical forecast, ERA5, Previous Runs) downloads in the background** | Network-bound, kick off first. Place Kaggle files now |
| 2 | adapters + cleaning + timestamp-alignment test + NASA vs ERA5 comparison; physics modules + unit tests | Freeze `CANON_COLS` today |
| 3 | **Kaggle validation (parallel-able with day 2 once physics exists)**; energy_sim; hold the gate | If thresholds miss, document and move on; do not block |
| 3–4 | **Freeze contracts:** `FEATURE_SPEC`, predictions long format, registry schema, API `schemas.py` | Costs hours now, saves days later |
| 4 | features + splits + leakage + parity tests; baselines 1–3; evaluate harness (first leaderboard) | Baseline 3 evaluated with lead-matched data where possible |
| 5–6 | LightGBM (direct, residual variant) + first registry; **walking skeleton API with Baseline3Predictor + scheduler + SQLite** | API on baseline 3 is deployable end to end |
| 5+ | **Frontend against mocked/OpenAPI JSON** (can start as soon as `schemas.py` freezes) | Parallel to modelling |
| 6–9 | LSTM seq2seq, then TFT, trained on GPU **in background** while doing frontend, API hardening, deployment | TFT first to cut |
| 9–10 | Evaluate all, §9.4 selection, `promote`, plug LightGBM/others into the API | Registry-dispatch means no API changes |
| 10–12 | Deploy backend container + frontend; stale fallback test; mobile check; performance page from leaderboard JSON | Deploy early, not on day 14 |
| 12–15 | Report figures/tables, README, tests green, slides, viva walkthrough, buffer | Per PROJECT.md: results/report outrank site polish |

**Cut order if behind:** TFT → LSTM tuning → bias-correction beyond linear → Plotly extras → About-page polish. **Never cut:** physics validation, baseline 3, leakage + parity tests, honest leaderboard.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0–1k users (this project) | Monolith: one FastAPI process, SQLite cache, static SPA. Reads are 360 rows from an indexed table (<10 ms) so the 500 ms budget is easy |
| 1k–100k users | Put a CDN in front of `/api/forecast` (Cache-Control ≈ 5 min); the data changes once an hour |
| 100k+ / multi-site | Postgres + a separate worker/cron for refresh; site_id in keys (config is already location-agnostic) |

### Scaling Priorities

1. **First bottleneck:** upstream Open-Meteo rate/terms, not users. One fetch per hour regardless of traffic; users never trigger a fetch.
2. **Second bottleneck:** container RAM if torch is shipped; fixed by ONNX or LightGBM-only.

## Anti-Patterns

### Anti-Pattern 1: Re-implementing features in the API ("serving version")

**What people do:** Copy notebook feature code into the service and tweak it.
**Why it's wrong:** Silent skew; the model degrades live with no error. **Do this instead:** one `swf.features`, spec hash in the artifact, parity test with a frozen raw-response fixture.

### Anti-Pattern 2: Computing the model in the request path or fetching on request

**What people do:** Fetch + infer on each `/api/forecast`. **Why it's wrong:** Latency, rate-limit exposure, downtime = outage. **Do this instead:** scheduler writes, API reads, stale flag.

### Anti-Pattern 3: Mixing timestamp conventions or time zones

**What people do:** Join NASA and Open-Meteo on raw labels; use IST in the pipeline. **Why it's wrong:** One-hour shifts alone can wreck solar skill and look like model weakness. **Do this instead:** one adapter layer, UTC canonical, offset in config, evaluate solar mid-interval zenith (hourly means labelled at the end: use t−30 min for geometry), IST only in the SPA.

### Anti-Pattern 4: Model-specific evaluation code

**What people do:** Compute metrics inside each training script. **Why it's wrong:** Different masks/normalisation between models make the leaderboard meaningless. **Do this instead:** common predictions long-format and one `evaluate` module; shared issue-time grid; solar daytime mask in one place.

### Anti-Pattern 5: Test-set peeking through selection and tuning

**What people do:** Tune and select on the test year. **Why it's wrong:** Optimistic, challengeable in the viva. **Do this instead:** tune/select on validation; test once at `evaluate --final`.

### Anti-Pattern 6: Heavy MLOps for a one-site demo

MLflow, Airflow, feature stores, Kubernetes: skip all. The JSON registry, Makefile and parquet stages are enough and are easier to explain at the viva.

### Anti-Pattern 7: Training torch inside the serving image / importing torch at API module load

Gate with lazy imports and extras; otherwise the container is >1.5 GB and may not fit the free tier.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| NASA POWER hourly | Offline only; 1 call/year, 14 params, `time-standard=UTC`, ≥1 s sleep, backoff on 429/5xx | Not available in real time (lags); confirm label convention; never used at serve time |
| Open-Meteo Forecast | Online hourly; `timezone=GMT`, `wind_speed_unit=ms`, `past_days`, `forecast_days=4` | Radiation = preceding-hour mean (docs). One call/hour is far below free limits; non-commercial terms; show attribution |
| Open-Meteo Historical Forecast | Offline, training covariates (2022+) | Stitched short-lead series (docs); not lead-time specific |
| Open-Meteo Previous Runs | Offline, lead-matched covariates (`*_previous_dayN`, mostly archived from 2024) | Use for honest baseline 3 at long horizons and val/test covariates |
| Open-Meteo ERA5 archive | Offline: NASA cross-check; covariate proxy for 2001–2021 | Wind heights differ (100 m, not 80/120 m in archive: verify) |
| Kaggle CSVs | Manual placement; offline validation only | Missing → stop and ask |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| offline → online | Files only: `models/deployed/**`, `config/**`, `reports/evaluation/*.json` | No shared DB; versioned by `registry.json` + `feature_spec_hash` |
| scheduler ↔ API | Same process; SQLite as the only shared state; refresh in a single transaction | WAL mode; one worker |
| API ↔ frontend | JSON over HTTPS, UTC ISO-8601, OpenAPI-generated TS types | CORS allow-list; stale + `last_updated` fields in every payload |
| features ↔ models | DataFrame with `FEATURE_SPEC` columns / window tensors with fixed channel order from `meta.json` | Hash checked at load |
| physics ↔ everything | Pure functions on canonical frames + config | Tested once, used for labels, baseline 3, fallback |

## Sources

- `docs/PRD.md` §5, §7, §9, §10, §12, §15, §16 and `.planning/PROJECT.md` (project constraints)
- Open-Meteo Historical Forecast API docs, https://open-meteo.com/en/docs/historical-forecast-api (fetched 2026-11-01): past forecasts from 2022; stitches first hours of each run; radiation is past-hour average; wind at 10/80/100/120/180/200 m (HIGH)
- Open-Meteo Previous Runs API docs, https://open-meteo.com/en/docs/previous-runs-api (fetched 2026-11-01): `_previous_dayN` lead-time-specific values; most models archived from Jan 2024 (HIGH)
- Darts TFTModel docs/examples via Context7 `/unit8co/darts`: past/future covariates, `QuantileRegression`, `num_samples>1` for probabilistic prediction (MEDIUM)
- `forecast_days` / `past_days` start-of-day semantics, LightGBM `Booster` save/load, ONNX/CPU-torch packaging, free-tier sleep behaviour: general practice, not re-verified this session (MEDIUM; confirm on host and Open-Meteo forecast docs during P8)

---
*Architecture research for: multivariate solar & wind energy forecasting (Davanagere)*
*Researched: 2026-11-01*
