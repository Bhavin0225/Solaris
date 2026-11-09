# Phase 7: Frontend & Full Local Site - Research

**Researched:** 2026-11-10
**Domain:** React 19 / Vite 8 dashboard over an existing FastAPI + SQLite backend; small read-only backend additions
**Confidence:** HIGH for backend facts and package versions (read from code, data files and npm). MEDIUM for chart and motion details (checked against Context7 docs, not run here).

## Summary

The backend already has six endpoints (`/api/health`, `/api/forecast`, `/api/forecast/summary`, `/api/history`, `/api/metrics`, `/api/site`). It serves `frontend/dist` through a `StaticFiles` mount added last. Everything the UI-SPEC still needs can come from data that is already on disk:
- **Weather:** the live Open-Meteo response is not kept in SQLite. It is cached as raw JSON at `data/raw/openmeteo/forecast/gfs_seamless/{run_time + 1 h:%Y%m%dT%H}.json` and already holds `temperature_2m`, `cloud_cover` and `precipitation`.
- **Correlation:** the history tables `data/interim/energy_sim.parquet` and `data/interim/weather_nasa.parquet` give a 5x5 correlation in 0.08 s.
- **Performance:** the `reports/evaluation/*.csv` files have every number the Performance page needs.
- **Footer:** `models/deployed/registry.json` has the model and version data.

So the backend work is five small read-only additions: weather, correlation, performance, build-info and figures, plus a `day=` parameter on the summary endpoint. Add one SPA-fallback fix as well. Without it, reloading `/performance` returns 404, because Starlette's `StaticFiles(html=True)` has no SPA fallback.

On the frontend, install seven npm packages on top of the Phase 5 template (all checked on npm today, all have React 19 / Vite 8 peers). Then build four routed pages from about 15 shared components. All the new code is client-side. Pure helper logic (condition rule, IST formatting, greeting, correlation sentences, day aggregation) can be unit-tested with **Node 24's built-in `node --test`** with zero new dependencies. Type stripping works here (checked live), and the tsconfig already sets `erasableSyntaxOnly` and `allowImportingTsExtensions`.

The biggest correctness trap: **forecast hours are UTC hour labels, so in IST every point sits at :30** (16:00Z = 21:30 IST). The UI-SPEC examples ("14:00", ticks "00/06/12/18", a midnight line) assume whole IST hours. Use a numeric time x-axis with ticks placed on IST 00:00/06:00/12:00/18:00 (epoch ms). The data points then fall between the ticks, and labels like "Peak solar hour" honestly read "12:30 IST".

**Primary recommendation:** Do the backend additions first, in one plan with pytest tests and `create_app` kwargs for every new path. Then the frontend shell, tokens and shared components. Then the pages (Energy, Performance, Weather, About). Verify with `npm run build` + `npm run lint` + `node --test` + pytest, plus Playwright MCP screenshots at 1440 px and 375 px against `python -m swf serve`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Visual reference (owner, 2026-11-09)
- **D-31:** Reference = owner's video `Arastoo___A_clean_and_premium_admin_dashboard_UI...(720p)~2.mp4` in the repo root (sharper copy of `WhatsApp Video 2026-11-09 at 11.31.27 PM.mp4`, 5.6 s, 720x1280 phone recording of a desktop "Admin Dashboard V2"). Owner wants the same look and feel ("that exact glossy finish").
  - Ocean/teal-to-blue blurred gradient background, brighter towards the right.
  - Floating rounded glass panels: darker blue glass sidebar, frosted top bar, one large frosted content panel; inside it pale frosted white-blue cards.
  - Left sidebar: logo block, grouped nav sections with small uppercase group labels, outline icons, count badges, active item = bright cyan pill.
  - Header: large bold greeting ("Good afternoon, ...") with a small grey subtitle; dark navy pill primary button plus a light secondary pill button on the right.
  - Cards: icon chip top-left, big bold number, small label, tiny grey sub-label, optional small coloured "+x%" badge top-right.
  - Charts: light sky-blue bars with the latest bar bright cyan and a value label; a segmented pill toggle (dark selected segment); donut with multi-colour segments and centre value; ring progress with centre %.
  - Motion: on page change the content panel blurs to an empty frosted state, then cards fade/slide in staggered, numbers count up, bars grow left to right, donut/ring fill. Sidebar hover highlight.
  - Typography: bold geometric sans for headings and numbers; small muted grey for subtitles. Outline icon set (Lucide-like).
- **D-32:** Copy the style, not the template's code, names or images. Drop admin-only elements: search bar, user avatar/name, "Invite an agent", Approve/Review buttons, property photo cards.

#### Pages (owner, 2026-11-09)
- **D-33 Energy (first page):** five cards, one per model output (solar kW `t1_kw`, wind kW `t5_kw`, sunlight `ghi`, humidity `rh`, wind speed `ws10`), each with current-hour P50, P10-P90 range and a small trend line; a 72 h chart with a 24h/48h/72h segmented toggle and a target switch (P50 line + P10-P90 band); summary cards (today/tomorrow solar kWh, wind kWh, peak hour, combined energy); a 5x5 correlation grid of the five targets (computed from historical data, static) placed below the chart with one-line explanations of the strong links. Greeting line shows "Davanagere" and a small temperature/condition chip labelled "from Open-Meteo".
- **D-34 Temperature is not a model target.** It must never look like a prediction: only as the small Open-Meteo chip on Energy and on the Weather page.
- **D-35 Weather page:** phone-weather-app style: condition icon (sunny / partly cloudy / cloudy / rain, a simple rule from cloud cover and precipitation), current temperature, hourly strip, 3 day cards with high/low. Cloud cover, rain and temperature come from Open-Meteo, labelled as such; humidity, sunlight and wind speed shown there are our model's forecasts and labelled as ours.
- **D-36 Performance page:** TFT vs baseline 3 skill per target, error by horizon, P10-P90 coverage with wind flagged as less reliable (coverage 0.66 ws10 / 0.68 t5_kw vs 0.80 nominal, D-30 limitation reported, not fixed), leaderboard, skill heatmap, validation scatters (roadmap criterion 4).
- **D-37 About page:** project, site and plant specs, methodology, simulated-energy caveat, wind capacity-factor story, attribution NASA POWER, Open-Meteo (CC BY 4.0), Kaggle. Footer: git SHA, data-through date, model version.

#### Theme and layout
- **D-38:** Default theme = the light glossy blue of the video. A Settings menu (gear icon in the top bar) holds a light/dark toggle; choice remembered in localStorage (wrapped in try/catch).
- **D-39:** Charts sit on more solid cards than the background glass so thin lines and bands stay readable.
- **D-40:** Phone (375 px): sidebar becomes a bottom navigation bar. All times IST, with "last updated" and the stale warning (roadmap criterion 2).
- **D-41:** Keep roadmap criteria: synchronized hover across the five target panels where five panels are shown, "simulated energy" label on t1_kw and t5_kw, model badge per target linking to Performance.

