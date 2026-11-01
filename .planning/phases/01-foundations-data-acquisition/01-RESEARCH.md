# Phase 1: Foundations & Data Acquisition - Research

**Researched:** 2026-11-01
**Domain:** Reproducible uv/CUDA Python env, direct-REST data acquisition with verbatim on-disk cache (NASA POWER, Open-Meteo x4 APIs, Kaggle CLI), coverage probing that locks D1-D3
**Confidence:** HIGH for API coverage facts (measured live today against the project site) and uv recipe (lock/sync/export executed). MEDIUM for Kaggle auth behaviour and Open-Meteo rate weighting.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Environment & task runner
- **D-01:** Use **uv** for environment + lockfile (`pyproject.toml` + `uv.lock`). The CUDA torch wheel comes from the PyTorch CUDA index via uv sources/index config (cu134, fallback cu132), so darts never pulls the CPU wheel.
- **D-02:** Dependency split via **pyproject extras**: core deps = serving set (no torch/darts/matplotlib); `[train]` extra adds torch, darts, matplotlib, kaggle and other training-only deps. This satisfies SETUP-01's intent (separate train vs serve deps) without two requirements files; the serving Docker image installs core only. (An exported `requirements-serve.txt` may be generated from the lock if Docker needs it.)
- **D-03:** **Python 3.12** for dev and Docker.
- **D-04:** Task runner is a **Python CLI**: `python -m swf <command>` (e.g. `data`, `fetch nasa`, `fetch openmeteo`, `kaggle`, `coverage`; later `train`, `evaluate`, `serve`). Satisfies DEPLOY-03's "or CLI equivalents". No Makefile required (`make` isn't native on Windows).
- **D-05:** SETUP-02 check: a command or test asserts `torch.cuda.is_available()` is True and prints the device name.

#### NWP model choice
- **D-06:** **One Open-Meteo model everywhere** - training covariates, baseline 3, and the live site use the same model to avoid skew. A Day-1 probe compares candidates (**ECMWF IFS 0.25 deg preferred**, GFS, `best_match`) on Previous Runs coverage for 2024-2025 and on variable availability (80 m wind, GTI, radiation components). The winner and rationale are recorded in `docs/data_notes.md` and in config.
- **D-07:** **No extra comparison models** - archive only the chosen model.
- **D-08:** Previous Runs lead days **1, 2, 3** (`*_previous_day1..3`) for 2024-2025, covering the 72 h horizon.
- **D-09:** If the chosen model lacks 80 m wind, derive hub-height wind with the **same power-law alpha method as NASA** (10 m + nearest upper level, alpha clipped to [0.05, 0.40]). Phase 1 only needs to fetch the needed levels; the computation lives in Phase 2 physics.

#### Cache & storage layout
- **D-10:** Store raw responses as **verbatim JSON** plus a sidecar meta file (URL, params, retrieval UTC timestamp, HTTP status, row count, % missing). No parsing to parquet at fetch time; adapters do that in Phase 2.
- **D-11:** **One file per year** per API/model, e.g. `data/raw/nasa/{year}.json`, `data/raw/openmeteo/{api}/{model}/{year}.json`. Resumable.
- **D-12:** Never re-download an existing cached file **unless `--force`** is passed. Complete past years are immutable.
- **D-13:** The live forecast isn't archived as training data. Commit **1-2 raw live responses** under `tests/fixtures/` for the Phase 4 train/serve parity test.
- **D-14:** `data/` is git-ignored. NASA `-999` is converted to NaN at the parse boundary (DATA-03); the raw JSON stays verbatim.

#### Kaggle acquisition
- **D-15:** Download via the **kaggle CLI** (`python -m swf kaggle`), token at `~/.kaggle/kaggle.json` (never in the repo).
- **D-16:** On CLI or auth failure, **print manual browser download steps** (dataset URLs and the exact target folder). The target is `data/raw/kaggle/` either way.
- **D-17:** Commands that need Kaggle files (power-curve build, validation) **hard-stop with instructions** if the files are missing. Everything else runs.
- **D-18:** Phase 1 check: the expected files exist (Plant_1/2 Generation + Weather Sensor CSVs, `T1.csv`) and the row counts are plausible (`T1.csv` ~ 50,530 rows). Deeper schema/unit checks are in Phase 3.

#### Carried forward (project-level, not re-decided)
- httpx directly, no wrapper libraries; tenacity for retry/backoff on 429/5xx; NASA >=1 s spacing, <=15 params/call, one year per call, `time-standard=UTC`; Open-Meteo `timezone=GMT`, `wind_speed_unit=ms`.
- Live forecast call: `past_days=7`, `forecast_days=4` (slice now+1 h ... now+72 h downstream).
- D1 (lag source ERA5/past_days), D2 (dual windows; val 2024, test 2025), D3 (baseline 3 on lead-matched Previous Runs). Phase 1's coverage probe must **confirm or flag** each.
- All site/plant values come from config. No hard-coded coordinates.

### Claude's Discretion
- Exact CLI subcommand names and flags, the config schema shape (pydantic models), the logging format (structured logs per DATA-04), the coverage-report layout in `docs/data_notes.md`, and the module layout under `src/swf/` (follow ARCHITECTURE.md `swf.core` / `swf.fetch`).
- Chunk size per Open-Meteo API, if a one-year request exceeds response limits.

### Deferred Ideas (OUT OF SCOPE)
- Archiving our own live-forecast history going forward (useful for a future live forecast-vs-actual overlay, PROD-02). Not in v1.
- Multi-model NWP comparison figure. Not in v1.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01 | uv env from pinned `pyproject.toml` + `uv.lock`; core = serve set, `[train]` = training set | "uv recipe" below: lock executed (128 pkgs, 4.5 s), `uv export` of core is torch-free, `environments` restriction, explicit cu134 index |
| SETUP-02 | `torch.cuda.is_available()` True after install | cu134 wheel exists for cp312 win_amd64; driver 617.14 reports CUDA 13.4; scratch install result in "Environment Availability" |
| SETUP-03 | Site/plant values load from `config/site.yaml`, `config/plant.yaml` | pydantic `extra="forbid"` models, config skeleton, literal-grep test |
| SETUP-04 | `pytest` passes from repo root | Validation Architecture: markers, MockTransport, fixtures |
| SETUP-05 | Kaggle files present in `data/raw/kaggle/`, stop if missing | kaggle 2.2.5 behaviour (needs `six`, anonymous public download works, zip layout, row counts measured) |
| DATA-01 | NASA hourly 2001-2025 cached, >=1 s spacing, backoff | NASA probe: 14 params, 2.3 MB/yr, ~4 s/call, 422 below 2001, `fill_value=-999` |
| DATA-02 | Open-Meteo HF (2017+), PR (2024+), ERA5, live, cached with URL + date | Per-model coverage matrix, `models=era5` requirement, accepted range sizes, exact endpoints |
| DATA-03 | `-999` -> NaN before clipping/interpolation | Header `fill_value`; `ALLSKY_KT` is structurally -999 at night (~48%) |
| DATA-04 | Every fetch logs URL, status, rows, % missing per column | Sidecar schema; aggregate coverage from sidecars |
| DATA-05 | Coverage report in `docs/data_notes.md` | Coverage design + pre-measured expected values; D1-D3 verdicts |
</phase_requirements>

## Summary

All external sources were probed live today (about 45 small requests, no 429s). The headline: **the D-06 premise does not hold on the data.** ECMWF IFS 0.25 deg (the preferred model) has no history before 2024-02-03 in the Historical Forecast API and 2024-03-06 in Previous Runs, so it cannot supply 2017-2023 training covariates and it leaves ~66 days of the 2024 validation year without lead-matched data. `best_match` is not a single model: in Previous Runs it equals ICON through 2025-09-30 and IFS HRES from 2025-10-01 (switches mid-test-year); in Historical Forecast it equals `ecmwf_ifs` (HRES 9 km). Under a strict "one model everywhere" rule the only eligible candidate is **`gfs_seamless`**: Historical Forecast from 2021-03-23, Previous Runs from 2024-01-19 (80 m wind from 2024-02-16), complete through 2025-12-31. This shrinks covariate-model training from the planned 2017-2023 to about 2021-04..2023-12 (~2.75 y). The alternative (IFS HRES for training/live with IFS 0.25 for lead-matched eval) keeps 7 training years but mixes models. This is a user-visible trade-off and is flagged as Open Question 1; the plan must contain an explicit confirmation step.

