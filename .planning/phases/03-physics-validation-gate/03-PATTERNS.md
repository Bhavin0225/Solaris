# Phase 3: Physics Validation Gate - Pattern Map

**Mapped:** 2026-11-03
**Files analyzed:** 12 (new/modified)
**Analogs found:** 11 / 12

Locked user decisions (override RESEARCH S5): keep `config/plant.yaml` `loss_pct: 14`; report the tuned value (about 9) alongside only. Do NOT edit plant.yaml and do NOT re-run `simulate-energy`. Plant 2 is a documented non-gating miss.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/swf/physics/solar.py` (modify: extract `ac_from_poa`) | service | transform | itself, lines 39-48 | exact |
| `config/validation.yaml` (new) | config | n/a | `config/plant.yaml` | role-match |
| `src/swf/core/settings.py` (modify: add `ValidationCfg` + loader) | model/config | transform | `AlignCfg`/`WindCfg` + `load_settings` | exact |
| `src/swf/core/paths.py` (modify: add `REPORTS_DIR`) | config | n/a | existing `DOCS_DIR` line | exact |
| `src/swf/validate/__init__.py` | package marker | n/a | `src/swf/physics/__init__.py` | exact |
| `src/swf/validate/kaggle.py` (parse + metrics, pure) | service | file-I/O + transform | `physics/wind.py::build_power_curve` | role-match |
| `src/swf/validate/plots.py` (lazy matplotlib) | utility | file-I/O | none | no analog |
| `src/swf/validate/run.py` (CLI handler) | controller | batch / file-I/O | `src/swf/physics/simulate.py::run` | exact |
| `src/swf/cli.py` (modify: `validate` subparser) | route | request-response | `simulate-energy` registration | exact |
| `tests/test_validate_*.py` (parse, tune, wind, outputs) | test | n/a | `tests/test_physics_wind.py` | exact |
| `tests/test_validate_real.py` | test | file-I/O | `tests/test_pipeline.py` lines 79+ (`@pytest.mark.realdata`) | exact |
| `tests/test_cli.py` (modify: add `validate` to the command list) | test | n/a | itself, line 12 | exact |

## Pattern Assignments

### `src/swf/physics/solar.py` (refactor; service, transform)

**Analog:** itself (lines 39-48). Extract the post-POA tail so validation and production share it. `simulate_solar` output must stay identical (`tests/test_physics_solar.py` stays green).

Current tail to extract (lines 41-48):
```python
poa = poa_global(df, s)
tc = temperature.faiman(poa, df["temp"], df["ws10"])
dc = pvsystem.pvwatts_dc(poa, tc, s.solar.dc_kwp * 1000, s.solar.gamma_pdc)
dc = dc * (1 - s.solar.loss_pct / 100)
ac = inverter.pvwatts(dc, pdc0_w(s), eta_inv_nom=s.solar.eta_inv_nom) / 1000
night = solar_position(df.index, s)["zenith"] > 90
ac = ac.where(~night, 0.0)
```
Target shape: `ac_from_poa(poa, tc, s) -> Series` (kW) containing only the `pvwatts_dc` -> loss -> `inverter.pvwatts` / 1000 lines. `simulate_solar` calls it, then applies the night mask (the night mask stays in `simulate_solar`, since it needs Davanagere geometry).
Validation needs per-plant `dc_kwp`, `loss_pct`, and `pdc0`. `ac_from_poa` reads them from `s.solar` and `pdc0_w(s)`. So the validator must pass a settings copy with the plant anchor, e.g. `s.model_copy(update={"solar": s.solar.model_copy(update={"dc_kwp": ..., "loss_pct": ...})})`. Pydantic models here are not frozen (only `extra="forbid"`), so `model_copy` works. Alternative is to give `ac_from_poa` explicit kwargs (dc_kwp, loss_pct) with `s` supplying only gamma/eta/ratio. Pick one; the copy approach needs no signature churn.

### `config/validation.yaml` + `ValidationCfg` in settings.py (config, pydantic)

**Analog:** `config/plant.yaml` (flow-style YAML, top-level key per section) and `settings.py`.

YAML style (plant.yaml lines 1-5):
```yaml
solar: {dc_kwp: 1000, tilt_deg: 15, ...}
wind: {rated_kw: 3600, ...}
```
Model pattern (settings.py lines 17-18, 120-139):
```python
class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AlignCfg(_Base):
    max_gap_h: int = Field(ge=1, le=6)
    ...
    @field_validator("thresholds")
    @classmethod
    def _thr(cls, v): ...
