# Roadmap: Solar & Wind Energy Forecasting — Davanagere

## Overview

Fifteen days, solo, viva around 2026-11-16. The order of work protects the core value: rigorous, honest results come first and site polish comes last. Phase 1 probes the data (what the Open-Meteo archive actually holds, timestamp conventions, NASA sentinels) and locks decisions D1-D3, because those choices change the splits, the features and what baseline 3 means. Phases 2-3 turn raw weather into simulated solar and wind kW and check that simulation against real Kaggle plant data. Phase 4 builds the leakage-tested feature pipeline and the baseline leaderboard, so every later model result has a bar to beat. Phase 5 puts a walking skeleton online by Day 6: live Open-Meteo, then physics, then SQLite, then the API, then a minimal public page, serving baseline 3. LightGBM is added in the same phase. Phase 6 trains the deep models in the background on the GPU (time-boxed, TFT hard stop Day 11), then selects a model per target on validation and evaluates on test once. Phase 7 builds the full frontend in parallel against the API schemas frozen in Phases 2 and 5. Phase 8 covers reproducibility, the README, report figures and viva readiness, and keeps one buffer day.

**Day-1 user action (blocking):** download the Kaggle files (anikannal solar Plant 1/2, berkerisen wind `T1.csv`) into `data/raw/kaggle/`. Phase 3 validation cannot start without them.

**Cut order if behind schedule:** TFT, then LSTM tuning, then bias correction beyond linear, then About-page polish. **Never cut:** physics validation, baseline 3, leakage and parity tests, the honest leaderboard.

**Parallel tracks:** GPU training (Phase 6) runs in the background while Phase 7 frontend work proceeds against the frozen API schemas. Report figures are produced when each phase exits, not saved up for Phase 8.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundations & Data Acquisition** (Days 1-2) - Pinned GPU environment, config, cached NASA and Open-Meteo pulls, coverage probe, Kaggle files in place (completed 2026-11-02)
- [ ] **Phase 2: Alignment, Cleaning & Physics** (Days 2-3) - Canonical hourly UTC weather with verified timestamps, plus pvlib solar and power-curve wind simulation
- [ ] **Phase 3: Physics Validation Gate** (Days 3-4) - Simulated kW checked against real Kaggle plant data, with nRMSE and plots
- [ ] **Phase 4: Features, Splits, Baselines & Evaluation Harness** (Days 4-5) - Leakage-tested shared feature builder and a leaderboard with all three baselines
- [ ] **Phase 5: Walking Skeleton & LightGBM** (Days 5-6) - Baseline-3 forecasts served live end-to-end on a public URL; LightGBM trained and on the leaderboard
- [ ] **Phase 6: Deep Models, Selection & Final Evaluation** (Days 6-11) - Time-boxed LSTM and TFT, model selection on validation, test evaluated once, registry written
- [ ] **Phase 7: Frontend & Full Public Site** (Days 7-12, parallel) - Dashboard, performance and About pages live against the deployed backend, mobile-checked
- [ ] **Phase 8: Reproducibility, Report & Viva Readiness** (Days 12-15) - Fresh clone reproduces everything; README and report figures complete; buffer day

## Phase Details

### Phase 1: Foundations & Data Acquisition

**Goal**: The developer has a working GPU environment and every raw data source cached on disk, with coverage facts known well enough to lock decisions D1-D3 (lag source, training windows, baseline-3 definition)
**Depends on**: Nothing (first phase)
**Target**: Days 1-2
**Requirements**: SETUP-01, SETUP-02, SETUP-03, SETUP-04, SETUP-05, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):

  1. The developer can build the env with uv from pinned `pyproject.toml` + `uv.lock` (core = serve, `[train]` extra). `torch.cuda.is_available()` prints True, `pytest` passes from the repo root, and site and plant values load from `config/*.yaml` with nothing hard-coded
  2. NASA POWER hourly 2001-2025 is cached on disk. A second fetch run makes no network calls. The fetch log shows URL, status, rows and % missing per column, and no `-999` value survives parsing
  3. Open-Meteo Historical Forecast (GFS, 2021-03+), Previous Runs (GFS, 2024-01+, lead-matched), ERA5 archive (`models=era5`, 2001+) and the live forecast (GFS) (`past_days=7`, `forecast_days=4`) are cached, each with its URL and retrieval date
  4. `docs/data_notes.md` shows the coverage report: Open-Meteo availability per variable and per model, ERA5 start year, NASA latency. Decisions D1-D3 are recorded against it
  5. The Kaggle solar Plant 1/2 and wind `T1.csv` files are present in `data/raw/kaggle/` via `python -m swf kaggle` (kaggle CLI; token is a Day-1 user action)

