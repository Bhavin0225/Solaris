# Phase 5: Walking Skeleton & LightGBM - Research

**Researched:** 2026-11-07
**Domain:** FastAPI + APScheduler 3 + sqlite3 serving of an existing feature/physics chain; LightGBM residual models on baseline 3
**Confidence:** HIGH (codebase read directly; library versions already pinned and installed in `.venv`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (Phase 4):** Hourly origins for training and evaluation.
- **D-02 (Phase 4):** Lead-matched GFS mapping, horizon h uses `previous_day{ceil(h/24)}`.
- **D-03a (Phase 4):** Official baseline 3 per target = lower validation (2024) RMSE of corrected vs raw GFS. Frozen in `config/baseline3_choice.json`.
- **D-05 (Phase 4):** No GTI covariate.
- **D-06 (Phase 4):** Purge-only splits, no 168 h embargo.
- **D-07:** LightGBM predicts the **residual** = observed target minus the official baseline-3 series for that target (per `config/baseline3_choice.json`). Serving adds the baseline-3 value back, then applies the physical clipping layer.
- **D-08:** Three bucket models per target, one per horizon bucket: 1-6 h, 7-24 h, 25-72 h (PRD 9.2 buckets). Each bucket model trains only on its own horizons. Horizon is not a row-expanding feature.
- **D-09:** P10-P90 bands come from **empirical validation residual quantiles by horizon bucket**. The same method applies to baseline 3 and LightGBM. No LightGBM quantile objective. Quantiles are sorted (no crossing) and clipped (MODEL-04).
- **D-10:** On startup, serve the cached forecast immediately if one exists, and fetch Open-Meteo right away in the background (no wait for the first hourly tick).
- **D-11:** The served forecast is marked `stale: true` with its age when the last successful refresh is more than **2 hours** old (two missed hourly refreshes). The forecast is still served from cache in every case.

### Claude's Discretion
- LightGBM hyperparameters, feature subset (taken from the shared `FEATURE_SPEC`), and the search method (small grid or early stopping on validation, per the PRD anti-feature list). Fixed seeds are required.
- Minimal page scope for success criterion 1. Keep it a placeholder that shows the five targets with P50 and bands. The full dashboard is Phase 7.
- Module layout inside `swf.api` and `swf.predict`, following the research architecture (Predictor protocol, registry-dispatched lazy imports).

### Deferred Ideas (OUT OF SCOPE)
- Lazy refresh on request when cache is older than 60 min (v2 cloud, API-02)
- Committed seed snapshot for ephemeral-disk restarts (v2, API-03)
- Torch-free serving image and ONNX runtime (v2, API-05)
- Public deployment on Render and Vercel/Netlify, `VITE_API_URL`, keep-alive pinger, "waking up" UI state (v2, DEPLOY-01, UI-03 cloud parts)
- Deep models LSTM/GRU and TFT (Phase 6)
- Full dashboard and performance pages (Phase 7)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-01 | FastAPI, 1 worker, 6 endpoints, Pydantic, ISO UTC | `swf.api.main/schemas`; `python -m swf serve` runs `uvicorn.run(app, workers=1)`; OpenAPI at `/openapi.json` |
| API-02 | Hourly APScheduler 3 job (`max_instances=1, coalesce=True`) + startup refresh | BackgroundScheduler in `lifespan`; startup refresh via `next_run_time=now` or a thread (D-10) |
| API-03 | SQLite WAL cache (run_time, target_time, target, model, p10, p50, p90) | `swf.api.db`, stdlib sqlite3, `data/app.db` |
| API-04 | Stale fallback with `stale:true` + age, tested | Refresh job swallows `httpx.HTTPError`; age from `meta.last_success`; test with `httpx.MockTransport` |
| API-05 | Registry dispatch, lazy imports | `swf.predict.registry` + `Predictor` protocol; `lightgbm` imported inside the predictor |
| API-06 | `/api/forecast` < 500 ms | One indexed SELECT of 360 rows; no model run on request |
| API-07 | Next-24 h summary with IST day bounds | `zoneinfo.ZoneInfo(settings.site.display_timezone)` (tzdata present) |
| DEPLOY-02 | Walking skeleton on localhost, one command | `python -m swf serve` + minimal Vite page (see Frontend) |
| MODEL-01 | LightGBM per target, fixed seeds, saved artifacts | `swf.models.lgbm` train, 15 boosters under `models/lightgbm/` |
| MODEL-04 | Sorted, clipped bands from validation residual quantiles | `swf.predict.bands` + `swf.physics.constraints.enforce` |
</phase_requirements>

## Summary

Almost everything the serving path needs already exists. `swf.features.build.serve_features(raw_bytes, s, cfg, coefs, curve, origin)` returns the 72-row covariate-feature frame for one live origin and is already parity-tested against the training path (`tests/test_features_parity.py`). `swf.fetch.openmeteo.fetch_live` writes the hourly-keyed raw JSON cache (retry/backoff via tenacity inside `fetch_to_cache`). `swf.features.history.history_frame(canon, s, curve, coefs_or_None)` is the baseline-3 chain (correction -> `simulate` -> `enforce`) and works unchanged on a live canon frame. **The one gap:** no function turns a live payload into baseline-3 values per target at `t+1..t+72`; it is a 6-line composition (`openmeteo_canon` -> `clean(source="live")` -> `history_frame` with `coefs` if `choice[target]=="corrected"` else `None`, then `.reindex(target_times)`). All of fastapi 0.162.0, uvicorn, apscheduler 3.11.3 and lightgbm 4.7.0 are already in `pyproject.toml` and installed in `.venv`; no new Python dependency is needed. `frontend/` does not exist; it must be scaffolded (Node 24.16 / npm 11 available).

LightGBM training reuses the Phase 4 training recipe exactly: history features from ERA5 (`history_frame(history_input(load_source("era5")), coefs)`), target-axis tables from the same index, covariates from the stitched GFS (`weather_gfs_hf.parquet` via `covariate_table`) for train_covariate (2021-04..2023), lead-matched dict `{1,2,3}` from `weather_gfs_pr_d{k}` for validation. The residual target is `truth(target_time) - b3_stitched(target_time)` where `b3_stitched = b3_table(hf, s, curve, coefs if choice=="corrected" else None)[target]`. The leaderboard picks up a model automatically when its long-format parquet is written to `data/processed/predictions/val/<model>.parquet`: `evaluate.report.load_split` globs the directory, so no leaderboard code change is required.

**Primary recommendation:** Build bottom-up in three slices: (1) `swf.predict` + `swf.models.lgbm` train/score (writes val long parquet, artifacts, `models/registry.json`), (2) `swf.api` (db, refresh, schemas, endpoints, tests with mocked Open-Meteo), (3) Vite scaffold + `serve` subcommand + README. Serve baseline 3 first (registry `runtime: baseline3`), then flip targets to `lightgbm` only where val RMSE beats baseline 3.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live fetch + feature build + inference | API / Backend (scheduler job) | - | Runs hourly, never on the request path (API-06) |
| Forecast cache, stale flag, age | Database / Storage (SQLite) | API | Request handlers only SELECT |
| IST day bounds for summary | API / Backend | - | Server-side per API-07; frontend only formats |
| Band computation | Offline training | API (reads from registry) | Offsets frozen at training; serving adds them |
| Clipping / physical constraints | API (`swf.predict`) | - | `enforce` applied to p10/p50/p90 before storage |
| Minimal page | Browser (Vite React) | API | Fetch `/api/forecast`, render; IST conversion in browser only |

## Standard Stack

All already pinned (`pyproject.toml`, `uv.lock`); verified installed in `.venv` (fastapi 0.162.0, apscheduler 3.11.3, lightgbm 4.7.0). [VERIFIED: .venv import]

### Core
| Library | Version | Purpose |
|---------|---------|---------|
| fastapi / uvicorn | 0.162.0 / 0.54.0 | API, 1 worker |
| apscheduler | 3.11.3 (`<4`) | `BackgroundScheduler`, hourly job |
| sqlite3 (stdlib) | - | WAL cache, no ORM |
| lightgbm | 4.7.0 | residual boosters; early stopping via `lgb.early_stopping` callback |
| httpx + tenacity | 0.28.1 / 9.2.1 | already used by `fetch_to_cache` |
| pytest + `fastapi.testclient.TestClient` | 9.2 | API tests (TestClient needs httpx: present) |

### Frontend (new, scaffolded once)
| Package | Version | Note |
|---------|---------|------|
| create-vite (react-ts template) | 9.3.4 [VERIFIED: npm view] | scaffold; yields vite 8.3.6, react 19.3.1 [VERIFIED: npm view] |

No Recharts/Tailwind/router needed in Phase 5: the placeholder is a table (target, unit, first-hours P50, P10-P90 range, model, stale banner). Phase 7 adds the rest. These are the template's own dependencies from the official `npm create vite`, so no extra slopcheck-gated installs; slopcheck was not run (no new third-party package beyond the official scaffold) [ASSUMED: template contents unchanged from STACK.md note].

**Installation:** `npm create vite@latest frontend -- --template react-ts` then `npm --prefix frontend install`. Python: nothing (`uv sync`).

## Package Legitimacy Audit

| Package | Registry | Source | slopcheck | Disposition |
|---------|----------|--------|-----------|-------------|
| create-vite (+ vite, react via template) | npm | github.com/vitejs/vite | not run | Approved (official scaffold, versions confirmed via `npm view`); planner may add a one-line human glance at generated `package.json` |

No Python packages added. Removed: none. Flagged: none.

## Architecture Patterns

### System Architecture Diagram

```
 startup / hourly tick (APScheduler BackgroundScheduler, max_instances=1, coalesce=True)
        |
        v
 fetch_live(client, s, root=RAW_DIR) --httpx error--> log, keep old rows (stale grows)
        | raw JSON bytes (hour-keyed disk cache)
        v
 openmeteo_canon -> clean(source="live") -> canon (past 7 d + 4 d forecast)
        |                                   |
        |                                   +--> history_frame(canon, coefs?) per target choice -> b3[t+1..t+72], and observed past 7 d (history table)
        v
 serve_features(raw, s, cfg, coefs, curve, origin)  (72 x 101 covariate features)
        |
        v
 registry.json -> per target Predictor (baseline3 | lightgbm[3 buckets])  -> p50 = b3 + residual
        |
        v
 bands: + validation residual quantile offsets per bucket -> sort -> enforce (clip) -> sqlite forecast rows + meta.last_success
        |
 HTTP request ----------------> SELECT latest run_time (360 rows) -> Pydantic -> JSON  (stale = now - last_success > 2 h)
        ^
 Vite page (/api proxy) / StaticFiles(frontend/dist)
```

### Recommended Project Structure
```
src/swf/
  models/lgbm.py        # training + val scoring (train-only code; may import lightgbm, evaluate.*)
  predict/              # serving-safe: registry.py (load + dispatch), baseline.py, lgbm.py (lazy import lightgbm), bands.py
  api/                  # main.py (app, lifespan), db.py, refresh.py, schemas.py, summary.py, run.py (uvicorn)
models/registry.json    # committed
models/lightgbm/<target>_<bucket>.txt (+ meta json)   # committed, MBs
frontend/               # vite react-ts
tests/test_api_*.py, tests/test_predict_*.py, tests/test_lgbm_*.py
```
Rule from CONTEXT: `swf.api`/`swf.predict` must not import `swf.evaluate`, `swf.validate`, torch, darts, matplotlib at module load. `swf.evaluate.baselines` and `metrics` are numpy/pandas-only and technically safe but `evaluate.report` imports matplotlib lazily; keep API off `evaluate` entirely and enforce with a test (run `python -c "import swf.api.main, sys; assert 'matplotlib' not in sys.modules and 'torch' not in sys.modules"` in a subprocess).

### Pattern 1: Baseline 3 at serve time (the gap)
```python
# swf.predict.baseline
def b3_live(raw: bytes, s, cfg, coefs, curve, choice, origin) -> pd.DataFrame:
    canon = clean(openmeteo_canon(raw, s), s, source="live")[0]
    cor, rawt = history_frame(canon, s, curve, coefs), history_frame(canon, s, curve, None)
    T = pd.date_range(origin + pd.Timedelta(hours=1), periods=cfg.horizon_max, freq="h")  # tz-aware UTC
    return pd.DataFrame({t: (cor if choice["choice"][t] == "corrected" else rawt)[t].reindex(T) for t in TARGETS})
```
Compute both tables once per refresh (a few hundred rows, fast). `choice` comes from `load_choice()` (asserts feature_spec hash; `swf.evaluate.baselines` import is fine at train time, but for serving read the JSON through `registry.json` which copies `choice`, so the API never imports `evaluate`).

### Pattern 2: LightGBM training rows (D-07/D-08)
```python
# swf.models.lgbm (sketch; reuse Phase 4 recipe from tests/test_features_real.py)
raw = load_source("era5", s); hist = history_frame(history_input(raw, s, source="era5"), s, curve, coefs)
otab, ttab = origin_table(hist, cfg, s), target_table(hist.index, cfg, s)
cov_tc = covariate_table(pd.read_parquet(INTERIM/"weather_gfs_hf.parquet"), s, coefs, cfg)
cov_val = {k: covariate_table(pd.read_parquet(INTERIM/f"weather_gfs_pr_d{k}.parquet"), s, coefs, cfg) for k in (1,2,3)}
X_tr = assemble(otab, ttab, origins_for("train_covariate", cfg)[::stride], range(lo, hi+1), cov=cov_tc, cfg=cfg)
# baseline-3 for the same rows, stitched GFS, official variant per target:
b3_tr = {t: b3_table(hf, s, curve, coefs if choice["choice"][t]=="corrected" else None)[t] for t in TARGETS}
tt = X_tr.index.get_level_values("issue_time") + pd.to_timedelta(X_tr.index.get_level_values("horizon"), unit="h")
y_res = truth[t].reindex(tt).to_numpy() - b3_tr[t].reindex(tt).to_numpy()   # drop NaN rows
```
Bucket models: call `assemble(..., horizons=range(1,7))`, `range(7,25)`, `range(25,73)` per bucket (assemble takes `horizons`, so each bucket gets only its rows; `horizon` stays as a feature column inside the bucket). Build X once per bucket, reuse for all 5 targets (features are target-independent; only `y_res` differs). Validation X uses lead-matched `cov_val` dict (D-02), exactly like the baseline-3 val frames. Use fixed `random_state/seed`, `deterministic=True`, `force_row_wise=True`, `num_threads` fixed, for reproducibility. Hyperparameters: small fixed set (e.g. `num_leaves 31`, `learning_rate 0.05`, `min_data_in_leaf 200`, `feature_fraction 0.8`, `bagging_fraction 0.8, bagging_freq 1`), `n_estimators` up to ~1000 with `early_stopping(50)` on validation residual RMSE; optional tiny grid on `num_leaves` in {15,63}. Persist `best_iteration` and `feature_columns` + `artifact_meta("covariate")` (`feature_spec_hash`) in the sidecar JSON; serving calls `assert_spec(meta)` at load.

Size/perf: train_covariate origins ~24k; full 72 h = ~1.7 M rows x 101 float32 = ~0.7 GB. Use an origin stride (SUMMARY.md notes stride 3 h; ~8k origins, ~0.6 M rows) configurable via CLI/`config/lgbm.yaml`, default 3. Adjacent hourly origins are near-duplicates, so little is lost. Validation scoring uses ALL hourly val origins (must equal the baseline grid or `validate_long(origins=...)`/shared-sample math diverges): `origins_for("val", cfg)`, ~8.6k x 72 = 0.62 M rows, fine; predict in chunks via `iter_features`.

### Pattern 3: Leaderboard row
Build the long frame with `make_long(issue, hor, target, "lightgbm", y_true, p50, p10, p90)` per target using `grid(origins, horizons)` for ordering (same as `baselines._long`; `y_true = truth[t].reindex(tt)`), concat the five targets, `validate_long(df, truth=truth, origins=origins)`, `write_long(df, "val", "lightgbm")`. Then `python -m swf evaluate --split val` rewrites `reports/evaluation/leaderboard.csv` with the lightgbm rows and skill_vs_baseline3 (official baseline3 alias is built in `with_official`). **Note:** `_merge` keeps existing test rows only when the spec hash matches, so test rows stay. Do NOT write `test/lightgbm.parquet` in this phase: hyperparameters/early stopping use val; test scoring belongs to the final selection step (PRD 9.4 / Phase 8). Consequence: `evaluate --split all` would require every model to exist in test only for those present; it globs, so a missing lightgbm test file is simply absent from the test table. That is acceptable but record it in the plan summary. LightGBM p50 must be clipped via `enforce` before writing (and for t1_kw/ghi night = 0 comes for free); the clipped value, not the raw one, is what is scored.

For leaderboard fairness, also write the NaN rule: rows where baseline 3 (lead-matched) is NaN yield `p50 = NaN` (b3 + residual), which `scored_mask` drops. Do not fill.

### Pattern 4: Bands (D-09, MODEL-04)
On val, per target and bucket compute `q10, q90` of `(y_true - p50_clipped)` over daytime-valid rows (for t1_kw/ghi use daytime rows only, `daytime_mask`, else night zeros collapse the quantiles). Save as `bands: {target: {bucket: [q10, q90]}}` in the registry for BOTH baseline3 and lightgbm (baseline3: residual `y - b3`). Serving: `lo = p50 + q10`, `hi = p50 + q90`, then `np.sort` of `[lo, p50, hi]` along axis (guarantees no crossing), then `enforce` each column (index = target time so night zeroing applies). The same function is used offline for the long-format p10/p90 so the leaderboard and live bands match. Report empirical coverage on val as a sanity print (should be about 80%, by construction); this is in-sample for val, so state that the honest check is on test in the final phase.

### Pattern 5: Registry and lazy dispatch
`models/registry.json` (shape per SUMMARY.md): `schema_version`, `feature_spec_hash`, `baseline3_choice` (copied dict), and per target `{selected: "baseline3"|"lightgbm", runtime, artifacts: {"1-6": path, "7-24": path, "25-72": path}, bands: {...}, val_rmse: {model: x, baseline3: y}, reason}`. Selection in this phase uses VAL (documented as provisional; the PRD 9.4 rule uses test and is finalized in Phase 8). `swf.predict.registry.load()` does `assert feature_spec_hash == spec_hash()`; `get_predictor(target)` does `importlib.import_module("swf.predict." + runtime)` so `lightgbm` is imported only when a target selects it. A `Predictor` protocol: `predict(features: DataFrame, b3: Series, target) -> (p10, p50, p90)`. Initial committed registry should select `baseline3` for all targets, then training updates it.

### Pattern 6: API app
```python
@asynccontextmanager
async def lifespan(app):
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(refresh, "interval", hours=1, id="refresh", max_instances=1, coalesce=True,
                  next_run_time=datetime.now(UTC))        # D-10: immediate first run, in the scheduler thread
    sched.start(); yield; sched.shutdown(wait=False)
```
`next_run_time=now` runs the first refresh in the scheduler's thread pool, so uvicorn starts serving cached rows immediately (D-10) without a separate thread. Endpoints are sync `def` and open a short-lived `sqlite3.connect` each call; WAL set once at init (`PRAGMA journal_mode=WAL`). `refresh()` wraps everything in try/except (`httpx.HTTPError`, `ValueError`, `KeyError` as `fetch.openmeteo.run` does), logs, and leaves `meta.last_success` untouched. Write all 360 rows plus `meta` in ONE transaction (`INSERT OR REPLACE`), so readers never see a half run. Keep the last ~7 days of runs? Not needed: serve only the latest `run_time`; delete older runs in the same transaction (YAGNI). Make DB path injectable (`SWF_DB` env or app factory `create_app(db_path, refresh_fn)`) for tests.

- `stale = (now - last_success) > 2 h`; `age_minutes` always returned; `/api/health` returns `{status, last_success, stale, age_minutes}`. No cached forecast yet: `/api/forecast` returns 503 with a clear message (only on first-ever run with Open-Meteo down).
- `/api/forecast?hours=72`: validate `1 <= hours <= 72` via `Query(ge=1, le=72)`; response `{run_time, stale, age_minutes, targets: {t: {unit, model, points: [{time, p10, p50, p90}]}}}`, times as `datetime` serialized `...Z` (use `AwareDatetime` / ensure UTC; Pydantic v2 emits `Z` for UTC tz-aware).
- `/api/history?days=7`: from a `history(time, target, value)` table written each refresh from the history chain frame (observed/analysis-based, 7 days).
- `/api/metrics`: read committed `reports/evaluation/leaderboard.csv` with stdlib `csv` (no `evaluate` import); return rows as typed models.
- `/api/site`: `load_settings()` dump (site + plant, no secrets).
- Summary (API-07): see Open Questions Q1. Use `zoneinfo.ZoneInfo(s.site.display_timezone)`; energy kWh = sum of hourly kW x 1 h; peak hour = argmax of combined/solar p50 (return ISO UTC); mean RH; max wind (ws10).

### Pattern 7: Frontend + one command
No `frontend/` exists. Smallest satisfying criterion 1: scaffold react-ts, replace `App.tsx` with a `useEffect` fetch of `/api/forecast` rendering a five-row table plus a stale banner and the attribution line; `vite.config.ts` gets `server.proxy: {"/api": "http://127.0.0.1:8000"}`. `python -m swf serve` (new `cli.py` subcommand via `_run("swf.api.run", args)`) runs `uvicorn.run("swf.api.main:app", host="127.0.0.1", port=8000, workers=1)` and, if `frontend/dist` exists, the app mounts it with `StaticFiles(directory=..., html=True)` AFTER the `/api` routes, so one command serves page + API at http://127.0.0.1:8000 after a one-time `npm --prefix frontend ci && npm --prefix frontend run build`. Document the dev alternative (`npm --prefix frontend run dev`, proxy). README gets a "Run locally" section (DEPLOY-02). Generate TypeScript types from `/openapi.json` is optional; commit `docs/openapi.json` exported by a tiny test/script so Phase 7 can build against it ("Publish OpenAPI").

### Anti-Patterns to Avoid
- Running models in the request handler (breaks API-06 and the cache contract).
- Re-serializing the raw API response or bypassing `fetch_to_cache` (violates the cache-raw rule); always go through `fetch_live`.
- Wall-clock `now` inside feature/physics code; pass `origin` explicitly and compute it once per refresh.
- Refitting bias coefficients or recomputing the baseline-3 choice at serve time (frozen in config files).
- Filling NaN b3 values; NaN rows are legitimately excluded from scoring.
- Writing test-split LightGBM predictions or tuning on test.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Live features | A second feature builder | `serve_features` | Parity-tested vs training (FEAT-06) |
| Baseline-3 chain | New physics call | `history_frame` | Same chain as training and baselines |
| Clipping | Ad hoc `np.clip` | `physics.constraints.enforce` | Handles night zeros, capacity, RH 0-100 |
| Retry/backoff | Own loop | `fetch_to_cache` (tenacity) | Already handles 429/5xx/Retry-After |
| Long format + leaderboard | Own metrics | `make_long`/`write_long`/`evaluate` | Leaderboard auto-includes new parquets |
| Scheduling | threading.Timer loop | APScheduler 3 BackgroundScheduler | `max_instances`/`coalesce` guarantees |
| IST conversion | Fixed +5:30 offset math | `zoneinfo` | Config-driven timezone |
| Band quantiles | Quantile objective | `np.quantile` on val residuals | D-09 |

## Common Pitfalls

### Pitfall 1: Baseline-3 training values from the wrong GFS table
**What goes wrong:** residual targets built from lead-matched `pr_d{k}` (only from 2024) leave train years NaN, or mismatch serving. **How to avoid:** training residuals use stitched `weather_gfs_hf` (corrected or raw per choice); validation residuals use the lead-matched tables (identical to the official baseline-3 val frames). Skew between stitched train and lead-matched val/serve is the documented W1 skew; report it, do not fix it.
**Warning sign:** val RMSE of "b3 + residual" far worse than b3 alone at 25-72 h.

### Pitfall 2: Bucket horizon grids vs `assemble`
Building bucket features by slicing the full 72 h frame wastes memory; pass `horizons=` per bucket. Do not drop the `horizon` column (spec columns must match; `assert_spec` checks `feature_columns`).

### Pitfall 3: Origin definition at serve time
`serve_features` requires history `>= 168 h` before and `72 h` of forecast after the origin. With `past_days=7` (168 h) plus the current day, history is just enough: `need_h = max(max(lags)=168, 23) = 168`; the payload starts at today-7d 00:00 UTC, so origin must be >= start + 168 h = today 00:00 UTC, which holds (origin = floor(now) - 1 h could equal 23:00 of previous day only at the 00:00 hour -> `ValueError`). **Mitigation:** compute `origin = max(floor_hour(now) - 1h, canon.index[0] + 168h)` or bump `past_days` to 8 (a one-key edit in `config/site.yaml`; note that changes the live fixture params only, not the spec hash). Plan a test at `now = 00:30 UTC`. Also origin+72 <= last label: forecast_days=4 gives enough. [ASSUMED: verify boundary on the committed fixture]

### Pitfall 4: Scoring only where all models are finite
A LightGBM frame that covers more rows than baseline 3 is fine (shared sample); but `leaderboard_rows` raises if `shared_frac < 0.5`. Val pr covariates start ~2024-01-19..02-18 so lightgbm NaN features early in val: LightGBM predicts anyway; b3 NaN drops them. OK.

### Pitfall 5: Stale test hangs on retry sleeps
`fetch_to_cache` retries 6 times with exponential backoff (up to 60 s). In tests inject `sleep=lambda s: None` (parameter exists on `fetch_live`) and a `MockTransport` returning `ConnectError`/503; the refresh function must accept `client` and `sleep` as parameters. At runtime a long outage means a refresh job blocks a few minutes; `max_instances=1` + `coalesce` makes this safe.

### Pitfall 6: Hour-keyed live cache and "now" skew
`fetch_live` keys by `{now:%Y%m%dT%H}`; a restart in the same hour reads the cache with no network (fine). Pass `now` explicitly in tests. Disk grows by one file per hour; leave it (it IS the raw cache), optionally note a cleanup as deferred.

### Pitfall 7: Windows + SQLite + multiple writers
Use `timeout=10` on `sqlite3.connect`, one connection per call, `PRAGMA journal_mode=WAL` once, `PRAGMA synchronous=NORMAL`. Do not share connections across scheduler and request threads. Use `tmp_path` DBs in tests.

### Pitfall 8: Pydantic datetime serialization
Naive `datetime` serializes without `Z`. Store epoch/ISO strings in UTC and build `AwareDatetime`; assert in a test that every timestamp string ends with `Z`/`+00:00`.

### Pitfall 9: Static mount swallowing /api
`app.mount("/", StaticFiles(...))` must be registered after the routers, otherwise `/api/*` 404s.

### Pitfall 10: Deterministic committed artifacts
CONTEXT convention: no timestamps in committed outputs. Registry and sidecars must be deterministic (sorted keys, `\n` newline, rounded floats), and LightGBM text models should be saved with `booster.save_model(path)` (stable across a fixed-seed re-run on the same machine; do not assert byte equality across machines, test prediction equality instead).

## Code Examples

### Stale computation
```python
age = now - datetime.fromisoformat(last_success)          # UTC aware
stale = age > timedelta(hours=2)                           # D-11
```

### Test: unreachable Open-Meteo serves cache with stale
```python
def test_stale(tmp_path, seeded_db_old):                   # last_success 3 h ago
    def boom(request): raise httpx.ConnectError("down")
    client = httpx.Client(transport=httpx.MockTransport(boom))
    refresh(db=seeded_db_old, client=client, sleep=lambda s: None)   # swallows, keeps rows
    r = TestClient(create_app(seeded_db_old, start_scheduler=False)).get("/api/forecast")
    assert r.status_code == 200 and r.json()["stale"] is True and r.json()["age_minutes"] >= 180
```
Use `TestClient` without `with` (or `create_app(start_scheduler=False)`) so the lifespan scheduler does not start in unit tests.

### Perf test
`time.perf_counter()` around `TestClient.get("/api/forecast")` on a seeded 360-row DB, assert `< 0.5` (use best of 5; test client overhead is small).

## State of the Art

| Old | Current | Impact |
|-----|---------|--------|
| `@app.on_event("startup")` | `lifespan` context manager | Use lifespan |
| APScheduler 4 alpha | 3.11.3 BackgroundScheduler | Pinned `<4` |
| `pvwatts_ac` | `pvlib.inverter.pvwatts` | Already handled in `physics.solar` |

## Runtime State Inventory
Not a rename/refactor phase: omitted.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Next-24 h summary uses IST day bounds" means the next full IST calendar day (tomorrow 00:00-24:00 IST), not a rolling 24 h | Pattern 6 / Q1 | Summary window differs from user's expectation; cheap to flip |
| A2 | Create-vite template contents are unchanged from STACK.md notes (oxlint, TS ~7) and need no further package vetting | Frontend | Minor |
| A3 | Origin boundary at 00:xx UTC fails with `past_days=7` as analysed | Pitfall 3 | Would be a startup/refresh failure for one hour per day if not handled; a test catches it |
| A4 | Val-set early stopping + val residual quantiles is acceptable (bands slightly optimistic in-sample) | Pattern 4 | Honest-reporting nuance; report test coverage in Phase 8 |
| A5 | Provisional selection per target on val RMSE in this phase; PRD 9.4 test-based final selection is later | Pattern 5 | If the user wants test-based selection now, test LightGBM preds must be written |
| A6 | Origin stride 3 for training rows has negligible accuracy cost | Pattern 2 | Slightly weaker models; configurable |

## Open Questions (RESOLVED)

1. **Summary window (API-07).** Rolling next 24 h vs "tomorrow IST". Recommendation: next IST calendar day (matches PRD "tomorrow's solar kWh" and the "IST day bounds" wording); also return the window start/end as ISO UTC and IST so the choice is visible. Planner may confirm with the user, otherwise go with this. RESOLVED: next full IST calendar day; bounds computed server-side as UTC instants, all returned timestamps UTC with Z (05-CONTEXT.md D-12).
2. **One command.** `python -m swf serve` serving built `frontend/dist` (single process) vs documenting two terminals (uvicorn + `npm run dev`). Recommendation: implement the former (3 lines) and document the latter as dev mode. Criterion 1 says "(Vite)": both are Vite-built. RESOLVED: `python -m swf serve` serves frontend/dist on 127.0.0.1 with 1 worker; `npm run dev` is the documented alternative (05-CONTEXT.md "Other locked choices").
3. **Origin when the clock is near 00:00 UTC.** See Pitfall 3; recommend the `max(...)` clamp, no config change. RESOLVED: live fetch past_days raised 7 to 8, no origin clamp, with a 00:xx UTC test (05-CONTEXT.md "Other locked choices").
4. **Test split LightGBM rows.** Deferred to Phase 8; confirm acceptable that `/api/metrics` shows val rows only (plus existing test baseline rows) for now. RESOLVED: no LightGBM test-split file in Phase 5 (05-CONTEXT.md "Other locked choices"); test rows arrive with Phase 6 selection.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + `.venv` | all | yes | 3.12.10 | - |
| fastapi/uvicorn/apscheduler/lightgbm | API, MODEL-01 | yes | 0.162.0 / - / 3.11.3 / 4.7.0 | - |
| tzdata / zoneinfo `Asia/Kolkata` | API-07 | yes | - | - |
| Node / npm | frontend | yes | 24.16.0 / 11.12.0 | - |
| Training data (`data/interim/*.parquet`, ERA5 raw) | MODEL-01 | yes (interim parquets present; ERA5 raw required by `load_source("era5")` should be in `data/raw/openmeteo/archive`) | - | `python -m swf data` / `build-weather` |
| Live Open-Meteo network | live refresh | runtime only | - | cached forecast (stale) |

Cached live payload exists at `data/raw/openmeteo/forecast/gfs_seamless/20261102T16.json`. `data/` is git-ignored, so `data/app.db` is never committed; `models/` and `models/registry.json` ARE committed (`.gitignore` does not exclude `models/`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2 (`addopts = -q -m 'not network and not realdata'`) |
| Config | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run | `.venv/Scripts/python -m pytest tests/test_api_*.py tests/test_predict_*.py tests/test_lgbm_*.py -x` |
| Full suite | `.venv/Scripts/python -m pytest` (and `-m realdata` for the LightGBM real-data run) |

### Phase Requirements to Test Map
| Req | Behavior | Type | Command | Exists |
|-----|----------|------|---------|--------|
| API-01 | six endpoints return schema-valid JSON, `Z` timestamps, 1 worker in `serve` | unit (TestClient, seeded DB) | `pytest tests/test_api_endpoints.py` | Wave 0 |
| API-02 | job registered with `max_instances=1, coalesce=True`; startup triggers refresh | unit (inspect `scheduler.get_job`, mock refresh) | `pytest tests/test_api_scheduler.py` | Wave 0 |
| API-03 | rows (run_time,target_time,target,model,p10,p50,p90) round-trip; WAL on; atomic replace | unit | `pytest tests/test_api_db.py` | Wave 0 |
| API-04 | Open-Meteo down -> 200, `stale: true`, `age_minutes` | unit (MockTransport ConnectError/503, no sleep) | `pytest tests/test_api_stale.py` | Wave 0 |
| API-05 | registry dispatch per target; `lightgbm` not in `sys.modules` for an all-baseline3 registry; API import hygiene (no torch/matplotlib/evaluate) | unit + subprocess | `pytest tests/test_predict_registry.py` | Wave 0 |
| API-06 | `/api/forecast` < 500 ms from cache | unit (timing) | `pytest tests/test_api_perf.py` | Wave 0 |
| API-07 | summary uses IST day bounds (fixed `now`, window start 18:30 UTC); kWh/peak/mean RH/max wind on a synthetic series | unit | `pytest tests/test_api_summary.py` | Wave 0 |
| DEPLOY-02 | refresh end-to-end on the committed live fixture -> DB -> `/api/forecast` has 5 targets x 72; `serve --help` registered | integration (fixture, mocked transport returning fixture bytes) | `pytest tests/test_api_refresh.py tests/test_cli.py` | Wave 0 |
| MODEL-01 | train on synthetic builder: 15 boosters saved, seeds fixed (two runs give identical predictions), meta spec hash enforced | unit (`tests/synth.py`) | `pytest tests/test_lgbm_train.py` | Wave 0 |
| MODEL-01 | real run writes `val/lightgbm.parquet`, passes `validate_long`, appears in `leaderboard.csv` | realdata | `python -m swf train-lgbm` then `python -m swf evaluate --split val`; `pytest -m realdata tests/test_lgbm_real.py` | Wave 0 |
| MODEL-04 | bands sorted p10<=p50<=p90, clipped to bounds (solar night 0, RH <=100), coverage ~80% on val | unit | `pytest tests/test_predict_bands.py` | Wave 0 |

Additional: baseline-3 serve parity: `b3_live` equals `baseline3` long-format values for the same canon frame (unit, synthetic); the residual identity `y_res + b3 == y_true` on train rows.

### Sampling Rate
- Per task commit: the quick run command for the touched module.
- Per wave merge: full suite.
- Phase gate: full suite green plus `-m realdata` LightGBM run before `/gsd:verify-work` (CLAUDE.md: run pytest before declaring done).

### Wave 0 Gaps
- [ ] New test files listed above; shared fixtures for a seeded temp DB and a mock Open-Meteo client returning `tests/fixtures/om_live_gfs_seamless.json`.
- [ ] `tests/synth.py` helper for a small synthetic ERA5/GFS/truth set to train 15 tiny boosters quickly (`num_boost_round` ~5).
- [ ] No framework install needed.

## Security Domain

### Applicable ASVS Categories
| Category | Applies | Control |
|----------|---------|---------|
| V2/V3 Auth, Session | no | Local-only, read-only public endpoints (v1 localhost) |
| V4 Access Control | minimal | Bind uvicorn to `127.0.0.1`, not `0.0.0.0` |
| V5 Input Validation | yes | `Query(ge=, le=)` on `hours`/`days`; Pydantic response models |
| V6 Cryptography | no | none |
| V12 Files | yes | Registry/artifact paths resolved under `models/`; reject `..` |

| Threat | STRIDE | Mitigation |
|--------|--------|------------|
| SQL injection | Tampering | Parameterized sqlite3 queries only |
| Path traversal via registry artifact | Tampering | Resolve and assert path inside `models/` |
| Untrusted model files | Tampering | Models committed by owner; load text boosters only (no pickle) |
| Upstream abuse/limits | DoS | Hourly refresh only (24 calls/day), hour-keyed cache |
| CORS | Info disclosure | Not needed (proxy / same origin); do not enable `*` |

## Sources

### Primary (HIGH)
- Codebase read directly: `swf.features.{build,spec,history,splits}`, `swf.evaluate.{baselines,longfmt,metrics,report}`, `swf.fetch.{openmeteo,cache}`, `swf.align.{adapters,consistency}`, `swf.physics.{constraints,simulate,solar}`, `swf.cli`, `config/*.yaml|json`, `pyproject.toml`, tests/test_features_parity.py, tests/test_features_real.py
- `.venv` imports (fastapi 0.162.0, apscheduler 3.11.3, lightgbm 4.7.0); `npm view` (create-vite 9.3.4, vite 8.3.6, react 19.3.1)
- `docs/PRD.md` §9-10, `.planning/research/SUMMARY.md` registry shape and Pattern 4, `.planning/REQUIREMENTS.md`, `CLAUDE.md`

### Secondary / Tertiary
- Library API specifics (APScheduler `next_run_time`, FastAPI lifespan, LightGBM callbacks) from training knowledge, well established across versions but NOT re-checked against Context7 this session [ASSUMED]; the planner should have the executor sanity-run them (a 10-line smoke) early.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (pinned and installed)
- Architecture / integration points: HIGH (code read), MEDIUM on APScheduler/lightgbm API details (not doc-verified)
- Pitfalls: MEDIUM-HIGH (origin boundary analysed, not executed)

**Research date:** 2026-11-07
**Valid until:** 2026-12-07