```
Loader pattern (lines 160-164): `yaml.safe_load((d / "x.yaml").read_text(encoding="utf-8"))`.
CAUTION: `Settings` is `extra="forbid"` and `load_settings` does `Settings(**site, **plant)`. Do NOT add a `validation` key to plant.yaml/site.yaml. Add a separate `load_validation_cfg(config_dir=None)` returning a `ValidationCfg(_Base)` (loss grid 8..20, tune_end, irr threshold 0.02, nrmse targets 10/14, n_inverters 22, wind slices, wind normalisation 3600 via `s.wind.rated_kw` not duplicated). Keep `Settings` untouched.

### `src/swf/core/paths.py` (modify)

Add next to line 8: `REPORTS_DIR = REPO_ROOT / "reports"`; outputs go to `REPORTS_DIR / "validation"`. `run` must take an injectable out dir for tests.

### `src/swf/validate/kaggle.py` (service, file-I/O + transform)

**Analog:** `src/swf/physics/wind.py::build_power_curve` (lines 18-25): explicit encoding, column selection, explicit date format that fails loud.
```python
df = pd.read_csv(t1_csv, encoding="utf-8-sig")
df = df[["Date/Time", "Wind Speed (m/s)", "Theoretical_Power_Curve (KWh)"]]
pd.to_datetime(df["Date/Time"], format="%d %m %Y %H:%M")  # fail loud on a wrong date order
```
(Header `Wind Direction (°)` is mojibake-prone; select by name only for the columns above, or rename positionally. `build_power_curve` already avoids the direction column.)

File location pattern: `from swf.fetch.kaggle import require_kaggle_files` (kaggle.py lines 70-75), returns `dict[name -> Path]` keyed by `s.kaggle.expected_rows` names (`T1.csv` plus the Plant 1/2 generation and weather file names; read those from `config/site.yaml` kaggle.expected_rows rather than hard-coding).
```python
files = require_kaggle_files(s)
```
Wind simulation reuse (wind.py lines 45-53, do not copy): `simulate_wind(df, s, curve)` with df columns `ws_hub, pressure, temp`; call with `pressure=1013.25, temp=15.0`.
Plant 1 generation uses `%d-%m-%Y %H:%M`; others ISO. Always pass `format=`. Assert the span (15 May to 17 Jun 2020).
Keep this module free of matplotlib imports. Pure functions: `nrmse(sim, act, norm)`, `daytime_mask`, `sum_ac_full_inverters`, `tune_loss(grid)`, `wind_metrics(slice)`.

### `src/swf/validate/plots.py` (utility) - NO ANALOG

No plotting code exists in `src/`. Use RESEARCH rule: `import matplotlib; matplotlib.use("Agg")` inside the function, never at module load (serving image stays matplotlib-free; matplotlib is in the `train` extra only). Tests use `pytest.importorskip("matplotlib")`.

### `src/swf/validate/run.py` (controller, batch)

**Analog:** `src/swf/physics/simulate.py` lines 1-13 and 82-93.

Imports/OPENER pattern:
```python
from swf.core.paths import CONFIG_DIR, DOCS_DIR, INTERIM_DIR
from swf.core.settings import load_settings
from swf.coverage.report import _table, write_auto_block

OPENER = "Generated by `python -m swf simulate-energy`. Do not edit inside this block."
```
Use OPENER = "Generated by `python -m swf validate`. Do not edit inside this block."

Handler pattern (lines 82-93):
```python
def run(args) -> int:
    s = load_settings()
    ...
    block = render_physics(energy, s)
    write_auto_block(DOCS_DIR / "data_notes.md", block, name="physics")
    print(block)
    return 0