#### Stack
- **D-42:** React 19 + Vite 8 + TypeScript + Tailwind 4 (Vite plugin) + Recharts 3 + `motion` (formerly Framer Motion; import from `motion/react`) + lucide-react icons. @tanstack/react-query for fetch/polling, react-router-dom for page URLs (STACK.md).
- **D-43:** Backend additions allowed: a weather endpoint (hourly temperature, cloud cover, precipitation from the cached live Open-Meteo fetch), a correlation endpoint or static JSON, performance data (prob metrics, heatmap, wind CF) and a footer/build-info endpoint (git SHA, data-through, model from `models/deployed/registry.json`). Keep `swf.api` free of torch/darts imports.

### Claude's Discretion
- Exact component split, colour tokens, font choice (free close match), spacing, chart details.
- Skills to use (owner request): design-taste-frontend (dashboard mode), impeccable, ui-ux-pro-max (design-system), dataviz, apple-design for mobile, find-docs/context7 for Motion/Recharts/Tailwind 4 docs, Playwright side-by-side screenshots against the video, design-critique + accessibility-review at the end. Ask the owner before installing any new skill.

### Deferred Ideas (OUT OF SCOPE)
- Cloud deployment and cold-start "waking up" state (v2).
- Wind band recalibration (owner chose to report the limitation instead).
</user_constraints>

**UI-SPEC (`07-UI-SPEC.md`, approved) is the visual and interaction source of truth.** This research does not repeat its tokens. It only flags places where the data facts below force a change to it (see Pitfalls 1, 2 and 9).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Five synchronized 72 h panels, P50 + P10-P90 band, shared hover | Recharts 3 `syncId` + `syncMethod="index"` (Context7), range `Area` with `[p10,p90]` tuple dataKey (Context7 Area docs: "dataKey already returns [min, max] tuples"). Pattern 5, Pitfalls 1 and 6 |
| UI-02 | Tomorrow solar kWh, wind kWh, peak hour, combined energy | Existing `/api/forecast/summary` (`solar_kwh`, `wind_kwh`, `peak_hour`). Add `day=today\|tomorrow` (Pattern 2). Peak kW comes from the forecast points on the client; combined = solar + wind on the client |
| UI-03 | IST display, last updated, stale warning | `Forecast.stale`, `age_minutes`, `run_time`, `/api/health.last_success`. `Intl.DateTimeFormat` with `timeZone: display_timezone` and `hourCycle: 'h23'` (checked in Node 24). Pitfall 1 |
| UI-04 | "Simulated energy" on t1/t5 | Static `SimulatedTag` keyed on target |
| UI-05 | Model badge per target, linking to Performance | `/api/forecast` `targets[t].model` is the runtime string (`"tft"` for all 5 today). Map to display names. Hash scroll fix (Pitfall 7) |
| UI-06 | Leaderboard, skill bars, error by horizon, heatmap, validation PNGs | `/api/metrics` (leaderboard) + new `/api/performance` (coverage, breakdown, heatmap, wind_cf) + new `/api/figures/{name}` allowlist |
| UI-07 | About: specs, methodology, caveat, wind CF story, attribution | `/api/site` + `wind_cf` rows from `/api/performance` + `wind_cf.png` figure. Kaggle slugs live in `config/site.yaml` `kaggle:` (not exposed today; hard-code in the About copy or add to build-info, see Open Question 3) |
| UI-08 | Footer: git SHA, data-through, model version | New `/api/build`: `git rev-parse --short HEAD`, `registry.schema_version`, `registry.git_sha`, per-target runtime, `meta.run_time` |
| UI-09 | Works at 375 px | One `lg` breakpoint, bottom nav. Playwright MCP screenshot at 375x812 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- `docs/PRD.md` §11 Frontend is the spec. `.planning/research/SUMMARY.md` errata override it.
- All timestamps UTC internally. Convert to Asia/Kolkata **only in the frontend**. The API keeps returning `...Z` times (AwareDatetime). New endpoints must do the same (use `db.iso()`).
- Site/plant values come from `config/*.yaml`, never hard-coded. Read the timezone from the API's `display_timezone` and site facts from `/api/site`. Do not hard-code "Asia/Kolkata" or coordinates in TS.
- Every model compared against baseline 3. The Performance page shows the served model vs baseline 3.
- Run pytest before declaring the phase done.
- Weather APIs only via httpx directly. This phase makes **no new network calls**: the weather endpoint reads the cached live file.
- Cache raw API responses under `data/raw/`; never re-download. The weather endpoint reads that cache read-only.
- Tech stack pinned by STACK.md (React 19, Vite 8, TS ~7.0, Tailwind 4 Vite plugin, Recharts 3, oxlint not typescript-eslint).
- Uvicorn 1 worker (already in `swf/api/run.py`).
- GSD workflow: edits only through `/gsd-execute-phase`.
- Import hygiene (existing test `tests/test_api_endpoints.py::test_import_hygiene`): importing `swf.api.main` must not load `torch`, `darts`, `matplotlib`, `lightgbm`, `swf.evaluate*`, `swf.validate*` or `swf.models*`. **Do not import `swf.evaluate.*` helpers into the API** (for example `daytime_mask` lives in `swf.evaluate.metrics`). Use `swf.physics.common.is_night` instead (pvlib only, allowed).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 72 h forecast, bands, stale flag | API (existing) | Browser renders | Already in SQLite |
| Today/tomorrow totals | API (`summary.py`) | Browser (combined = sum, peak kW lookup) | IST day window math stays in Python next to its tests |
| Weather (temp, cloud, rain, is_day) | API: reads cached raw JSON via `openmeteo_canon` | Browser: condition rule + day aggregation | Reusing the adapter keeps time labels identical to forecast `target_time` (Open-Meteo label shift -1 h, D-15) |
| Correlation matrix | API (pandas over interim parquet, cached in process) | — | 0.08 s; no build step or new CLI needed |
| Performance tables | API (CSV readers) | Browser (filter served model, charts) | CSVs are the evaluation artefacts; no recompute |
| Figures (PNG) | API allowlist `FileResponse` | Browser `<img>` | Never expose `reports/` wholesale |
| Build info / footer | API | Browser | git + registry live on the server |
| IST formatting, greeting, condition icons, theme | Browser | — | CLAUDE.md: IST only in the frontend |
| SPA routing (`/performance` reload) | API static mount (fallback to index.html) | Browser router | `StaticFiles(html=True)` does not fall back (checked in starlette 1.10.0 source) |

