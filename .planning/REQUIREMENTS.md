# Requirements: Solar & Wind Energy Forecasting — Davanagere

**Defined:** 2026-11-01
**Core Value:** Rigorous, honest model results — a leaderboard showing whether ML beats the Open-Meteo + physics (NWP) baseline per target, backed by physics simulation validated against real Kaggle plant data.
**Spec:** `docs/PRD.md` (source of truth); research errata in `.planning/research/SUMMARY.md` override PRD where they conflict.

## v1 Requirements

### Setup & Environment

- [x] **SETUP-01**: Developer can create the Python 3.12 environment with uv from pinned `pyproject.toml` + `uv.lock`: core deps = serving set (no torch/darts), `[train]` extra = training set
- [x] **SETUP-02**: Developer can confirm `torch.cuda.is_available()` is True on the local NVIDIA GPU after install (torch from CUDA index before darts)
- [x] **SETUP-03**: All site and plant values load from `config/site.yaml` and `config/plant.yaml`; no coordinates or plant specs are hard-coded
- [x] **SETUP-04**: `pytest` runs from the repo root and passes
- [x] **SETUP-05**: Kaggle files (solar Plant 1/2, wind T1.csv) are present in `data/raw/kaggle/`; validation stops and asks if they are missing

### Data Acquisition

- [x] **DATA-01**: Developer can fetch NASA POWER hourly data (2001-01-01 → 2025-12-31, ≤15 params/call, one year per call, `time-standard=UTC`) with on-disk cache, ≥1 s spacing, and backoff on 429/5xx
- [x] **DATA-02**: Developer can fetch Open-Meteo Historical Forecast (GFS, 2021-03+), Previous Runs (GFS, 2024-01+, lead-matched), ERA5 archive (`models=era5`, 2001+), and live forecast (GFS) (`past_days=7`, `forecast_days=4`) directly via httpx, cached with URL and retrieval date
- [x] **DATA-03**: NASA `-999` sentinel is converted to NaN at the fetch/parse boundary before any clipping or interpolation
- [x] **DATA-04**: Every fetch logs URL, status, rows, and % missing per column
- [x] **DATA-05**: Developer can print a coverage report: Open-Meteo per-variable/per-model availability, ERA5 start year, NASA latency — recorded in `docs/data_notes.md`

### Alignment & Cleaning

- [x] **ALIGN-01**: Each source has one adapter producing a canonical hourly UTC frame (`CANON_COLS`) with a documented, unit-tested timestamp offset
- [x] **ALIGN-02**: Timestamp convention is verified with sunrise onset and diurnal centroid vs pvlib clear-sky at interval midpoint; result recorded in `docs/data_notes.md`
- [x] **ALIGN-03**: Cleaning reindexes to a complete hourly UTC index, interpolates gaps ≤3 h (GHI via clear-sky index, never across sunrise/sunset), leaves longer gaps NaN, clips to physical ranges, and logs clip counts
- [x] **ALIGN-04**: Night-time GHI is forced to 0 where midpoint solar zenith > 90°
- [x] **ALIGN-05**: Developer can view a NASA vs ERA5 consistency table (bias, RMSE, correlation for GHI, RH, WS10M, per month) in `docs/data_notes.md`
- [x] **ALIGN-06**: If the consistency check shows large bias, a linear per-variable correction is fitted and applied identically in training and serving

### Physics Simulation

- [x] **PHYS-01**: Solar kW is simulated with pvlib (Perez transposition with `dni_extra`/`airmass`, Faiman cell temp using WS10M, `pvwatts_dc`, `pvlib.inverter.pvwatts`) from config
- [x] **PHYS-02**: AC clipping uses one config value (`pdc0` = 833 kW DC input → effective AC cap ≈ 800 kW); both numbers stated in the report
- [x] **PHYS-03**: Azimuth conversion between pvlib (180 = south) and Open-Meteo (0 = south) lives in one unit-tested function
- [x] **PHYS-04**: Wind kW is simulated from the re-binned manufacturer power curve (from T1 Theoretical_Power_Curve) (`config/power_curve.csv`, 0.5 m/s bins; parametric fallback), hub-height (80 m) extrapolation from 10/50 m with clipped α, air-density correction, and 3.5% availability loss
- [x] **PHYS-05**: Unit tests cover unit conversions, hub-height extrapolation, power-curve interpolation, a clear-sky-day PV run, south-vs-north POA ratio, clipping at cap, and night = 0
- [x] **PHYS-06**: A physical-constraint layer enforces PRD §6 bounds on all outputs (0 ≤ T1 ≤ AC cap, T1 = 0 at night, 0 ≤ RH ≤ 100, GHI ≥ 0 and 0 at night, WS ≥ 0, 0 ≤ T5 ≤ 3600)

