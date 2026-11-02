# Solar & Wind Energy Forecasting — Davanagere

## What This Is

A publicly deployed web application that forecasts the next 72 hours (hourly) of five physically coupled targets for Davanagere, Karnataka: solar PV generation (kW), relative humidity (%), global horizontal irradiance (W/m²), 10 m wind speed (m/s), and wind turbine generation (kW). It is Bhavin's final-year project: the deliverables are the live site, a written report, slides, and a code walkthrough for the viva. Full technical spec lives in `docs/PRD.md` (source of truth).

## Core Value

Rigorous, honest model results: a leaderboard showing whether ML beats the Open-Meteo + physics (NWP) baseline for each target, backed by physics simulation validated against real Kaggle plant data. If time runs out, the results and report figures must be solid even if the site is rough.

## Requirements

### Validated

- ✓ Raw data acquisition: NASA POWER hourly 2001–2025, Open-Meteo ERA5 (`models=era5`) 2001–2025, GFS historical forecast 2021–2025, GFS previous runs (lead days 1–3) 2024–2025, live forecast, Kaggle solar + wind files — cached verbatim with sidecars, never re-fetched — Validated in Phase 1: Foundations & Data Acquisition
- ✓ uv + CUDA environment (torch 2.15.0+cu134 on RTX 4060), config-driven settings, `python -m swf` CLI, coverage report in `docs/data_notes.md` locking D1–D3 — Validated in Phase 1

### Active

- [ ] Verify timestamp conventions (NASA vs Open-Meteo) and compare NASA vs ERA5; document in `docs/data_notes.md`
- [ ] Clean weather into a complete hourly UTC table (gap interpolation ≤ 3 h, physical clipping, night GHI = 0)
- [ ] Simulate solar kW (pvlib, Perez, Faiman, PVWatts, clipping) and wind kW (empirical Kaggle power curve, hub-height extrapolation, air-density correction, availability loss) from config-driven plant specs
- [ ] Validate physics against Kaggle: solar nRMSE ≤ 10% (daytime, loss % tuned 8–20%), wind nRMSE ≤ 14%; save scatter plots + metrics
- [ ] Build features (lags, rolling stats, Open-Meteo known-future covariates, solar geometry, cyclic calendar, direction sin/cos, horizon) with chronological train/val/test splits and a leakage test
- [ ] Implement three baselines: persistence, climatology, NWP + physics
- [ ] Train LightGBM (direct multi-horizon), LSTM/GRU seq2seq (multivariate, 5 targets jointly), and TFT (P10/P50/P90)
- [ ] Evaluate MAE/RMSE/nRMSE/skill vs baseline 3 by horizon, season, target (solar on daytime only); write leaderboard + `models/registry.json` per §9.4 selection rule
- [ ] FastAPI backend with hourly APScheduler refresh, SQLite forecast cache, stale fallback, and endpoints: health, forecast, forecast/summary, history, metrics, site
- [ ] React + Vite + TS + Tailwind frontend: dashboard (5 synced panels with P10–P90 bands + summary cards), model performance page, about page with attribution and simulated-energy caveat; mobile-responsive; stale warning
- [ ] Public deployment (backend container + static frontend)
- [ ] Reproducible commands (`make data/train/evaluate/serve` or CLI), pytest suite per PRD §13, README
- [ ] Report-ready figures and tables in `reports/` (validation plots, leaderboard, skill charts, error by horizon)

### Out of Scope

- Multiple locations / location picker — v1 is Davanagere only; code stays location-agnostic via config for an easy v2
- Real-time SCADA integration — no physical plant exists
- Grid dispatch, pricing, financial modelling — not part of the forecasting question
- User accounts / authentication — public read-only demo
- Using Kaggle data as ML training targets — validation/calibration only (different sites)

## Context

