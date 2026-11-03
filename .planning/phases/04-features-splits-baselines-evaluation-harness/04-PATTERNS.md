# Phase 4: Features, Splits, Baselines & Evaluation Harness - Pattern Map

**Mapped:** 2026-11-03
**Files analyzed:** 24 new/modified (14 src/config, 10 test/fixture)
**Analogs found:** 22 / 24 (the two-axis builder and the long-format validator have only partial analogs)

All paths relative to `F:\Claude first project`. Line numbers refer to the files as of commit 0532096.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `config/features.yaml` | config | n/a | `config/validation.yaml` | exact |
| `src/swf/core/settings.py` (add `FeaturesCfg`, `load_features_cfg`) | config model | n/a | same file: `ValidationCfg` / `load_validation_cfg` (l.203-235) | exact |
| `src/swf/core/paths.py` (add `PROCESSED_DIR`) | config | n/a | same file | exact |
| `src/swf/features/spec.py` | utility | transform (hash) | none for hash; `align/consistency.save_coefs` for canonical JSON | partial |
| `src/swf/features/history.py` | service | transform | `physics/simulate.py::simulate` + `align/consistency.apply_correction` | exact (composition) |
| `src/swf/features/build.py` | service | transform (index gather) | `align/clean.py` (hourly reindex) + `physics/common.py` | partial |
| `src/swf/features/covariates.py` | service | transform | `align/adapters.py::load_source` + `apply_correction` | role-match |
| `src/swf/features/splits.py` | utility | transform | none; pydantic cfg pattern from `core/settings.py` | no analog (pure fn) |
| `src/swf/evaluate/longfmt.py` | utility/validator | file-I/O (parquet) | `align/canon.py::validate_canon` | role-match |
| `src/swf/evaluate/baselines.py` | service | batch | `physics/simulate.py::simulate`, `run()` writing parquet | role-match |
| `src/swf/evaluate/metrics.py` | utility | transform | `validate/metrics.py::error_stats` | exact |
| `src/swf/evaluate/report.py` (+ `run`) | CLI handler / report | batch, file-I/O | `validate/run.py` + `validate/plots.py` + `coverage/report.write_auto_block` | exact |
| `config/baseline3_choice.json` (D-03a frozen) | config artifact | file-I/O | `config/bias_correction.json` via `save_coefs`/`load_coefs` | exact |
| `src/swf/cli.py` (add `features`, `baselines`, `evaluate`) | CLI | request-response | same file l.62-77 | exact |
| `docs/data_notes.md` AUTO:features / AUTO:evaluation | doc | file-I/O | `write_auto_block` callers | exact |
| `tests/synth.py` (extend) | test helper | n/a | same file | exact |
| `tests/test_features_{spec,build,history,leakage,parity}.py` | test | n/a | `tests/test_align_consistency.py`, `tests/test_validate_core.py` | role-match |
| `tests/test_splits.py` | test | n/a | `tests/test_validate_core.py` | role-match |
| `tests/test_evaluate_{baselines,longfmt,metrics,report}.py` | test | n/a | `tests/test_validate_core.py`, `tests/test_validate_real.py` (realdata) | role-match |

## Pattern Assignments

### `config/features.yaml` + `FeaturesCfg` in `core/settings.py` (config)

**Analog:** `config/validation.yaml`, `src/swf/core/settings.py` (`_Base` l.18-19; `ValidationCfg` l.203-206; `load_validation_cfg` l.233-235).

**Model base and validators** (settings.py l.18-19, 121-141):
```python
class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AlignCfg(_Base):
    max_gap_h: int = Field(ge=1, le=6)
    fit_years: tuple[int, int]
    ...
    @field_validator("fit_years")
    @classmethod
    def _years(cls, v): 
        if v[0] > v[1] or v[0] < 2001:
            raise ValueError("...")
        return v
```
**Loader** (settings.py l.233-235), copy verbatim with new name and file:
```python
def load_validation_cfg(config_dir: Path | None = None) -> ValidationCfg:
    d = Path(config_dir) if config_dir else paths.CONFIG_DIR
    return ValidationCfg(**yaml.safe_load((d / "validation.yaml").read_text(encoding="utf-8")))
```
**YAML style:** top comment line naming the requirement IDs, inline `# reason` comments, lists as `[a, b]` (validation.yaml l.1, 9, 31-33). Keep new keys out of site.yaml/plant.yaml (CONTEXT). Put model names through a regex like `_MODEL_RE = ^[a-z0-9_]+$` (settings.py l.14, `_check_model_name` l.22-27) because `model` becomes a file name (RESEARCH security table).

