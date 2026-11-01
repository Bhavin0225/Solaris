# Phase 1: Foundations & Data Acquisition - Context

**Gathered:** 2026-11-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a reproducible Python 3.12 GPU environment, the config skeleton (`config/site.yaml`, `config/plant.yaml`), a `python -m swf` CLI entry point, and fetchers that download and cache every raw data source verbatim:

- NASA POWER hourly 2001-01-01 → 2025-12-31
- Open-Meteo Historical Forecast (GFS, 2021-03-23+), Previous Runs (GFS, 2024-01-19+, lead days 1–3), ERA5 archive (`models=era5`, 2001+), and the live forecast (GFS)
- Kaggle solar Plant 1/2 + wind `T1.csv` (via kaggle CLI)

Ends with a coverage report in `docs/data_notes.md` that locks decisions D1–D3 (lag source, training windows, baseline-3 definition) and the single NWP model choice.

Out of this phase: parsing into canonical frames, timestamp alignment, cleaning (Phase 2); Kaggle schema/unit validation (Phase 3).

Requirements: SETUP-01..05, DATA-01..05.

</domain>

<decisions>
## Implementation Decisions

### Environment & task runner
- **D-01:** Use **uv** for environment + lockfile (`pyproject.toml` + `uv.lock`). The CUDA torch wheel comes from the PyTorch CUDA index via uv sources/index config (cu134, fallback cu132), so darts never pulls the CPU wheel.
- **D-02:** Dependency split via **pyproject extras**: core deps = serving set (no torch/darts/matplotlib); `[train]` extra adds torch, darts, matplotlib, kaggle and other training-only deps. This satisfies SETUP-01's intent (separate train vs serve deps) without two requirements files; the serving Docker image installs core only. (An exported `requirements-serve.txt` may be generated from the lock if Docker needs it.)
- **D-03:** **Python 3.12** for dev and Docker.
- **D-04:** Task runner is a **Python CLI**: `python -m swf <command>` (e.g. `data`, `fetch nasa`, `fetch openmeteo`, `kaggle`, `coverage`; later `train`, `evaluate`, `serve`). Satisfies DEPLOY-03's "or CLI equivalents". No Makefile required (`make` isn't native on Windows).
- **D-05:** SETUP-02 check: a command or test asserts `torch.cuda.is_available()` is True and prints the device name.

### NWP model choice
- **D-06 (revised 2026-11-01 after research probe):** **One Open-Meteo model everywhere = GFS (`models=gfs_seamless`)** for training covariates, baseline 3, and the live site. The probe ruled out the alternatives:
  - ECMWF IFS 0.25° starts 2024-02 (Historical Forecast) and 2024-03-06 (Previous Runs), so it has no training history.
  - IFS HRES has Previous Runs only from 2025-10.
  - `best_match` silently switches models (ICON, then IFS).
  - GFS coverage: Historical Forecast from 2021-03-23; Previous Runs from 2024-01-19, with 80 m wind from 2024-02-16.
  - Consequence: covariate models train 2021-04 → 2023-12 (D2 updated). Model name lives in config.

  The coverage step still re-probes and records start dates in `docs/data_notes.md`, because Open-Meteo archive dates drift.
- **D-07:** **No extra comparison models** — archive only the chosen model.
- **D-08:** Previous Runs lead days **1, 2, 3** (`*_previous_day1..3`) for 2024–2025, covering the 72 h horizon.
- **D-19 (baseline-3 lead mapping, locked in Phase 1):** horizon h is scored with Previous Runs lead day ⌈h/24⌉: h 1–24 → `_previous_day1`, 25–48 → `_previous_day2`, 49–72 → `_previous_day3`. This is the conservative rule: each forecast is at least as old as the lead it claims, so baseline 3 is never flattered. Lead-matched eval origins start once day3 coverage exists (GFS ≈ 2024-01-21; 80 m wind ≈ 2024-02-18). Phase 4 implements it; Phase 1 records it in the D3 verdict.
- **D-09:** If the chosen model lacks 80 m wind, derive hub-height wind with the **same power-law α method as NASA** (10 m + nearest upper level, α clipped to [0.05, 0.40]). Phase 1 only needs to fetch the needed levels; the computation lives in Phase 2 physics.

### Cache & storage layout
- **D-10:** Store raw responses as **verbatim JSON** plus a sidecar meta file (URL, params, retrieval UTC timestamp, HTTP status, row count, % missing). No parsing to parquet at fetch time; adapters do that in Phase 2.
- **D-11:** **One file per year** per API/model, e.g. `data/raw/nasa/{year}.json`, `data/raw/openmeteo/{api}/{model}/{year}.json`. Resumable.
- **D-12:** Never re-download an existing cached file **unless `--force`** is passed. Complete past years are immutable.
- **D-13:** The live forecast isn't archived as training data. Commit **1–2 raw live responses** under `tests/fixtures/` for the Phase 4 train/serve parity test.
- **D-14:** `data/` is git-ignored. NASA `-999` is converted to NaN at the parse boundary (DATA-03); the raw JSON stays verbatim.

### Kaggle acquisition
- **D-15:** Download via the **kaggle CLI** (`python -m swf kaggle`), token at `~/.kaggle/kaggle.json` (never in the repo).
- **D-16:** On CLI or auth failure, **print manual browser download steps** (dataset URLs and the exact target folder). The target is `data/raw/kaggle/` either way.
- **D-17:** Commands that need Kaggle files (power-curve build, validation) **hard-stop with instructions** if the files are missing. Everything else runs.
- **D-18:** Phase 1 check: the expected files exist (Plant_1/2 Generation + Weather Sensor CSVs, `T1.csv`) and the row counts are plausible (`T1.csv` ≈ 50,530 rows). Deeper schema/unit checks are in Phase 3.