## Standard Stack

### Already installed (frontend/package.json)
react/react-dom ^19.3.1, vite ^8.3.6, @vitejs/plugin-react ^6.1.2, typescript ~7.0.2, oxlint ^1.90.0, @types/node ^24.19.2. Vite already proxies `/api` to `http://127.0.0.1:8000` (`frontend/vite.config.ts`).

### Core (to add)
| Library | Version (npm, 2026-11-10) | Purpose | Peer check |
|---------|---------|---------|-----------|
| tailwindcss | 4.3.5 | Styling, `@theme` tokens | — |
| @tailwindcss/vite | 4.3.5 | Vite plugin (no PostCSS, no config file) | vite ^5.2-^8 ✓ |
| recharts | 3.10.1 | Panels, bars, donut | react ^19 ✓, needs `react-is` peer (npm 11 auto-installs peers; react-is 19.3.1 current) |
| motion | 14.11.1 | Page transition, stagger, count-up | react ^18\|\|^19 (optional peer) ✓ |
| lucide-react | 1.70.0 | Icons | react ^19 ✓ |
| @tanstack/react-query | 5.107.1 | Fetch, polling, retries | react ^18\|\|^19 ✓ |
| react-router-dom | 7.18.5 | 4 routes | react >=18 ✓ (note `react-router` 8.5.1 exists; stay on the 7.x `react-router-dom` that STACK.md names) |
| @fontsource-variable/plus-jakarta-sans | 5.3.0 | Self-hosted font | — |

[VERIFIED: npm registry] for versions and peers. All `postinstall` scripts are empty (checked with `npm view <pkg> scripts.postinstall`).

**Lucide icon names (checked in the 1.70.0 tarball typings):** all UI-SPEC names exist: `SolarPanel, Fan, SunMedium, Droplets, Wind, Zap, CloudSun, ChartColumn, Info, MapPin, Settings, Sun, Moon, Clock, Thermometer, ArrowUpRight, Cloud, CloudRain, CloudMoon, Activity, ChevronRight, ChevronDown`. **`TriangleAlert` is only an alias** of the renamed `TriangleExclamationPoint` (`export { TriangleExclamationPoint as TriangleAlert }`). Import `TriangleExclamationPoint` so a future alias removal does not break the build.

**Installation:**
```bash
cd frontend
npm install tailwindcss@4.3.5 @tailwindcss/vite@4.3.5 recharts@3.10.1 motion@14.11.1 lucide-react@1.70.0 @tanstack/react-query@5.107.1 react-router-dom@7.18.5 @fontsource-variable/plus-jakarta-sans@5.3.0
```

### Backend: nothing new
FastAPI 0.162.0, starlette 1.10.0, pandas 3.0.6, pvlib 0.16.1, pyarrow are installed (checked in `.venv`).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `node --test` for TS helpers | vitest 5 | vitest adds a dependency and config. Node 24.16 runs `.ts` tests natively (checked) |
| `@playwright/test` dev dep | Playwright MCP (already used: `.playwright-mcp/`) | The npm package needs a ~150 MB browser download for 2 screenshots. Use the MCP |
| BrowserRouter + SPA fallback | HashRouter | HashRouter clashes with `/performance#target-x` anchors (UI-05) |
| Correlation computed live | Precomputed JSON + new CLI step | Live is 0.08 s, needs no new CLI command and cannot go out of date |

## Package Legitimacy Audit

slopcheck could not run (install blocked by the permission classifier), so per protocol **every package below is `[ASSUMED]`**. Registry facts below were gathered with `npm view` and the npm downloads API.

| Package | Registry | Age | Downloads/wk | Source Repo | slopcheck | Disposition |
|---------|----------|-----|--------------|-------------|-----------|-------------|
| tailwindcss | npm | 9 yrs | 175.8M | github.com/tailwindlabs/tailwindcss | n/a | Approved [ASSUMED] |
| @tailwindcss/vite | npm | 2.8 yrs | 61.0M | github.com/tailwindlabs/tailwindcss | n/a | Approved [ASSUMED] |
| recharts | npm | 11 yrs | 64.5M | github.com/recharts/recharts | n/a | Approved [ASSUMED] |
| motion | npm | 13 yrs | 34.1M | github.com/motiondivision/motion | n/a | Approved [ASSUMED] |
| lucide-react | npm | 6 yrs | 131.2M | github.com/lucide-icons/lucide | n/a | Approved [ASSUMED] |
| @tanstack/react-query | npm | 4.3 yrs | 84.0M | github.com/TanStack/query | n/a | Approved [ASSUMED] |
| react-router-dom | npm | 10 yrs | 56.4M | github.com/remix-run/react-router | n/a | Approved [ASSUMED] |
| @fontsource-variable/plus-jakarta-sans | npm | 3.5 yrs | 0.93M | github.com/fontsource/font-files | n/a | Approved [ASSUMED] |

**Packages removed:** none. **Flagged suspicious:** none. All are well-known, long-lived and high-download, and every name was already in STACK.md / UI-SPEC. The planner may fold the human check into one `checkpoint:human-verify` before `npm install` (or skip it, since the owner approved these names in the UI-SPEC).

## Architecture Patterns

### System Architecture Diagram

```
 hourly APScheduler job (existing)                 Browser (React, IST formatting only)
 ┌───────────────────────────────┐                 ┌──────────────────────────────────────┐
 │ fetch_live -> raw JSON cache  │──┐              │ react-query (5 min poll: forecast,   │
 │ build_run -> SQLite forecast  │  │              │   summary, health, weather;          │
 │            + meta.run_time    │  │              │   staleTime ∞: metrics, perf, corr,  │
 └───────────────────────────────┘  │              │   site, build)                       │
                                    v              │        │                             │
 data/raw/openmeteo/forecast/gfs_seamless/         │        v                             │
   {run_time+1h:%Y%m%dT%H}.json ─> /api/weather ──>│  Energy  Weather  Performance About  │
 data/app.db (forecast, meta) ──> /api/forecast ──>│   (AnimatePresence keyed on path,    │
                              ──> /api/forecast/summary?day=           │  shared GlassCard etc)│
                              ──> /api/health, /api/build ──>│        │                     │
 data/interim/*.parquet ───────> /api/correlation (cached) ─>│        v                     │
 reports/evaluation/*.csv ─────> /api/metrics, /api/performance ─>  <img src=/api/figures/x>│
 reports/**/allowlisted.png ───> /api/figures/{name} ────────>└──────────────────────────────┘
 models/deployed/registry.json ─> /api/build
 frontend/dist ─> StaticFiles mount (LAST) with index.html fallback for /weather, /performance, /about
```