**Paths:** `core/paths.py` has no `PROCESSED_DIR`. Add `PROCESSED_DIR = DATA_DIR / "processed"` next to `INTERIM_DIR` (paths.py is 8 lines of constants; `data/` is gitignored). `REPORTS_DIR` already exists.

---

### `src/swf/features/history.py` (service, transform)

**Analog:** `src/swf/physics/simulate.py::simulate` (l.113-123 in the printed numbering; weather in, `t1_kw`/`t5_kw` out, already ends in `enforce`) and `align/consistency.apply_correction` (l.105-124).

**Imports pattern** (from simulate.py header):
```python
import pandas as pd
from swf.physics.constraints import enforce
from swf.physics.solar import ac_cap_kw, pdc0_w, simulate_solar
from swf.physics.wind import load_power_curve, simulate_wind
```
**Core pattern:** `history_frame(canon, s, coefs, curve)` = `corrected = apply_correction(canon, coefs, s)`; `energy = simulate(corrected, s, curve)`; assemble columns `rh, ghi, ws10` from `corrected` plus `t1_kw, t5_kw`; then `enforce(...)` (constraints.py l.201-212: clips rh 0-100, ghi/ws10 >= 0, zeroes `t1_kw`/`ghi` at night via `is_night`). `enforce` ignores absent columns (`if col in out`), so it is safe on the 5-column frame. `simulate(weather, s, curve=None)` takes `curve` as optional; `load_power_curve(s)` is how `run()` gets it (simulate.py `run`, `energy = simulate(pd.read_parquet(src), s, load_power_curve(s))`).

**Truth frame (y_true)** is the OTHER path: `pd.read_parquet(INTERIM_DIR / "weather_nasa.parquet")[["rh","ghi","ws10"]]` joined to `INTERIM_DIR / "energy_sim.parquet"[["t1_kw","t5_kw"]]`. Column keys: `swf.physics.constraints.TARGET_COLS = {"t1": "t1_kw", "t2": "rh", "t3": "ghi", "t4": "ws10", "t5": "t5_kw"}` (l.198), use it as the single list of target names rather than re-typing them.

**Note for planner:** `apply_correction` is the single train/serve function (its docstring says so); do not wrap or re-fit it. `apply_correction` only calls `is_night` when `"ghi" in coefs["variables"]` (consistency.py l.112), so the committed rh/ws10/ws_hub coefficients leave GHI untouched.

---

### `src/swf/features/build.py` (service, transform: two-axis origin/target)

**Analog (partial):** no existing rolling/lag code. Reuse of geometry from `physics/common.py`:

```python
def midpoints(index): return index + pd.Timedelta(minutes=30)          # l.65-66
def solar_position(index, s) -> pd.DataFrame:                           # l.69-71
    sp = location(s).get_solarposition(midpoints(index))
    return sp.set_axis(index)
def clearsky(index, s) -> pd.DataFrame:                                 # l.78-80
    cs = location(s).get_clearsky(midpoints(index), model="ineichen")
    return cs.set_axis(index)
```
Use `solar_position(idx, s)["zenith"]`/`["azimuth"]` and `clearsky(idx, s)["ghi"]` on the target-axis index (once for the whole hourly range; RESEARCH says about 7 s each). Never compute from `index` without these helpers (they apply the +30 min interval-midpoint convention).

**Gap-free hourly index guarantee:** `align/clean.py::clean` (l.64-72) reindexes to `pd.date_range(..., freq="h", tz="UTC", name="time")`; `align/canon.py::validate_canon` (l.30-50 in canon.py) enforces tz-aware UTC, name `"time"`, unique, sorted, on-the-hour. Copy its checks as the asserts the RESEARCH Pitfall 2 asks for before `get_indexer`:
```python
if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None or str(idx.tz) != "UTC":
    raise ValueError("index must be a tz-aware UTC DatetimeIndex")
if not idx.is_monotonic_increasing: raise ValueError("index not sorted")
```
Add: raise when `get_indexer` returns -1 (never NaN-fill) and when the serving window is shorter than 169 h.

**Origin-table and `gather`:** the code in RESEARCH Pattern 1 (lines 175-191) is the pattern; no repo analog. dtype `float32`, pandas 3 copy-on-write: build `pd.DataFrame(parts, index=...)` from a dict, no chained assignment.

---

### `src/swf/features/covariates.py` (service, transform)

