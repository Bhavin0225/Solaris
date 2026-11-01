# Project Research Summary

**Project:** Solar & Wind Energy Forecasting, Davanagere, Karnataka (Bhavin's final-year project)
**Domain:** Single-site, multivariate 72 h hourly forecasting of 5 coupled targets. Offline ML pipeline plus a public read-only web app. Viva-examined. Solo build, about 15 days (2026-11-01 to viva around 2026-11-16).
**Researched:** 2026-11-01
**Confidence:** MEDIUM overall. HIGH for package versions and for Open-Meteo / NASA behaviour checked live today. MEDIUM for hosting and schedule feasibility. Several [K]-tagged library items still need confirmation on Days 1-2.

## Executive Summary

This is a graded research deliverable with a public site attached, not a product launch. Experts building this class of system split it into two programs that share one pure-function core: an offline batch pipeline (fetch, clean, physics, features, train, evaluate, writing parquet and a JSON registry) and a small online service that only reads artifacts, runs the same feature code, and writes a SQLite forecast cache. The examiner grades evaluation discipline (chronological splits, leakage tests, a baseline the ML must beat, honest labelling of simulated targets) far above site polish. PROJECT.md's priority, results and report first and site second, is correct and should drive phase ordering.

The recommended approach is Python 3.12 with pandas 3.0.x, pvlib 0.16.1 for the physics chain, and LightGBM as the expected workhorse. A hand-written PyTorch LSTM/GRU and darts 0.48.1 (TFT only) make up the deep ladder. The backend is FastAPI with APScheduler 3.x (one worker) and stdlib `sqlite3`. The frontend is React 19, Vite 8, Tailwind v4 and Recharts 3. Ship a torch-free serving image. Build a walking skeleton that serves baseline 3 and is deployed by about Day 6, then swap in whichever model wins each target under the PRD section 9.4 rule through a `registry.json`. Host the backend on Render Free and the static frontend on Vercel or Netlify, using a same-origin `/api` rewrite.

The key risks: (1) the Open-Meteo Historical Forecast API is a stitched series of short-lead forecasts, not true lead-time forecasts, and lead-matched data (Previous Runs) only exists from about 2024. That changes the covariate plan (PRD 5.2), the split design (PRD 7.5) and what baseline 3 means, so it must be resolved on Days 1-2. (2) Timestamp conventions and the NASA -999 sentinel can quietly corrupt solar results. (3) Leakage through lag and multi-horizon features. (4) Free hosts sleep and wipe their disk, so the in-process scheduler cannot be the only refresh path. (5) A 15-day schedule cannot fit three model families, physics validation and a public deploy if built serially. Mitigations: probe data semantics first, freeze contracts by Day 3-4, put a deployed skeleton on the critical path by Day 6, and time-box TFT with a hard cut around Day 11.

## Cross-Cutting Findings

Bracketed names show which files raised each point.

1. **Open-Meteo Historical Forecast is stitched, not lead-time specific.** [STACK, ARCHITECTURE, PITFALLS, FEATURES]
   The API concatenates the first hours of successive model runs (hour 0 is near-analysis). Training covariates look far more accurate than the day-1 to day-3 forecasts served live. This is the central train/serve skew of the project.
   - Start date: Open-Meteo docs and ARCHITECTURE say "from 2022". STACK's live probe for this site shows all 14 variables non-null from **2017-01-01** (2016-07 all null). Use 2017 as the working value and re-verify per variable and per model on Day 1.
   - Implication for PRD 5.2 and 7.5: covariate-based models train on about 2017-2023 (about 7 years), not 2001-2023. Weather-only (NASA-based) models keep 2001-2023.

2. **Lead-matched covariates exist only from about 2024.** [STACK, ARCHITECTURE, PITFALLS]
   Previous Runs API (`*_previous_dayN`, fixed lead times) is archived mostly from January 2024, and per model, not uniformly. That window matches planned val (2024) and test (2025).
   - Recommendation: evaluate baseline 3 and covariate-based models on lead-matched Previous Runs for val and test. Report the stitched (train) vs lead-matched (eval) gap as direct evidence of skew.

3. **NASA and Open-Meteo use different timestamp conventions.** [PITFALLS, ARCHITECTURE, STACK, FEATURES]
   NASA POWER hourly stamps mark the start of the hour ([M], per NASA FAQ). Open-Meteo radiation is the mean over the preceding hour, labelled at the end. Instantaneous variables are instants at the label. A one-hour shift barely changes daily correlation (about 0.95) but moves sunrise, sunset and the diurnal peak, which solar skill depends on.
   - Recommendation: one adapter per source, one UTC convention internally, one tested offset function. Verify with **sunrise onset and the diurnal centroid against clear-sky at the interval midpoint**. Cross-correlation alone cannot resolve 30 minutes (PITFALLS), so do not rely on it by itself.
   - Solar position at interval midpoint (label minus 30 min for Open-Meteo means).

4. **Torch stays out of the serving image.** [STACK, ARCHITECTURE, PITFALLS]
   Linux CPU torch wheel is about 210 MB (about 0.7 GB installed), with 300-400 MB RSS once imported. Borderline on a 512 MB free instance, and unnecessary if LightGBM or baseline 3 wins.
   - Serving image: FastAPI, uvicorn, APScheduler, httpx, pandas, pvlib, lightgbm, pyyaml, pydantic, plus onnxruntime only if an LSTM/GRU wins. Target about 400-500 MB.
   - TFT has no first-class ONNX export. If TFT wins: (a) CPU torch on a 1 GB host (Fly about $6.70/mo or Railway trial), or (b) precompute TFT forecasts in a scheduled job that writes into the cache. Decide at end of model phase (Day 10-11).

5. **Free-tier hosting breaks an in-process scheduler.** [STACK, ARCHITECTURE, PITFALLS]
   Render Free spins down after about 15 minutes idle (cold start about 30-60 s), has an ephemeral filesystem (SQLite lost on restart), and may have 512 MB RAM (LOW confidence). APScheduler does not run while asleep.
   - Required design: rebuild cache on startup from a committed seed snapshot; lazy refresh on request when cache is older than 60 min (serve stale with `stale: true`, refresh in background); one uvicorn worker; optional external ping on `/api/health` (UptimeRobot or cron-job.org) before viva; a "waking up" state in the frontend.

6. **Evaluation honesty rules.** [all four]
   Chronological splits with full annual cycles, no shuffle. Test set touched once. Select on validation. Solar scored daytime only (midpoint zenith below 85 degrees), same mask for every model. All models compared on the same sample intersection. Baseline 3 is the bar. Persistence includes same-hour-yesterday for solar. No MAPE. Report capacity factor and MAE relative to mean daytime output alongside capacity-normalised nRMSE.

7. **Schedule is the binding constraint.** [PITFALLS, ARCHITECTURE, FEATURES, PROJECT]
   Kaggle files downloaded Day 1 (they block physics validation). Contracts frozen by Day 3-4. Deployed baseline-3 skeleton by about Day 6. TFT hard cut around Day 11. Report figures produced at each phase's exit, not in a final polish phase.

### Errata and resolved conflicts

| Item | PRD or source says | Resolved value | Basis |
|---|---|---|---|
| pvlib AC function | `pvsystem.pvwatts_ac` | `pvlib.inverter.pvwatts(pdc, pdc0, eta_inv_nom=0.96, eta_inv_ref=0.9637)`. `pvwatts_ac` does not exist in pvlib 0.16.1. | STACK (introspected); PITFALLS C7 |
| AC limit | "DC/AC 1.2, AC limit 833 kW" and "inverter 96%" | `pdc0` = 1000/1.2 = 833 kW (DC input). Effective AC clip = 0.96 x 833 = about 800 kW. One config value; section 6 constraint `0 <= T1 <= computed AC clip`; state both numbers in report. Clear-sky test peaked about 770 kW, so 800 kW clip is not yet exercised. | STACK; PITFALLS C7 |
| ERA5 archive wind heights | Archive offers only 100 m | Archive returned `wind_speed_80m`, `_100m`, `_120m` for this site. Use **80 m** across sources. | STACK (live); ARCHITECTURE still says "verify" |
| Historical Forecast start | Docs and ARCHITECTURE: "from 2022" | **2017-01-01** at this site (all 14 variables non-null). Re-verify per variable Day 1. | STACK (live) |
| NASA POWER start | PRD "verify" | **2001-01-01** (earlier requests return HTTP 422) | STACK (live) |
| Open-Meteo forecast window | STACK's example uses `forecast_days=3` | `past_days=7`, `forecast_days=4`, slice [now+1 h, now+72 h]. Three days from 00:00 UTC gives under 72 h ahead. | ARCHITECTURE. STACK's example is a verification call, not the serving call. |
| Python | PROJECT.md "3.11+" | **3.12** (numpy 2.5 requires 3.12; dev machine has 3.12.10) | STACK |
| pandas | Unpinned | `>=3.0.6,<3.1` (3.1.0 too new; pytorch-forecasting caps it) | STACK |
| Open-Meteo azimuth | pvlib 180 = south | Open-Meteo 0 = south (east -90, west +90). One tested function: `az_om = wrap(az_pvlib - 180)`. | STACK; PITFALLS C7 |
| NASA parameters per call | PRD 14 | Documented max 15. Stay at 15 or fewer; server accepted 16 once, do not rely on it. | STACK |
| TFT library | PRD allows darts or pytorch-forecasting | **darts 0.48.1** (native multi-target and quantiles; pytorch-forecasting has tight pins and fiddly `MultiLoss`) | STACK; ARCHITECTURE |
| Charts | PRD allows Recharts or Plotly | **Recharts 3.10** for synced time-series; matplotlib PNGs for validation scatters | STACK; FEATURES |
| Torch install order | Not specified | Install `torch==2.15.0` from CUDA index (cu134, fallback cu132) first, then `darts[torch]`; else darts pulls CPU wheel. Assert `torch.cuda.is_available()`. | STACK; PITFALLS M6 |

## Key Findings

### Recommended Stack

Python 3.12 with pandas 3.0.6 and numpy 2.5 for data and physics; pvlib 0.16.1 (solar position, clear-sky, Perez, Faiman, PVWatts DC, inverter AC); LightGBM 4.7.0 for direct multi-horizon forecasts; plain PyTorch for LSTM/GRU; darts 0.48.1 for TFT; FastAPI 0.162, Uvicorn 0.54 (one worker), APScheduler 3.11.3 (not 4.x alphas), httpx 0.28.1, tenacity 9.2, stdlib `sqlite3` with WAL. Frontend: React 19.3, Vite 8.3, TypeScript 7, Tailwind 4.3 (Vite plugin, no `tailwind.config.js`), Recharts 3.10, TanStack Query 5, react-router 7. Hosting: Render Free for backend (torch-free image), Vercel or Netlify for static frontend.

- **pvlib 0.16.1**: solar physics. Verified by introspection and clear-sky smoke test (Perez needs `dni_extra` and `airmass`).
- **pandas 3.0.6 / numpy 2.5**: tables, UTC index. Copy-on-write; no chained assignment.
- **LightGBM 4.7.0**: direct multi-horizon GBM, optional quantile objective. Expected workhorse; artifacts a few MB, committed.
- **plain PyTorch LSTM/GRU**: hand-written seq2seq so ONNX export stays easy; onnxruntime only if it wins.
- **darts 0.48.1 (TFT)**: `TFTModel(input_chunk_length=168, output_chunk_length=72, likelihood=QuantileRegression([0.1,0.5,0.9]))`. Native multivariate target and quantiles.
- **FastAPI + APScheduler 3.x + sqlite3 WAL**: one process, one scheduler, one table. No SQLAlchemy. Sync endpoints.
- **React + Vite 8 + Tailwind v4 + Recharts 3**: `syncId` shares hover across five panels on one shared 72-point hourly index. Band as `Area` over `[p10, p90]`.
- **Render Free (Docker)**: 750 instance-hours/month covers 24 h x 31 d. Verify RAM and sleep policy on deploy day.

Install notes: torch first (CUDA index), then `darts[torch]`. Pin `requirements.txt` for training and a separate `requirements-serve.txt` with no torch and no darts. Hugging Face Docker Spaces now need a paid plan. Railway Free ($1 credit/mo, 0.5 GB RAM) is a fallback; Fly.io has no free tier (about $4-7/mo).

### Expected Features

**Must have (table stakes):**
- Data: NASA and Open-Meteo fetchers with disk cache, backoff, 15-param/1-year chunks; fetch log with % missing; timestamp check documented in `docs/data_notes.md`; clean hourly UTC table (gap fill up to 3 h, physical clipping, night GHI = 0, clip counts logged); chronological splits with dates logged; automated leakage test.
- Physics and validation: pvlib solar chain from config; wind chain (empirical curve, hub extrapolation, air density, availability); Kaggle gate (solar nRMSE at most 10% daytime, wind at most 14%) with scatter plots and metrics saved; unit tests (conversions, hub height, interpolation, clear-sky day, clipping); physical-constraint layer on all outputs; NASA vs ERA5 consistency table (bias, RMSE, correlation for GHI, RH, WS10M).
- Modelling: three baselines (persistence with same-hour-yesterday, climatology hour x month, NWP + physics); cyclic calendar and direction encodings only (no raw day-of-year); LightGBM direct; at least one deep multivariate model; fixed seeds, saved artifacts, `models/registry.json`; section 9.4 selection (deploy baseline 3 if ML does not beat it; UI says which model serves each target).
- Evaluation: MAE, RMSE, nRMSE (normalisation stated), skill vs baseline 3 (and vs persistence), daytime-only solar, error by horizon (1, 6, 24, 48, 72 h), season and target breakdowns, leaderboard CSV, forecast-vs-actual plots for clear, cloudy and monsoon days, predicted-vs-actual scatters, test touched once.
- Backend: `/api/forecast`, `/forecast/summary`, `/history`, `/metrics`, `/site`, `/health` with typed schemas; hourly refresh; SQLite cache; under 500 ms from cache; stale fallback with `stale: true` and age.
- Frontend: five synced 72 h panels; summary cards (next-24 h solar kWh, wind kWh, peak hour, combined); "last updated" and stale warning; IST display with UTC internally; performance page; about page (sources, attribution, methodology, simulated caveat); mobile at 375 px; visible "simulated" label on T1/T5.
- Deployment: public deploy (backend container, static frontend); `make` or CLI targets; README with fresh-clone steps; pinned dependencies; pytest; report-ready figures in `reports/`.

**Should have (differentiators), cheapest and most valuable first:**
- Probabilistic evaluation: PICP at 80% (target about 80%), mean interval width, pinball loss, reliability diagram. High value per hour.
- Model-used-per-target badge with link to performance page.
- Ablations: with and without Open-Meteo covariates; cyclic vs raw day-of-year (one LightGBM run; reproduces Appendix A lesson).
- Skill-score heatmap (target x horizon bucket x season).
- One TFT interpretability figure (variable-selection weights) plus LightGBM gain importance.
- Coverage number on performance page. Provenance footer (git SHA, data-through date, model version) from `meta.json`.
- Wind capacity-factor and monsoon-vs-dry story with honest "weak site" finding.

**Defer unless spare time:** bootstrap or Diebold-Mariano test (block bootstrap by week is simpler; check viva norm first); learned bias-correction between NASA and Open-Meteo (only if section 7.4 shows large bias); live forecast-vs-actual archive overlay and forecast revision history; CSV download; physics-consistency diagnostics.

**Anti-features (do not build):** location picker or multi-site; auth or accounts; alerts; real-time SCADA; financial or dispatch modelling; Kaggle data as ML targets; Optuna mega-sweeps (use small grid or about 30 LightGBM trials; early stopping for nets); more model families (XGBoost, N-BEATS, ensembles); per-target bespoke deep architectures; online retraining; re-labelling the test set or tuning on it; 3D, maps, dark mode, i18n, PWA, websockets, interactive model playground; reporting solar scores over all 24 h; claiming measured generation.

### Architecture Approach

Two programs sharing one pure-function core. The offline pipeline runs on the laptop GPU and writes parquet and model artifacts. The online service is one FastAPI process with an APScheduler job, a SQLite cache, and no model or fetch in the request path. The shared core (`swf.core`, `swf.physics`, `swf.features`, `swf.predict`) prevents train/serve skew. The API imports only core, Open-Meteo fetcher, adapters, physics, features and predict runtime. It must never import `datasets`, `evaluate`, `validate`, torch, darts or matplotlib at module load.

**Major components:**
1. **`swf.core`**: pydantic config over `site.yaml` and `plant.yaml`; UTC helpers; `CANON_COLS` (`ghi, dni, dhi, temp, rh, pressure, ws10, ws_hub, wd10, wd_hub, precip, cloud`); paths; logging.
2. **`swf.fetch`**: httpx clients for NASA POWER and Open-Meteo (historical forecast, previous runs, ERA5 archive, live forecast). Disk cache keyed by API, params and range; raw JSON verbatim with URL and retrieval date; retry/backoff; fetch log. No parsing.
3. **`swf.align` (adapters + clean)**: the only place that knows NASA vs Open-Meteo quirks. Output canonical hourly UTC frame. Gap fill up to 3 h, clipping, midpoint-zenith night mask, missing-data report.
4. **`swf.physics`**: canonical weather to T1/T5 kW (pvlib chain, hub extrapolation, density once, power curve, availability). Used for training truth (NASA), baseline 3 (Open-Meteo), serving fallback.
5. **`swf.validate`**: Kaggle calibration of loss %, power-curve bins, nRMSE gates, plots. Offline only.
6. **`swf.features`**: single causal feature builder plus `FEATURE_SPEC` (ordered names, dtypes, hash). Many issue times in training; one in serving.
7. **`swf.datasets`**: splits, direct-row builder, sequence windows, scalers. Offline only.
8. **`swf.models`**: training code and `Predictor` implementations (`Baseline3`, `Persistence`, `Climatology`, `LGBM`, `Seq2Seq`, `TFT`), each returning the common long format.
9. **`swf.evaluate`**: model-agnostic metrics over `predictions.parquet`; leaderboard; section 9.4 selection; writes `registry.json`.
10. **`swf.predict`**: registry loader, `Predictor` protocol, physical clipping. Only model-facing module the API imports. Lazy imports keep torch optional.
11. **`swf.api`**: FastAPI app, scheduler job, SQLite repository, Pydantic schemas, stale logic. One process, one worker.
12. **`frontend/`**: Vite, React, TypeScript, Tailwind, Recharts. Types generated from OpenAPI. IST conversion only here.

**Key patterns:**
- **Pattern 1, one feature function, two call sites.** Guard-rails: `FEATURE_SPEC` hash in every `meta.json`, checked at load; truncation-invariance test (features at t from full data equal features from data cut at t); train/serve parity test against a committed raw Open-Meteo fixture.
- **Pattern 2, canonical frame plus source adapters.** Three skews, three answers: (A) lag inputs (NASA in training, Open-Meteo `past_days` at serving); (B) known-future covariates (no archived NWP for early years); (C) lead-time mismatch (stitched short-lead in training, long-lead at serving). See decisions D1-D3.
- **Pattern 3, common prediction contract.** Every model emits `issue_time, horizon, target_time, target, model, y_true, p10, p50, p90` to `data/processed/predictions/<split>_<model>.parquet`. Evaluation is a pure groupby on a shared issue-time grid.
- **Pattern 4, registry-dispatched Predictor, baseline 3 first-class.** "Deploy baseline 3 for this target" is a registry entry. Bands for baseline 3 and LightGBM come from empirical residual quantiles by horizon bucket (validation). TFT supplies native P10/P50/P90.
- **Pattern 5, idempotent stage CLI.** Parquet in, pure function, parquet out; `Makefile` targets call `python -m swf.cli <stage>`. No Airflow, MLflow, DVC or Prefect. Lineage in `manifest.json` copied into each `meta.json`.

**Registry shape:** `models/deployed/registry.json` with `schema_version`, `feature_spec_hash`, `split`, and per target `{selected, runtime (lightgbm | onnx | torch | baseline3), artifact, reason, test metrics, baseline3_rmse, bands}`. All candidates kept for the report.

### Critical Pitfalls

1. **Stitched Historical Forecast treated as lead-time forecast (C1).** Over-trusted covariates; wrong baseline 3 and skill scores. Prevention: probe per-variable coverage and lead semantics Day 1; Previous Runs for val and test; log coverage in `docs/data_notes.md`; never call ERA5 a forecast.
2. **Lag features from a source unavailable live (C2).** NASA lags by days and is a different product from Open-Meteo analysis. Prevention: decide live history source Day 1-2; training lags from closest equivalent source; section 7.4 comparison at lag-feature level; replay test of a past date through the serving path.
3. **Timestamp offsets and time zones (C3, M1).** One-hour radiation shifts ruin solar. Prevention: one adapter per source; tested offset; midpoint zenith; `time-standard=UTC` asserted; `timezone=GMT` on Open-Meteo; tz-aware UTC asserted at boundaries; IST day bounds computed server-side for "tomorrow" totals.
4. **Leakage in lags, rolling stats and multi-horizon rows (C4).** Features per origin t0; only known-future covariates indexed at t0+h; purge training origins whose 72 h target crosses into val (and val into test); scalers fit on train only; truncation and perturbation tests; test frozen until final evaluation.
5. **-999 sentinel becomes valid data (C6).** Clipping turns GHI and RH to zero; rolling means and interpolation poisoned. Prevention: replace at fetch boundary using `header.fill_value`; assert minimum above -900; % missing per column and year; interpolate only gaps of 3 h or less; never interpolate GHI across sunrise or sunset (interpolate clear-sky index).
6. **PV chain mistakes (C7).** Azimuth convention (180 vs 0 gives plausible but wrong panel); inverter cap (use `pvlib.inverter.pvwatts`, one config value); Perez inputs mandatory; component closure (GHI vs DNI cos z + DHI) unchecked; loss % tuned on 34 days is a calibration constant. Prevention: unit tests (south vs north POA ratio, clip at cap, night = 0), closure check on NASA components.
7. **Free-tier sleep, ephemeral disk, duplicate schedulers (C8).** Lazy refresh, seed snapshot, one worker with `max_instances=1` and `coalesce=True`, external pinger, "waking up" state.
8. **Torch on 512 MB host (C9).** Torch-free serving image; ONNX for LSTM/GRU if it wins; separate `requirements-serve.txt`; measure RSS in Phase 5.
9. **Schedule collapse (C10).** Kaggle Day 1; contracts early; skeleton by Day 6; TFT hard cut Day 11 with "attempted, did not beat baseline 3" write-up if needed; figures at each phase exit.

Other moderate items: Windows torch installs CPU-only from PyPI (M6); DataLoader `num_workers>0` on Windows needs `if __name__ == "__main__"` (start at 0); mixed `pytorch_lightning` and `lightning` versions; quantile crossing (sort, clip, check coverage); Kaggle parsing (`dayfirst=True`; DC_POWER about 10x AC_POWER; IRRADIATION in kW/m2, sensor type unknown; wind Date/Time `dd mm yyyy` local with 3.9% missing, do not ffill); power-curve convexity (Jensen bias); CORS and build-time `VITE_API_URL` (prefer same-origin rewrite); Open-Meteo free tier non-commercial, CC BY 4.0 attribution required.

## Implications for Roadmap

### Decisions to lock in Phase 1 (by end of Day 2)

- **D1. Lag and rolling source.** Recommended: compute lag and rolling features from the same source family that serves live history: Open-Meteo archive (ERA5) for training history, Open-Meteo `past_days` at serving. NASA remains target truth and cross-check (section 7.4). Verify the ERA5 archive start year on Day 1; not established by research.
- **D2. Training and evaluation windows.** Recommended: weather-only and NASA-based models train 2001-2023; covariate-based models train 2017-2023. Both use val = 2024, test = 2025, so the leaderboard shares the 2024-2025 index. Do not build the ERA5 stage-1 proxy for 2001-2016 (ARCHITECTURE Pattern 2B) unless the 2017-2023 window proves too short.
- **D3. Baseline 3 definition.** Recommended: baseline 3 uses lead-matched Previous Runs for val and test. Report a stitched-data variant alongside so the gap is visible.
- **D4. AC limit.** `pdc0` = 833 kW, effective AC clip about 800 kW, from one config value. State both in report.
- **D5. Serving image.** Torch-free by default. TFT serving path decided end of Phase 6 (Day 10-11).
- **D6. Model selection.** Choose on validation; confirm on test once through `evaluate --final`. State the rule in the report. If the literal "lowest test RMSE" reading is used, say so.

### Suggested phase structure (8 phases, 15 days)

**Phase 1: Foundations and data acquisition (Days 1-2)**
- Rationale: network-bound; Kaggle files block validation; coverage probe decides splits and baseline 3.
- Delivers: pinned env with CUDA check; config; background pulls of NASA 2001-2025 hourly, Open-Meteo Historical Forecast 2017+, Previous Runs 2024+ (per model), ERA5 archive, live forecast; each file with URL and retrieval date; coverage and missing-data table; `docs/data_notes.md` started; `CANON_COLS` frozen; Kaggle files in `data/raw/kaggle/`.
- Avoids: C1 (probe coverage and lead semantics), C6 (sentinel), M1 (UTC assertion), M9 (chunked, cached pulls).
- Research flag: empirical probing, not a research phase (OM coverage per model and variable; ERA5 start year; NASA per-variable timestamp).

**Phase 2: Alignment, cleaning and physics (Days 2-3)**
- Rationale: every later stage reads canonical hourly UTC; physics must exist before the Kaggle gate.
- Delivers: adapters for NASA, Open-Meteo, ERA5; clean step; timestamp test (sunrise onset, diurnal centroid); NASA vs ERA5 consistency table per month; pvlib solar chain (Perez with `dni_extra` and `airmass`, Faiman on WS10M, `pvwatts_dc`, `inverter.pvwatts`); wind chain (curve, hub extrapolation from 10 m and 50 m, density once, availability); unit tests.
- Avoids: C3, C7, M2, M3, M5, M10.
- Contracts frozen by end Day 3-4: `FEATURE_SPEC` names, predictions long format, `registry.json` schema, API `schemas.py`.

**Phase 3: Physics validation gate (Days 3-4)**
- Rationale: only defence of simulated targets. A gate, not a blocker.
- Delivers: Kaggle schema and units check; loss % calibrated within 8-20% on solar Plant 1 (daytime); wind power-curve bins; nRMSE (solar at most 10%, wind at most 14%); scatter and bias-vs-speed plots in `reports/validation/`; written list of misses.
- Avoids: M4 (dayfirst, DC/AC units, IRRADIATION type), M3, C7 (34-day caveat), M5 (validation does not test NASA input quality; say so).

**Phase 4: Features, splits, baselines and evaluation harness (Days 4-5)**
- Rationale: baselines are the bar; leaderboard before any ML claim.
- Delivers: shared causal feature builder; splits per D2; truncation and perturbation tests; parity fixture test; baselines 1-3 (baseline 3 on lead-matched data per D3); metrics module (MAE, RMSE, nRMSE, skill, daytime mask, horizon, season); first leaderboard CSV.
- Avoids: C1, C2, C4, C5, m1, m2.

**Phase 5: Walking skeleton and LightGBM (Days 5-6)**
- Rationale: deploy early; registry dispatch lets later models plug in without API changes.
- Delivers: FastAPI (one worker), sqlite3 WAL, APScheduler 3 hourly job, lazy refresh (>60 min), startup refresh, committed seed snapshot; serving path with baseline 3 for all five targets; clipping layer; endpoints `/api/health`, `/api/forecast`, `/forecast/summary`, `/history`, `/metrics`, `/site`; torch-free `requirements-serve.txt`; Render deploy; LightGBM direct residual-on-baseline-3 (config switch vs raw target); first `registry.json`; OpenAPI for frontend mocks; horizon buckets (1-6, 7-24, 25-72 h); origin stride 3 h.
- Avoids: C8, C9, M7 (same-origin plan), M8.
- Milestone: deployed baseline-3 site by Day 6.

**Phase 6: Deep models, time-boxed (Days 6-11)**
- Rationale: highest risk; background GPU training while Phases 5 and 7 proceed.
- Delivers: LSTM/GRU seq2seq in plain PyTorch (smoke run first; five targets jointly; scalers in `meta.json`; ONNX if it wins); TFT via darts (one-epoch spike first; 3-4 trials; quantiles sorted and clipped; PICP and pinball; trained on 2017-2023 per D2); training curves in `reports/`; TFT serving decision recorded.
- Avoids: M6 (`num_workers=0`, CUDA assert, gradient clip near 0.1, `--smoke` flag, early stopping on val), C10, C9.
- Cut rules: LSTM stops around Day 10 if not stable (minimal version, report honestly). TFT hard cut Day 11; if not converged, report "attempted, did not beat baseline 3" with curves.
- Research flag YES: darts multi-target spike; TFT serving path; variable-importance and attention outputs (FEATURES gap).

**Phase 7: Selection, frontend and public deploy (Days 7-12, partly parallel)**
- Rationale: frontend can start against mocked JSON once schemas freeze (Day 3-4); selection follows Phase 6.
- Delivers: section 9.4 selection on validation; test once via `evaluate --final`; promote to `models/deployed/`; dashboard (five synced Recharts panels with P10-P90 bands, summary cards, stale banner, "last updated", IST, "simulated" label); performance page (leaderboard, skill bars, error by horizon, validation PNGs); about page (attribution for NASA POWER, Open-Meteo CC BY 4.0, Kaggle; methodology; simulated caveat); mobile check at 375 px; full deploy with same-origin `/api` rewrite; stale-fallback test; "waking up" state.
- Avoids: M1, M7, C8 (cold-start UX), C5.
- Milestone: full site deployed by Day 12.

**Phase 8: Report, figures and viva readiness (Days 12-15)**
- Rationale: figures generated per phase; this phase is writing, reproducibility and rehearsal.
- Delivers: `make` targets reproduce from fresh clone; README; pytest green; figures in `reports/`; ablations if time; TFT interpretability figure if TFT ran; slides; viva checklist walk-through; live-site check from phone and fresh browser the day before; warm service 5-10 min before viva. Keep one buffer day.
- Avoids: C10.

Viva around 2026-11-16.

### Phase ordering rationale

- Data semantics first: D1-D3 change splits, baseline 3 and features. Discovering them at evaluation is the costliest failure.
- Physics and Kaggle gate before features: simulated targets are the labels.
- Baselines and leaderboard before ML: every model result has a bar in the same table.
- Deployed baseline-3 skeleton before deep models: a live, honest site exists even if the deep ladder fails.
- Deep models in background: training overlaps frontend and deploy.
- Selection and test evaluation after all candidates exist, once.

### Cut order if behind schedule

TFT, then LSTM tuning, then bias-correction beyond linear, then About-page polish. Never cut physics validation, baseline 3, leakage and parity tests, or the honest leaderboard.

### Research flags

**Needs empirical probing or research during planning:**
- Phase 1: OM coverage and lead semantics per model and variable; NASA per-variable timestamp convention. Probe Days 1-2.
- Phase 6: darts multi-target TFT spike; TFT serving path; interpretability outputs.
- Phase 7: current Render Free RAM and sleep policy; Vercel or Netlify rewrite behaviour (MEDIUM; re-check on deploy day).

**Standard patterns (skip research-phase):** Phase 2 (pvlib chain, introspected, smoke-tested); Phase 4 (metrics, leaderboard, persistence and climatology); Phase 5 (FastAPI + APScheduler 3 + sqlite3 WAL; LightGBM `Booster` save/load); Phase 7 (Recharts `syncId`, Tailwind v4 Vite plugin, TanStack Query polling); Phase 8 (report, README, reproducibility).

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack | HIGH (versions, APIs) / MEDIUM (hosting) | Versions from PyPI and npm on 2026-11-01; pvlib introspected; NASA and Open-Meteo verified live for the site. Hosting limits from vendor docs, change often. Render RAM LOW. |
| Features | MEDIUM | PRD plus general forecasting-verification practice; no authoritative feature list for this domain; viva norms unknown. |
| Architecture | MEDIUM-HIGH | Open-Meteo semantics checked against official docs. Darts API from Context7 (MEDIUM). Packaging, scheduler and free-tier behaviour are general practice. |
| Pitfalls | MEDIUM | API semantics verified; library and hosting items partly [K]; confirm when each phase starts. |

**Overall: MEDIUM.** High confidence on what was checked live (versions, API parameters and coverage). Lower on schedule feasibility and on items that resolve only with data in hand.

### Gaps to Address

- **Historical Forecast start:** docs say 2022; live probe says 2017. Re-verify per variable Day 1.
- **Previous Runs coverage per model for 2024-2025:** "mostly from January 2024". Confirm baseline 3 models are archived for full val and test. If not, D3 needs a fallback.
- **NASA per-variable timestamp convention:** not documented. Resolve with sunrise onset and midpoint zenith.
- **ERA5 archive start year:** not established. Needed for D1. If not 2001 onward, fall back to NASA-only lags with documented skew.
- **Lag-source decision (D1):** research recommends matching the serving history source; PRD wording differs. Decide Day 1-2.
- **Training windows (D2):** leaderboard fairness depends on shared 2024-2025 index; note fewer training years for covariate models in report.
- **Render free tier:** RAM (512 MB historically, LOW), cold start, idle policy. If RAM too small, Railway trial or Fly.io (about $4-7/mo).
- **TFT serving path:** no ONNX. Decide Day 10-11 (CPU torch on 1 GB host, or precomputed forecasts).
- **Darts TFT details:** multi-target layout, quantile shape, variable-importance outputs (MEDIUM, Context7). Verify in one-epoch spike.
- **Kaggle files:** day-first dates, DC vs AC units, IRRADIATION sensor type unverified until files in hand. Check with pvlib clear-sky Day 3.
- **Open-Meteo GTI cross-check:** sanity only; transposition differs by a few percent.
- **Vercel and Netlify free tiers:** not re-verified (MEDIUM). Check on deploy day.
- **Viva norms:** ask whether a significance test or a deployed deep model is expected (PRD section 17 Q1, Q3). If no answer: cheap block bootstrap; report deep-model outcome honestly either way.
- **Section 9.4 literal reading:** state in report whether selection is on validation with test confirmation (recommended) or on test RMSE.
- **Wind site:** Davanagere wind expected near zero for most of October to May. Expect a "no ML win" outcome for wind; plan seasonal breakdown and capacity-factor figures to report it.

## Sources

**Primary (HIGH):** PyPI JSON API (pvlib, lightgbm, torch, darts, pytorch-forecasting, httpx, fastapi, uvicorn, apscheduler, pandas, numpy, onnxruntime, lightning; read 2026-11-01); npm registry (vite, react, tailwindcss, @tailwindcss/vite, recharts, typescript, create-vite) and create-vite react-ts template; pvlib 0.16.1 installed and introspected, pvlib what's-new; Context7 `/pvlib/pvlib-python` and `/unit8co/darts`; Recharts AreaChart API (https://recharts.github.io/en-US/api/AreaChart/); NASA POWER hourly docs (https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) and live calls (API v2.10.3, lat 14.4644 / lon 75.9218); Open-Meteo Historical Forecast docs (https://open-meteo.com/en/docs/historical-forecast-api) and live calls 2016-2023; Open-Meteo Previous Runs docs (https://open-meteo.com/en/docs/previous-runs-api); Open-Meteo Forecast docs (https://open-meteo.com/en/docs); Open-Meteo pricing and terms (https://open-meteo.com/en/pricing, https://open-meteo.com/en/terms); PyTorch wheel index (https://download.pytorch.org/whl/).

**Secondary (MEDIUM):** Open-Meteo "Introducing the Historical Forecast API" (https://openmeteo.substack.com/p/introducing-the-historical-forecast); Render free tier (https://render.com/docs/free) and community or aggregator pages; Railway, Fly.io, Hugging Face pricing docs; pytorch-forecasting getting-started docs; probabilistic-verification references (arXiv 1710.01720; k-diagram docs); ERCOT and PJM operator dashboard references; Lim et al., IJF 2021 (TFT interpretability; PRD section 18); NASA POWER FAQ (https://power.larc.nasa.gov/docs/faqs/other/) and pvlib `get_nasa_power`.

**Tertiary (LOW, needs validation):** Render Free RAM (512 MB historical) and CPU share; Open-Meteo Single Runs API coverage; Kaggle dataset quirks (anikannal solar Plant 1/2; berkerisen wind T1); skill-score and daytime conventions (training knowledge); [K]-tagged library behaviour (Windows torch wheel default, DataLoader spawn, CORS and Starlette).

---
*Research completed: 2026-11-01*
*Ready for roadmap: yes, once decisions D1-D6 and the gaps above are resolved in Phases 1-2*