### Recommended Project Structure
```
src/swf/api/
├── main.py          # + 5 endpoints, summary day param, SPA static subclass
├── schemas.py       # + Weather, Correlation, Performance, BuildInfo models
├── summary.py       # ist_day_window(now, tz, day="tomorrow")
└── extras.py        # (optional) weather_rows(), correlation(), read_csv_rows() if main.py gets long
src/swf/fetch/openmeteo.py  # extract live_path(s, root, now) used by fetch_live AND /api/weather
tests/test_api_extras.py    # new endpoint tests (tmp files, create_app kwargs)

frontend/
├── index.html       # inline theme script (no flash), title
├── vite.config.ts   # + tailwindcss() plugin
├── src/
│   ├── main.tsx     # QueryClientProvider, BrowserRouter, MotionConfig, font import
│   ├── index.css    # @import "tailwindcss"; @custom-variant dark; @theme tokens; glass utilities
│   ├── api.ts       # typed fetchers + react-query hooks (one file)
│   ├── lib/         # pure helpers: time.ts (IST), weather.ts (condition rule, day agg), targets.ts (meta table), corr.ts
│   ├── components/  # GlassCard, IconChip, ModelBadge, SimulatedTag, SourceTag, Segmented, CountUp,
│   │                #   ForecastPanel, MatrixGrid, Ring, FigureCard, StaleBanner, StateBlock, Shell (sidebar/topbar/bottomnav/footer)
│   └── pages/       # Energy.tsx, Weather.tsx, Performance.tsx, About.tsx
└── tests/           # *.test.ts for lib/ (node --test), OUTSIDE src so `tsc -b` does not need node types
```

### Pattern 1: New endpoints follow `create_app` injection (existing style)
Every new file path becomes a `create_app` kwarg with a repo default, like the existing `leaderboard_path`. Tests then point it at `tmp_path`. Keep existing kwargs unchanged so current fixtures keep working.
```python
def create_app(db_path=None, *, start_scheduler=True, refresh_fn=None, static_dir=FRONTEND_DIST,
               leaderboard_path=None, reports_dir=None, interim_dir=None, raw_root=None, registry_path=None):
    reports_dir = reports_dir or REPORTS_DIR
    ...
```
`create_app` must still not touch disk (`test_create_app_touches_no_disk`). Read files inside the handlers. For correlation, cache in a closure dict, not at app creation.

### Pattern 2: Summary `day` parameter
```python
# summary.py
def ist_day_window(now, tz_name, day="tomorrow"):
    tz = ZoneInfo(tz_name)
    today = now.astimezone(tz).date()
    end = datetime.combine(today + timedelta(days=1), time(), tzinfo=tz)
    if day == "today":  # rest of today: from the current UTC hour label (= first forecast point)
        return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0), end.astimezone(UTC)
    return end.astimezone(UTC), (end + timedelta(days=1)).astimezone(UTC)
# main.py: def forecast_summary(day: Literal["today", "tomorrow"] = "tomorrow")
```
The default stays `tomorrow`, so existing tests pass. Start "today" at the floored UTC hour, because the first forecast `target_time` = origin + 1 h = floor(now). [VERIFIED: refresh.py `origin_for` and meta in data/app.db: run_time 16:00Z, last_success 17:49Z]

### Pattern 3: Weather endpoint over the cached live file
```python
from swf.align.adapters import openmeteo_canon   # pandas + pvlib only; passes import hygiene
from swf.physics.common import is_night

@app.get("/api/weather", response_model=Weather)
def weather():
    run_time = db.read_meta(db_path).get("run_time")
    if run_time is None: raise HTTPException(503, "no forecast cached yet")
    origin = pd.Timestamp(run_time)
    path = live_path(s, raw_root, origin + pd.Timedelta(hours=1))   # same name fetch_live wrote
    if not path.exists(): raise HTTPException(503, "weather not cached yet")
    c = openmeteo_canon(path.read_bytes(), s)[["temp", "cloud", "precip"]]
    start = pd.Timestamp(ist_day_window(origin.to_pydatetime(), tz, "today")[0])  # or IST midnight today
    c = c.loc[<IST midnight today> : origin + pd.Timedelta(hours=hmax)]
    day = ~is_night(c.index, s)
    return Weather(display_timezone=tz, run_time=run_time,
                   points=[WeatherPoint(time=db.iso(t), temp=..., cloud=..., precip=..., is_day=bool(d)) ...])
```
Facts [VERIFIED: codebase + live run]:
- The live file name is `f"{now:%Y%m%dT%H}.json"` where `now` is the refresh wall clock, and `origin = floor(now) - 1 h`. So **file stamp = run_time + 1 h** (on disk: `20261109T17.json` for run_time `2026-11-09T16:00Z`). Extract that name into `live_path()` in `fetch/openmeteo.py` so the two cannot drift.
- `openmeteo_canon` shifts every Open-Meteo column -1 h (D-15), so weather labels line up 1:1 with forecast `target_time`. Prototyped on the fixture: 264 rows; `temp`, `cloud` and `precip` came back correctly.
- `is_night` uses the sun position at label + 30 min (pvlib), matching the physics everywhere else.
- Return rows from **IST midnight today** to origin + 72 h. The Weather page "Today" card needs today's earlier hours for high/low, and the payload has `past_days: 8`, so they exist.
- NaN to `None` (gfs can have nulls at the tail).

### Pattern 4: Correlation, performance, figures, build
- **Correlation** `/api/correlation`: `energy_sim.parquet[t1_kw,t5_kw]` joined to `weather_nasa.parquet[ghi,rh,ws10]` (this is the evaluation truth, per `swf/evaluate/report.py`). Use `df.corr()` (Pearson) and return `{targets, matrix (5x5 floats), period_start, period_end, n}`. Cache on first call. Missing files → 503. Real values today (2001-2025, n = 219,144): t1-ghi **0.99**, t5-ws10 **0.84**, t1-rh **-0.61**, ghi-rh **-0.59**, all others |r| <= 0.24. So exactly 4 explanation lines show. The UI-SPEC's "Wind speed-Humidity" reason never triggers (r = 0.14). [VERIFIED: computed]
- **Performance** `/api/performance`: one generic CSV reader (lift the existing `/api/metrics` parse into a helper `_read_csv(path, str_cols)`). Return:
  - `coverage`: `prob_metrics.csv`, `split == "test"` (columns target, model, n, coverage, width, pinball)
  - `horizon`: `breakdown.csv`, `split == "test"`, `horizon != "all"` (the horizon column is **strings** `'1','6','24','48','72','all'`, so cast to int after filtering), models = served runtimes ∪ {`baseline3`}
  - `heatmap`: `skill_heatmap_test.csv` (models lightgbm/lstm/tft; horizons 1/6/24/48/72; seasons all/monsoon/dry; 225 rows)
  - `wind_cf`: `wind_cf.csv` (12 rows)

  Missing file → empty list (same style as `/api/metrics`).
