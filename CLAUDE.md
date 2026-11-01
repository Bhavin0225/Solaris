# Solar-Wind Forecast: project rules

- Spec: docs/PRD.md is the source of truth; .planning/research/SUMMARY.md errata override it where they conflict. Re-read the relevant PRD section before each phase.
- Weather data: call NASA POWER and Open-Meteo REST APIs directly with httpx. No wrapper libraries.
- Cache every raw API response under data/raw/; never re-download what exists.
- All timestamps are UTC internally. Convert to Asia/Kolkata only in the frontend.
- Time-based splits only. Never shuffle time-series data.
- Every model must be compared against baseline 3 (Open-Meteo + physics).
- Site/plant values come from config/*.yaml, never hard-coded.
- Run pytest before declaring any phase done.
- Kaggle files live in data/raw/kaggle/, fetched with `python -m swf kaggle` (kaggle CLI, token at ~/.kaggle/kaggle.json; manual download as fallback); stop and ask if they are missing.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Solar & Wind Energy Forecasting — Davanagere**

A publicly deployed web application that forecasts the next 72 hours (hourly) of five physically coupled targets for Davanagere, Karnataka: solar PV generation (kW), relative humidity (%), global horizontal irradiance (W/m²), 10 m wind speed (m/s), and wind turbine generation (kW). It is Bhavin's final-year project: the deliverables are the live site, a written report, slides, and a code walkthrough for the viva. Full technical spec lives in `docs/PRD.md` (source of truth).

**Core Value:** Rigorous, honest model results: a leaderboard showing whether ML beats the Open-Meteo + physics (NWP) baseline for each target, backed by physics simulation validated against real Kaggle plant data. If time runs out, the results and report figures must be solid even if the site is rough.

### Constraints

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
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Python runtime
| Technology | Version | Purpose | Why |
|---|---|---|---|
| Python | **3.12** (already installed, 3.12.10) | Everything | numpy 2.5.4 needs >=3.12; pvlib 0.16.1 / torch 2.15 / darts 0.48 all support it. Do not use 3.11 (numpy 2.5 won't install) or 3.14+ (ecosystem lag). Use the same 3.12 in the Docker image. |
### Data + physics
| Technology | Version | Purpose | Why |
|---|---|---|---|
| pandas | **>=3.0.6,<3.1** | Tables, UTC time index | pandas 3.1.0 shipped 2026-10-22 and is too new (pytorch-forecasting caps `<3.1`; a week of ecosystem exposure only). 3.0.6 smoke-tested with lightgbm 4.7.0 and pvlib 0.16.1. pandas 3 means copy-on-write and the default `str` dtype, so never rely on chained assignment. Fallback if something breaks: pandas 2.3.x. |
| numpy | 2.5.4 | Arrays | Pulled in automatically. |
| pyarrow | 26.0.0 | Parquet I/O | Required for `data/interim/*.parquet`. |
| pvlib | **0.16.1** (2026-09-26) | Solar position, clear-sky, Perez, Faiman, PVWatts | Current stable. See "pvlib API facts" below; the PRD has two errors. |
| scipy | latest (pvlib dep) | Interpolation of power curve | `np.interp` is enough for the curve; scipy only comes along as a dependency. |
| PyYAML | 6.0.3 | `config/*.yaml` | Config-driven site/plant per PRD. |
| pydantic | 2.14.2 | Config models + API schemas | FastAPI uses it already. Validate YAML into pydantic models so a bad config fails at load. |
### Modelling
| Technology | Version | Purpose | Why |
|---|---|---|---|
| lightgbm | **4.7.0** (2026-07-18) | Direct multi-horizon GBM, quantile objective | Stable. Windows wheel is 1 MB, Linux 3 MB, so it is free to ship. Use `objective="quantile"` if you want P10/P90 from LightGBM too. |
| scikit-learn | 1.9.1 | Metrics, scalers, `TimeSeriesSplit` | Standard. |
| torch | **2.15.0 +cu134** (local training) / **2.15.0 +cpu** (serving, if used) | LSTM/GRU seq2seq, TFT backend | Windows CUDA wheels for 2.15.0 exist for cu132 and cu134 (cp312, ~2.16 GB each). Install from the PyTorch index, not PyPI. PyPI's Windows wheel is a 126 MB CPU build. |
| **darts** | **0.48.1** (2026-10-16), install as `darts[torch]` | TFT (multi-target, quantile) | See the TFT decision below. |
| pytorch-lightning | >=2.6.6 (pulled by darts) | Trainer | darts 0.48 requires `>=2.6.6`. pytorch-forecasting's changelog says it excludes "compromised" lightning releases (it pins `!=2.6.2,!=2.6.3`). Pin `pytorch-lightning>=2.6.6` and don't downgrade. |
| onnxruntime | 1.31.1 (14 MB Win / 23 MB Linux wheel) | CPU serving of LSTM/GRU, only if the deep model wins | Avoids shipping torch (see Deployment). |
### Backend
| Technology | Version | Purpose | Why |
|---|---|---|---|
| FastAPI | **0.162.0** | REST API | Current. Pydantic v2 native. |
| Uvicorn | **0.54.0** | ASGI server | Run **one worker only**. With several workers each one starts its own scheduler and refreshes duplicate. |
| APScheduler | **3.11.3** (2026-06-28) | Hourly refresh job | Use the **3.x** `BackgroundScheduler`, started in the FastAPI `lifespan`. APScheduler 4.0.0a1-a6 are still alphas on PyPI. Do not use them. |
| httpx | **0.28.1** | NASA/Open-Meteo REST | Latest stable (1.0 is only dev builds). Plain sync `httpx.Client` is fine for the fetchers. |
| tenacity | 9.2.1 | Retry/backoff on 429/5xx | `httpx.HTTPTransport(retries=n)` retries connection errors only, not 429/5xx. Use tenacity (a 3-line decorator) rather than hand-rolling backoff. |
| SQLite via stdlib `sqlite3` | n/a | Forecast cache | Use plain `sqlite3`, `PRAGMA journal_mode=WAL`, one short-lived connection per call, sync (`def`) endpoints. No SQLAlchemy, no aiosqlite: one table, two writers (scheduler plus startup), a handful of readers. SQLAlchemy 2.1 would be a dependency for zero benefit. |
| pytest | 9.2.0 | Tests | Per PRD section 13. |
| ruff | 0.17.3 | Lint/format | One tool. |
### Frontend
| Technology | Version | Purpose | Why |
|---|---|---|---|
| Vite | **8.3.5** (Node ^20.19 or >=22.12; you have 24.16) | Build | Current. |
| React / React DOM | 19.3.1 | UI | Current. |
| TypeScript | **~7.0.2** (what the create-vite template pins) | Types | TS 7 is `latest` on npm. Caveat: `typescript-eslint` 8.72 peers `typescript <6.1`, so skip typescript-eslint. The template now ships **oxlint** instead, so use that. |
| @vitejs/plugin-react | 6.1.2 (peer `vite ^8`) | React transform | Matches Vite 8. |
| Tailwind CSS | **4.3.3** + `@tailwindcss/vite` 4.3.3 | Styling | **Yes, v4.** Use the Vite plugin (peer supports Vite 5-8): `@import "tailwindcss";` in the CSS and **no `tailwind.config.js`, no PostCSS config**. Tutorials showing `tailwind.config.js` or `@tailwind base` are v3 and will mislead. |
| **Recharts** | **3.10.1** | Time-series panels | See the chart decision below. |
| @tanstack/react-query | 5.105.1 | Fetch + cache + polling | `refetchInterval` plus stale-state handling for free. |
| react-router-dom | 7.18.5 | 3 pages | Fine. Could be skipped for 3 tabs in `useState`, but routing gives shareable `/performance` URLs for the examiner. |
| vitest | 5.0.5 | Optional | Needs Node >=22.12. Low priority; the PRD's tests are Python. |
### Infrastructure / Deployment
| Target | Role | Free-tier facts (read from vendor docs 2026-11-01) | Verdict |
|---|---|---|---|
| **Render Free web service** | Backend (Docker) | 750 instance-hours/month; spins down after 15 min idle, about 1 min cold start; **ephemeral filesystem** (SQLite lost on every restart/spin-down); no persistent disk; RAM not stated on the docs page (historically 512 MB, **LOW** confidence) | **Recommended backend**, but only for a torch-free image. |
| Railway Free | Backend alternative | $1 credit/month; 0.5 GB RAM, 1 vCPU; image limit 4 GB. One-time Trial: $5, 1 GB RAM, 2 vCPU | Fallback. Credit burns out in days if the service runs 24/7. |
| Fly.io | Backend alternative | **No free tier**; 2 h / 7 day trial; `shared-cpu-1x` 512 MB about $3.69/mo, 1 GB about $6.70/mo | Cheapest always-on option if you accept about $4-7/month. |
| Hugging Face Spaces | -- | Docker Spaces now **require a paid plan**; only Static Spaces are free | **Do not plan on it.** (Older advice about free 16 GB Docker Spaces is outdated.) |
| Vercel / Netlify | Frontend (static `dist/`) | Not re-verified today (MEDIUM, widely known): free static hosting, env var `VITE_API_URL` at build time | Pick either. Vercel Hobby is non-commercial; fine for a student project. |
- Torch CPU on Linux is a 210 MB wheel (about 0.7 GB installed) and about 300-400 MB RSS once imported. That is borderline on a 512 MB free instance and pointless if LightGBM wins the target (PRD section 9.4 allows that).
- Image contents: FastAPI, uvicorn, APScheduler, httpx, pandas, pyarrow, pvlib, lightgbm, onnxruntime (only if needed). About 400-500 MB, well under Railway's 4 GB cap.
- If a deep model wins a target: export the LSTM/GRU with `torch.onnx.export` and serve with onnxruntime. **darts TFT has no first-class ONNX export.** If TFT wins, serve it with CPU torch (needs a 1 GB+ host, i.e. Fly 1 GB at about $6.70/mo or Railway trial) or precompute its forecasts in a scheduled job. Decide this at the end of the model phase, not before.
- Free-tier survival design (mandatory): (1) the app must **rebuild the SQLite cache on startup** (filesystem is wiped), (2) run a refresh on boot and also lazily on request when the cache is older than 60 min, because APScheduler does not run while the instance is asleep, (3) optionally ping `/api/health` every 10 min from an external cron (cron-job.org or UptimeRobot) before the viva. 24h x 31d = 744 h fits the 750 h cap for a single service.
- Commit the model artifacts and `registry.json` to the repo (LightGBM files are MBs). No git-LFS needed.
## Decisions on the questions asked
### TFT library: **darts 0.48.1** (not pytorch-forecasting)
| | darts 0.48.1 | pytorch-forecasting 1.8.0 |
|---|---|---|
| Maintenance | Very active; last commit 2026-10-30, releases monthly (0.47.0 on 09-04, 0.48.0 on 10-15, 0.48.1 on 10-16) | Active; last commit 2026-10-31, but releases are slower (1.7.0 on 04-05, 1.8.0 on 06-24), with a **v2 beta in flux** alongside v1 |
| Multi-target | Native: multivariate `TimeSeries` target, one model | Possible only via `MultiLoss([...])` plus lists of normalisers; fiddly, easy to get wrong |
| Quantiles | `likelihood=QuantileRegression(quantiles=[0.1,0.5,0.9])` (the default for TFT). Docs example confirms it | `QuantileLoss`; multi-target means a `MultiLoss` of `QuantileLoss` |
| Known-future covariates | `future_covariates=`, required for TFT unless `add_relative_index` or `add_encoders` | `time_varying_known_reals` in `TimeSeriesDataSet` |
| Dependency pins | pandas >=2.2, pytorch-lightning >=2.6.6 | **pandas <3.1, lightning <2.7, scikit-base <1.1** (tight; will fight your env) |
| Verdict | **Use** | Do not use |
- `output_chunk_length=72` with 5 targets x 3 quantiles is fine on a 4060 (8 GB) at `hidden_size` about 64, batch 64-128. Do the TFT hyper-parameter search with at most 3-4 trials.
- The deep models' training window is limited by the known-future covariates (see Open-Meteo below, from 2017). Either train the TFT on 2017+ only, or train on 2001+ using NASA-derived values as stand-in covariates (train/serve skew). This is a design decision for the roadmap's modelling phase.
- Write the hand-coded LSTM/GRU in plain PyTorch (PRD says `pytorch`), not through darts, so the ONNX export is easy. Keep darts for TFT only.
### pvlib API facts (0.16.1, verified by introspection)
| Item | Actual API | Note |
|---|---|---|
| Transposition | `pvlib.irradiance.get_total_irradiance(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth, dni, ghi, dhi, dni_extra=None, airmass=None, albedo=0.25, surface_type=None, model='isotropic', model_perez='allsitescomposite1990', diffuse_components=False)` | Use `model='perez'`. **Perez needs `dni_extra` and `airmass`**: pass `irradiance.get_extra_radiation(times)` and `location.get_airmass(solar_position=sp)['airmass_relative']`, or it fails or returns NaN. Use `apparent_zenith`. Azimuth 180 = south in pvlib. |
| Cell temperature | `pvlib.temperature.faiman(poa_global, temp_air, wind_speed=1.0, u0=25.0, u1=6.84)` | Defaults are fine. Feed it WS10M (matches PRD T4 to T1 coupling). |
| DC | `pvlib.pvsystem.pvwatts_dc(effective_irradiance, temp_cell, pdc0, gamma_pdc, temp_ref=25.0, k=None, cap_adjustment=False)` | The old `g_poa_effective` keyword was **removed in 0.16.0**. Pass positionally or as `effective_irradiance=`. pdc0 is in W. |
| AC | **`pvlib.inverter.pvwatts(pdc, pdc0, eta_inv_nom=0.96, eta_inv_ref=0.9637)`** | **PRD says `pvwatts_ac`. That function does not exist in 0.16.1** (`hasattr(pvsystem, 'pvwatts_ac')` is False). Here `pdc0` is the inverter DC input limit and the AC clip is `eta_inv_nom * pdc0`. |
| Clear sky | `Location.get_clearsky(times, model='ineichen')` and `Location.get_solarposition(times)` | Pass `altitude=` (about 598 m) to `Location` so Ineichen uses it. |
| Deprecations to avoid | `Location.pytz` (0.15.2), `irradiance.king()` (0.16), `iotools.get_psm3` (removed) | None are in your chain. |
### Chart library: **Recharts 3.10.1**, not Plotly
- Sync: charts sharing the same `syncId` synchronise Tooltip and Brush events. `syncMethod="index"` (default) needs all charts to have equal-length data on the same ticks. That holds here: one shared 72-point hourly timestamp array for all 5 panels. Verified in the Recharts docs. Hover on one panel highlights the same hour on all five. HIGH confidence.
- P10-P90 band: `<Area dataKey="band" />` where each row carries `band: [p10, p90]` (Recharts supports range areas via a tuple dataKey), plus a `<Line dataKey="p50" />` on top. MEDIUM: standard Recharts pattern, not run today. Build one `ForecastPanel` component and map it over the 5 targets.
- Why not Plotly: bundle of 3-4 MB (plotly.js 4.2.0 requires Node >=22), awkward cross-subplot hover sync in React, heavy on phones. Plotly is only better for scatter/heatmap plots, and those validation scatters can be pre-rendered PNGs from matplotlib in `reports/validation/`, shown with `<img>`. Use that.
- The Model Performance page (bar chart, error-by-horizon line chart) also fits Recharts.
- Not recommended: uPlot (fast, but sync/band code is DIY) and ECharts 6.1 (excellent, but a second paradigm to learn in 15 days).
### NASA POWER hourly (verified live, API v2.10.3)
| Item | Result |
|---|---|
| Endpoint | `https://power.larc.nasa.gov/api/temporal/hourly/point` works with the PRD params |
| Earliest hourly date | **2001-01-01** (earlier start returns HTTP 422: "The data starts at 2001/01/01"). PRD "verify" resolved. |
| Latest | Data returned through 2026-11-01 (near-real-time); "most recent complete year" = 2025 for the project's splits, so train/val/test = 2001-2023 / 2024 / 2025 in the PRD's N-2/N-1/N scheme. |
| Params per call | Docs say **max 15**. A live 16-parameter call was accepted, so the limit isn't strictly enforced today. **Stay at <=15 anyway** (the PRD's 14 is fine). Don't rely on enforcement. |
| Date range | A 2-year range returned 17,520 hourly rows in one call (about 2 s for a 1-year, 2-param call, about 330 KB). The "one year per call" rule is a safe convention, not a hard limit. Keep it for cacheable per-year files. |
| Rate limits | Not stated on the hourly docs page. Keep sequential + 1 s sleep + backoff. |
| `time-standard=UTC` | Supported (alternative: LST, which is the default, so always pass UTC). |
| Missing sentinel | `header.fill_value = -999.0` confirmed. |
| Response shape | `properties.parameter.<NAME>.<YYYYMMDDHH> -> value`. Elevation in the response: 597 m. |
| Sources | Header lists `MERRA2` (plus `SYN1DEG`/`POWER` for the radiation fields). Resolution is coarse (MERRA-2 is 0.5 x 0.625 deg; CERES SYN1deg is 1 deg), which matters for the NASA vs Open-Meteo bias check in section 7.4. |
| Invalid names | `WS100M` rejected with HTTP 422. Stick to WS10M/WS50M. |
### Open-Meteo (verified live for the site)
| Item | Result |
|---|---|
| Historical Forecast API earliest date | **2017-01-01** at this site (all 14 requested variables present from 2017-01-01; 2016-07 all null). Docs: IFS HRES is available since 2017-01-01 (other models 2021-2022+). So covariates cover about 9 years, vs 25 for NASA. PRD "verify" resolved. |
| What it actually is | A **stitched** series of the first hours of each successive model run (best_match), not a fixed 1-72 h lead-time forecast. Docs also warn it is "not suitable for long time series due to model version changes." **Train/serve skew risk: training covariates are day-0/short-lead forecasts, while serving uses day 1-3 leads.** The Previous Runs API (data from 2024) gives fixed lead times. Flag for the modelling phase. |
| Variable names (all accepted, 72/72 non-null) | `shortwave_radiation, direct_normal_irradiance, diffuse_radiation, global_tilted_irradiance, temperature_2m, relative_humidity_2m, surface_pressure, cloud_cover, precipitation, wind_speed_10m, wind_speed_80m, wind_speed_120m, wind_direction_10m, wind_direction_80m`. PRD names are correct. |
| Archive (ERA5) API | **Also returned `wind_speed_80m` and `wind_speed_120m` for this site** (and `wind_speed_100m`, `global_tilted_irradiance`). The PRD claim that the archive offers only 100 m is wrong, or at least not true today. Use 80 m consistently in both sources. |
| GTI params | `tilt=15&azimuth=0`. Docs: azimuth 0 = South, -90 = East, 90 = West, +-180 = North. **pvlib is 180 = South. Keep one mapping function and unit-test it.** |
| Wind unit | `wind_speed_unit=ms` accepted. Always send `timezone=GMT`. |
| Forecast API | `past_days=7&forecast_days=3` returns hourly; 72 values per variable for a 3-day window. |
| Grid snap | Request returned lat 14.446 / lon 75.904 / elevation 598 m (snapped to its grid), a different cell than NASA's. Log both coordinates. |
| Free-tier limits | **<10,000 calls/day, 5,000/hour, 600/min, 300,000/month**; no uptime guarantee. |
| Terms | Free API is **non-commercial only**; data is **CC BY 4.0** (attribution required, indicate modifications). Server code is AGPLv3. Put "Weather data by Open-Meteo.com (CC BY 4.0)" and the NASA POWER credit on the About page and in the footer. A student viva demo is non-commercial. |
| Usage plan | Hourly refresh = 24 calls/day for serving, so limits are irrelevant at runtime. The one-time bulk history pull is a few dozen calls; cache per year to `data/raw/`. Open-Meteo's call weighting by variables x days is MEDIUM/unverified; chunk by year and sleep, and you stay far below the limits either way. |
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| TFT | darts 0.48.1 | pytorch-forecasting 1.8.0 | Multi-target via `MultiLoss` is fiddly, tight pins (pandas <3.1, lightning <2.7), v1/v2 split |
| TFT | darts | hand-written TFT | Not feasible in 15 days |
| Charts | Recharts 3 | Plotly 4.2 / react-plotly | 3-4 MB bundle, weak cross-panel hover sync, heavy on mobile |
| Charts | Recharts 3 | ECharts 6.1 / uPlot | Capable, but a new API to learn and DIY band/sync code |
| Scheduler | APScheduler 3.11.3 | APScheduler 4 alphas | Still alpha on PyPI |
| Scheduler | APScheduler (in-process) | external cron / GitHub Actions | Fine for production, but the PRD asks for APScheduler, and free hosts sleep anyway (use lazy refresh) |
| DB | stdlib sqlite3 | SQLAlchemy 2.1 + aiosqlite | One table, no migrations; extra layers burn days |
| HTTP | httpx 0.28.1 | requests | PRD names httpx; either works. httpx keeps one client with timeouts and is async-capable |
| Retry | tenacity | `HTTPTransport(retries=)` | Only retries connect errors, not 429/5xx |
| Weather wrappers | direct REST | `openmeteo-requests`, `nasa-power` wrappers | Banned by PRD G3 |
| Torch in prod | onnxruntime / LightGBM-only image | torch CPU in the image | RAM/image size on free hosts |
| Backend host | Render Free (or Railway / Fly $4-7) | Hugging Face Spaces | Docker Spaces no longer free |
| Pandas | 3.0.6 | 3.1.0 | Released 2026-10-22; pytorch-forecasting caps it; avoid early-adopter bugs |
| Tailwind | v4 + Vite plugin | v3 + PostCSS | Old tutorials only; v4 is current |
| ESLint | oxlint (template default) | typescript-eslint | Doesn't support TS 7 (`typescript <6.1`) |
## Installation
# --- Python (Windows, venv, Python 3.12) ---
# --- Serving image (requirements-serve.txt) -- NO torch, NO darts ---
# fastapi uvicorn apscheduler<4 httpx tenacity pandas<3.1 pyarrow pvlib lightgbm pyyaml pydantic
# + onnxruntime==1.31.1   (only if an LSTM/GRU wins a target)
# --- Frontend ---
## Sources
- PyPI JSON API (versions, release dates, `requires_python`, `requires_dist`) for pvlib, lightgbm, torch, darts, pytorch-forecasting, httpx, fastapi, uvicorn, apscheduler, pandas, numpy, onnxruntime, lightning, etc. (2026-11-01) - HIGH
- npm registry (`vite`, `react`, `tailwindcss`, `@tailwindcss/vite`, `recharts`, `typescript`, `typescript-eslint`, `create-vite`) and create-vite template-react-ts `package.json` (2026-11-01) - HIGH
- pvlib 0.16.1 installed and introspected locally; pvlib what's-new page https://pvlib-python.readthedocs.io/en/stable/whatsnew.html; Context7 `/pvlib/pvlib-python` - HIGH
- Context7 `/unit8co/darts` (TFTModel, QuantileRegression, GPU config); GitHub commit feeds and CHANGELOG of unit8co/darts and sktime/pytorch-forecasting - HIGH
- Recharts AreaChart API (`syncId`, `syncMethod`): https://recharts.github.io/en-US/api/AreaChart/ - HIGH
- NASA POWER hourly docs https://power.larc.nasa.gov/docs/services/api/temporal/hourly/ plus live API calls (v2.10.3) - HIGH
- Open-Meteo historical-forecast docs https://open-meteo.com/en/docs/historical-forecast-api, pricing https://open-meteo.com/en/pricing, terms https://open-meteo.com/en/terms, plus live calls per year 2016-2023 - HIGH
- Render https://render.com/docs/free; Railway https://docs.railway.com/reference/pricing/plans; Fly https://docs.fly.io/about/pricing; Hugging Face https://huggingface.co/docs/hub/spaces-overview - MEDIUM (free tiers change; re-check the day you deploy)
- PyTorch wheel index https://download.pytorch.org/whl/ (cu132/cu134/cpu builds for 2.15.0, sizes via Content-Length) - HIGH
- Vercel/Netlify free-tier details were not re-fetched - MEDIUM
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