- **Spec:** `docs/PRD.md` (AI-drafted v1.0, 1 Nov 2026). Values tagged *(verify)* must be checked against live API docs/data before relying on them.
- **Pre-project test (PRD Appendix A):** with one year of Kaggle wind data, ML did not beat persistence/physics; raw `day_of_year` hurt LightGBM. Motivates multi-year NASA history, cyclic encodings, and mandatory baseline 3 comparison.
- **Energy targets are simulated**, not measured (no public Davanagere plant data). Guide has accepted this given §7.3 validation. Caveat must appear in report and UI.
- **Davanagere is a weak wind site**: expect low capacity factor outside monsoon (Jun–Sep). Realistic finding, report honestly with seasonal breakdown.
- **Train/serve skew risk:** NASA (satellite/reanalysis) history vs Open-Meteo (NWP) live inputs; Open-Meteo historical-forecast API covers fewer years than NASA.
- **Kaggle files not yet downloaded** (anikannal solar Plant 1/2, berkerisen wind T1.csv). Must be placed manually in `data/raw/kaggle/` before the validation phase; stop and ask if missing.
- **Builder:** Bhavin, solo, strong in both Python ML and React. Local NVIDIA GPU available for PyTorch.
- **Deliverables:** live public site, written report, slides, code walkthrough.

## Constraints

- **Timeline**: ~15 days, viva around 2026-11-16 — full model ladder kept by user choice despite risk; results/report take priority over site polish if time slips
- **Data access**: NASA POWER and Open-Meteo called directly over HTTPS (httpx/requests), no wrapper libraries — PRD G3
- **API limits**: NASA hourly ≤ 15 parameters/call, one year per call, sequential with ≥ 1 s sleep; Open-Meteo free non-commercial terms — politeness and licensing
- **Time handling**: UTC everywhere internally, IST only in the UI — avoids alignment bugs
- **Splits**: strictly chronological, full annual cycles per split, never shuffle — prevents leakage
- **Config**: no hard-coded coordinates or plant specs; all from `config/*.yaml` — location-agnostic for v2
- **Tech stack**: Python 3.12, pandas 3.0.x, pvlib 0.16.1, LightGBM 4.7, plain PyTorch (LSTM/GRU), darts 0.48 (TFT), FastAPI + Uvicorn (1 worker) + APScheduler 3.x + stdlib sqlite3; React 19 + Vite 8 + TypeScript + Tailwind 4 + Recharts 3 — versions per `.planning/research/STACK.md`
- **Serving image**: torch-free (LightGBM / ONNX runtime only) — free hosts have ~512 MB RAM
- **Performance**: `/api/forecast` < 500 ms from cache
- **Hardware**: local NVIDIA GPU for deep models
- **Layout**: code at repo root (not a `solar-wind-forecast/` subfolder)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Deploy best model per target (§9.4), not necessarily a deep model | Guide accepts best-performing model; honest results over forced deep model | — Pending |
| Keep full ladder: LightGBM + LSTM + TFT | User choice; TFT gives interpretability + quantile bands | — Pending |
| Simulated energy (pvlib / power curve) as T1/T5 training targets | No public Davanagere plant data; guide accepted given Kaggle validation | — Pending |
| Public deployment required in v1 | Viva/examiner access | — Pending |
| If schedule slips, protect results/report over site polish | Core value is rigorous model evaluation | — Pending |
| Code at repo root, PRD moved to `docs/PRD.md` | Git root is this folder; matches PRD's CLAUDE.md reference | — Pending |
| Dual training window: weather-only 2001–2023, covariate models 2021-04–2023; val 2024, test 2025 | GFS archived forecasts start 2021-03; shared val/test keeps leaderboard fair | — Pending |
| Baseline 3 scored on lead-matched Previous Runs (stitched variant alongside) | Historical Forecast API is stitched short-lead data; would flatter baseline 3 | — Pending |
| Select models on validation, evaluate test once | Avoids test-set selection bias (refines PRD §9.4 "lowest test RMSE") | — Pending |
| Lag/rolling features from ERA5 (train) / Open-Meteo past_days (serve); NASA = target truth | NASA has no live feed; matches serving source | — Pending |
| Single NWP model = GFS (`gfs_seamless`) for covariates, baseline 3 and live site | Phase 1 probe: ECMWF IFS 0.25° lacks 2017–2023 history, IFS HRES lacks lead-matched 2024, best_match switches models; GFS is the only model covering train+val+test | — Pending |
| Model profile `adaptive` (Opus heavy, Sonnet balanced, Haiku light) | User asked for workload-based model assignment | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-02 after Phase 1 completion*