- **Figures** `/api/figures/{name}`: `FIGURES = {"solar_plant_1_scatter": reports/validation/..., "solar_plant_2_scatter": ..., "wind_scatter": ..., "reliability_test": reports/evaluation/..., "wind_cf": reports/evaluation/...}`. Look up `name` in the dict (unknown → 404). `FileResponse(path, media_type="image/png")`. Never join user input into a path. Living under `/api/` means the existing Vite dev proxy covers it.
- **Build** `/api/build`: `{git_sha: short HEAD or None, registry_git_sha, schema_version, final_split, models: {target: runtime}, data_through: meta.run_time or None}`. Git via `subprocess.run(["git","rev-parse","--short","HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)` inside try/except (OSError, SubprocessError) → None, computed once per process. Registry path default = `default_registry_path(MODELS_DIR)` logic. **Do not import `swf.api.refresh`** at module level (it pulls `swf.features`/`swf.predict`; main imports it lazily in the lifespan today). Re-implement the 2-line "deployed else models/registry.json" check, or move `default_registry_path` to a light module.

### Pattern 5: SPA fallback mount (replace the plain mount)
```python
class SPAStatic(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:   # starlette.exceptions.HTTPException
            if e.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise
app.mount("/", SPAStatic(directory=static_dir, html=True), name="site")   # still LAST
```
[VERIFIED: starlette 1.10.0 `StaticFiles.get_response` source raises `HTTPException(404)` when there is no file and no 404.html]

### Pattern 6: Frontend wiring
```tsx
// main.tsx
import '@fontsource-variable/plus-jakarta-sans'          // font-family: "Plus Jakarta Sans Variable" [CITED: package README]
const qc = new QueryClient({ defaultOptions: { queries: { retry: 2, refetchOnWindowFocus: true } } })
<QueryClientProvider client={qc}><BrowserRouter><MotionConfig reducedMotion="user"><App/></MotionConfig></BrowserRouter></QueryClientProvider>

// App.tsx route transitions (declarative router, keyed on pathname)
const location = useLocation()
<AnimatePresence mode="wait">
  <motion.div key={location.pathname} initial={{opacity:0}} animate={{opacity:1}}
              exit={{opacity:0, filter: reduce ? 'none' : 'blur(12px)'}} transition={{duration:0.18}}>
    <Routes location={location}> ...4 routes... </Routes>
  </motion.div>
</AnimatePresence>
```
- `AnimatePresence mode="wait"` supports **one child only**; changing the child's `key` triggers exit then enter. [CITED: motion.dev/docs/react-animate-presence]
- `MotionConfig reducedMotion="user"` disables **transform and layout** animations only. **Opacity (and filter) still animate**, and the imperative `animate()` used by CountUp is not affected. So also call `useReducedMotion()` (from `motion/react`) to drop the blur, the stagger and the count-up. [CITED: motion.dev/docs/react-accessibility]
- CountUp: `useEffect(() => { const c = animate(prev, value, { duration: .8, ease: [0.22,1,0.36,1], onUpdate: v => setText(fmt(v)) }); return () => c.stop() }, [value])`. `onUpdate` works for single-value animations. [CITED: motion.dev/docs/animate]
- Tailwind 4: `@import "tailwindcss"; @custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));` plus `@theme { --color-...; --font-sans: "Plus Jakarta Sans Variable", ui-sans-serif, ... }`, and `tailwindcss()` in the `vite.config.ts` plugins. [CITED: tailwindcss.com dark-mode docs via Context7]
- Recharts 3: use the chart's **`responsive` prop** (since 3.3) with CSS width/height instead of wrapping in `ResponsiveContainer`. Charts sharing `syncId` sync Tooltip/Brush. `syncMethod` defaults to `"index"`. Area animation default is **1500 ms**, so set `animationDuration={600}`. [CITED: recharts.github.io/en-US/api/AreaChart, /api/Area, /guide/sizes]

### Anti-Patterns to Avoid
- **Mounting `reports/` with StaticFiles:** exposes CSV/markdown/everything. Use the allowlist.
- **Computing IST on the server or formatting with `toLocaleString()` without `timeZone`:** shows the laptop's zone (fine on the owner's laptop, wrong in principle and wrong on an examiner's phone set to another zone).
- **Importing `swf.api.refresh` or anything under `swf.evaluate` at the top of `main.py`:** breaks the import-hygiene test.
- **One `backdrop-filter` per card inside an already blurred panel:** costly and nearly invisible (Pitfall 4).
- **Re-running `evaluate --final` or retraining to get numbers:** CONTEXT boundary. Read the CSVs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polling, retries, stale/loading states | `useEffect` + `setInterval` | react-query `refetchInterval`, `retry`, `staleTime: Infinity` | Window-focus refetch, dedupe, error states included |
| IST time math | manual `+5:30` offsets | `Intl.DateTimeFormat(…, {timeZone})`, `formatToParts` | DST-free here, but offsets are a classic bug source; the tz comes from config |
| Number formatting | string padding | `Intl.NumberFormat('en-IN', {maximumFractionDigits})` | Lakh grouping, locale |
| Open-Meteo time shift for weather | re-parse JSON in the endpoint | `swf.align.adapters.openmeteo_canon` | Same D-15 shift as the forecast; tested already |
| Solar day/night | elevation formula | `swf.physics.common.is_night` | pvlib, interval midpoints |
| Synced hover across 5 charts | custom mouse events | Recharts `syncId` | Built in |
| Count-up tween | rAF loop | motion `animate(from, to, {onUpdate})` | Easing, stop() |
| Icons | inline SVGs | lucide-react | Consistent stroke |

## Common Pitfalls

### Pitfall 1: Forecast hours land on :30 in IST (UI-SPEC examples assume :00)
**What goes wrong:** `target_time` labels are UTC hour starts (`16:00Z`). In IST (UTC+5:30) these are 21:30, 22:30 and so on. A categorical x-axis cannot place an "IST midnight" line, and "00/06/12/18" tick labels never match a data point. "Peak solar hour 13:00 IST" would be a lie.
**How to avoid:** Use `dataKey="t"` (epoch ms), `type="number"`, `scale="time"`, `domain={['dataMin','dataMax']}`, explicit `ticks` = epoch ms of each IST 00:00/06:00/12:00/18:00 inside the range, and `ReferenceLine x={istMidnightMs}`. Show point times as real IST clock times ("12:30"). Tooltip "Wed 11 Nov, 12:30 IST". Daily totals: IST day = labels 00:30..23:30 (what `ist_day_window` already does: window starts at 18:30Z, first included label 19:00Z). Planner: amend the UI-SPEC example strings, not the design.
**Warning signs:** Every time ends in ":30" in screenshots and the midnight line sits on a point. Both are correct; fix the copy, not the data.