**Plans**: 7 plans (6 waves)

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — uv/CUDA env + lock (STACK pins), `python -m swf` CLI contract, check-gpu, packaging/GPU/CLI tests (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-06-PLAN.md — config yamls + validated pydantic settings, paths, azimuth helper, shared test fixtures (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-02-PLAN.md — cached-fetch primitive (atomic, sidecar, retry, log), NASA fetcher + -999 parse, real NASA 2001-2025 pull (wave 3)
- [x] 01-04-PLAN.md — `swf kaggle` wrapper, file check, hard-stop helper, real Kaggle download (manual fallback checkpoint), Kaggle section in data_notes (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-03-PLAN.md — Open-Meteo ERA5/HF/PR/live fetchers for gfs_seamless (PR smoke + per-lead fallback), real pulls, live fixture (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-05-PLAN.md — coverage probe + eligibility rule, deterministic report tables (wave 5)

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 01-07-PLAN.md — integrity re-hash, AUTO-block writer, `swf coverage`, real run, D-06/D1-D3 (incl. D-19) record in docs/data_notes.md, phase gate (wave 6)

**Notes**: Network-bound, so start long NASA pulls in the background first. Research flag: probe the data empirically (Open-Meteo lead semantics, ERA5 start year, NASA per-variable timestamps). No separate research phase.

### Phase 2: Alignment, Cleaning & Physics

**Goal**: Every source becomes one canonical, clean hourly UTC weather table with verified timestamps, and the physics chain turns that table into solar and wind kW within physical bounds
**Depends on**: Phase 1
**Target**: Days 2-3
**Requirements**: ALIGN-01, ALIGN-02, ALIGN-03, ALIGN-04, ALIGN-05, ALIGN-06, PHYS-01, PHYS-02, PHYS-03, PHYS-04, PHYS-05, PHYS-06
**Success Criteria** (what must be TRUE):

  1. Each source adapter produces a `CANON_COLS` hourly UTC frame with a unit-tested offset. `docs/data_notes.md` records the sunrise-onset and diurnal-centroid check against clear-sky at the interval midpoint
  2. The cleaned table has a complete hourly index. Gaps of 3 h or less are filled (GHI via clear-sky index, never across sunrise or sunset), longer gaps stay NaN, clip counts are logged, and GHI is 0 wherever midpoint zenith exceeds 90°
  3. `docs/data_notes.md` contains the monthly NASA vs ERA5 table (bias, RMSE, correlation for GHI, RH, WS10M). The linear-correction decision is recorded, and if a correction is applied, the same function runs in training and serving
  4. A clear-sky-day PV run gives a physically sensible curve (zero at night, peak around 770 kW, never above the ~800 kW effective AC cap from `pdc0` = 833 kW). The wind chain gives kW from the config-driven power curve. All physics unit tests pass, including azimuth conversion and south-vs-north POA
  5. The constraint layer clamps every target output to the PRD §6 bounds, and a test proves it

**Plans**: TBD
**Notes**: Freeze the contracts by the end of Day 3-4 so frontend and model work can run in parallel: `CANON_COLS`, `FEATURE_SPEC` names, the long prediction format, the `registry.json` schema, and the API `schemas.py`.

### Phase 3: Physics Validation Gate

**Goal**: The simulated energy targets are shown to be credible against real plant data. This is the only defence of simulated labels at the viva
**Depends on**: Phase 2 (and SETUP-05 Kaggle files from Phase 1)
**Target**: Days 3-4
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04
**Success Criteria** (what must be TRUE):

  1. Kaggle solar data parses correctly (day-first dates, AC_POWER summed per timestamp, IRRADIATION units documented). Loss % is tuned within 8-20% on daytime rows
  2. The solar validation report shows daytime nRMSE against the ≤10% target, or a written justification if the target is missed
  3. The wind validation report shows nRMSE (empirical curve × availability vs `LV ActivePower`) against the ≤14% target, and it is no worse than the 13.0% manufacturer-curve reference
  4. Simulated-vs-actual scatter plots and `metrics.json` are in `reports/validation/`, ready for the report

**Plans**: TBD
**Notes**: Never cut. This phase is a gate, not a blocker: a written explanation of a miss is an acceptable result.

### Phase 4: Features, Splits, Baselines & Evaluation Harness

**Goal**: One causal feature pipeline serves training and serving. A provably leak-free split exists, and the leaderboard shows all three baselines for all five targets, so every ML claim has a bar
**Depends on**: Phase 3
**Target**: Days 4-5
**Requirements**: FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07
**Success Criteria** (what must be TRUE):

  1. `swf.features` builds lags, rolling stats, known-future covariates, solar geometry, cyclic calendar and direction sin/cos (no raw day-of-year), and every artifact stores the `FEATURE_SPEC` hash
  2. The truncation/perturbation leakage test and the train/serve parity test (committed raw Open-Meteo fixture) both pass in `pytest`
  3. Split date ranges are logged per D2: weather-only models train 2001-2023, covariate models 2021-04-2023 (GFS), val 2024, test 2025, with boundary origins purged
  4. `reports/evaluation/leaderboard.csv` lists persistence, climatology and baseline 3 for all five targets. Baseline 3 is scored on lead-matched Previous Runs with the stitched variant alongside, and solar is scored on daytime only
  5. The developer can view MAE, RMSE, nRMSE and skill broken down by horizon (1, 6, 24, 48, 72 h), season (monsoon vs dry) and target, all from the common long prediction format

**Plans**: TBD
**Notes**: Never cut baseline 3, the leakage and parity tests, or the leaderboard.

### Phase 5: Walking Skeleton & LightGBM

**Goal**: A public URL serves live baseline-3 forecasts for all five targets end-to-end (live Open-Meteo, physics, SQLite, FastAPI, minimal page) by Day 6, and LightGBM, the expected workhorse, is trained and scored against baseline 3
**Depends on**: Phase 4
**Target**: Days 5-6 (DEPLOY-02 milestone: Day 6)
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06, API-07, DEPLOY-01, DEPLOY-02, MODEL-01, MODEL-04
**Success Criteria** (what must be TRUE):

  1. Anyone can open the public URL and see a minimal page with the live 72 h baseline-3 forecast for all five targets. The backend runs as a torch-free Docker image and the frontend as a static build with a same-origin `/api` rewrite
  2. `/api/health`, `/api/forecast`, `/api/forecast/summary`, `/api/history`, `/api/metrics` and `/api/site` return valid Pydantic schemas with ISO-8601 UTC timestamps. `/api/forecast` responds in under 500 ms from cache, and the next-24 h summary uses IST day bounds
  3. After a restart with an empty disk, the cache rebuilds from the committed seed snapshot. Forecasts refresh hourly, on startup, and lazily when the cache is older than 60 min. With Open-Meteo unreachable, the API serves the cached forecast with `stale: true` and its age (tested)
  4. Serving dispatches per target through the registry with lazy imports, and the serving image contains no torch
  5. LightGBM direct multi-horizon models (fixed seeds, saved artifacts) appear on the validation leaderboard next to baseline 3, with sorted, clipped P10-P90 bands from validation residual quantiles

**Plans**: TBD
**UI hint**: yes
**Notes**: Research flag: re-check the Render Free RAM and sleep policy and the Vercel/Netlify rewrite behaviour on deploy day. Publish OpenAPI so Phase 7 can build against it.

### Phase 6: Deep Models, Selection & Final Evaluation

**Goal**: The full model ladder has been tried within its time box. Each target's serving model is chosen on validation and confirmed on test exactly once, and the probabilistic and seasonal results are reported honestly
**Depends on**: Phase 5
**Target**: Days 6-11 (LSTM stabilise by ~Day 10; TFT hard stop Day 11)
**Requirements**: MODEL-02, MODEL-03, MODEL-05, MODEL-06, MODEL-07, EVAL-08, EVAL-09, EVAL-10
**Success Criteria** (what must be TRUE):

  1. The LSTM/GRU seq2seq (168 h encoder, 72 h decoder, five targets jointly) has trained on the GPU and appears on the validation leaderboard, and it exports to ONNX. If it is unstable by ~Day 10, a minimal version is reported honestly
  2. TFT (darts) has produced P10/P50/P90 for the five targets, or it was stopped at the Day-11 hard stop and the attempt is written up with its training curves
  3. `evaluate --final` has run once on test. `models/deployed/registry.json` records the selected model, runtime, artifact, reason, test metrics, baseline-3 RMSE, band method, `feature_spec_hash`, split dates and git SHA for every target. Any target where no ML model beats baseline 3 deploys baseline 3
  4. `reports/evaluation/` contains P10-P90 coverage, interval width, pinball loss, a reliability diagram, the skill heatmap (target × horizon bucket × season), and the wind capacity-factor and monsoon-vs-dry breakdown
  5. Interpretability figures are saved: LightGBM gain importance, plus TFT variable-selection weights if TFT ran

**Plans**: TBD
**Notes**: First in the cut order: TFT, then LSTM tuning. Research flag YES: darts multi-target spike, TFT serving path (CPU torch on a 1 GB host, or precomputed forecasts), interpretability outputs. Record the TFT serving decision by Day 10-11. GPU training runs in the background while Phase 7 proceeds.

### Phase 7: Frontend & Full Public Site

**Goal**: A visitor on a phone or laptop can explore the 72 h forecast, see which model serves each target and how it scored, and read the methodology and attribution, all on the live public site
**Depends on**: Phase 5 (API schemas; can start against mocked JSON once the Phase 2 contracts freeze), Phase 6 (final registry and figures)
**Target**: Days 7-12 (parallel with Phase 6)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09
**Success Criteria** (what must be TRUE):

  1. The dashboard shows five synchronized 72 h panels (P50 line with a P10-P90 band), where hovering one panel highlights the same hour on all five, plus summary cards for tomorrow's solar kWh, wind kWh, peak hour and combined energy
  2. All times show in IST with "last updated". A stale warning appears when the API reports `stale: true`, and a "waking up" state covers backend cold starts
  3. T1 and T5 carry a visible "simulated energy" label, and every target has a model badge linking to the performance page
  4. The performance page shows the leaderboard, skill-vs-baseline bars, error by horizon, the skill heatmap and the validation scatters. The About page shows site and plant specs, the methodology diagram, the simulated-energy caveat, the wind capacity-factor story, and attribution for NASA POWER, Open-Meteo (CC BY 4.0) and Kaggle. The footer shows git SHA, data-through date and model version
  5. The full site works against the live backend serving the registry-selected models, and its layout holds at 375 px width

**Plans**: TBD
**UI hint**: yes
**Notes**: About-page polish is last in the cut order. Results and report take priority over site polish.

### Phase 8: Reproducibility, Report & Viva Readiness

**Goal**: Anyone can reproduce the results from a fresh clone, and every report figure and table exists, so the viva rests on solid, regenerable evidence
**Depends on**: Phase 6, Phase 7
**Target**: Days 12-15 (keep one buffer day before the viva around 2026-11-16)
**Requirements**: DEPLOY-03, DEPLOY-04, DEPLOY-05
**Success Criteria** (what must be TRUE):

  1. From a fresh clone, `make data`, `make train`, `make evaluate` and `make serve` (or CLI equivalents) reproduce the artifacts and a working site
  2. The README documents fresh-clone setup, commands, data sources and the deployed URL
  3. `reports/` holds every report-ready figure and table: validation scatters, leaderboard, skill charts, error by horizon, skill heatmap, probabilistic metrics, interpretability. `pytest` is green
  4. The live site loads from a phone and a fresh browser the day before the viva

**Plans**: TBD
**Notes**: DEPLOY-05 (figures at each phase's exit) is enforced in every phase's success criteria. This phase only consolidates and audits it.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 8, with 7 running in parallel with 6 (Days 7-12).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundations & Data Acquisition | 7/7 | Complete   | 2026-11-02 |
| 2. Alignment, Cleaning & Physics | 0/TBD | Not started | - |
| 3. Physics Validation Gate | 0/TBD | Not started | - |
| 4. Features, Splits, Baselines & Evaluation Harness | 0/TBD | Not started | - |
| 5. Walking Skeleton & LightGBM | 0/TBD | Not started | - |
| 6. Deep Models, Selection & Final Evaluation | 0/TBD | Not started | - |
| 7. Frontend & Full Public Site | 0/TBD | Not started | - |
| 8. Reproducibility, Report & Viva Readiness | 0/TBD | Not started | - |