Other probe results that change the plan: (a) the Open-Meteo archive default (`models` omitted) is ERA5 only until 2016-12-31 and ECMWF IFS analysis from 2017-01-01 - the fetcher **must send `models=era5`** or the 2001-2025 series has a silent regime break; (b) ERA5 (`models=era5`) has all 14 variables including `wind_speed_80m/120m` back to 2001 (and 1940) with 0% missing, but only ~5 days of latency, so serving lags must come from forecast `past_days` (D1 confirmed as stated); (c) NASA `ALLSKY_KT` is `-999` at every night hour (~48%/yr) so "no -999 survives parsing" must mean "converted to NaN", not "0% missing"; NASA met data lags ~2 days, irradiance ~2 months; (d) NASA timestamps are start-of-hour for GHI (centroid -0.455 h vs solar noon) and Open-Meteo radiation is end-of-hour (+0.472 h), a clean 1 h offset (Phase 2 formalises); NASA vs ERA5 2024 means already show GHI -5%, RH +3.3 pts, WS10M +34% (NASA higher), so ALIGN-06 will likely trigger; (e) `kaggle==2.2.5` crashes at import without `six` (undeclared dependency) and downloads public datasets without credentials; (f) the uv recipe (explicit cu134 index, `environments`, extras) was executed and locks in 4.5 s with darts' transitive torch pinned to `2.15.0+cu134`.

**Primary recommendation:** Build in this order: scaffold+config+CLI+tests -> shared cache/throttle/retry core -> NASA and `models=era5` pulls started in the background immediately (model-independent, ~10 min wall) -> run the probe -> user confirms the NWP model (default `gfs_seamless`) -> fetch Historical Forecast, Previous Runs, live for that model -> `coverage` writes the report and D1-D3 verdicts.

## Architectural Responsibility Map

Phase 1 is an offline Python pipeline stage (no browser/SSR tier). Tiers are mapped to the project's actual layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP fetch, retry, throttle | `swf.fetch` (offline pipeline) | - | Only module that talks to NASA/Open-Meteo; reused by serving for the live call |
| Raw cache + sidecar meta | Filesystem (`data/raw/`) | `swf.fetch.cache` | Verbatim JSON is the lineage record; Phase 2 adapters read it |
| Sentinel -> NaN, % missing | `swf.fetch` parse helper | Phase 2 adapters | DATA-03/04 live at the fetch/parse boundary; canonical frames are Phase 2 |
| Site/plant config + azimuth conversion | `swf.core` (shared) | serving image | Needed by fetch (GTI params) now and by physics/serving later; one tested function |
| Env/lock/dep split | `pyproject.toml` + `uv.lock` | Docker (core only) | Core = serving set; torch only via `[train]` |
| GPU check | CLI (`swf check-gpu`) + pytest | - | Train-env only; must skip cleanly in serve-only env |
| Kaggle acquisition | CLI wrapper over `kaggle` CLI | manual browser fallback | Offline, train-env only, never at runtime |
| Coverage report + D1-D3 | CLI (`probe`, `coverage`) | `docs/data_notes.md` | Derived from sidecars + a small live probe; auto-section markers keep hand-written decisions |

## Standard Stack

### Core (serving set, installed by default)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.x (pin `.python-version` = 3.12) | Runtime | D-03; Python 3.13 is also installed on this machine, so pin it |
| httpx | 0.28.1 | NASA/Open-Meteo REST | Project rule: direct httpx; `MockTransport` gives network-free tests [CITED: python-httpx docs] |
| tenacity | 9.2.1 | Retry/backoff on 429/5xx | Locked in STACK.md; do not hand-roll backoff |
| pydantic | 2.14.2 | Config models | Fail at load on bad YAML |
| PyYAML | 6.0.3 | `config/*.yaml` | `yaml.safe_load` only |
| pandas | >=3.0.6,<3.1 (resolved 3.0.6) | Coverage report tables | STACK.md pin |
| numpy | 2.5.4 (resolved) | Arrays | pandas dependency |
| pyarrow | 26.0.0 | Parquet (Phase 2+) | Declared now so the lock is stable |
| pvlib | 0.16.1 | Physics (Phase 2+) | Declared now: resolves cleanly with pandas 3.0.6 |
| lightgbm | 4.7.0 | Model (Phase 5) | Declared now |
| fastapi / uvicorn / APScheduler | 0.162.0 / 0.54.0 / >=3.11.3,<4 | Serving (Phase 5) | Declared now so the serving set in the lock is final (resolved set verified conflict-free) |

### Train extra (`[project.optional-dependencies] train`)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| torch | ==2.15.0 (`+cu134` from explicit index) | LSTM/GRU/TFT backend | Declared **directly** in the extra so `tool.uv.sources` pins it; darts' transitive torch then resolves to the same wheel (verified in lock) |
| darts[torch] | ==0.48.1 | TFT | Pulls pytorch-lightning 2.6.6 |
| kaggle | ==2.2.5 | Kaggle CLI | **Also add `six`** (undeclared import, crashes otherwise) |
| six | 1.17.0 | kaggle workaround | Remove when kaggle declares it |
| matplotlib | 3.11.2 | Plots | darts also requires it |
| scikit-learn | 1.9.1 | Metrics | |
| pytorch-lightning | >=2.6.6 | Trainer | Match STACK.md |

### Dev group (`[dependency-groups] dev`)
pytest 9.2.0, ruff 0.17.3 (uv syncs the `dev` group by default).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argparse (stdlib) | typer/click | argparse is enough for ~6 subcommands; no extra dependency in the serving image |
| `gfs_seamless` single model | IFS HRES (train+live) + IFS 0.25 (lead-matched eval) | 7 vs 2.75 training years and a stronger NWP baseline, but violates D-06 "one model" and the live site would run a model whose lead-matched archive does not exist |
| separate `requirements-serve.txt` | `uv export --no-dev --no-hashes --no-emit-project` from the lock | Export verified torch-free (50 lines); generate only when Docker needs it |

**Installation (dev machine, Windows):**
```bash
uv python pin 3.12
uv lock
uv sync --extra train          # exact sync; ALWAYS include --extra train or torch is removed
uv run python -m swf check-gpu
```

**Version verification:** versions above were read from PyPI JSON today and confirmed by `uv lock`/`uv export` (see "uv recipe"). `torch 2.15.0+cu134` wheels exist for cp312 `win_amd64` and `manylinux_2_28_x86_64` on `download.pytorch.org/whl/cu134` (and cu132) [VERIFIED: PyTorch index listing].

## Package Legitimacy Audit

slopcheck 0.x installed in a throwaway venv; every package scanned with `slopcheck scan --pkg pypi <name>` (the `install ... --json` form in the protocol is not supported by this slopcheck build).

| Package | Registry | Age / releases | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|----------------|-----------|-------------|-----------|-------------|
| httpx | PyPI | 77 releases | not checked | github.com/encode/httpx | [OK] | Approved |
| tenacity | PyPI | 62 releases | not checked | tenacity.readthedocs.io | [OK] | Approved |
| pyyaml | PyPI | 40 releases | not checked | github.com/yaml/pyyaml | [OK] | Approved |
| pydantic | PyPI | 210 releases | not checked | pydantic.dev | [OK] | Approved |
| pandas | PyPI | 120 releases | not checked | pandas.pydata.org | [OK] | Approved (pin <3.1) |
| pyarrow | PyPI | 66 releases | not checked | arrow.apache.org | [OK] | Approved |
| pvlib | PyPI | 76 releases | not checked | github.com/pvlib/pvlib-python | [OK] | Approved |
| lightgbm | PyPI | 38 releases | not checked | github.com/lightgbm-org/LightGBM | [OK] | Approved |
| fastapi | PyPI | 359 releases | not checked | fastapi.tiangolo.com | [OK] | Approved |
| uvicorn | PyPI | 204 releases | not checked | uvicorn.dev | [OK] | Approved |
| apscheduler | PyPI | 59 releases | not checked | apscheduler.readthedocs.io | [OK] | Approved (<4) |
| torch | PyPI + PyTorch index | 52 releases | not checked | pytorch.org | [OK] | Approved; CUDA wheel from `download.pytorch.org/whl/cu134` only |
| darts | PyPI | 59 releases | not checked | github.com/unit8co/darts | [OK] | Approved |
| pytorch-lightning | PyPI | 223 releases | not checked | github.com/Lightning-AI/pytorch-lightning | [OK] | Approved (>=2.6.6) |
| kaggle | PyPI | 93 releases | not checked | github.com/Kaggle/kaggle-cli | [OK] | Approved |
| six | PyPI | 29 releases | not checked | github.com/benjaminp/six | [OK] | Approved |
| matplotlib | PyPI | 143 releases | not checked | github.com/matplotlib/matplotlib | [OK] | Approved |
| scikit-learn | PyPI | 76 releases | not checked | scikit-learn.org | [OK] | Approved |
| pytest | PyPI | 193 releases | not checked | docs.pytest.org | [OK] | Approved |
| ruff | PyPI | 430 releases | not checked | github.com/astral-sh/ruff | [OK] | Approved |