### Pitfall 2: `en-IN` defaults to 12-hour and a comma
**What goes wrong:** `new Intl.DateTimeFormat('en-IN',{timeZone,hour:'2-digit',minute:'2-digit'})` gives `"09:30 pm"`; weekday/day/month gives `"Tue, 10 Nov"`. [VERIFIED: Node 24.16]
**How to avoid:** Pass `hourCycle: 'h23'` (gives "21:30", checked). For "Wed 11 Nov", build it from `formatToParts` (weekday, day, month) instead of trusting the locale's punctuation. Put all of this in `lib/time.ts` with `node --test` cases.

### Pitfall 3: Reload on `/performance` returns 404
**What goes wrong:** `StaticFiles(html=True)` only serves `index.html` for directory URLs. `/performance` has no file, so the user gets 404 (`{"detail":"Not Found"}`).
**How to avoid:** Use the SPA subclass (Pattern 5). Test with `TestClient(create_app(..., static_dir=tmp_dist)).get("/performance")` → 200 HTML, and `/api/nope` → 404 JSON.

### Pitfall 4: backdrop-filter stacking and the blur page transition
**What goes wrong:** An element with `backdrop-filter` (or an ancestor with `filter`/`opacity < 1`) becomes a *backdrop root*, so child cards' `backdrop-filter` only sees the panel's own content. That costs GPU time for little visual effect. Animating `filter: blur(12px)` on the page wrapper also changes how nested backdrop filters render mid-transition, and filter animation over many blurred layers can stutter on an integrated GPU. [ASSUMED: CSS Filter Effects 2 "backdrop root" behaviour; check in the browser]
**How to avoid:** Put `backdrop-filter` only on the sidebar, top bar/bottom nav, content panel and popover. Cards and chart cards use their semi-opaque fill (+ inset highlight) with **no** backdrop-filter. Keep the `@supports not (backdrop-filter…)` fallback. Check in Chrome DevTools Performance during a page switch.

### Pitfall 5: Theme flash and localStorage throwing
**How to avoid:** An inline `<script>` in `index.html` `<head>`: `try{document.documentElement.dataset.theme=localStorage.getItem('swf-theme')||'light'}catch(e){document.documentElement.dataset.theme='light'}`. Wrap the same try/catch around writes (D-38). oxlint does not lint `index.html` scripts, so keep the script tiny.