### Physics Validation (Kaggle gate)

- [x] **VAL-01**: Kaggle solar data is parsed correctly (`dayfirst`, AC_POWER summed per timestamp, IRRADIATION units checked) and loss % is tuned in 8–20% to minimise daytime normalised RMSE
- [x] **VAL-02**: Solar validation reports nRMSE on daytime rows against the ≤10% target, or a written justification if missed
- [x] **VAL-03**: Wind validation compares simulated power (re-binned manufacturer curve (from T1 Theoretical_Power_Curve) × availability) to `LV ActivePower`, reporting nRMSE against the ≤14% target (must not be worse than 13.0% manufacturer curve)
- [x] **VAL-04**: Scatter plots (simulated vs actual) and `metrics.json` are saved to `reports/validation/`

### Dataset & Features

- [ ] **FEAT-01**: One causal feature builder (`swf.features`) is used by both training and serving, with a `FEATURE_SPEC` hash stored in every model artifact and checked at load
- [ ] **FEAT-02**: Features include target lags (t−1…6, 12, 24, 48, 168), 6/24 h rolling mean/std, Open-Meteo known-future covariates, solar geometry and clear-sky index, cyclic hour/day-of-year, monsoon flag, direction sin/cos, and horizon — no raw day-of-year
- [ ] **FEAT-03**: Lag/rolling history features come from ERA5 archive in training and Open-Meteo `past_days` at serving (fallback to NASA with documented skew if ERA5 history is too short); NASA remains target truth
- [ ] **FEAT-04**: Splits are chronological with full annual cycles: weather-only models train 2001–2023, covariate models train 2021-04–2023 (GFS history); all use val = 2024, test = 2025; boundary origins whose 72 h targets cross splits are purged; date ranges are logged
- [ ] **FEAT-05**: A truncation/perturbation leakage test proves no feature at origin t uses data after t (except known-future covariates)
- [ ] **FEAT-06**: A train/serve parity test replays a committed raw Open-Meteo fixture through both code paths and gets identical features

### Baselines & Evaluation

- [ ] **EVAL-01**: Persistence baseline (value at t; same hour yesterday for solar) produces predictions for all five targets
- [ ] **EVAL-02**: Climatology baseline (hour-of-day × month mean over training years) produces predictions for all five targets
- [ ] **EVAL-03**: Baseline 3 (Open-Meteo forecast → physics chain, no ML) is scored on lead-matched Previous Runs data for val/test, with a stitched variant reported alongside
- [ ] **EVAL-04**: Every model writes the common long prediction format (`issue_time, horizon, target_time, target, model, y_true, p10, p50, p90`)
- [ ] **EVAL-05**: Metrics module computes MAE, RMSE, nRMSE (normalisation stated), skill vs baseline 3 and vs persistence on a shared sample index; solar scored on daytime only (midpoint zenith < 85°)
- [ ] **EVAL-06**: Developer can view breakdowns by horizon (1, 6, 24, 48, 72 h), season (monsoon vs dry), and target
- [ ] **EVAL-07**: Leaderboard is written to `reports/evaluation/leaderboard.csv` with plots, and includes all three baselines for all five targets
- [ ] **EVAL-08**: Probabilistic metrics are reported: P10–P90 coverage (target ≈ 80%), mean interval width, pinball loss, reliability diagram
- [ ] **EVAL-09**: A skill-score heatmap (target × horizon bucket × season) is saved to `reports/evaluation/`
- [ ] **EVAL-10**: Wind capacity factor and monsoon-vs-dry breakdown are reported honestly

### Models

- [ ] **MODEL-01**: LightGBM direct multi-horizon model (horizon as feature or per bucket 1–6/7–24/25–72 h) is trained per target with fixed seeds and saved artifacts
- [ ] **MODEL-02**: LSTM/GRU seq2seq (plain PyTorch; encoder 168 h, decoder 72 h known-future covariates, 5 targets jointly) is trained on GPU and exportable to ONNX
- [ ] **MODEL-03**: TFT (darts) is trained with P10/P50/P90 quantile outputs for the 5 targets, time-boxed with a hard stop ~Day 11; if it fails, the attempt is reported honestly
- [ ] **MODEL-04**: Quantile outputs are sorted (no crossing) and clipped by the constraint layer; LightGBM/baseline bands come from validation residual quantiles by horizon bucket
- [ ] **MODEL-05**: Model selection per target is done on validation; test is evaluated once (`evaluate --final`); a target with no ML model beating baseline 3 deploys baseline 3
- [ ] **MODEL-06**: `models/deployed/registry.json` records per target: selected model, runtime, artifact, reason, test metrics, baseline-3 RMSE, band method, `feature_spec_hash`, split dates, git SHA
- [ ] **MODEL-07**: Interpretability figures are saved: TFT variable-selection weights (if TFT ran) and LightGBM gain importance