```
Use `name="validation"` (must match `[a-z_]+`, per `write_auto_block` line 196). Tables: `L += _table(["head", ...], [[...], ...])` (report.py lines 18-21; returns a list of lines ending in "" so `L +=` it). Render pattern builds `L = [OPENER, "", ...]` then `"\n".join(L)`.
metrics.json: `json.dumps(..., indent=2, sort_keys=True)`, write with `encoding="utf-8"`, `newline="\n"` (same as `write_auto_block` lines 207-208).
Hand-written justification text (Plant 2 cause, 14-vs-9 loss note, POA-not-GHI caveat, "empirical curve is re-binned manufacturer curve") belongs outside the AUTO block in `docs/data_notes.md`, since the block is overwritten on rerun.
Pass: `run` must NOT write `config/plant.yaml` or `INTERIM_DIR/energy_sim.parquet`. Report `loss_pct_tuned` and also the nRMSE at the configured 14.
Exit code: return 0 on Plant 1 and wind gates passing; return 1 if gating fails (Plant 2 never affects the code).

### `src/swf/cli.py` (route)

**Analog:** lines 75-77, `simulate-energy` registration:
```python
sub.add_parser("simulate-energy", help="NASA weather -> simulated T1/T5 kW + physics notes").set_defaults(
    handler=lambda a: _run("swf.physics.simulate", a)
)
```
Add `sub.add_parser("validate", help="...").set_defaults(handler=lambda a: _run("swf.validate.run", a))`. `_run` lazy-imports (line 24-25). Update `tests/test_cli.py` line 12 command list with `"validate"`.

### Tests (`tests/test_validate_*.py`)

**Analog:** `tests/test_physics_wind.py`.
- Synthetic CSV via `tmp_path` with header constant + `write_text(..., encoding="utf-8-sig")` (lines 11-17).
- `settings` fixture from `tests/conftest.py` (`load_settings()`).
- Synthetic frame helper `_df(ws, p=1013.3, t=15.0)` and `CURVE` DataFrame (lines 48-54); density identity: `abs(air_density(1.225*287.05*288.15/100, 15) - RHO0) < 1e-9`.
- Bad-date test via `pytest.raises(ValueError)` (lines 29-31).
- Real-data tests: `@pytest.mark.realdata` (excluded by default via pyproject addopts line 43; opt in with `pytest -m realdata`; see `tests/test_pipeline.py` line 79+ for skip-if-absent style, `raw_root` fixture in conftest lines 37-41).
- Loss recovery test: generate series with `ac_from_poa` at a known loss, assert grid argmin equals it.

## Shared Patterns

### Config-driven, no hard-coding
Source: `swf/core/settings.py`. Apply to all validate modules: gamma, eta, dc_ac_ratio from `s.solar`; wind rated/availability from `s.wind`; thresholds and grid from `validation.yaml`.

### Kaggle file guard
Source: `swf/fetch/kaggle.py::require_kaggle_files` (lines 70-75). Raises SystemExit with manual steps; never download or modify `data/raw/kaggle`.

### AUTO block output
Source: `swf/coverage/report.py::write_auto_block` (line 194) and `_table` (line 18). Apply to run.py.

### Lazy imports
Source: `cli.py::_run` and docstring line 1. `swf.validate` must never be imported by the API.

### UTC rule
Plant timestamps are local clock; for the UTC-internal rule use `tz_localize("Asia/Kolkata").tz_convert("UTC")` (RESEARCH A1). Scoring is timezone-independent.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/swf/validate/plots.py` | utility | file-I/O | No matplotlib code in the repo; follow RESEARCH lazy-Agg rule |

## Metadata

**Analog search scope:** `src/swf/**`, `tests/`, `config/`
**Files read:** solar.py, wind.py, simulate.py, cli.py, settings.py, fetch/kaggle.py, report.py (grep), test_physics_wind.py, conftest.py, test_cli.py, plant.yaml
**Pattern extraction date:** 2026-11-03