### Pitfall 6: Synced charts need equal-length data and a Tooltip in every chart
**What goes wrong:** With `syncMethod="index"`, a chart whose data array is shorter or differently ordered highlights the wrong hour. Charts without a `<Tooltip>` do not show the synced cursor or active dot. [ASSUMED from Recharts behaviour; syncMethod semantics CITED]
**How to avoid:** Build one `rows` array (72 objects: `t`, and for each target `{p50, band:[p10,p90]}`). Slice it once for 24/48/72 h and pass the same slice to all five panels. Give each panel a `<Tooltip>` (content can render only that panel's target, or `content={() => null}` plus a shared readout). Use `band: null` when either quantile is null, never `[null, 5]`. Set `isAnimationActive` true only on first mount. 5 charts x 72 points is light for SVG. Keep `throttleDelay` default `'raf'`.

### Pitfall 7: `/performance#target-x` does not scroll
**What goes wrong:** React Router does not scroll to hash anchors, and with `AnimatePresence mode="wait"` the target element does not exist until the exit finishes.
**How to avoid:** In Performance, a `useEffect` on `[location.hash, dataLoaded]` that calls `document.getElementById(hash.slice(1))?.scrollIntoView({block:'start'})` once data has rendered (or in `onAnimationComplete` of the page wrapper).

### Pitfall 8: Stale "current hour" and the first point
**What goes wrong:** Taking `points[0]` as "now" is right when fresh. When stale (refresh failed for hours), `points[0]` is in the past.
**How to avoid:** Current point = the last point with `t <= Date.now()`, else `points[0]`. The "Now" ReferenceLine uses `Date.now()` clamped to the domain.

### Pitfall 9: Wording traps from the data
- Served `model` strings are runtimes (`"tft"`, `"baseline3"`, `"lightgbm"`, `"lstm"`, `"gru"`). Map them to display names ("TFT", "Baseline 3", "LightGBM", "LSTM", "GRU") in one table.
- Coverage on test (served TFT): t1 0.806, ghi 0.791, **rh 0.743**, ws10 0.662, t5 0.684. UI-SPEC flags only the two wind targets (D-36), but **humidity is also under 0.80**. Planner/owner: either add a neutral note for RH or show its ring without a badge. Do not hide it (Core Value: honest results). [VERIFIED: prob_metrics.csv]
- Test skill vs baseline 3 (TFT): t1 +51.9%, rh +42.8%, ghi +51.4%, ws10 +16.2%, t5 +19.9%. All positive, so "Baseline wins" badges will not appear with current data, but keep the branch.
- The leaderboard has many rows per target (`baseline3_corrected`, `_stitched_*`, `climatology`, `persistence`, …: 10 models x 5 targets on test). Decide whether the table shows all rows (honest, long) or served + baseline 3 + persistence + climatology. Recommend: all test rows, sorted by RMSE per target, served row pinned with the "Serving" pill.

### Pitfall 10: Windows paths and git
- Build every server path from `swf.core.paths` (`Path` objects). Never string-join, and never accept a path from the client (figures allowlist).
- `git` may be missing from PATH when the server starts outside a dev shell. Fall back to `None`; the footer then shows "Build unknown".
- `frontend/dist` is git-ignored, and `swf.api.main` decides the mount **at import time** (`app = create_app()` checks `is_dir()`). Run `npm run build` *before* `python -m swf serve`, or the site is not mounted until restart. Phase 8's README must say so.
- npm scripts run under cmd.exe on Windows. Quote globs: `"test": "node --test \"tests/**/*.test.ts\""` (Node expands the glob itself).

### Pitfall 11: `tsc -b` and test files
`tsconfig.app.json` includes only `src` with `types: ["vite/client"]`. Test files importing `node:test` inside `src/` would fail the build. Put tests in `frontend/tests/` and import `../src/lib/x.ts` with the `.ts` extension (allowed by `allowImportingTsExtensions`). Node type stripping needs erasable syntax only (no `enum`, no parameter properties), and `erasableSyntaxOnly: true` already enforces that.

## Code Examples

### ForecastPanel core (Recharts 3)
```tsx
// Source: recharts.github.io API (syncId, responsive, Area tuple dataKey) — composed by researcher
<ComposedChart data={rows} syncId="forecast" responsive style={{ width: '100%', height: 120 }}
               margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
  <CartesianGrid vertical={false} strokeDasharray="3 3" />
  <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={istTicks}
         tickFormatter={fmtHourIST} hide={!isLast} />
  <YAxis hide={compact} />
  <Area dataKey={(r) => r[k].band} stroke="none" fill={hue} fillOpacity={0.18} isAnimationActive={first} />
  <Line dataKey={(r) => r[k].p50} stroke={hue} strokeWidth={2} dot={false} isAnimationActive={first} />
  <ReferenceLine x={nowMs} stroke="var(--accent)" strokeDasharray="4 4" />
  <Tooltip content={<PanelTip target={k} />} />
</ComposedChart>
```

### Condition rule (lib/weather.ts, from UI-SPEC)
```ts
export function condition(precip: number | null, cloud: number | null, isDay: boolean) {
  if ((precip ?? 0) >= 0.5) return 'rain'
  if ((cloud ?? 0) >= 70) return 'cloudy'
  if ((cloud ?? 0) >= 30) return isDay ? 'partly' : 'partly-night'
  return isDay ? 'sunny' : 'clear'
}
```

### Backend test style (matches tests/test_api_endpoints.py)
```python
def test_figures_allowlist(tmp_path, seed):
    (tmp_path / "validation").mkdir(); (tmp_path / "validation" / "wind_scatter.png").write_bytes(b"\x89PNG")
    c = TestClient(create_app(seed(), start_scheduler=False, static_dir=None, reports_dir=tmp_path))
    assert c.get("/api/figures/wind_scatter").headers["content-type"] == "image/png"
    assert c.get("/api/figures/..%2Fleaderboard").status_code == 404
    assert c.get("/api/figures/leaderboard").status_code == 404
```
Weather test: write a db with `db.write_run(path, run, rows, hist, ...)` where `run` = a time inside the fixture `om_live_gfs_seamless.json` (fixture covers 2026-10-26 onward, 264 canon rows). Copy the fixture to `raw/openmeteo/forecast/gfs_seamless/{run+1h:%Y%m%dT%H}.json`, then assert `is_day` flips around 00:30Z/12:30Z (sunrise/sunset IST ~06:15/18:00) and that times end with `Z`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `framer-motion` package | `motion` package, `import … from "motion/react"` | motion 11+ | D-42 already says so |
| `<ResponsiveContainer>` | chart `responsive` prop + CSS size | Recharts 3.3 | Fewer wrappers; ResponsiveContainer still works |
| `tailwind.config.js` + `@tailwind base` | `@import "tailwindcss"` + `@theme` + `@custom-variant` | Tailwind 4 | Old tutorials mislead |
| lucide `AlertTriangle`/`TriangleAlert` | `TriangleExclamationPoint` (old names are aliases) | lucide 1.x | Import the new name |
| vitest for tiny TS units | `node --test` with native type stripping | Node 23.6+ / 24 | No dependency |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | All 8 npm packages are legitimate (slopcheck not run) | Package audit | Very low: long-lived, top-download packages named in STACK.md |
| A2 | Nested `backdrop-filter` inside a blurred panel or a filtered ancestor gives little visual gain and can cost frames | Pitfall 4 | Low: if wrong, cards could keep their blur; check in the browser |
| A3 | Every synced Recharts chart needs its own `<Tooltip>` for the synced cursor/active dot | Pitfall 6 | Low: found in the first manual hover test |
| A4 | `AnimatePresence` + `<Routes location={location}>` keyed on pathname works with react-router-dom 7 declarative mode | Pattern 6 | Low: common pattern; fallback is `useOutlet()` frozen per key |
| A5 | Numeric time XAxis (`type="number"`, explicit `ticks`) works with `syncMethod="index"` | Pitfall 1 | Medium: if sync misbehaves, use `syncMethod="value"` (same `t` values in all panels) |

## Open Questions (RESOLVED)

1. **What does "Data through" show?**
   - Known: `meta.run_time` is the interval-start label of the last fully observed hour (e.g. 16:00Z = the 21:30-22:30 IST hour).
   - Recommendation: show `run_time + 1 h` (the end of the last observed hour) as "Data through 22:30 IST", and say so in a code comment. Either is defensible; just be consistent. RESOLVED: D-44 (run_time + 1 h).
2. **RH coverage 0.74 is also below nominal.** It is not in D-36's flag list. Recommend a neutral note, which needs owner confirmation (cheap). RESOLVED: D-45 (neutral note).
3. **Kaggle slugs on About:** they come from `config/site.yaml` (CLAUDE.md: config, not code). Cheapest is adding `kaggle: {solar_slug, wind_slug}` to the `/api/build` payload (`load_settings().kaggle` already has them: `Settings.kaggle: KaggleCfg`, verified). Otherwise put them in the About copy as static text (they are attribution text, not site/plant values). RESOLVED: D-46 (via /api/build).
4. **Leaderboard row set** (Pitfall 9): all test rows vs a short list. Recommend all rows, served row pinned. RESOLVED: D-47.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node | Vite 8 build, `node --test` | ✓ | 24.16.0 | — |
| npm | installs | ✓ | 11.12.0 | — |
| Python venv | API + pytest | ✓ | 3.12 (.venv), fastapi 0.162.0, starlette 1.10.0, pandas 3.0.6, pvlib 0.16.1 | — |
| uv | env | ✓ | on PATH | — |
| git | build-info SHA | ✓ (dev shell) | — | `None` → "Build unknown" |
| Playwright MCP | screenshots 1440/375 | ✓ (used before: `.playwright-mcp/`) | — | manual browser DevTools device mode |
| Live data on disk | weather/correlation/perf | ✓ data/app.db (run_time 2026-11-09T16:00Z), live JSON, interim parquet, reports CSV/PNG | — | endpoints return 503 / empty → UI StateBlock |

**Missing with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | pytest 9.2 (`pyproject.toml` `[tool.pytest.ini_options]`, addopts `-q -m 'not network and not realdata'`) |
| Framework (frontend units) | Node 24 built-in `node:test` + `node:assert/strict` (no install) |
| Frontend static checks | `npm run build` (= `tsc -b && vite build`), `npm run lint` (oxlint) |
| Visual/manual | Playwright MCP against `python -m swf serve` on http://127.0.0.1:8000 at 1440x900 and 375x812 |
| Quick run command | `.venv/Scripts/python -m pytest tests/test_api_endpoints.py tests/test_api_extras.py tests/test_api_summary.py -x` |
| Full suite command | `.venv/Scripts/python -m pytest` && `cd frontend && npm run lint && npm run build && npm test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | rows builder: 72 equal-length rows, band null when a quantile is null; slice 24/48/72 | unit (node) | `cd frontend && node --test tests/forecast.test.ts` | ❌ Wave 0 |
| UI-01 | hover on panel 1 shows active dot on all 5 | manual (Playwright MCP hover + screenshot) | — | manual |
| UI-02 | `/api/forecast/summary?day=today` window = floor(now) → next IST midnight; `day=bad` → 422; default unchanged | unit/API | `pytest tests/test_api_summary.py tests/test_api_endpoints.py -x` | ✅ extend |
| UI-03 | IST formatting (`hourCycle h23`, "Wed 11 Nov", :30 labels), IST tick generation, greeting by IST hour | unit (node) | `node --test tests/time.test.ts` | ❌ Wave 0 |
| UI-03 | stale banner visible when `stale: true` | manual (seed stale db or stop refresh) | — | manual |
| UI-04/05 | tags and badges present per target; model display-name map | unit (node) for the map; manual visual | `node --test tests/targets.test.ts` | ❌ Wave 0 |
| UI-06 | `/api/performance` shapes (test-only rows, int horizons, served + baseline3); `/api/figures` allowlist 200/404 | API | `pytest tests/test_api_extras.py -x` | ❌ Wave 0 |
| UI-07 | `/api/site` (existing) + wind_cf rows | API | same | ✅ / ❌ |
| UI-08 | `/api/build` keys; git failure → `git_sha: null`; registry missing → 503 or nulls | API | same | ❌ Wave 0 |
| D-35 | condition rule thresholds + day/night; day aggregation high/low/rain | unit (node) | `node --test tests/weather.test.ts` | ❌ Wave 0 |
| D-35 | `/api/weather` from fixture: Z times, is_day flips at IST sunrise/sunset, 503 when the file is missing | API | `pytest tests/test_api_extras.py -k weather` | ❌ Wave 0 |
| D-33 | `/api/correlation` from tmp parquet: symmetric, diag 1, 503 when missing; corr sentence builder picks |r|>=0.5 strongest-first max 4 | API + unit | `pytest -k correlation`; `node --test tests/corr.test.ts` | ❌ Wave 0 |
| SPA | `/performance` → index.html 200; `/api/nope` → 404 JSON; `/api/*` routes still win | API | `pytest -k spa` | ❌ Wave 0 |
| hygiene | `swf.api.main` import still torch/darts/matplotlib/lightgbm/evaluate-free | existing | `pytest tests/test_api_endpoints.py::test_import_hygiene` | ✅ |
| perf | `/api/forecast` < 500 ms (existing test_api_perf) | existing | `pytest tests/test_api_perf.py` | ✅ |
| UI-09 | layout at 375 px: bottom nav, no horizontal page scroll, 44 px targets | manual (Playwright MCP `browser_resize 375 812` + screenshot; JS check `document.documentElement.scrollWidth <= 375`) | — | manual |

### Sampling Rate
- **Per task commit:** the quick pytest command (backend tasks) or `npm run lint && npm run build && npm test` (frontend tasks).
- **Per wave merge:** full suite.
- **Phase gate:** full suite green, then Playwright MCP screenshots of all 4 pages x {1440, 375} x {light, dark} saved under `.playwright-mcp/` and reviewed against the reference frames, before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_api_extras.py`: weather, correlation, performance, figures, build, SPA fallback
- [ ] extend `tests/test_api_summary.py` for `day="today"`
- [ ] `frontend/tests/{time,weather,forecast,corr,targets}.test.ts`
- [ ] `frontend/package.json` script `"test": "node --test \"tests/**/*.test.ts\""`

## Security Domain

Local-only, read-only site; no auth, no user data, no writes.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (localhost, v1) |
| V3 Session Management | no | — |
| V4 Access Control | partly | Figures allowlist; no generic file serving from `reports/` |
| V5 Input Validation | yes | FastAPI `Query`/`Literal` validation (`day`, `hours`), dict-key lookup for figure names |
| V6 Cryptography | no | — |
| V12 Files/Resources | yes | `FileResponse` only on allowlisted `Path`s; SPA fallback never serves outside `dist` (StaticFiles `lookup_path` guards traversal) |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via figure name | Information disclosure | Dict allowlist; never join input into a path |
| Leaking repo files via a broad static mount | Information disclosure | Mount only `frontend/dist`; no `reports/` mount |
| XSS via API strings | Tampering | React escapes by default; no `dangerouslySetInnerHTML` |
| `localStorage` exceptions (privacy mode) | DoS (blank page) | try/catch on read/write (D-38) |

## Sources

### Primary (HIGH confidence)
- Codebase: `src/swf/api/{main,schemas,db,refresh,summary,run}.py`, `src/swf/fetch/openmeteo.py`, `src/swf/align/adapters.py`, `src/swf/physics/common.py`, `src/swf/core/paths.py`, `config/site.yaml`, `tests/test_api_endpoints.py`, `tests/conftest.py`, `frontend/*`
- Data inspected live: `reports/evaluation/{prob_metrics,breakdown,skill_heatmap_test,wind_cf,leaderboard}.csv`, `models/deployed/registry.json`, `data/app.db` meta, `data/interim/*.parquet` (correlation computed), the live Open-Meteo JSON (columns)
- starlette 1.10.0 `StaticFiles.get_response` source (introspected)
- npm registry: versions, peers, postinstall, repo, created date, weekly downloads (2026-11-10)
- lucide-react 1.70.0 tarball typings (icon names and aliases)
- Node 24.16 live checks: `node --test` on `.ts`, `Intl.DateTimeFormat` en-IN output
- Context7 `/websites/motion_dev` (AnimatePresence mode, MotionConfig reducedMotion, useReducedMotion, animate onUpdate)
- Context7 `/websites/recharts_github_io` + `/recharts/recharts/v3.10.1` (syncId/syncMethod, responsive prop, Area tuple dataKey, animation defaults)
- Context7 `/tailwindlabs/tailwindcss.com` (dark variant via data-theme, @theme, Vite plugin)
- `@fontsource-variable/plus-jakarta-sans` README (import and family name)

### Tertiary (LOW, flagged)
- Backdrop-root behaviour of nested backdrop-filter (A2), Recharts Tooltip-per-chart requirement for sync (A3)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (npm-verified; peers match React 19/Vite 8)
- Backend additions: HIGH (code read, data prototyped)
- Frontend patterns: MEDIUM-HIGH (Context7-cited APIs; composition not run)
- Pitfalls: HIGH for the time/SPA/import ones (verified), MEDIUM for the CSS performance one

**Research date:** 2026-11-10
**Valid until:** 2026-12-10 (fast-moving frontend packages; re-check versions if installing after that)