**Packages removed ([SLOP]):** none. **Packages flagged ([SUS]):** none. `uv.lock` records hashes; npm postinstall check not applicable (PyPI-only phase). `[ASSUMED]` tags are not needed: every name comes from the project's own STACK.md and resolved through `uv lock`.

## Architecture Patterns

### Data-flow diagram (acquisition)

```
 python -m swf data
   |
   +--> swf.core.settings --(config/site.yaml, plant.yaml)--> lat/lon, years, nwp.model, GTI tilt/azimuth
   |
   +--> fetch plan (per source, per year) ---> cache check (data/raw/.../{year}.json + .meta.json exist?)
   |         |                                      |-- yes and not --force --> log "cache hit", NO network
   |         |                                      `-- no --> Throttle(min_interval) --> httpx.Client.get
   |         |                                                    |-- 429/5xx/transport error --> tenacity backoff (<=6 tries)
   |         |                                                    |-- 4xx other (422 etc.) --> fail loudly, no retry
   |         |                                                    `-- 200 --> write response BYTES to .tmp
   |         |                                                              --> count rows / % missing (sentinel-aware)
   |         |                                                              --> write sidecar --> os.replace (json last = commit marker)
   |         v
   |   NASA  /api/temporal/hourly/point        (2001..2025, 25 files, 14 params, time-standard=UTC)
   |   OM    archive  models=era5               (2001..2025, 25 files, 14 vars)           } model-independent: start first
   |   OM    historical_forecast  models=<nwp>  (start-year..2025)
   |   OM    previous_runs        models=<nwp>  (2024, 2025; 14 vars x day1..3 = 42)
   |   OM    forecast             models=<nwp>  (live, past_days=7, forecast_days=4, 1 file)
   |
   +--> python -m swf kaggle --> `kaggle datasets download` x2 --> unzip into data/raw/kaggle/ --> row-count check --> hard-stop text if missing
   |
   +--> python -m swf probe --> small windows per candidate model --> data/interim/coverage_probe.json (+ tiny raw under data/raw/openmeteo/_probe/)
   `--> python -m swf coverage --> reads sidecars + probe json (offline) --> rewrites AUTO block in docs/data_notes.md
```

### Recommended Project Structure
```
pyproject.toml            # core deps, [project.optional-dependencies].train, [dependency-groups].dev, [tool.uv*], [tool.pytest.ini_options]
uv.lock  .python-version  # 3.12
config/{site.yaml, plant.yaml}
src/swf/
  __init__.py  __main__.py            # `python -m swf` -> cli.main()
  cli.py                              # argparse subcommands: check-gpu, fetch {nasa,openmeteo}, kaggle, probe, coverage, data
  core/{settings.py, geometry.py, paths.py, logging.py}   # pydantic config; to_openmeteo_azimuth(); repo-root paths; key=value/JSON logging
  fetch/{cache.py, http.py, nasa.py, openmeteo.py, kaggle.py, parse.py}
  coverage/{probe.py, report.py}      # probe (network) vs report (offline)
tests/{conftest.py, fixtures/, test_*.py}
docs/data_notes.md                    # hand-written sections + <!-- BEGIN/END AUTO:coverage --> block
data/                                 # git-ignored (add .gitignore entry in plan 1)
```
Keep `fetch` free of pandas imports at module load (serving reuses the live-forecast client); `coverage/` and `parse.py` may use pandas.

### Pattern 1: one cached-fetch primitive for every source
**What:** a single `fetch_to_cache(client, throttle, url, params, dest, *, force, summarize)` used by all five fetchers. Writes `resp.content` bytes (verbatim - never `json.dump(resp.json())`), then the sidecar, then `os.replace`s both from `.tmp`. The sidecar is the commit marker: a cache hit means *both* files exist.
**Sidecar fields (D-10, DATA-04):** `url` (full, with params), `params`, `retrieved_utc`, `http_status`, `bytes`, `sha256`, `rows`, `pct_missing` (per column), `columns`, `api_version`/`fill_value` (NASA), response `latitude/longitude/elevation` (Open-Meteo snap, NASA geometry), `swf_version`, `force` flag.
**Logging:** one structured line per fetch from the same dict (`logger.info("fetch %s", json.dumps(summary))`) plus cache-hit lines. Coverage reads sidecars, not logs.

### Pattern 2: fetchers take an injected `httpx.Client` and a `sleep` callable
Makes the "second run makes no network calls" success criterion testable (`MockTransport` call counter) and lets tests run backoff/throttle instantly.

### Pattern 3: probe (network) is separate from coverage (offline)
`probe` makes ~15 small requests and stores a derived JSON; `coverage` is a pure function of sidecars + probe JSON + fixtures, so the report is reproducible and unit-testable offline.

### Anti-Patterns to Avoid
- **Omitting `models=` on the Open-Meteo archive** (silent ERA5 -> IFS switch at 2017-01-01).
- **Requesting `best_match`** for anything archived (model changes underneath; Previous Runs flips ICON -> IFS HRES on 2025-10-01).
- **Re-serialising JSON** (`json.dump(resp.json())`) - breaks "verbatim" and sha256 lineage.
- **`if path.exists()` as the cache test** - an interrupted write leaves a truncated file; require the sidecar and write via `.tmp` + `os.replace`.
- **`uv sync` without `--extra train` after a train install** - exact sync uninstalls torch.
- **`import kaggle` in the CLI process** - the module authenticates at import and prints a banner; always subprocess the `kaggle` console script.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry/backoff on 429/5xx | custom loop | `tenacity` (`retry_if_exception`, `wait_exponential`, `stop_after_attempt`) | `httpx` transport retries only connect errors |
| HTTP mocking in tests | monkeypatching `httpx.get` | `httpx.MockTransport` passed to `httpx.Client(transport=...)` | Counts calls; no extra dependency |
| Config validation | dict access + asserts | pydantic models (`extra="forbid"`) | Bad YAML fails at load |
| Serve requirements file | hand-maintained `requirements-serve.txt` | `uv export --no-dev --no-hashes --no-emit-project -o requirements-serve.txt` | Verified torch-free; cannot drift |
| Kaggle download | Kaggle REST client | `kaggle datasets download -d <slug> -p <dir> --unzip` | Handles zip, redirects, license |
| CLI | hand-parsed `sys.argv` | `argparse` subparsers | stdlib |
| Atomic writes | bare `open(..., "w")` | `.tmp` + `os.replace` (5 lines) | Interrupted 25-file pull must stay resumable |
| Solar-noon/centroid timestamp test | a custom ephemeris | Phase 2 uses pvlib; Phase 1 only records the preliminary numbers | pvlib is the project's solar position source |

**Key insight:** this phase has almost no algorithms; the risk is in silent data-semantics errors (model aliases, archive regime change, sentinels, timestamp labels), not in code volume. Spend effort on probes and assertions.

## uv recipe (executed in a scratch project; uv 0.11.8, Windows)

`uv lock` resolved 128 packages in 4.5 s; `uv sync --no-dev` (core only) installed in 30 s and `import torch` fails as intended; `uv export --no-dev --no-hashes --no-emit-project` produced a 50-line torch/darts/kaggle-free file. Resolved: pandas 3.0.6, numpy 2.5.4, pvlib 0.16.1, lightgbm 4.7.0, fastapi 0.162.0, uvicorn 0.54.0, apscheduler 3.11.3, tenacity 9.2.1, pydantic 2.14.2, scipy 1.18.1, torch 2.15.0+cu134, darts 0.48.1, pytorch-lightning 2.6.6, kaggle 2.2.5, scikit-learn 1.9.1, matplotlib 3.11.2, pytest 9.2.0, ruff 0.17.3. [VERIFIED: uv lock/sync/export run 2026-11-01]

```toml
# pyproject.toml (verified to lock)
[project]
name = "swf"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "pandas>=3.0.6,<3.1", "numpy", "pyarrow", "pyyaml", "pydantic",
  "httpx==0.28.1", "tenacity",
  "pvlib==0.16.1", "lightgbm==4.7.0",
  "fastapi==0.162.0", "uvicorn==0.54.0", "apscheduler>=3.11.3,<4",
]