### Backend API

- [ ] **API-01**: FastAPI app (one Uvicorn worker) serves `/api/health`, `/api/forecast?hours=72`, `/api/forecast/summary`, `/api/history?days=7`, `/api/metrics`, `/api/site` with Pydantic schemas and ISO-8601 UTC timestamps
- [ ] **API-02**: Forecast refresh runs hourly via APScheduler 3 (`max_instances=1`, `coalesce=True`), on startup, and lazily on request when cache is older than 60 min
- [ ] **API-03**: Forecasts are cached in SQLite (WAL) as (run_time, target_time, target, model, p10, p50, p90); a committed seed snapshot rebuilds the cache after an ephemeral-disk restart
- [ ] **API-04**: If Open-Meteo is unreachable, the latest cached forecast is served with `stale: true` and its age (tested)
- [ ] **API-05**: Serving dispatches models via the registry with lazy imports; the serving image contains no torch (ONNX runtime only if LSTM wins)
- [ ] **API-06**: `/api/forecast` responds in < 500 ms from cache
- [ ] **API-07**: Next-24 h summary (solar kWh, wind kWh, peak hour, mean RH, max wind) uses IST day bounds computed server-side

### Frontend

- [ ] **UI-01**: Dashboard shows five synchronized 72 h panels (T1–T5) with P50 line and P10–P90 band; hovering one panel highlights the same hour on all five
- [ ] **UI-02**: Summary cards show tomorrow's solar kWh, wind kWh, peak generation hour, and combined energy
- [ ] **UI-03**: All times are displayed in IST; "last updated" time and a visible stale warning are shown; a "waking up" state covers backend cold starts
- [ ] **UI-04**: T1 and T5 carry a visible "simulated energy" label
- [ ] **UI-05**: Each target shows a badge naming the serving model, linking to the performance page
- [ ] **UI-06**: Model performance page shows leaderboard table, skill-vs-baseline bars, error-by-horizon chart, skill heatmap, and validation scatter PNGs
- [ ] **UI-07**: About page shows site and plant specs, methodology diagram, simulated-energy caveat, wind capacity-factor story, and attribution for NASA POWER, Open-Meteo (CC BY 4.0), and Kaggle datasets
- [ ] **UI-08**: Provenance footer shows git SHA, data-through date, and model version
- [ ] **UI-09**: Layout works on mobile (checked at 375 px width)

### Deployment & Reproducibility

- [ ] **DEPLOY-01**: Backend is publicly deployed as a torch-free Docker image (Render Free by default) and frontend as a static build (Vercel/Netlify) with a same-origin `/api` rewrite
- [ ] **DEPLOY-02**: A baseline-3 walking skeleton (live Open-Meteo → physics → SQLite → API → page) is deployed by ~Day 6
- [ ] **DEPLOY-03**: `make data`, `make train`, `make evaluate`, `make serve` (or CLI equivalents) reproduce everything from a fresh clone
- [ ] **DEPLOY-04**: README documents fresh-clone setup, commands, data sources, and the deployed URL
- [ ] **DEPLOY-05**: Report-ready figures and tables are produced into `reports/` at each phase's exit

## v2 Requirements

Deferred. Tracked but not in current roadmap.

### Evaluation

- **EVAL2-01**: Statistical significance test (weekly block bootstrap CI or Diebold-Mariano) for model vs baseline 3
- **EVAL2-02**: Ablations: with/without Open-Meteo covariates; cyclic vs raw day-of-year
- **EVAL2-03**: Non-linear NASA↔Open-Meteo bias correction

### Product

- **PROD-01**: Location picker / multiple sites (code already location-agnostic via config)
- **PROD-02**: Live forecast-vs-actual archive overlay and forecast revision history
- **PROD-03**: CSV download of forecasts

## Out of Scope