### Carried forward (project-level, not re-decided)
- httpx directly, no wrapper libraries; tenacity for retry/backoff on 429/5xx; NASA ≥1 s spacing, ≤15 params/call, one year per call, `time-standard=UTC`; Open-Meteo `timezone=GMT`, `wind_speed_unit=ms`.
- Live forecast call: `past_days=7`, `forecast_days=4` (slice now+1 h … now+72 h downstream).
- D1 (lag source ERA5/past_days), D2 (dual windows; val 2024, test 2025), D3 (baseline 3 on lead-matched Previous Runs). Phase 1's coverage probe must **confirm or flag** each.
- All site/plant values come from config. No hard-coded coordinates.

### Research facts the plan must honour (from 01-RESEARCH.md)
- ERA5 archive **must** be requested with `models=era5`. Without it, data from 2017 on silently switches to the IFS analysis. With it, all 14 variables, including 80 m and 120 m wind, are non-null from 2001.
- NASA `ALLSKY_KT` is -999 at every night hour (~48%). DATA-03 means "-999 converted to NaN", not "0% missing".
- kaggle 2.2.5 needs `six` (add it to the `[train]` extra). Call the `kaggle` console script via subprocess (`import kaggle` prints an auth banner). Use `--unzip` so files land flat in `data/raw/kaggle/`. Expected rows:
  - `T1.csv`: 50,530
  - Plant 1 generation: 68,778
  - Plant 1 weather: 3,182
  - Plant 2 generation: 67,698
  - Plant 2 weather: 3,259
- uv:
  - Run `uv sync --extra train` for dev. Bare `uv sync` removes torch.
  - Set `link-mode = "copy"`, since the uv cache is on C: and the repo is on F:.
  - The CUDA torch build comes from an explicit cu134 index.
- Previous Runs accepts `start_date`/`end_date`, and multi-year requests work. Per-year files (D-11) are a convention, not an API limit.

### Claude's Discretion
- Exact CLI subcommand names and flags, the config schema shape (pydantic models), the logging format (structured logs per DATA-04), the coverage-report layout in `docs/data_notes.md`, and the module layout under `src/swf/` (follow ARCHITECTURE.md `swf.core` / `swf.fetch`).
- Chunk size per Open-Meteo API, if a one-year request exceeds response limits.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec
- `docs/PRD.md` §4.1 (site), §5.1 (NASA POWER), §5.2 (Open-Meteo), §5.3 (Kaggle), §7.1 (pipeline stage paths), §12 (repo structure), §13 (non-functional), §14.1 (project rules)
- `.planning/REQUIREMENTS.md` — SETUP-01..05, DATA-01..05
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria
- `.planning/PROJECT.md` — Key Decisions table (D1–D3, selection rule, adaptive model profile)

### Research (errata override PRD)
- `.planning/research/SUMMARY.md` — Errata table (NASA start 2001, Historical Forecast 2017+, Previous Runs ~2024, `forecast_days=4`, ERA5 has 80 m wind), decisions D1–D6, Phase 1 delivers
- `.planning/research/STACK.md` — pinned versions, torch CUDA install order, Open-Meteo/NASA limits, kaggle
- `.planning/research/PITFALLS.md` — C1 (stitched forecasts), C3/M1 (UTC/timestamps), C6 (-999 sentinel), M6 (Windows torch), M9 (chunked cached pulls), C10 (schedule)
- `.planning/research/ARCHITECTURE.md` — `swf.core` / `swf.fetch` boundaries, cache keying, no parsing in fetch

### External docs
- NASA POWER hourly API: https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
- Open-Meteo Historical Forecast: https://open-meteo.com/en/docs/historical-forecast-api
- Open-Meteo Previous Runs: https://open-meteo.com/en/docs/previous-runs-api
- Open-Meteo ERA5 archive: https://open-meteo.com/en/docs/historical-weather-api
- Open-Meteo Forecast: https://open-meteo.com/en/docs
- Kaggle solar: https://www.kaggle.com/datasets/anikannal/solar-power-generation-data
- Kaggle wind: https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None. Greenfield repo (only `docs/PRD.md`, `.planning/`, `CLAUDE.md`).

### Established Patterns
- `CLAUDE.md` project rules: direct REST via httpx, cache raw under `data/raw/`, UTC internally, config from YAML, pytest before phase done, stop and ask if Kaggle files are missing.
- Code at repo root (`src/swf/`, `config/`, `tests/`, `frontend/` later), per PRD §12.

### Integration Points
- Phase 2 adapters read `data/raw/**/*.json` + meta sidecars.
- Phase 4 parity test reads `tests/fixtures/` live responses.
- Serving (Phase 5) reuses `swf.fetch` live-forecast client and `swf.core` config.

</code_context>

<specifics>
## Specific Ideas

- Coordinates 14.4644° N, 75.9218° E. Verify that Open-Meteo `elevation` in the response is ~600 m and record it.
- The coverage report should state: per-variable non-null start date for the Historical Forecast, Previous Runs availability per lead day for 2024–2025 for each candidate model, the ERA5 start year and 80 m wind availability, NASA data-through date, and the % missing per column per year.
- Start the long NASA/ERA5 pulls first; they're network-bound and can run in the background while the env and config are built.

</specifics>

<deferred>
## Deferred Ideas

- Archiving our own live-forecast history going forward (useful for a future live forecast-vs-actual overlay, PROD-02). Not in v1.
- Multi-model NWP comparison figure. Not in v1.

</deferred>

---

*Phase: 1-Foundations & Data Acquisition*
*Context gathered: 2026-11-01*