[project.optional-dependencies]
train = [
  "torch==2.15.0", "darts[torch]==0.48.1", "pytorch-lightning>=2.6.6",
  "matplotlib", "scikit-learn", "kaggle==2.2.5", "six",   # six: kaggle 2.2.5 imports it but does not declare it
]

[dependency-groups]
dev = ["pytest>=9.2", "ruff"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[tool.hatch.build.targets.wheel]
packages = ["src/swf"]

[tool.uv]
# Without this, uv tries to resolve macOS too and fails (PyTorch has no CUDA wheels for macOS).
environments = ["sys_platform == 'win32'", "sys_platform == 'linux'"]
link-mode = "copy"   # uv cache is on C:, project on F:; avoids hardlink-fallback warnings (cross-volume)

[tool.uv.sources]
torch = [{ index = "pytorch-cu134", marker = "sys_platform == 'win32' or sys_platform == 'linux'" }]

[[tool.uv.index]]
name = "pytorch-cu134"
url = "https://download.pytorch.org/whl/cu134"
explicit = true     # only `torch` may come from here; everything else stays on PyPI
```
- **Fallback to cu132:** change the index name/URL only; both have cp312 win_amd64 and manylinux x86_64 wheels.
- **Lock behaviour:** one universal `uv.lock` covers Windows dev and Linux Docker. Docker installs core only (`uv sync --frozen --no-dev --no-install-project`, or `uv export` -> `pip install -r`), so the 2 GB torch wheel and the Linux `nvidia-*` packages never enter the image. The `[train]` extra on Linux would pull `nvidia-*` from PyPI; irrelevant for serving.
- **`tool.uv.sources` and transitive torch:** darts' `torch>=2.6.0` requirement resolved to `2.15.0+cu134` from the explicit index (single `torch` entry in the lock) because `torch` is also a direct dependency of the extra. Do not remove the direct `torch==2.15.0` entry. [VERIFIED: lock inspection] The uv PyTorch guide itself does not address transitive deps. [CITED: docs.astral.sh/uv/guides/integration/pytorch]
- **Commands:** `uv sync --extra train` = full dev env (exact). `uv run <cmd>` is *inexact* (does not remove extras already installed) [CITED: uv docs, sync.md "Handling of extraneous packages"], so `uv run pytest` after a train sync keeps torch; bare `uv sync` does not. Document `uv sync --extra train` as the only sync command in the README. CI/Docker check: `uv lock --check` and `uv sync --locked`.
- Python 3.13 is also installed here; `.python-version` + `requires-python <3.13` keeps uv on 3.12.10.

## Open-Meteo: verified API facts (site 14.4644 N, 75.9218 E; probes 2026-11-01)

Common params on every call: `latitude`, `longitude` (from config), `timezone=GMT`, `wind_speed_unit=ms`, `tilt=15`, `azimuth=<to_openmeteo_azimuth(180)=0>` (for `global_tilted_irradiance`), `hourly=<comma list>`, `start_date`/`end_date` (YYYY-MM-DD). Variables (14): `shortwave_radiation, direct_normal_irradiance, diffuse_radiation, global_tilted_irradiance, temperature_2m, relative_humidity_2m, surface_pressure, cloud_cover, precipitation, wind_speed_10m, wind_speed_80m, wind_speed_120m, wind_direction_10m, wind_direction_80m`. With a single `models=` value the response keys are the plain variable names (no model suffix).

| API | Endpoint | Model param | Notes |
|-----|----------|-------------|-------|
| Historical Forecast | `https://historical-forecast-api.open-meteo.com/v1/forecast` | `models=<m>` | Stitched first hours of successive runs [CITED: open-meteo.com/en/docs/historical-forecast-api]; a 9-year, 14-var request (6.5 MB, 32 s) was accepted; no range limit stated |
| Previous Runs | `https://previous-runs-api.open-meteo.com/v1/forecast` | `models=<m>` | Vars as `<var>_previous_day1..3`; **start_date/end_date work** (docs page does not mention them, probes used them); 2-year, 14-var request accepted (1.4 MB, 11-42 s); `_previous_dayN` = value predicted N x 24 h before valid time [CITED: previous-runs-api docs]; run init hour not documented |
| ERA5 archive | `https://archive-api.open-meteo.com/v1/archive` | **`models=era5` (required)** | 10-year request accepted; 1 year = 0.73 MB, ~5 s |
| Live forecast | `https://api.open-meteo.com/v1/forecast` | `models=<m>` | `past_days=7&forecast_days=4` -> 264 hourly rows, 2026-10-25T00:00 .. 2026-11-04T23:00, 0 nulls for gfs_seamless, ecmwf_ifs025, ecmwf_ifs, icon_seamless (22 KB) |

### Per-model coverage at this site (first non-null; day-2/3 Previous Runs start +1/+2 days later)
| Model | Historical Forecast | Previous Runs day1 (2024-2025) | Verdict |
|-------|---------------------|-------------------------------|---------|
| `ecmwf_ifs` (HRES 9 km; grid 14.446/75.904) | **2017-01-01**, 0% missing 2017-2025, all 14 vars | **2025-10-01** (cloud/ws10/wd10: 2025-01-02) - 87% missing | no lead-matched val/test |
| `ecmwf_ifs025` (grid 14.5/76.0) | rad 2024-03-05T08, wind80 2024-03-05T18, T/P/cloud/ws10 2024-02-03, RH 2024-02-28 | rad/wind80 **2024-03-06**, T 2024-02-04, RH 2024-02-29; no internal gaps; day3 rad 2024-03-08T23 | 66 days (18%) of 2024 lacks lead-matched data; no training history |
| `gfs_seamless` (grid 14.468/75.9375) | **2021-03-23** all 14 vars; only gap: precipitation 3.9% missing in 2022 | rad etc. **2024-01-19T12**, wind80/120 **2024-02-16T06**; day3 rad 2024-01-21T12, wind80 2024-02-18 | **eligible** |
| `icon_seamless` / `icon_global` (identical; grid 14.5/75.875) | 2022-11-16T08 | 2024-01-19T12, wind80 2024-02-16T12 | only 1.1 training years -> ineligible |
| `ecmwf_aifs025_single` | 2025-02-17 | 2025-02-18 | ineligible |
| `best_match` | identical values to `ecmwf_ifs` (checked 2019, 2022, 2024, 2025) | **= ICON through 2025-09-30, = IFS HRES from 2025-10-01** | unstable alias - never use for archive |

ERA5 archive: **default (no `models`) equals ERA5 for wind/shortwave through 2016 and equals `ecmwf_ifs` from 2017-01-01** (max abs difference vs `models=era5`: 0.0 in 2010 and 2016-06, 339 W/m2 and 3.7 m/s in 2017). `models=era5` -> grid 14.5/76.0, all 14 variables non-null from 2001-01-01 (and 1940-01-01), `wind_speed_80m/120m` included; 2025 full year 0% missing. Native ERA5 wind levels are 10 m and 100 m, so 80/120 m are presumably derived by Open-Meteo [ASSUMED]. `models=era5` latency ~5 days (last valid 2026-10-26 on 2026-11-01). `models=era5_land` has no radiation/80 m wind. Elevation reported = 598 m for every API/model (matches CONTEXT "~600 m").

Rate/weight: no 429 during ~45 requests including 2-year x 14-var calls, spaced 2-3 s. Free limits per STACK.md (600/min, 5,000/h, 10,000/day). Request weight scales with variables x days [ASSUMED from Open-Meteo convention, unverified]; the full Phase 1 pull totals ~60 requests of weight ~40-110, far under the daily cap. Use >=2 s spacing for Open-Meteo, >=1 s for NASA, and tenacity on 429.

### Previous Runs lead semantics (for D3 / Phase 4, record in data_notes)
`previous_dayN` is a fixed 24N h lead for each valid hour, so for horizon h the **conservative lead-matched mapping is h in 1-24 -> day1, 25-48 -> day2, 49-72 -> day3** (lead is never shorter than real serving lead). Origins are only valid from the day-3 start (GFS: 2024-01-21T12; with wind80: 2024-02-18). [ASSUMED design rule; confirm in Phase 4]

## NASA POWER: verified API facts
- Endpoint `https://power.larc.nasa.gov/api/temporal/hourly/point`; params `parameters` (14 names, accepted), `community=RE`, `latitude`, `longitude`, `start=YYYYMMDD`, `end=YYYYMMDD`, `format=JSON`, `time-standard=UTC`. API v2.10.3. [VERIFIED: live]
- One year: 2.26-2.27 MB, 3-4 s server time; 2024 has 8784 rows (leap), 2001 and 2025 8760. Keys are `YYYYMMDDHH` (no tz). Response `geometry.coordinates = [75.922, 14.464, 597.04]`; header `fill_value: -999.0`, `time_standard: UTC`, sources `SYN1DEG, MERRA2, POWER`. Units: irradiance `Wh/m^2`, `PS` in **kPa**, `PRECTOTCORR` mm/hour, `QV2M` g/kg.
- `start` before 2001-01-01 -> HTTP 422 with message "The data starts at 2001/01/01".
- **Sentinels:** 2001, 2024, 2025: every column 0 sentinels **except `ALLSKY_KT` (4207-4220/yr, i.e. every night hour)**. Parse by comparing to `header.fill_value`; flag KT's missingness as structural in the coverage report. Do not assert "0% missing" for KT.
- **Latency (as of 2026-11-01):** T2M/RH2M/WS10M/WS50M/PS valid through 2026-10-30T23 (~2 days); `ALLSKY_SFC_SW_DWN/DNI`, `CLRSKY` valid through 2026-08-31T23 (~2 months). Requesting a current partial year yields mostly sentinels; Phase 1 requests 2001-2025 only.
- **Timestamp convention (preliminary, 2024, clear days only):** daily GHI centroid (hour-label) minus solar noon: NASA **-0.455 h** (sd 0.07, n=145) -> label = start of the hour; Open-Meteo ERA5 shortwave **+0.472 h** (n=178) -> label = end of the hour. Hourly correlation NASA vs ERA5 peaks when ERA5 is shifted by -1 h: GHI 0.972 (vs 0.925 at 0), T2M 0.963 (vs 0.947), PS 0.970 (vs 0.946), RH2M 0.926 (vs 0.908), WS10M 0.814 (vs 0.807, weak). NASA first-light hour 0.90 UTC vs ERA5 1.85. So NASA T2M/RH/PS also behave as start-of-hour. Phase 2 (ALIGN-02) must still verify with pvlib at the interval midpoint. [VERIFIED: numpy script, solar noon from NOAA equation of time]
- **Preliminary NASA vs ERA5 (`models` default, 2024) bias:** mean GHI 213.3 vs 223.6 W/m2, RH 70.0 vs 66.7 %, WS10M 4.07 vs 3.03 m/s (NASA +34%). That probe used the *default* archive (IFS analysis in 2024), so redo the real table with `models=era5` in Phase 2; the direction (large WS10M bias) is a heads-up for ALIGN-06 and for the NASA-vs-OM skew.

## Kaggle CLI (kaggle 2.2.5, released 2026-10-22)
- Install: only via `[train]` extra; **add `six`** - `kaggle` 2.2.5 raises `ModuleNotFoundError: No module named 'six'` at startup in a clean venv. [VERIFIED: clean venv]
- Auth methods (docs): `kaggle auth login` (OAuth), env `KAGGLE_API_TOKEN`, file `~/.kaggle/access_token`, legacy `~/.kaggle/kaggle.json`. [CITED: github.com/Kaggle/kaggle-cli docs/README.md]
- Observed: with `HOME`/`USERPROFILE` pointed at an empty dir, **public dataset downloads still succeeded** (also with `KAGGLE_API_TOKEN=bogus`). Whether this machine has other Kaggle env vars is unknown (not inspected). Treat credentials as optional-but-supported; keep D-16's manual fallback. [VERIFIED once; MEDIUM]
- Command: `kaggle datasets download -d anikannal/solar-power-generation-data -p data/raw/kaggle --unzip -q` and `-d berkerisen/wind-turbine-scada-dataset`. Without `--unzip` the archive is `<slug>.zip` (`solar-power-generation-data.zip` 1.9 MB, `wind-turbine-scada-dataset.zip`). `--unzip` extracts flat into `-p` and deletes the zip. `-o/--force` overwrites. Both datasets go in the same `data/raw/kaggle/` folder with no name clashes.
- Files (measured data rows): `Plant_1_Generation_Data.csv` 68,778; `Plant_1_Weather_Sensor_Data.csv` 3,182; `Plant_2_Generation_Data.csv` 67,698; `Plant_2_Weather_Sensor_Data.csv` 3,259; `T1.csv` **50,530** (matches PRD/D-18). `T1.csv` header begins with a UTF-8 byte-order mark before `Date/Time` (read with `encoding="utf-8-sig"`); Plant 1 generation dates are `dd-mm-yyyy HH:MM` while the other three solar files are ISO `YYYY-MM-DD HH:MM:SS`. These are Phase 3 parsing notes; Phase 1 check = presence + row count within a tolerance (suggest +/-2%).
- Error surface: nonexistent/private slug -> stderr "You don't have access to this resource." and exit 1; success exit 0. `import kaggle` (also `python -m kaggle`) prints an "Authentication required" banner when no token exists, so call the `kaggle` console script via `subprocess.run([shutil.which("kaggle") or ..., "datasets", "download", ...], capture_output=True, text=True)` and judge success by exit code **and** presence of expected files. Treat any other outcome (missing executable, network error, exit != 0) as failure -> print the D-16 manual steps (URLs + exact target folder `data/raw/kaggle/`).

## Common Pitfalls

### Pitfall 1: D-06's preferred model has no training history
**What goes wrong:** picking `ecmwf_ifs025` leaves no 2017-2023 covariates and 66 days of 2024 un-scoreable. **Why:** Open-Meteo archives IFS 0.25 only from Feb-Mar 2024. **Avoid:** apply the deterministic eligibility rule in the Coverage section and get the user's confirmation. **Warning sign:** `coverage` shows HF first-valid >= 2024.

### Pitfall 2: `best_match` (or omitted `models`) changes the underlying model
**What goes wrong:** Previous Runs `best_match` is ICON until 2025-09-30 then IFS HRES; Historical Forecast `best_match` is IFS HRES; archive default flips ERA5 -> IFS analysis on 2017-01-01. **Avoid:** always send an explicit `models=`; validate `models` against an allow-list in code (`era5` for archive; the configured NWP model otherwise); record `models` in the sidecar. **Warning sign:** a step change in 2017 in NASA-vs-archive bias.

### Pitfall 3: `ALLSKY_KT` makes the DATA-03 assertion fail or lie
**What goes wrong:** a naive `assert pct_missing == 0` fails on KT (~48%), or someone "fixes" it by dropping the -999 rows and misaligns the index. **Avoid:** convert sentinel -> NaN for all columns, assert `min > -900` and `not (df == -999).any().any()` *after* conversion, and report per-column missing with KT marked structural (night). Optionally keep KT in the pull (cheap; PRD lists it) but nothing downstream should use it (PITFALLS m3).

### Pitfall 4: non-atomic or re-serialised cache files
**What goes wrong:** an interrupted pull leaves a half-written `2013.json` that later counts as "cached"; re-serialising reorders/rounds numbers. **Avoid:** write `.tmp`, sidecar last, `os.replace`; store `resp.content`; sha256 in sidecar; a `swf data --verify` (or the coverage step) re-hashes files against sidecars.

### Pitfall 5: `uv sync` removes torch; CPU torch sneaks in
**What goes wrong:** exact sync uninstalls the 2 GB CUDA wheel; or someone `pip install`s darts and gets the PyPI CPU torch. **Avoid:** single documented sync command; the GPU test **fails loudly** (not skips) when torch is installed but `cuda.is_available()` is False; use only `uv add/lock/sync`, never bare `pip install`.

### Pitfall 6: kaggle import side effects and missing `six`
See Kaggle section. Subprocess only; pin `six` in the extra; test the wrapper with a fake executable on PATH.

### Pitfall 7: timestamps without timezone in raw JSON
NASA keys (`2024010100`) and Open-Meteo times (`2024-01-01T00:00`) carry no tz. Phase 1's only parse helper must localise to UTC (`tz="UTC"`) immediately and assert it; never use naive indexes. NASA 2024 has 8784 rows - tests must not hard-code 8760.

### Pitfall 8: cross-volume uv cache and Python 3.13 coexistence
uv cache lives on C:, repo on F: -> hardlinks fall back to copy with a warning (`link-mode = "copy"` fixes it). Python 3.13 is installed; without `.python-version`/`requires-python <3.13` uv could pick it.

### Pitfall 9: probe responses violate "archive only the chosen model"
D-07 and CLAUDE.md ("cache every raw API response") pull in opposite directions for candidate-model probes. **Resolution:** probe windows are tiny, stored under `data/raw/openmeteo/_probe/` (git-ignored) and only the derived `coverage_probe.json` feeds the report; the training/eval archive contains the chosen model only.

### Pitfall 10: Open-Meteo GTI azimuth
`global_tilted_irradiance` needs `tilt` and `azimuth` (0 = south, -90 east, +90 west, +/-180 north) [CITED: previous-runs/forecast docs]. Phase 1 must already convert pvlib's 180 -> 0, so put `to_openmeteo_azimuth(az) = (az % 360) - 180` in `swf.core.geometry` with a unit test now (180->0, 90->-90, 270->90, 0->-180); PHYS-03 in Phase 2 re-uses it. [VERIFIED: arithmetic; parameter convention CITED]

## Code Examples

### Sentinel-aware NASA parse helper (DATA-03)
```python
# swf/fetch/parse.py - source: NASA response shape verified 2026-11-01
import json, numpy as np, pandas as pd

def nasa_to_frame(raw: bytes) -> pd.DataFrame:
    d = json.loads(raw)
    fill = d["header"]["fill_value"]                       # -999.0
    assert d["header"]["time_standard"] == "UTC"
    params = d["properties"]["parameter"]
    first = next(iter(params.values()))
    idx = pd.to_datetime(list(first), format="%Y%m%d%H", utc=True)
    df = pd.DataFrame({k: list(v.values()) for k, v in params.items()}, index=idx)
    df = df.mask(df == fill)                                # sentinel -> NaN BEFORE anything else
    assert not (df == fill).any().any() and (df.min() > -900).all()
    return df
```

### Cached fetch primitive with injectable client/sleep (sketch)
```python
import hashlib, json, os, time, httpx, tenacity
RETRY_STATUS = {429, 500, 502, 503, 504}

def _retryable(e: BaseException) -> bool:
    return isinstance(e, httpx.TransportError) or (
        isinstance(e, httpx.HTTPStatusError) and e.response.status_code in RETRY_STATUS)

def fetch_to_cache(client, url, params, dest, *, force=False, min_interval=1.0,
                   summarize, _sleep=time.sleep):
    meta_path = dest.with_suffix(".meta.json")
    if dest.exists() and meta_path.exists() and not force:
        return "hit"                                       # no network, no sleep
    @tenacity.retry(retry=tenacity.retry_if_exception(_retryable), reraise=True,
                    wait=tenacity.wait_exponential(multiplier=2, max=60),
                    stop=tenacity.stop_after_attempt(6), sleep=_sleep)
    def _get():
        r = client.get(url, params=params); r.raise_for_status(); return r
    r = _get()
    tmp = dest.with_suffix(".json.tmp"); tmp.write_bytes(r.content)      # verbatim bytes
    meta = {"url": str(r.request.url), "params": params, "http_status": r.status_code,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(r.content).hexdigest(), **summarize(r.content)}
    mtmp = meta_path.with_suffix(".tmp"); mtmp.write_text(json.dumps(meta, indent=2))
    os.replace(tmp, dest); os.replace(mtmp, meta_path)
    _sleep(min_interval)                                    # spacing only after a real call
    return "fetched"
```
Pass `tenacity`'s `sleep=` so tests inject a no-op; do not use `tenacity.nap` monkeypatching.

### Network-free test (httpx.MockTransport) [CITED: python-httpx docs]
```python
def test_second_run_makes_no_network_calls(tmp_path):
    calls = []
    def handler(req):
        calls.append(str(req.url)); return httpx.Response(200, content=FIXTURE_BYTES)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch_nasa_years(client, cfg, [2001, 2002], root=tmp_path, sleep=lambda s: None)
    n = len(calls)
    fetch_nasa_years(client, cfg, [2001, 2002], root=tmp_path, sleep=lambda s: None)
    assert len(calls) == n == 2
```

### Config skeleton (SETUP-03)
```yaml
# config/site.yaml
site: {name: Davanagere, latitude: 14.4644, longitude: 75.9218, display_timezone: Asia/Kolkata}
data:
  nasa: {start_year: 2001, end_year: 2025, community: RE, min_interval_s: 1.0,
         parameters: [ALLSKY_SFC_SW_DWN, ALLSKY_SFC_SW_DNI, ALLSKY_SFC_SW_DIFF, CLRSKY_SFC_SW_DWN, ALLSKY_KT,
                      T2M, RH2M, QV2M, WS10M, WS50M, WD10M, WD50M, PS, PRECTOTCORR]}
  openmeteo:
    nwp_model: gfs_seamless          # set after the Day-1 probe + user confirmation (see Open Question 1)
    era5_model: era5
    previous_day_leads: [1, 2, 3]
    min_interval_s: 2.0
    hourly: [shortwave_radiation, direct_normal_irradiance, diffuse_radiation, global_tilted_irradiance,
             temperature_2m, relative_humidity_2m, surface_pressure, cloud_cover, precipitation,
             wind_speed_10m, wind_speed_80m, wind_speed_120m, wind_direction_10m, wind_direction_80m]
    live: {past_days: 7, forecast_days: 4}
kaggle: {solar_slug: anikannal/solar-power-generation-data, wind_slug: berkerisen/wind-turbine-scada-dataset,
         expected: {T1.csv: 50530}}
# config/plant.yaml (excerpt): solar {dc_kwp: 1000, tilt: 15, azimuth_pvlib: 180, dc_ac_ratio: 1.2, eta_inv_nom: 0.96,
#   gamma_pdc: -0.004, loss_pct: 14}, wind {rated_kw: 3600, hub_height_m: 80, availability_loss: 0.035}
```

### Auto-section in `docs/data_notes.md`
Hand-written decisions (D1-D3, NWP choice, timestamp notes) sit outside `<!-- BEGIN AUTO:coverage -->` ... `<!-- END AUTO:coverage -->`; `python -m swf coverage` rewrites only that block (regex replace; create block if absent). Report sorted deterministically and stamped with the sidecars' latest `retrieved_utc` (not `now`), so re-running offline yields a byte-identical file.

### GPU check (D-05)
```python
def check_gpu() -> int:
    import torch
    if not torch.cuda.is_available():
        print(f"FAIL: torch {torch.__version__} (cuda build={torch.version.cuda}) cannot see a GPU"); return 1
    print(f"torch {torch.__version__} cuda {torch.version.cuda} device {torch.cuda.get_device_name(0)}"); return 0
```

## Coverage report design (DATA-05) and decision rule

`python -m swf probe` (network, ~15 requests, >=3 s apart) then `python -m swf coverage` (offline). Computed content:

1. **Grid/elevation table:** requested vs snapped lat/lon/elevation per API x model (from sidecars/probe) - record elevation 598 m; NASA 597.04 m.
2. **NASA:** per-year x per-parameter % missing (KT flagged structural), rows per year (leap-aware), min/max sanity, data-through per family (tail probe `start=today-60d`): met ~2 d, irradiance ~2 mo.
3. **ERA5 (`models=era5`):** earliest date (probe window 1940 and 2001), per-variable first-valid, per-year % missing, `wind_speed_80m` availability by year, data-through (~5 d).
4. **Historical Forecast per candidate:** first-valid per variable (probe `2016-01-01..2025-12-31`, 4 key vars: `shortwave_radiation, wind_speed_80m, relative_humidity_2m, temperature_2m`), per-year % missing for the chosen model (from the real files).
5. **Previous Runs per candidate x lead day x variable:** first-valid (probe `2024-01-01..2025-12-31`; day1 for all 14 vars, day2/day3 for the 4 key vars + GTI), % missing in 2024 and 2025 separately, and share of the 2024 validation year covered.
6. **Eligibility + winner** (deterministic, encoded and unit-tested against a recorded probe fixture):
   (a) Previous Runs day1 first-valid <= 2024-02-28 for all non-wind80 variables; (b) wind80 first-valid <= 2024-03-01; (c) Historical Forecast first-valid <= 2021-12-31 (>= 2 full years before 2024); (d) not an alias (`best_match`, `*_seamless` allowed only if its resolved models are constant - verified by the alias test below). Measured outcome: only `gfs_seamless` passes.
   *Alias test (optional, 2 requests):* compare `best_match` vs candidate over a week per year; report equality segments (this is how the ICON/IFS switch was found).
7. **D1-D3 verdict block (hand-written text citing the auto numbers):**
   - **D1 confirmed:** ERA5 (`models=era5`) complete 2001-2025 for all 14 variables incl. 80 m wind; ERA5 latency ~5 d so serving history must be the forecast API `past_days` (analysis-like hours of the chosen model). Skew to be measured in Phase 4.
   - **D2 flagged (changes with model choice):** weather-only models train 2001-2023; covariate models train from the chosen model's HF start (gfs_seamless: 2021-03-23 -> use 2021-04-01..2023-12-31, ~2.75 y; IFS HRES alternative: 2017-01-01). Val 2024 / test 2025 hold. Lead-matched val origins start ~2024-01-22 (T5: ~2024-02-19); test fully covered.
   - **D3 confirmed with gap:** baseline 3 = chosen model Previous Runs day1-3 (conservative h->day mapping), stitched HF variant alongside; report the val gaps explicitly.
8. **Timestamp preliminary note** (numbers above) marked "to be verified in Phase 2".

## Plan decomposition hint (Days 1-2)

| Plan | Scope | Requirements |
|------|-------|--------------|
| 01 scaffold | pyproject/uv.lock/.python-version, src layout, `__main__`/argparse skeleton, `config/*.yaml` + pydantic settings, `to_openmeteo_azimuth`, `.gitignore` (`data/`, `.env`, Kaggle tokens), pytest config + first tests, `check-gpu`, `uv sync --extra train` on the dev machine | SETUP-01..04 |
| 02 fetch core + NASA | cache/sidecar/throttle/retry primitive, NASA fetcher + parse helper, tests; **then launch the NASA pull** | DATA-01, 03, 04 |
| 03 Open-Meteo | HF / PR / ERA5 / live fetchers with allow-listed `models`, committed live fixtures (1-2 files), tests; **launch ERA5 pull immediately** | DATA-02 |
| 04 Kaggle | `swf kaggle` wrapper + presence/row-count check + hard-stop helper + tests with fake executable | SETUP-05 |
| 05 probe + coverage + decisions | probe, coverage report, eligibility rule, `docs/data_notes.md`, **checkpoint:decision for NWP model**, then pulls for HF/PR/live | DATA-05 (+ closes DATA-02) |

Plans 02-04 are independent after 01 (parallelisable). Total fetch wall time: NASA 25 x (~4 s + 1 s) ~ 2 min; ERA5 25 x (~5 s + 2 s) ~ 3 min; HF 5 files + PR 2 files + live ~ 2 min. Disk: ~100 MB.

## Runtime State Inventory
Not applicable (greenfield, not a rename/refactor/migration phase).

## State of the Art

| Old assumption (PRD/research) | Current fact (probed 2026-11-01) | Impact |
|-------------------------------|-----------------------------------|--------|
| IFS 0.25 deg is a viable single model | HF from 2024-02-03, PR from 2024-03-06 | D-06 outcome changes (Open Question 1) |
| Archive default is "ERA5" | Default = ERA5 pre-2017, IFS analysis from 2017 | Must pass `models=era5` |
| `best_match` is a model | PR: ICON -> IFS HRES on 2025-10-01 | Exclude alias |
| Historical Forecast starts 2022 (docs) | `ecmwf_ifs`/`best_match` from 2017-01-01; gfs 2021-03-23; icon 2022-11-16 | Already in SUMMARY errata (2017); now per model |
| kaggle needs a token | public datasets download anonymously (CLI 2.2.5) | Fewer Day-1 blockers; keep manual fallback |
| `requirements-serve.txt` hand-maintained | `uv export` from the lock | One source of truth |

**Deprecated/outdated:** `~/.kaggle/kaggle.json` is now the "legacy" credential file (OAuth / `KAGGLE_API_TOKEN` / `~/.kaggle/access_token` preferred) [CITED: Kaggle CLI docs]; D-15's wording still works.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Open-Meteo ERA5 80/120 m wind is derived from native 10/100 m levels | Open-Meteo facts | Physics hub-height method choice in Phase 2 (low) |
| A2 | Open-Meteo request weight = variables x days convention | Open-Meteo facts | Pull could hit per-minute cap if spacing too low (mitigated by tenacity + 2 s spacing) |
| A3 | Conservative lead mapping h 1-24 -> day1, 25-48 -> day2, 49-72 -> day3 | Previous Runs semantics | Baseline-3 bar slightly pessimistic/optimistic (Phase 4 decision) |
| A4 | Kaggle anonymous download works on the user's machine for the same reason as in the probe (no hidden creds) | Kaggle | If wrong, `swf kaggle` falls back to manual steps (handled by D-16) |
| A5 | Eligibility thresholds (PR day1 <= 2024-02-28, HF <= 2021-12-31) are the right bar | Coverage decision rule | Different thresholds could admit ecmwf_ifs025 (user may prefer IFS quality) |
| A6 | GFS quality over India is acceptable as the single NWP for baseline 3 | Open Question 1 | Weak baseline 3 makes "ML beats baseline" less meaningful; user decision |

## Open Questions (RESOLVED)

1. **Which single NWP model? (needs user confirmation before the HF/PR/live pulls)**
   - Known: strict D-06 + the probe rule select `gfs_seamless` (train covariates ~2.75 y, lead-matched val from 2024-01-22, test complete). IFS 0.25 fails on history; IFS HRES has 7 training years but no lead-matched val/test; ICON has 1.1 training years.
   - Unclear: whether the user prefers (i) GFS everywhere (consistent, weaker NWP, shorter training), or (ii) IFS HRES (`ecmwf_ifs`) for training + live and IFS 0.25 for lead-matched baseline-3 eval (stronger NWP, 7 y, but two models and a live model with no lead-matched archive).
   - Recommendation: default to (i); plan a `checkpoint:decision` after `coverage` runs; record the choice and rationale in `docs/data_notes.md` and `config/site.yaml: data.openmeteo.nwp_model`. Fetching ERA5 and NASA does not depend on it.
   - **RESOLVED (2026-11-01):** user chose (i) `gfs_seamless` everywhere — see 01-CONTEXT.md D-06 (revised). No checkpoint needed.
2. **Does the live site need the same model as Previous Runs eval?** Yes under D-06; with (i) live uses `models=gfs_seamless` (verified 264 rows, 0 nulls).
   - **RESOLVED:** yes; live uses `models=gfs_seamless` (D-06).
3. **Kaggle token:** appears unnecessary for these two public datasets with CLI 2.2.5; confirm once on the dev machine (`python -m swf kaggle`), else fall back to manual steps.
   - **RESOLVED:** try kaggle CLI anonymously first; on failure use the D-16 manual path. Outcome recorded in 01-04-SUMMARY.
4. **GTI in the archive and HF at tilt 15/azimuth 0:** available everywhere probed; Open-Meteo GTI is only a sanity cross-check, not a physics input (STACK).
   - **RESOLVED:** GTI is a sanity cross-check only; no Phase 1 action beyond fetching it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | SETUP-01 | yes | 0.11.8 | pip + venv (loses lock) |
| Python 3.12 | D-03 | yes | 3.12.10 (3.13.12 also present) | `uv python install 3.12` |
| NVIDIA GPU + driver | SETUP-02 | yes | RTX 4060 Laptop 8 GB, driver 617.14 (CUDA 13.4) | cu132 index |
| CUDA torch wheel | SETUP-02 | yes (index) | 2.15.0+cu134 cp312 win_amd64 | cu132 |
| Network to power.larc.nasa.gov, open-meteo (4 hosts), download.pytorch.org, pypi.org, kaggle.com | all | yes | - | - |
| git | commits | yes | 2.55.0 | - |
| Docker | Phase 5 only | yes | 29.8.0 | - |
| Node | Phase 7 only | yes | 24.16.0 | - |
| kaggle CLI | SETUP-05 | not installed globally; comes with `[train]` | 2.2.5 | manual browser download (D-16) |
| Free disk | env + data | yes | F: 46 GB free; C: 131 GB (uv cache) | - |

**Scratch CUDA result (executed 2026-11-01, throwaway project with the pyproject above, `uv sync --extra train --no-dev`):** `torch 2.15.0+cu134`, `torch.version.cuda == 13.4`, `torch.cuda.is_available() == True`, device "NVIDIA GeForce RTX 4060 Laptop GPU", a 1000x1000 CUDA matmul ran, `darts 0.48.1` + `pytorch-lightning 2.6.6` import, and `kaggle --version` prints "Kaggle CLI 2.2.5" once `six` is installed. A harmless "triton not found" warning prints on Windows. The torch wheel is ~2.0 GiB, so the uv cache now holds it and the real install in plan 01 will be fast. [VERIFIED: executed]

**Missing dependencies with no fallback:** none. **With fallback:** kaggle CLI (manual download).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 (dev group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths=["tests"]`, `addopts="-q -m 'not network'"`, markers `network` (live APIs) and `gpu` |
| Quick run command | `uv run pytest -x -q` (network-free, <10 s; skips `gpu` if torch missing) |
| Full suite command | `uv run pytest -q && uv run python -m swf check-gpu && uv lock --check` |
| Live probes (manual, optional) | `uv run pytest -m network` (a couple of 1-day requests asserting response shape) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SETUP-01 | Lock is current; core export has no torch/darts/kaggle; extra pins cu134 | unit/smoke | `uv lock --check`; `pytest tests/test_packaging.py` (parses `pyproject.toml`/`uv.lock` with `tomllib`) | Wave 0 |
| SETUP-02 | CUDA visible, device name printed | gpu | `pytest -m gpu tests/test_gpu.py` and `python -m swf check-gpu` (exit 0) | Wave 0 |
| SETUP-03 | Config loads and validates; bad YAML rejected; no coordinate literals in `src/` | unit | `pytest tests/test_config.py` (includes grep for `14.4644`/`75.9218` in `src/**/*.py`) | Wave 0 |
| SETUP-04 | pytest runs from repo root | meta | `uv run pytest` from root passes | Wave 0 |
| SETUP-05 | Kaggle check: missing file -> hard-stop message with URLs/folder; present files with plausible rows -> OK; wrapper handles non-zero exit/missing exe | unit | `pytest tests/test_kaggle.py` (tmp_path CSVs, fake `kaggle` script) | Wave 0 |
| DATA-01 | 25 NASA files requested with correct params; spacing; 429->retry->success; 422 not retried; no network on 2nd run; `--force` refetches | unit (MockTransport) | `pytest tests/test_nasa_fetch.py` | Wave 0 |
| DATA-02 | HF/PR/ERA5/live URL + params correct (`models=era5`, `timezone=GMT`, `wind_speed_unit=ms`, `*_previous_day1..3`, `past_days=7&forecast_days=4`); `models` allow-list rejects `best_match`; sidecar has URL + retrieval date | unit | `pytest tests/test_openmeteo_fetch.py` | Wave 0 |
| DATA-03 | Sentinel -> NaN using header fill; KT night NaN; assert no -999 remains; UTC-aware index | unit | `pytest tests/test_parse.py` (fixture with a -999 row) | Wave 0 |
| DATA-04 | Sidecar contains url/status/rows/pct_missing per column; log line emitted | unit | `pytest tests/test_cache_meta.py` (caplog) | Wave 0 |
| DATA-05 | `coverage` is offline-deterministic (twice -> identical bytes), preserves hand-written sections, eligibility rule picks `gfs_seamless` from recorded probe fixture and rejects ifs025/ICON/best_match | unit | `pytest tests/test_coverage.py` | Wave 0 |
| (azimuth) | `to_openmeteo_azimuth` 180->0, 90->-90, 270->90, 0->-180 | unit | `pytest tests/test_geometry.py` | Wave 0 |
| (atomicity) | Truncated `.tmp` or missing sidecar is not a cache hit | unit | `pytest tests/test_cache_atomic.py` | Wave 0 |

Manual-only: placing/confirming Kaggle files on the dev box (`python -m swf kaggle`), user confirmation of the NWP model, and the real 2001-2025 pulls (verified by `python -m swf coverage` output, not by pytest).

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q`
- **Per wave merge:** `uv run pytest -q` plus `uv lock --check`
- **Phase gate:** full suite green + `python -m swf check-gpu` exit 0 + second `python -m swf fetch ...` run logs only cache hits + `docs/data_notes.md` AUTO block present before `/gsd:verify-work`

### Wave 0 Gaps (greenfield; everything is new)
- [ ] `tests/conftest.py` - `MockTransport` client factory, no-op `sleep`, `tmp_path` data root
- [ ] `tests/fixtures/` - `nasa_sample.json` (3 days x 3 params incl. a `-999` and header), `om_hf_sample.json`, `om_pr_sample.json`, `om_era5_sample.json`, `probe_summary.json` (recorded from today's numbers), plus the 1-2 real live responses (D-13, ~22 KB each, fetched with the real client during plan 03 and committed)
- [ ] test files listed above; framework install: `uv sync --extra train`

## Security Domain

`security_enforcement` is not disabled in config, so included (scope is small: offline fetch tooling).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no app auth); Kaggle token handled as a secret | token only in `~/.kaggle/` or env; never in repo/logs/sidecars |
| V3 Session Management | no | - |
| V4 Access Control | no | - |
| V5 Input Validation | yes | pydantic config validation; allow-list for `models` and API names; sanitise path components (`[a-z0-9_]+`) so config values cannot escape `data/raw/` |
| V6 Cryptography | no hand-rolled crypto | `hashlib.sha256` for lineage only; TLS verification left at httpx default (never `verify=False`) |
| V10/V14 Supply chain | yes | `uv.lock` with hashes; slopcheck [OK] on all 20 packages; explicit-index pin for torch so no dependency-confusion via the PyTorch index (`explicit = true`) |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via model/api name into cache path | Tampering | allow-list + regex on path parts; test |
| Secret leakage (Kaggle token, `.env`) into git or sidecar | Information disclosure | `.gitignore` (`.env`, `kaggle.json`, `access_token`, `data/`); sidecar stores params but never headers/env; do not log environment |
| Untrusted downloaded archives (Kaggle zip) | Tampering | Use `kaggle ... --unzip` into `data/raw/kaggle/` only; never execute anything from it; treat CSVs as data (Phase 3 parses) |
| Dependency confusion on `torch` | Tampering | `explicit = true` index + lock hashes |

## Project Constraints (from CLAUDE.md)
- Spec `docs/PRD.md` is source of truth; `.planning/research/SUMMARY.md` errata override it. This research adds errata (ERA5 `models=era5`, per-model coverage, `best_match` alias) - copy them into SUMMARY/data_notes.
- Weather data: call NASA POWER and Open-Meteo REST directly with httpx; **no wrapper libraries**.
- Cache every raw API response under `data/raw/` and never re-download what exists (-> `--force` only; probe responses under `data/raw/openmeteo/_probe/`).
- All timestamps UTC internally; Asia/Kolkata only in the frontend (config `display_timezone` is for the UI/API only).
- Time-based splits only; every model compared against baseline 3.
- Site/plant values from `config/*.yaml`, never hard-coded (including GTI tilt/azimuth, expected row counts, NASA years).
- Run `pytest` before declaring any phase done.
- Kaggle files live in `data/raw/kaggle/`; stop and ask if missing (D-16/D-17 refine this: try CLI, then manual steps, then hard-stop).
- Stack pins per `.planning/research/STACK.md`; Python 3.12; torch-free serving image; code at repo root.
- GSD workflow: file changes go through GSD commands.

## Sources

### Primary (HIGH confidence)
- Live probes against Open-Meteo (historical-forecast, previous-runs, archive, forecast), NASA POWER hourly, PyTorch index, PyPI JSON, run 2026-11-01 for lat 14.4644 / lon 75.9218 (all numbers in this document)
- `uv` 0.11.8 executed: `uv lock`, `uv sync --no-dev`, `uv sync --extra train`, `uv export` in a scratch project
- Context7 `/astral-sh/uv` and https://docs.astral.sh/uv/guides/integration/pytorch/ (explicit index, markers, extras/conflicts), uv concepts sync.md (exact vs inexact)
- https://open-meteo.com/en/docs/previous-runs-api (endpoint, `_previous_dayN` naming, "predicted N x 24 h before valid time", archived mostly from Jan 2024)
- https://open-meteo.com/en/docs/historical-forecast-api (endpoint, stitching, per-model availability table, IFS 0.25 since 2024-02-03)
- https://github.com/Kaggle/kaggle-cli (docs/README.md auth; docs/datasets.md download flags)

### Secondary (MEDIUM confidence)
- kaggle 2.2.5 behaviour observed once in a scratch venv (anonymous download, exit codes, missing `six`)
- slopcheck scan (installed from PyPI into a throwaway venv)

### Tertiary (LOW / ASSUMED)
- Open-Meteo request-weight convention; derivation of ERA5 80/120 m wind; conservative lead-mapping rule (Assumptions Log)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - resolved and installed via uv; versions match STACK.md
- Architecture: HIGH for fetch/cache design (derived from probes); MEDIUM for the NWP-model recommendation (data-driven, but a user trade-off)
- Pitfalls: HIGH for the ones reproduced live (ERA5 regime, best_match alias, KT sentinel, six); MEDIUM for Kaggle auth and rate weights

**Research date:** 2026-11-01
**Valid until:** ~7 days for Open-Meteo coverage (archive start dates and model lists change; re-run `swf probe` at pull time), 30 days for the uv/stack recipe