| Feature | Reason |
|---------|--------|
| User accounts / authentication | Public read-only demo |
| Real-time SCADA integration | No physical plant exists |
| Grid dispatch, pricing, financial modelling | Not part of the forecasting question |
| Kaggle data as ML training targets | Different sites; validation/calibration only |
| Alerts / notifications | Not needed for viva demo |
| Hyperparameter mega-sweeps, extra model families (XGBoost, N-BEATS, ensembles) | 15-day schedule; three-model ladder is enough |
| Online retraining on the server | Training is offline on local GPU |
| Websockets, 3D/maps, dark mode, i18n, PWA, model playground | Polish with no evaluation value |
| Solar scores over all 24 h; claiming measured generation | Inflates metrics / dishonest |

## Definition of Done

- All v1 requirements checked, `pytest` green
- Leaderboard has all baselines and models for all five targets; registry written per selection rule
- Public site reachable from a phone, serving forecasts with correct attribution
- Fresh clone → documented commands → working site

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Complete |
| SETUP-02 | Phase 1 | Complete |
| SETUP-03 | Phase 1 | Complete |
| SETUP-04 | Phase 1 | Complete |
| SETUP-05 | Phase 1 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| ALIGN-01 | Phase 2 | Complete |
| ALIGN-02 | Phase 2 | Complete |
| ALIGN-03 | Phase 2 | Complete |
| ALIGN-04 | Phase 2 | Complete |
| ALIGN-05 | Phase 2 | Complete |
| ALIGN-06 | Phase 2 | Complete |
| PHYS-01 | Phase 2 | Complete |
| PHYS-02 | Phase 2 | Complete |
| PHYS-03 | Phase 2 | Complete |
| PHYS-04 | Phase 2 | Complete |
| PHYS-05 | Phase 2 | Complete |
| PHYS-06 | Phase 2 | Complete |
| VAL-01 | Phase 3 | Complete |
| VAL-02 | Phase 3 | Complete |
| VAL-03 | Phase 3 | Complete |
| VAL-04 | Phase 3 | Complete |
| FEAT-01 | Phase 4 | Pending |
| FEAT-02 | Phase 4 | Pending |
| FEAT-03 | Phase 4 | Pending |
| FEAT-04 | Phase 4 | Pending |
| FEAT-05 | Phase 4 | Pending |
| FEAT-06 | Phase 4 | Pending |
| EVAL-01 | Phase 4 | Pending |
| EVAL-02 | Phase 4 | Pending |
| EVAL-03 | Phase 4 | Pending |
| EVAL-04 | Phase 4 | Pending |
| EVAL-05 | Phase 4 | Pending |
| EVAL-06 | Phase 4 | Pending |
| EVAL-07 | Phase 4 | Pending |
| EVAL-08 | Phase 6 | Pending |
| EVAL-09 | Phase 6 | Pending |
| EVAL-10 | Phase 6 | Pending |
| MODEL-01 | Phase 5 | Pending |
| MODEL-02 | Phase 6 | Pending |
| MODEL-03 | Phase 6 | Pending |
| MODEL-04 | Phase 5 | Pending |
| MODEL-05 | Phase 6 | Pending |
| MODEL-06 | Phase 6 | Pending |
| MODEL-07 | Phase 6 | Pending |
| API-01 | Phase 5 | Pending |
| API-02 | Phase 5 | Pending |
| API-03 | Phase 5 | Pending |
| API-04 | Phase 5 | Pending |
| API-05 | Phase 5 | Pending |
| API-06 | Phase 5 | Pending |
| API-07 | Phase 5 | Pending |
| UI-01 | Phase 7 | Pending |
| UI-02 | Phase 7 | Pending |
| UI-03 | Phase 7 | Pending |
| UI-04 | Phase 7 | Pending |
| UI-05 | Phase 7 | Pending |
| UI-06 | Phase 7 | Pending |
| UI-07 | Phase 7 | Pending |
| UI-08 | Phase 7 | Pending |
| UI-09 | Phase 7 | Pending |
| DEPLOY-01 | Phase 5 | Pending |
| DEPLOY-02 | Phase 5 | Pending |
| DEPLOY-03 | Phase 8 | Pending |
| DEPLOY-04 | Phase 8 | Pending |
| DEPLOY-05 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 70 total
- Mapped to phases: 70
- Unmapped: 0 ✓

Note: DEPLOY-05 (figures at each phase's exit) is mapped to Phase 8 for the final audit; every phase's success criteria require its figures on exit.

---
*Requirements defined: 2026-11-01*
*Last updated: 2026-11-01 after roadmap creation*