**Analog:** `align/adapters.py::load_source(source, s, raw_root)` (l.117) and `openmeteo_canon(raw, s, lead=None)` (l.78-91). The interim parquets are already clean canonical frames; read them directly:
```python
pd.read_parquet(INTERIM_DIR / "weather_gfs_pr_d1.parquet")   # also d2, d3, weather_gfs_hf
```
then `apply_correction(df, load_coefs(), s)` (consistency.py l.98-124). Lead mapping `k = -(-h // 24)` per RESEARCH. Covariate columns = the 12 `CANON_COLS` minus none, plus sin/cos of `wd10`, `wd_hub` (CANON_COLS in canon.py l.5-8). The canonical contract is float64; features are cast to float32 after.

---

### `src/swf/features/spec.py` (utility)

**Analog (partial):** deterministic JSON writer in `align/consistency.save_coefs` (l.91-95):
```python
text = json.dumps(coefs, indent=2, sort_keys=True) + "\n"
tmp = Path(str(path) + ".tmp")
tmp.write_text(text, encoding="utf-8", newline="\n")
os.replace(tmp, path)
```
Copy `sort_keys=True` and `newline="\n"`; for the hash use `json.dumps(spec, sort_keys=True, separators=(",", ":"))` then `hashlib.sha256(...).hexdigest()[:16]`. Include `sha256(config/bias_correction.json bytes)` and `loss_pct`/`dc_ac_ratio` in the hash input (RESEARCH Pitfall 6). Hash style precedent: `coverage/report.py` already imports `hashlib`; `tests/test_validate_real.py` l.16-17 uses `hashlib.sha256(plant.read_bytes()).hexdigest()`.

---

### `src/swf/features/splits.py` (utility)

No analog. Pure functions over `pd.date_range(..., freq="h", tz="UTC")`; boundaries from `FeaturesCfg`. Counts to assert are in RESEARCH (201,384 / 24,048 / 8,712 / 8,688). Logging pattern: `log = logging.getLogger("swf.validate")` (validate/run.py l.15 in file numbering) so use `logging.getLogger("swf.features")`; the CLI configures UTC time formatting (cli.py l.86-87, `logging.Formatter.converter = time.gmtime`).

---

### `src/swf/evaluate/metrics.py` (utility, transform)

**Analog:** `src/swf/validate/metrics.py` (whole file, 18 lines). Leave untouched (Phase 3 tests use its keys `rmse_kw`, `mae_kw`, `mbe_pct`, `nrmse_pct`).
```python
def error_stats(sim, act, norm: float) -> dict:
    sim, act = np.asarray(sim, float), np.asarray(act, float)
    m = ~np.isnan(sim) & ~np.isnan(act)
    sim, act = sim[m], act[m]
    rmse = float(np.sqrt(np.mean((sim - act) ** 2)))
    return {"n": int(m.sum()), "rmse_kw": rmse, "mae_kw": float(np.mean(np.abs(sim - act))),
            "mbe_pct": float(np.mean(sim - act) / np.mean(act) * 100), "nrmse_pct": rmse / norm * 100}
```
Copy the complete-pairs masking and `nrmse = rmse / norm * 100`; generalise key names (`rmse`, `mae`, `mbe`, `norm`, `norm_kind`). Norms: `ac_cap_kw(s)` from `swf.physics.solar` (used in simulate.py and constraints.py) and `s.wind.rated_kw`. Daytime mask: `solar_position(target_index, s)["zenith"] < 85` (common.py l.69-71). numpy-only (no sklearn; consistency.py docstring l.3 states the same rule).

---

### `src/swf/evaluate/longfmt.py` (validator + parquet I/O)

