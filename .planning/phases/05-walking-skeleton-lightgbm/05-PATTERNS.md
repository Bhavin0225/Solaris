# Phase 5: Walking Skeleton & LightGBM - Pattern Map

**Mapped:** 2026-11-07
**Files analyzed:** 27 new/modified
**Analogs found:** 22 / 27 (frontend, FastAPI app, sqlite db, APScheduler, lightgbm trainer internals have no in-repo analog; reuse pieces listed below)

All paths relative to `F:\Claude first project`. Python style in repo: module docstring on line 1, `from swf.x import y` absolute imports, `logging.getLogger("swf.<pkg>")`, `run(args) -> int` entry per CLI module, `# fmt: skip` on aligned dict literals, atomic write via `tmp` + `os.replace`, deterministic JSON (`indent=2, sort_keys=True` + trailing `\n`, `newline="\n"`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/swf/models/__init__.py`, `src/swf/predict/__init__.py`, `src/swf/api/__init__.py` | package marker | n/a | `src/swf/evaluate/__init__.py` | exact |
| `src/swf/models/lgbm.py` (train + val score, `run(args)`) | service (train job) | batch / transform | `src/swf/evaluate/baselines.py` (`build_split`, `run`) + `tests/test_features_real.py` (assembly recipe) | role-match |
| `src/swf/predict/baseline.py` (`b3_live`, baseline3 Predictor) | service | transform | `src/swf/evaluate/baselines.py::b3_table/baseline3` + `src/swf/features/build.py::serve_features` | role-match |
| `src/swf/predict/lgbm.py` (lazy-import Predictor) | service | transform | `src/swf/cli.py::check_gpu` (lazy import idiom) + `features/spec.py::assert_spec` | partial |
| `src/swf/predict/bands.py` | utility | transform | `src/swf/evaluate/metrics.py` (`daytime_mask`, `scored_mask`) + `physics/constraints.py::enforce` | partial |
| `src/swf/predict/registry.py` (load, dispatch) | utility | request-response | `evaluate/baselines.py::save_choice/load_choice` | role-match |
| `models/registry.json`, `models/lightgbm/*.txt` + sidecar json | config/artifact | file-I/O | `config/baseline3_choice.json` | role-match |
| `config/lgbm.yaml` + pydantic cfg in `core/settings.py` (modify) | config | file-I/O | `FeaturesCfg` / `load_features_cfg` in `core/settings.py:271-295` | exact |
| `src/swf/api/db.py` | repository | CRUD | none (stdlib sqlite3); atomic idiom from `evaluate/longfmt.py::write_long` | no analog |
| `src/swf/api/refresh.py` | service (scheduled job) | request-response (fetch) -> batch write | `src/swf/fetch/openmeteo.py::fetch_live` + `run` | role-match |
| `src/swf/api/schemas.py` | model | n/a | `core/settings.py` `_Base(extra="forbid")` | role-match |
| `src/swf/api/summary.py` | utility | transform | `evaluate/metrics.py` | partial |
| `src/swf/api/main.py` (app factory, lifespan, routes) | controller | request-response | none (first web code); `core/settings.py` for config load | no analog |
| `src/swf/api/run.py` (`run(args)` uvicorn) | entrypoint | n/a | `src/swf/features/run.py` | role-match |
| `src/swf/cli.py` (modify: `serve`, `train-lgbm`) | route/CLI | n/a | `cli.py:83-93` | exact |
| `frontend/**` (vite react-ts, `App.tsx`, `vite.config.ts`) | component | request-response | none | no analog |
| `tests/test_api_{db,endpoints,scheduler,stale,perf,summary,refresh}.py` | test | request-response | `tests/test_openmeteo_fetch.py`, `tests/test_features_parity.py` | role-match |
| `tests/test_predict_{registry,bands}.py` | test | transform | `tests/test_physics_constraints.py`, `tests/test_features_spec.py` | role-match |
| `tests/test_lgbm_train.py` | test | batch | `tests/test_evaluate_baselines.py` + `tests/synth.py` | role-match |
| `tests/test_lgbm_real.py` | test | batch | `tests/test_features_real.py` | exact |
| `tests/test_cli.py` (modify) | test | n/a | itself | exact |
| `tests/conftest.py` (modify: seeded_db, om_client fixtures) | test fixture | n/a | `conftest.py` `mock_client`, `no_sleep` | exact |
| `README.md` (modify: Run locally) | docs | n/a | existing README | n/a |

## Pattern Assignments

### `src/swf/cli.py` (modify) - add `train-lgbm` and `serve`

**Analog:** same file, lines 83-93 (handlers are lambdas calling `_run`, modules imported lazily so `serve` never loads training code and vice versa).

```python
sub.add_parser("baselines", help="persistence, climatology, baseline 3 -> data/processed/predictions").set_defaults(
    handler=lambda a: _run("swf.evaluate.baselines", a)
)
ev = sub.add_parser("evaluate", help="...")
ev.add_argument("--split", choices=["val", "test", "all"], default="all")
ev.set_defaults(handler=lambda a: _run("swf.evaluate.report", a))
```
Add: `train-lgbm` -> `_run("swf.models.lgbm", a)` (args: `--stride`), `serve` -> `_run("swf.api.run", a)` (args: `--host` default 127.0.0.1, `--port` default 8000). Update `tests/test_cli.py:12` command list and add a `serve --help` assertion in the same `_swf(...)` style (lines 5-26).

---

### `src/swf/models/lgbm.py` (train job, batch)

**Analog:** `src/swf/evaluate/baselines.py` (structure: module constants, pure builders, `run(args, ...) -> int`) and `tests/test_features_real.py:67-96` (the exact training-table recipe).

**Imports pattern** (baselines.py:3-18):
```python
from swf.align.consistency import load_coefs
from swf.core.paths import CONFIG_DIR, INTERIM_DIR
from swf.core.settings import load_features_cfg, load_settings
from swf.evaluate.longfmt import TARGETS, grid, make_long, validate_long, write_long
from swf.evaluate.metrics import align_models, metrics, scored_mask
from swf.features.history import history_frame
from swf.features.spec import assert_spec, lead_k, spec_hash
from swf.features.splits import origins_for
from swf.physics.wind import load_power_curve
```
Plus (training only; fine here, forbidden in `swf.api`/`swf.predict`): `from swf.evaluate.baselines import truth_frame, b3_table, load_choice`, `from swf.features.build import assemble, covariate_table, history_input, origin_table, target_table, iter_features`, `from swf.align.adapters import load_source`, `import lightgbm as lgb`.

**Training-table recipe** (test_features_real.py:69-85, copy verbatim then add `horizons=` per bucket):
```python
raw = load_source("era5", s)
hist = history_frame(history_input(raw, s, source="era5"), s, load_power_curve(s), coefs)
otab, ttab = origin_table(hist, cfg, s), target_table(hist.index, cfg, s)
tc = origins_for("train_covariate", cfg)   # then [::stride]
cov_tc = covariate_table(pd.read_parquet(INTERIM_DIR / "weather_gfs_hf.parquet"), s, coefs, cfg)
cov_val = {k: covariate_table(pd.read_parquet(INTERIM_DIR / f"weather_gfs_pr_d{k}.parquet"), s, coefs, cfg) for k in (1, 2, 3)}
X = assemble(otab, ttab, origins, range(lo, hi + 1), cov=cov_tc_or_cov_val, cfg=cfg)  # gather miss raises
```
Note `assemble(cov=dict)` requires keys `{1,2,3}` (build.py:119-128): that is the lead-matched val path (D-02). Bucket 1-6 only touches k=1, fine.

**Baseline-3 series for residual** (baselines.py:94-96, 120-130): `b3_table(hf, s, curve, coefs if choice["choice"][t] == "corrected" else None)[t]` over stitched `weather_gfs_hf` for train; for val use `{k: b3_table(pr[k], ...)}` with the lead-matched gather exactly as `baseline3()` does (baselines.py:99-112: `k = lead_k(hor.astype("int64"))`, loop `for kk, tab in tables.items(): m = k == kk; p[m] = tab[c].reindex(tt[m]).to_numpy()`). Reuse `baselines.baseline3(...)` outright for val b3 if convenient: it returns the long frame whose `p50` is the b3 aligned to `grid(origins, horizons)`.

**Truth + target time** (baselines.py:42-54, 57-66): `truth = truth_frame()`; `issue, hor, tt = grid(origins, horizons)`; `y_true = truth[t].reindex(tt).to_numpy()`. Residual `y_res = y_true - b3` and drop NaN before `lgb.Dataset`.

**Long-format write** (baselines.py:57-66 and 215-225):
```python
def _long(model, origins, horizons, truth, pred_by_target) -> pd.DataFrame:
    issue, hor, tt = grid(origins, horizons)
    parts = [make_long(issue, hor, t, model, truth[t].reindex(tt).to_numpy(), pred_by_target[t]) for t in TARGETS]
    return pd.concat(parts, ignore_index=True)
...
validate_long(df, truth=truth, origins=origins)
write_long(df, split, model, out_root)       # split="val" ONLY; model="lightgbm"
```
Pass `p10=`/`p90=` to `make_long` (signature `make_long(issue_time, horizon, target, model, y_true, p50, p10=None, p90=None)`, longfmt.py:58-60). Row order must follow `grid(origins, horizons)` with horizons = `range(1, 73)` across all three buckets so `validate_long`'s y_true/origin checks pass. Never write `test/lightgbm.parquet` (RESEARCH Pattern 3).

**Artifact meta / spec guard** (spec.py:101-123): sidecar JSON = `artifact_meta("covariate") | {"best_iteration":..., "bucket":..., "target":...}`; written deterministically (copy `save_choice` below). Load side calls `assert_spec(meta)`.

**Atomic deterministic JSON write** (baselines.py:177-187):
```python
text = json.dumps({**choice, "feature_spec_hash": spec_hash()}, indent=2, sort_keys=True) + "\n"
tmp = Path(str(path) + ".tmp")
tmp.write_text(text, encoding="utf-8", newline="\n")
os.replace(tmp, path)
```

**Precondition/exit-code idiom** (baselines.py:206-212):
```python
if any(not (interim / n).exists() for n in _NEED):
    print("run `python -m swf build-weather` and `python -m swf simulate-energy` first")
    return 1
```
Also `load_choice()` (baselines.py:190-203) enforces the spec hash and raises a helpful message; use it in training only. Serving reads the choice copied into `registry.json`.

---

### `src/swf/predict/baseline.py` (b3_live + baseline3 Predictor)

**Analog:** `features/build.py::serve_features` (lines 153-167) for the live canon chain and `features/history.py::history_frame`.

```python
raw_canon = openmeteo_canon(raw, s)
canon = clean(raw_canon, s, source="live")[0]
...
hist = history_frame(hi, s, curve, coefs)
```
Compose per RESEARCH Pattern 1: `history_frame(canon, s, curve, coefs)` and `history_frame(canon, s, curve, None)`, pick per `choice[t]`, `.reindex(T)` where `T = pd.date_range(origin + 1h, periods=cfg.horizon_max, freq="h")` (tz-aware UTC because origin is). Imports: `swf.align.adapters.openmeteo_canon`, `swf.align.clean.clean`, `swf.features.history.history_frame`. No `swf.evaluate` import (TARGETS from `swf.features.spec.TARGETS`, which is `tuple(TARGET_COLS.values())`; features.history exposes the same).

**Clipping:** `swf.physics.constraints.enforce(df, s)` (constraints.py:11-22). It needs a DataFrame whose index is the target times (night zeroing via `is_night(out.index, s)`) and columns among `t1_kw, t5_kw, rh, ghi, ws10`; call it once per band column (p10, p50, p90).

---

### `src/swf/predict/lgbm.py` (lazy-import Predictor)

**Analog (idiom):** `cli.py:11-16` lazy heavy import inside the function so the module is import-safe:
```python
def check_gpu() -> int:
    try:
        import torch
    except ImportError:
        print("torch not installed: run uv sync --extra train")
        return 1
```
Do the same: `import lightgbm as lgb` inside `load()`/`predict()`, never at module top. Load with `lgb.Booster(model_file=str(path))` (text only, no pickle; resolve path under `models/` and reject `..`, Security domain). Call `assert_spec(meta)` on the sidecar at load. Predict selects `X[meta["feature_columns"]]`, bucket by horizon `X["horizon"]`, and returns `b3 + residual`.

**Registry dispatch** (RESEARCH Pattern 5): `importlib.import_module("swf.predict." + runtime)` in `get_predictor(target)`; same `importlib` idiom as `cli.py:24-25` (`_run`).

---

### `src/swf/predict/registry.py`

**Analog:** `evaluate/baselines.py::load_choice` (lines 190-203): existence check with remedy message, `json.loads(path.read_text(encoding="utf-8"))`, then `assert_spec({"feature_spec_hash": d.get("feature_spec_hash")})` wrapped to append a remedy. Copy that shape, with path default `REPO_ROOT / "models" / "registry.json"` (add `MODELS_DIR = REPO_ROOT / "models"` to `core/paths.py`, same one-liner style as lines 4-9). Writer = `save_choice` atomic deterministic pattern above. Round floats (Pitfall 10).

---

### `src/swf/predict/bands.py` (MODEL-04)

**Analog:** `evaluate/metrics.py` for `daytime_mask` (used in `report.py:97` as `daytime_mask(g.index, s, cfg.eval.daytime_zenith_deg)`) and `enforce` for clipping. NOTE `daytime_mask`/`scored_mask` live in `swf.evaluate.metrics`, which the API must not import. Training-side quantile computation may import it; the serving side only needs the saved offsets plus `np.sort` + `enforce`. If serving needs a daytime test, use `swf.physics.common.is_night` (as `constraints.py:5` does), not `evaluate.metrics`.

Core, per RESEARCH Pattern 4: `lo = p50 + q10; hi = p50 + q90; stacked = np.sort(np.stack([lo, p50, hi], axis=1), axis=1)` then `enforce` per column. One function used by both the offline long-format writer and live serving.

---

### `config/lgbm.yaml` + `core/settings.py` (modify)

**Analog:** `FeaturesCfg` and `load_features_cfg` (settings.py:271-295) and `_Base` (`extra="forbid"`, lines 18-19):
```python
class FeaturesCfg(_Base):
    spec_version: int = Field(ge=1)
    ...
def load_features_cfg(config_dir: Path | None = None) -> FeaturesCfg:
    d = Path(config_dir) if config_dir else paths.CONFIG_DIR
    return FeaturesCfg(**yaml.safe_load((d / "features.yaml").read_text(encoding="utf-8")))
```
New `LgbmCfg(_Base)` with `origin_stride: int = Field(ge=1)`, `seed`, `params: dict`, `n_estimators`, `early_stopping_rounds`, `buckets: list[tuple[int,int]]`, and `load_lgbm_cfg`. Add `serving` knobs (stale hours = 2, refresh interval) either here or in `config/api.yaml` with its own model; per CLAUDE.md no hard-coded values. NOTE: do not add anything to `feature_spec()` (that would change the spec hash and invalidate `config/baseline3_choice.json` and all long parquets).

---

### `src/swf/api/refresh.py` (scheduled job)

**Analog:** `fetch/openmeteo.py::fetch_live` (141-150) and the error contract in `run` (183-185).

```python
def fetch_live(client, s, *, root, now=None, force=False, sleep=time.sleep) -> Path:
    now = now or datetime.now(UTC)
    dest = root / "openmeteo" / "forecast" / safe_part(s.data.openmeteo.nwp_model) / f"{now:%Y%m%dT%H}.json"
    fetch_to_cache(client, ENDPOINTS["forecast"], live_params(s), dest, summarize=summarize, force=force,
                   min_interval=s.data.openmeteo.min_interval_s, sleep=sleep)
    return dest
```
```python
except (httpx.HTTPError, ValueError, KeyError) as e:
    logger.error("Open-Meteo fetch failed: %s", e)
    return 1
```
`refresh(db, client=None, sleep=time.sleep, now=None)`: `client = client or make_client()` (from `swf.fetch.cache`), call `fetch_live(client, s, root=RAW_DIR, now=now, sleep=sleep)`, read bytes from the returned path, `origin = max(floor_hour(now) - 1h, canon.index[0] + need_h)` (Pitfall 3, `need_h` mirrors `serve_features` line 157), `serve_features(raw, s, cfg, coefs, curve, origin)`, predict per target through the registry, write rows in one transaction. Catch the same three exception types, log with `logging.getLogger("swf.api")`, leave `meta.last_success` untouched. Parameters `client`/`sleep`/`now` exist purely for the MockTransport stale test (Pitfall 5).

Logger idiom: `logger = logging.getLogger("swf.fetch")` at module top (openmeteo.py:18); use `"swf.api"`. UTC log format is configured once in `cli.main` (cli.py:101-103); `swf.api.run` should not reconfigure it.

---

### `src/swf/api/db.py` (sqlite3 WAL repository) - no in-repo analog

Use RESEARCH Pattern 6 / Pitfall 7: `sqlite3.connect(path, timeout=10)` per call; `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL` once at init; parameterized queries only; tables `forecast(run_time, target_time, target, model, p10, p50, p90)` (index on run_time), `history(time, target, value)`, `meta(key, value)`; write 360 rows + history + meta in a single `with conn:` transaction using `INSERT OR REPLACE`, and delete older runs there. Timestamps stored as ISO UTC strings ending `Z`. Atomicity precedent in repo: `tmp` + `os.replace` (`longfmt.py:139-152`). DB path default `DATA_DIR / "app.db"` (add to `core/paths.py`) with injection for tests (`SWF_DB` env or `create_app(db_path, ...)`).

---

### `src/swf/api/schemas.py`

**Analog:** pydantic style in `core/settings.py:18-19, 30-35`:
```python
class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")
class Site(_Base):
    name: str
    latitude: float = Field(ge=-90, le=90)
```
Response models use `AwareDatetime` (Pitfall 8) so `...Z` is emitted. Reuse `Site`, `SolarCfg`, `WindCfg` directly for `/api/site` (`load_settings().site.model_dump(mode="json")`).

---

### `src/swf/api/main.py` (app factory) - no in-repo analog

Follow RESEARCH Pattern 6 (lifespan with `BackgroundScheduler(timezone="UTC")`, `add_job(refresh, "interval", hours=1, id="refresh", max_instances=1, coalesce=True, next_run_time=datetime.now(UTC))`), `create_app(db_path=None, start_scheduler=True, refresh_fn=refresh)`, sync `def` endpoints, `Query(ge=1, le=72)` for `hours`, `Query(ge=1, le=...)` for `days`, StaticFiles mount LAST (Pitfall 9). `/api/metrics` reads `reports/evaluation/leaderboard.csv` with stdlib `csv` (columns written by `report.py` with `_CSV = {"index": False, "float_format": "%.6g", "lineterminator": "\n"}`). Import hygiene: only `swf.core`, `swf.fetch`, `swf.align`, `swf.physics`, `swf.features`, `swf.predict`. `swf.features.build` is clean; do NOT import `swf.evaluate.*` (report imports `swf.coverage.report`, matplotlib lazily).

---

### `src/swf/api/run.py`

**Analog:** `src/swf/features/run.py:28-34` (`run(args: argparse.Namespace) -> int`):
```python
def run(args: argparse.Namespace, notes_path: Path | None = None) -> int:
    cfg = load_features_cfg()
    ...
    return 0
```
Body: `import uvicorn; uvicorn.run("swf.api.main:app", host=args.host, port=args.port, workers=1); return 0`. Import uvicorn inside `run` (keeps `swf.cli` light).

---

### Tests

**API/refresh tests** - analog `tests/test_openmeteo_fetch.py:70-77` and `tests/conftest.py:24-29` (`mock_client`, `no_sleep`, `fixtures_dir`):
```python
def test_live(settings, mock_client, no_sleep, fixtures_dir, tmp_path):
    seen = []
    c = mock_client(_handler(fixtures_dir, "om_hf_sample.json", seen))
    now = datetime(2026, 11, 1, 15, 20, tzinfo=UTC)
    p = om.fetch_live(c, settings, root=tmp_path, now=now, sleep=no_sleep)
```
(`_handler` in that file returns fixture bytes via `httpx.MockTransport`; copy it into conftest as a shared fixture serving `tests/fixtures/om_live_gfs_seamless.json`.) For the stale test use handler that raises `httpx.ConnectError` (RESEARCH Code Examples). Use `tmp_path` DB, `TestClient(create_app(db, start_scheduler=False))` without `with`.

**Refresh end-to-end / parity** - analog `tests/test_features_parity.py:27-56`: uses `settings`, `fixtures_dir`, `load_coefs()`, `load_power_curve(settings)`, `serve_features(raw_bytes, s, cfg, coefs, curve, origin=t)`. The committed fixture has exactly 24 valid origins (line 46). Choose the origin accordingly in tests (fixture window is not "now").

**LGBM train test** - analog `tests/synth.py` (`canon_frame`, `hist_frame(start, days, s, seed)`, `pr_trio(start, days, s)` return synthetic canonical data without network) and `tests/test_evaluate_baselines.py`. Extend `synth.py` rather than adding a new helper module; keep `num_boost_round` ~5. Identity test: `y_res + b3 == y_true` on train rows.

**Real-data test** - analog `tests/test_features_real.py:27-31, 65-67`:
```python
HAVE = (RAW_DIR / "openmeteo").exists() and all((INTERIM_DIR / f"{n}.parquet").exists() for n in GFS)
@pytest.mark.realdata
@pytest.mark.skipif(not HAVE, reason="cached ERA5 raw / GFS interim parquets absent")
```
pytest config: `addopts = "-q -m 'not network and not realdata'"` (pyproject.toml:43).

**Import-hygiene test** (new, RESEARCH API-05): `subprocess.run([sys.executable, "-c", "import swf.api.main, sys; assert 'matplotlib' not in sys.modules and 'torch' not in sys.modules and 'lightgbm' not in sys.modules and 'swf.evaluate' not in sys.modules"])`, same subprocess style as `tests/test_cli.py:5-6`.

**Constraints test analog** for bands: `tests/test_physics_constraints.py` (night zero, RH <= 100 clipping assertions).

---

### `frontend/` - no analog

Scaffold `npm create vite@latest frontend -- --template react-ts`; `App.tsx` fetches `/api/forecast` in `useEffect`, renders a 5-row table (target, unit, first-hours P50, P10-P90 range, model), stale banner, and the Open-Meteo CC BY 4.0 / NASA POWER attribution line (STACK.md). `vite.config.ts`: `server.proxy: {"/api": "http://127.0.0.1:8000"}`. IST conversion in the browser only (CLAUDE.md). Ensure `frontend/node_modules` and `frontend/dist` are git-ignored (check `.gitignore`).

## Shared Patterns

### Feature spec hash guard
**Source:** `src/swf/features/spec.py:101-123` (`artifact_meta`, `assert_spec`)
**Apply to:** registry.json, every lightgbm sidecar, `write_long` (automatic: `longfmt.py:146-149` embeds `artifact_meta(None)`), `registry.load()`.
```python
meta = {"feature_spec_hash": spec_hash(spec)}
if set_name is not None:
    meta |= {"feature_set": set_name, "feature_columns": list(spec["sets"][set_name])}
...
raise ValueError(f"feature spec mismatch: artifact {got} vs current {want}; missing {missing}; extra {extra}")
```

### Physical clipping
**Source:** `src/swf/physics/constraints.py:11-22` (`enforce(df, s)`)
**Apply to:** LightGBM p50 BEFORE scoring/writing to long format, and p10/p50/p90 at serve time. Index must be target times.

### One feature function / one correction function
**Source:** `features/build.py::serve_features`, `align/consistency.py::apply_correction/load_coefs`. Never build a second feature path or refit coefs at serve time.

### Settings from config only
**Source:** `core/settings.py::load_settings` / `load_features_cfg`. Timezone for API-07: `zoneinfo.ZoneInfo(s.site.display_timezone)`. Horizon from `cfg.horizon_max` (72), not literal.

### Raw-cache rule
**Source:** `fetch/openmeteo.py::fetch_live` -> `fetch_to_cache` (tenacity retry, hour-keyed file under `data/raw/openmeteo/forecast/<model>/`). Always go through it.

### Deterministic committed outputs
**Source:** `evaluate/baselines.py:177-187`, `evaluate/report.py:20` (`_CSV` options). No timestamps, sorted keys, `\n` newlines, fixed seeds (`seed`, `deterministic=True`, `force_row_wise=True`, fixed `num_threads` for lightgbm).

### Paths
**Source:** `src/swf/core/paths.py`. Add `MODELS_DIR = REPO_ROOT / "models"` and `DB_PATH = DATA_DIR / "app.db"` rather than building paths inline.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/swf/api/main.py` | controller | request-response | No web code exists; use RESEARCH Pattern 6 |
| `src/swf/api/db.py` | repository | CRUD | No sqlite code exists; use RESEARCH Pitfall 7 |
| APScheduler wiring | scheduler | event-driven | None exists; RESEARCH Pattern 6 (verify `next_run_time` behavior with a 10-line smoke early, per RESEARCH Sources) |
| LightGBM `lgb.train`/`lgb.Dataset`/`early_stopping` | model | batch | No ML trainer yet; RESEARCH Pattern 2 hyperparameters |
| `frontend/**` | component | request-response | No frontend yet |

## Gotchas the planner should carry into plans

- `assemble(..., cov=dict)` needs lead keys 1, 2, 3 even for bucket 1-6; pass the full dict.
- `write_long` / `validate_long` require origin-major, horizon-minor ordering from `grid(origins, range(1,73))`, `target` categories = `TARGETS`, float32 casts (done by `make_long`), and `y_true` equal to `truth` reindexed (checked).
- `with_official` in `evaluate/report.py:38-41` aliases `baseline3_<choice>` to model `baseline3`; the leaderboard picks up `data/processed/predictions/val/lightgbm.parquet` by glob (report.py:33-35). No report change needed.
- Pitfall 3 origin clamp: `serve_features` raises `ValueError` if `origin - 168h < canon.index[0]` (build.py:158). Clamp at refresh.
- `serve_features` returns `(issue_time, horizon)`-indexed 72 rows; bucket predictors slice by the `horizon` level/column.
- `swf.predict` must not import `swf.evaluate`; `TARGETS` is available from `swf.features.spec`.

## Metadata

**Analog search scope:** `src/swf/**`, `tests/**`, `config/**`, `pyproject.toml`
**Files read:** cli.py, evaluate/{baselines,longfmt,report(1-120)}.py, fetch/openmeteo.py, physics/constraints.py, features/{build,spec,history,run}.py, core/{settings,paths}.py, tests/{conftest,synth,test_cli,test_features_parity,test_features_real,test_openmeteo_fetch(grep)}.py
**Pattern extraction date:** 2026-11-07