**Analog:** `align/canon.py::validate_canon` (l.30-50): raises `ValueError` with exact expected vs actual, one check per contract clause, returns the frame.
```python
def validate_canon(df):
    if tuple(df.columns) != CANON_COLS:
        raise ValueError(f"columns must be exactly {CANON_COLS}, got {tuple(df.columns)}")
    bad = [c for c in df.columns if df[c].dtype != "float64"]
    if bad: raise ValueError(f"non-float64 dtypes: {bad}")
    ...
    if not idx.is_unique: raise ValueError("duplicate index labels")
    return df
```
Mirror for `validate_long`: exact `LONG_COLS`, dtypes (`horizon` int16, `target`/`model` category, p's float32), `target_time == issue_time + horizon h`, horizon in 1..72, no duplicate `(issue_time, horizon, target, model)`. Parquet write: `df.to_parquet(path)` precedent (simulate.py `run`, `energy.to_parquet(INTERIM_DIR / "energy_sim.parquet")`); add `compression="zstd"` and `mkdir(parents=True, exist_ok=True)`. Atomic write precedent: `save_coefs` tmp + `os.replace`.

---

### `src/swf/evaluate/baselines.py` (service, batch)

**Analog:** `physics/simulate.py::run` (shape of a batch handler: load interim parquet, compute, write, print) and `simulate()` for the chain.
```python
def run(args) -> int:
    s = load_settings()
    src = INTERIM_DIR / "weather_nasa.parquet"
    if not src.exists():
        print("run `python -m swf build-weather` first")
        return 1
    ...
    return 0
```
Copy: missing-input message naming the command that produces it, return code 1; return 0 on success. Baseline-3 chain: `chain(df) = simulate(df, s, curve)` for `t1_kw`/`t5_kw` plus `rh, ghi, ws10` from the (corrected or raw) GFS frame, then `enforce`. Run once per variant per lead table (not per origin), then expand to long format by lookup. Corrected variant: `apply_correction(gfs, load_coefs(), s)`.

**D-03a frozen choice:** store `{target: "corrected"|"raw"}` in `config/baseline3_choice.json`, written with the `save_coefs` pattern (sorted keys, trailing newline, tmp+replace) and read with a `load_coefs`-style loader that raises `FileNotFoundError` with the producing command (consistency.py l.98-102). Selection runs on val only and the file is written before any test scoring; make `evaluate` refuse to score `test` if the file is absent.

---

### `src/swf/evaluate/report.py` (CLI handler, report/plots)

**Analog:** `src/swf/validate/run.py` (entire structure) + `validate/plots.py` + `coverage/report.py`.

**Imports** (validate/run.py l.1-15):
```python
import json, logging
from pathlib import Path
import pandas as pd
from swf.core.paths import DOCS_DIR, REPORTS_DIR
from swf.core.settings import load_settings
from swf.coverage.report import _table, write_auto_block
log = logging.getLogger("swf.validate")
OPENER = "Generated by `python -m swf validate`. Do not edit inside this block."
```
**Handler with injectable output paths (for tests)** (validate/run.py last lines):
```python
def run(args, out_dir: Path | None = None, notes_path: Path | None = None) -> int:
    s = load_settings()
    ...
    write_outputs(metrics, series, out_dir or REPORTS_DIR / "validation", notes_path or DOCS_DIR / "data_notes.md", caps)
    print(render_validation(metrics))
    return 0 if gate(metrics) else 1
```
Copy the `out_dir`/`notes_path` keyword defaults so tests write into `tmp_path`. Output dir: `REPORTS_DIR / "evaluation"`.

**AUTO block** (coverage/report.py l.194-208): `write_auto_block(DOCS_DIR / "data_notes.md", block, name="evaluation")`; names must match `[a-z_]+`; tables via `_table(head, rows)` (l.18). Two new names: `features`, `evaluation`.

**Plots** (validate/plots.py l.1-43, lazy import and determinism):
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
...
fig.savefig(path, dpi=120, metadata={"Software": None})
plt.close(fig)
```
Import matplotlib inside the function only.

**Deterministic CSV:** sort rows, `to_csv(..., float_format="%.6g", lineterminator="\n")`, no timestamps (CONTEXT determinism rule).

---

### `src/swf/cli.py` (add `features`, `baselines`, `evaluate`)

**Analog:** same file, `build-weather` / `simulate-energy` / `validate` registrations:
```python
sub.add_parser("validate", help="physics validation vs Kaggle plants -> reports/validation + data_notes").set_defaults(
    handler=lambda a: _run("swf.validate.run", a)
)
```
Add three one-liners the same way: `_run("swf.features.run", a)` (needs a `run` module or `run` in `swf/features/run.py`; keep `swf/features/__init__.py` import-free so the lazy import holds), `_run("swf.evaluate.baselines", a)` (module exposes `run(args) -> int`), `_run("swf.evaluate.report", a)`. Tests of CLI parsing live in `tests/test_cli.py` (extend it).

---

### Tests

**Config test analog:** `tests/test_validate_core.py` l.1-40: `_bad(tmp_path, mutate)` copies the committed yaml, mutates it, writes it to `tmp_path`, then `pytest.raises(ValidationError)` through `load_*_cfg(tmp_path)`. Reuse for `features.yaml` (extra key, reversed split dates, bad model name).

**Synthetic data:** `tests/synth.py` (`canon_frame(start, days, s, convention="start")` returns a 12-column canonical frame with exact clear-sky GHI; constants `_MET`). Extend with a `hist_frame` (5 target columns, built via `history_frame(canon_frame(...))`) and a fake PR trio (three shifted/perturbed canon frames). `settings` fixture comes from `tests/conftest.py` (`load_settings()`), `fixtures_dir` fixture points to `tests/fixtures/` (parity test uses `om_live_gfs_seamless.json`).

**Index + correction test shape:** `tests/test_align_consistency.py` l.1-30 builds `IDX = pd.date_range("2023-01-01", "2024-12-31 23:00", freq="h", tz="UTC", name="time")` and a frame from `clearsky(IDX, settings)`; copy that idiom for long synthetic ranges.

**Realdata tests:** `tests/test_validate_real.py` l.13-15:
```python
@pytest.mark.realdata
@pytest.mark.skipif(not (RAW_DIR / "kaggle" / "T1.csv").exists(), reason="Kaggle files absent")
def test_real_validation(tmp_path):
```
Use `INTERIM_DIR / "weather_gfs_pr_d1.parquet"` etc. in the skipif. It also shows the pattern of hashing an input file before the run and asserting it is unchanged (l.16-20), and the way `run(argparse.Namespace(), out_dir=tmp_path/..., notes_path=...)` is called. Default pytest opts: `-q -m 'not network and not realdata'` (pyproject.toml l.43); run realdata with `-o addopts="" -m realdata`.

**Identity test (EVAL-03):** baseline 3 chain fed NASA weather must equal `energy_sim.parquet` (RESEARCH Pitfall 5); compare with `pd.testing.assert_frame_equal`.

## Shared Patterns

### One train/serve correction function
**Source:** `src/swf/align/consistency.py::apply_correction` (l.105-124), `load_coefs` (l.98-102).
**Apply to:** `features/history.py`, `features/covariates.py`, `evaluate/baselines.py`. Never re-implement scaling; GHI is not in `bias_correction.json` so it passes through.

### Physics chain with constraints
**Source:** `src/swf/physics/simulate.py::simulate`, `physics/constraints.py::enforce` (l.201-212), `TARGET_COLS` (l.198).
**Apply to:** `history.py`, `baselines.py`. Capacities from `ac_cap_kw(s)` and `s.wind.rated_kw`, never literals (CLAUDE.md rule).

### Handler contract and lazy imports
**Source:** `src/swf/cli.py` `_run(module, args)` l.24-25; handlers `run(args) -> int`; print a "run `python -m swf <cmd>` first" hint and return 1 when an input is missing.
**Apply to:** all three new CLI handlers.

### Canonical frame validation (fail loud)
**Source:** `src/swf/align/canon.py::validate_canon` (UTC tz-aware, name `time`, unique, sorted, on-the-hour, no sentinels).
**Apply to:** `build.py` (before `get_indexer`), `longfmt.py`.

### Determinism of committed outputs
**Source:** `save_coefs` (sorted keys, `newline="\n"`), `write_auto_block` (`newline="\n"`, idempotent), `plots.scatter` (`metadata={"Software": None}`, `Agg`).
**Apply to:** `leaderboard.csv`, `breakdown.csv`, `gfs_bias_2024.csv`, PNGs, `baseline3_choice.json`, AUTO blocks.

### Pydantic `extra=forbid` config, no hard-coded site/plant values
**Source:** `core/settings.py::_Base`; CLAUDE.md "Site/plant values come from config/*.yaml".
**Apply to:** `features.yaml` (lags, windows, horizons, split dates, buckets, season months, covariate columns, baseline names).

### Serving-image purity
**Source:** `align/consistency.py` docstring ("numpy/pandas only: the serving image has no sklearn"), `validate/plots.py` lazy matplotlib.
**Apply to:** `swf.features.*` and `swf.evaluate.metrics`/`longfmt` import only numpy, pandas, pvlib (via `swf.physics.common`), stdlib.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/swf/features/splits.py` | utility | transform | No existing split or purge code; pure date arithmetic, use RESEARCH counts as test oracle |
| `src/swf/features/build.py` (lag/rolling/gather core) | service | transform | No existing shift/rolling code; use RESEARCH Pattern 1 and the leakage test in RESEARCH Code Examples |
| `tests/test_features_leakage.py`, `test_features_parity.py` | test | n/a | New test styles; use RESEARCH code examples; parity fixture `tests/fixtures/om_live_gfs_seamless.json` already committed (cache helpers: `swf/fetch/cache.py`) |

## Metadata

**Analog search scope:** `src/swf/**`, `tests/**`, `config/**`, `pyproject.toml`, `.gitignore`.
**Files scanned:** about 45 tracked files listed; 15 read in full or in relevant ranges.
**Pattern extraction date:** 2026-11-03
**Gotchas for planner:** (1) `core/paths.py` lacks `PROCESSED_DIR`; add it. (2) `validate_canon` requires float64, feature tables are float32, so cast only after assembly. (3) `enforce` ignores columns it does not know, so the 5-column history frame is safe. (4) `write_auto_block` names allow only `[a-z_]+`.
