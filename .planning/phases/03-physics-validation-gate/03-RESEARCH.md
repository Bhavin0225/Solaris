# Phase 3: Physics Validation Gate - Research

**Researched:** 2026-11-03
**Domain:** Offline validation of pvlib solar chain and wind power-curve chain against Kaggle plant/SCADA data
**Confidence:** HIGH (all numbers below were computed this session from the actual Kaggle files and the repo's own chain; only plant nameplate/location/timezone are ASSUMED)

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists (user chose to plan without discuss-phase). Binding inputs are CLAUDE.md, REQUIREMENTS VAL-01..VAL-04, and ROADMAP Phase 3 success criteria. Every "Decision" below is a recommendation for the planner to lock.

### Locked Decisions
None from discuss-phase.

### Claude's Discretion
All open questions (plant choice, drive mode, tuning split, nRMSE definition, wind protocol, outputs).

### Deferred Ideas (OUT OF SCOPE)
None recorded. Anti-features per SUMMARY: Kaggle data is never an ML target.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VAL-01 | Parse Kaggle solar (dayfirst, AC summed per timestamp, IRRADIATION units), tune loss % in 8-20% on daytime nRMSE | Parsing facts, units finding, tuning protocol (Decisions S1-S5) |
| VAL-02 | Solar daytime nRMSE vs <=10%, or written justification | Plant 1 gives ~3.1% (passes); Plant 2 ~12.9% (explained by inverter dropouts) |
| VAL-03 | Wind nRMSE vs <=14%, not worse than 13.0% manufacturer reference | 13.0% reproduced exactly; sim 12.1% full year / 12.3% on reference slice (Decisions W1-W4) |
| VAL-04 | Scatter plots + metrics.json in reports/validation/ | Output layout, matplotlib availability |
</phase_requirements>

## Summary

The phase is small and low-risk: both gates pass on the real data with the existing chain. Three facts reshape the plan versus the brief. (1) **The wind circularity trap does not exist as feared**: `config/power_curve.csv` is built from the `Theoretical_Power_Curve (KWh)` column (the manufacturer curve, re-binned), not from `LV ActivePower`. Comparing it with `LV ActivePower` is out-of-sample for the measured signal. The 13.0% reference is reproduced exactly (13.08% with the raw column on 19 Oct-31 Dec; PRD RMSE 470.7 vs 470.9 here). The only LV-derived quantity is the availability scalar (config 0.035 from PRD, not re-fitted). (2) **Loss % and dc_kwp are not separately identifiable** from plant data (only (1-loss)*dc_kwp is), and normalising each series by its own max makes loss tuning degenerate. The plan must fix a capacity anchor independent of loss and state this caveat. (3) **Kaggle `IRRADIATION` is plane-of-array in kW/m2** (max 1.22; daily max is 1.07x clear-sky GHI median at 14.8N), so the sensor-driven validation tests the DC/temperature/loss/inverter part of the chain, not Perez transposition. Plant 2 has heavy inverter dropouts and will miss 10%; that is an acceptable, documented result per the roadmap.

**Primary recommendation:** Gate on Plant 1 (22 inverters, clean), driving `pvwatts_dc -> loss -> inverter.pvwatts` with sensor POA + measured module temperature; tune loss on 15-30 May, report on 1-17 June and full period; report Plant 2 as a secondary non-gating miss with a written cause; validate wind as simulated-curve x (1-0.035) vs `LV ActivePower` over the full year plus the PRD's 19 Oct-31 Dec slice, normalised by 3600 kW.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Kaggle parsing, nRMSE, tuning, plots, metrics.json | Offline pipeline (`swf.validate`) | - | SUMMARY: validate module is offline only; must never be imported by API |
| Physics chain (reused) | `swf.physics` shared core | - | Same code serves train/serve; do not fork |
| Report text / AUTO block | docs/data_notes.md via `write_auto_block` | - | Existing pattern |
| Images for site Performance page | `reports/validation/*.png` (static) | Frontend (Phase 7 `<img>`) | Stack decision: matplotlib PNGs, not Plotly |

## Standard Stack

No new dependencies. [VERIFIED: pyproject.toml]

| Library | Version | Purpose |
|---------|---------|---------|
| pandas 3.0.x, numpy 2.5.4 | pinned | parse, merge, metrics |
| pvlib 0.16.1 | pinned | `pvsystem.pvwatts_dc`, `inverter.pvwatts`, `temperature.faiman` |
| matplotlib 3.11.2 | installed in `train` extra only (not core deps) [VERIFIED: ran `import matplotlib` in project env] | scatter PNGs |
| pytest 9.2, ruff 0.17.3 | dev group | tests |

**Package Legitimacy Audit:** no external packages are installed in this phase; nothing to check. matplotlib is already declared in the `train` extra. Rule: import matplotlib lazily inside the plotting function with `matplotlib.use("Agg")`; never at module load (serving image must stay matplotlib-free). Tests use `pytest.importorskip("matplotlib")`.

## Kaggle data facts (inspected read-only 2026-11-03)

| Item | Plant 1 | Plant 2 | T1 (wind) |
|------|---------|---------|-----------|
| Date format | `dd-mm-yyyy HH:MM` (generation); ISO in weather | ISO both | `dd mm yyyy HH:MM`, UTF-8 BOM, header `Wind Direction (°)` mojibake-prone: select columns by position or rename |
| Span | 2020-05-15..06-17 (34 d) | same | 2018-01-01..12-31 |
| Step | 15 min | 15 min | 10 min |
| Rows | gen 68,778 / wx 3,182 | gen 67,698 / wx 3,259 | 50,530 (2,030 missing 10-min slots = 3.9%; do not ffill) |
| Inverters | 22 | 22 | 1 turbine |
| Timestamps with all 22 inverters | 3,057 of 3,158 gen ts (others have 4-21) | 2,355 of 3,259 (840 ts have 18, 64 have 12) | n/a |
| Weather sensors | 1 (SOURCE_KEY constant) | 1 | n/a |
| Duplicates (ts, inverter) / negative AC | 0 / 0 | 0 / 0 | 57 rows LV < 0 (min -2.5), 2,881 rows LV > 3600 (max 3618.7) |
| Summed AC peak | 29,150 kW | 25,980 kW | - |
| Summed DC peak | 298,938 (**10x AC: DC_POWER is mis-scaled by 10**) | 26,631 (DC/AC daytime 0.978, plausible) | - |
| IRRADIATION max / p99 | 1.222 / 0.999 | 1.099 / 0.957 | - |
| MODULE_TEMPERATURE max | 65.5 C | 66.6 C | - |
| Daytime zero-AC while IRRADIATION>0.3 | worst inverter 1.9%, median 0% | worst 29.7%, median 16.7% (dropouts) | - |

**Units finding (VAL-01):** `IRRADIATION` is kW/m2, a 15-min mean of a single plane sensor. It is POA, not GHI: median ratio of daily sensor max to Ineichen clear-sky GHI max at ~14.8N/78.3E is 1.07 (p90 1.15), which GHI could not exceed on clear days. [VERIFIED: computed] Multiply by 1000 for W/m2. Plant coordinates are not in the data; 14.8N 78.3E (Gandikota, AP) is community knowledge [ASSUMED] and is used only for this sanity ratio, never for scoring.

**Timestamps:** local clock (IST, UTC+5:30) [ASSUMED; supported by sensor peak at hour 12 local and AC peak hour 11-12]. Scoring is timezone-independent (all columns share the clock). Convert with `tz_localize("Asia/Kolkata").tz_convert("UTC")` for the UTC-internal rule; do not attach any site-based sun geometry.

## Decisions to lock

### Solar

- **S1 Plants.** Plant 1 is the gating plant. Plant 2 is reported as secondary, non-gating, with its miss explained (22 inverters, but daytime zero-AC for 17-30% of rows on many inverters, and only 2,355/3,259 timestamps have all 22 reporting). Rationale: summing AC over a degraded plant measures the dropouts, not the chain. For both plants, keep only timestamps where all 22 inverters report (Plant 1 drops ~5 daytime rows; Plant 2 keeps ~1,086-1,164 daytime rows) - state that the filter is applied. Measured: Plant 2 nRMSE 12.9% (loss tuned to 20, edge of range, a sign of non-chain error).
- **S2 Drive mode.** Use sensor POA directly: `poa = IRRADIATION*1000`, `temp_cell = MODULE_TEMPERATURE`, then `pvsystem.pvwatts_dc(poa, tc, kwp*1000, gamma_pdc) * (1-loss/100)` then `inverter.pvwatts(dc, pdc0, eta_inv_nom)/1000` (same call shapes as `swf.physics.solar.simulate_solar`). Refactor: extract the post-POA tail of `simulate_solar` into e.g. `ac_from_poa(poa, tc, s)` so validation and production share it (reuse, not copy). Faiman-from-ambient is a secondary variant that tests the temperature model: it scores the same (Plant 1: 2.9-3.2% vs 3.0-3.3% with measured module T) [VERIFIED: computed], so report both. Do NOT drive from NASA/ERA5 at the Kaggle site: that would test NASA input quality (SUMMARY M5), not the chain, and needs unknown coordinates. Perez transposition is not exercised by this data; say so in the report (it is covered by unit tests and the clear-sky check).
- **S3 Capacity anchor (identifiability fix).** In a new `config/validation.yaml` (validated by a small pydantic model; Settings is `extra=forbid`, so do not add keys to plant.yaml/site.yaml) set per-plant `dc_kwp = dc_ac_ratio * peak_summed_AC / eta_inv_nom` computed from data using the same `dc_ac_ratio 1.2`, `eta_inv_nom 0.96`, `gamma_pdc -0.004` as `config/plant.yaml`. For Plant 1: dc_kwp 36,438, AC cap 29,150 kW. Document plainly: data determine only (1-loss)*dc_kwp; the 8-20% range is conditional on this anchor (Plant 1 with anchor 35,000 gives loss 4; with 40,000 gives 18). Same anchor convention as Davanagere, so the tuned loss transfers.
- **S4 Tuning protocol.** Grid loss 8..20 step 1. Tune on the first 17 days (15-31 May), report held-out on 1-17 June, also report full-period in-sample. Measured Plant 1: both halves choose loss 9; fit-half nRMSE 2.82%, held-out 3.36%, full 3.11% (14% config would give 4.26%). Plant 2 as independent plant at the Plant 1 loss. Report the argmin and the nRMSE-vs-loss curve in metrics.json. If the argmin hits an edge (8 or 20) say so.
- **S5 Adopting the tuned loss.** Recommend updating `config/plant.yaml loss_pct` to the tuned integer (9) and re-running `swf simulate-energy` (Phase 4 not started, so no downstream artifacts exist; `energy_sim.parquet` is regenerated). Flag as a user-confirmable choice [ASSUMED acceptable]: alternative is to keep 14 and report 9 as validation-tuned.
- **S6 nRMSE definition.** nRMSE = RMSE / AC cap of that plant (matches D-06 "solar normalised by AC cap" and the REQUIREMENTS wording of capacity-normalised), computed on daytime rows. Also report RMSE/MAE kW, RMSE / observed max, MBE as % of mean daytime AC, and hourly-aggregated nRMSE (Plant 1: 2.07%; the product is hourly). Gate on the 15-min native comparison.
- **S7 Daytime rows.** `IRRADIATION > 0.02 kW/m2` (sensor-based; no coordinates needed). This deviates from EVAL-05's "midpoint zenith < 85" because the Kaggle site coordinates are unknown; state the deviation. Pre-filter all-22-inverters.

Expected numbers (computed with the prototype): Plant 1 daytime nRMSE ~3.1% (target 10%: PASS), hourly ~2.1%, MBE ~ -0.4%; Plant 2 ~12.9% (MISS, explained).

### Wind

- **W1 Protocol.** The curve is the manufacturer curve re-binned (PRD 4.3), so validation against `LV ActivePower` is genuinely out-of-sample for the signal; no curve rebuild/split is required. State in the report that "empirical curve" in the PRD actually means "re-binned manufacturer curve". Chronological handling is still cheap and useful for the one LV-derived scalar (availability): config stays 0.035 (PRD), not re-fitted.
- **W2 Metrics (all /3600 kW, RMSE on 10-min rows, native, no hourly smoothing):**
  - Simulated = `simulate_wind` output (curve interp x (1-0.035), clipped 0..3600). T1 has no pressure/temperature: call with `pressure=1013.25, temp=15` (rho = 1.2250 = RHO0, so the density factor is exactly 1) and `ws_hub = Wind Speed`. State that density correction is untested here.
  - Reference = raw `Theoretical_Power_Curve (KWh)` vs LV on the identical rows.
  - Slices: full year; 19 Oct-31 Dec (the PRD's pre-project test slice that produced 13.0%); Jan-18 Oct.
- **W3 Measured results (prototype):** 

| Slice | Raw theoretical col | Rebinned curve | Sim (curve x 0.965) |
|-------|-------------------|----------------|---------------------|
| Full year (50,530 rows) | 12.94% | 12.90% | **12.11%** |
| 19 Oct-31 Dec (10,098) | 13.08% (RMSE 470.9 kW; PRD 470.7) | 13.05% | **12.31%** |
| Jan-18 Oct | 12.90% | 12.87% | 12.07% |

  Gate: sim <= 14% PASS; sim <= reference on identical rows PASS (12.31 < 13.08). Use the same-rows reference rather than the literal constant 13.0, and print both. Hourly aggregation gives 11.5% (secondary).
- **W4 Availability finding.** Share of rows with wind > 4 m/s and LV <= 0 is 4.6% (5.5% at > 3.5); PRD/config says 3.5%. Energy ratio LV/curve is 0.877 (monthly 0.72 in Jan to 0.94 in Mar), so curve overpredicts mean output by ~12% (the curve is the manufacturer's, real turbine underperforms it, plus wake/yaw/curtailment). Report as a limitation; do not retune (chronological check: availability factor fitted on Jan-Aug and applied to Sep-Dec gives 10.12% vs 10.02% for 0.965, no gain). Optional diagnostic only: an LV-median curve built on Jan-Aug scores 9.18% on Sep-Dec, shows headroom; do NOT adopt (would change Phase 2 outputs, adds scope).
- **W5 Not tested:** NWP/NASA wind-speed quality, hub-height extrapolation, air density. T1 wind speed is the turbine anemometer. Say so (SUMMARY M5).

## Architecture Patterns

### Data flow
```
data/raw/kaggle/*.csv --(read-only, require_kaggle_files)--> swf.validate.kaggle_solar / kaggle_wind
   solar: parse -> sum AC per ts (full-22 filter) -> UTC -> POA/Tmod -> ac_from_poa (swf.physics.solar) -> loss grid on tune half
          -> metrics (tune/held-out/full, Plant 1 + Plant 2)
   wind : parse (utf-8-sig, dd mm yyyy) -> simulate_wind (curve x avail) vs LV; reference = Theoretical col; slices
   both -> reports/validation/{solar_plant1,solar_plant2,wind}_scatter.png (+ optional bias-vs-speed png) + metrics.json
        -> write_auto_block(docs/data_notes.md, block, name="validation")
```

### Recommended structure
```
config/validation.yaml          # per-plant anchor rule, loss grid 8..20, tune_end 2020-05-31, irr threshold, nrmse targets, wind slices
src/swf/validate/__init__.py
src/swf/validate/kaggle.py      # parse + metrics (pure functions, no matplotlib import)
src/swf/validate/plots.py       # lazy matplotlib
src/swf/validate/run.py         # run(args): CLI handler, writes metrics.json + AUTO block
src/swf/cli.py                  # add "validate" subparser -> _run("swf.validate.run", a)  (existing pattern: set_defaults(handler=lambda a: _run(...)))
tests/test_validate_*.py
```
CLI pattern: copy the `simulate-energy` registration in `src/swf/cli.py`; handler returns int, uses `require_kaggle_files(s)` (raises SystemExit with manual steps if files absent). `write_auto_block(DOCS_DIR/"data_notes.md", block, name="validation")` (name must match `[a-z_]+`; `OPENER = "Generated by python -m swf validate. Do not edit inside this block."`). Hand-written justification text lives outside the AUTO block in data_notes.md (the AUTO block is overwritten on rerun).

### metrics.json shape (suggested)
`{"generated_utc", "solar": {"plant_1": {"dc_kwp","ac_cap_kw","loss_pct_tuned","tune_nrmse_pct","heldout_nrmse_pct","full_nrmse_pct","hourly_nrmse_pct","rmse_kw","mbe_pct","n_rows","loss_curve":{...}, "target_pct":10, "pass":bool}, "plant_2": {..., "gating": false, "note": "..."}}, "wind": {"normalisation_kw":3600, "full_year":{...}, "ref_slice":{"sim_nrmse_pct","reference_nrmse_pct","target_pct":14,"pass":bool}, "availability_measured_pct"}}`. Use `json.dumps(..., indent=2, sort_keys=True)`, floats rounded; no timestamps other than the generated stamp, so reruns are diffable.

### Anti-patterns
- Normalising sim and actual by their own maxima (PRD 7.3 wording): makes loss tuning degenerate. Use the fixed AC cap.
- Tuning loss on the report set only: use the S4 split, report both.
- Calling the chain with site/Davanagere solar geometry on Kaggle data (`simulate_solar` zeroes by Davanagere zenith>90 and requires ghi/dni/dhi); use the POA entry point.
- ffill of T1 gaps; `pd.to_datetime` without explicit format (Plant 1 is day-first, so month/day swap silently for days <= 12).

## Don't Hand-Roll

| Problem | Use Instead |
|---------|-------------|
| Solar DC/AC | `pvlib.pvsystem.pvwatts_dc`, `pvlib.inverter.pvwatts` via refactored shared helper |
| Wind sim | `swf.physics.wind.simulate_wind`, `load_power_curve` |
| Kaggle presence/row-count check | `swf.fetch.kaggle.require_kaggle_files` |
| Markdown table / AUTO block | `swf.coverage.report._table`, `write_auto_block` |
| Config validation | pydantic `_Base` pattern from `swf.core.settings` |

## Common Pitfalls

1. **Day-first dates:** Plant 1 generation `%d-%m-%Y %H:%M`; others ISO; T1 `%d %m %Y %H:%M`. Pass explicit formats; assert min/max span equals expected (15 May-17 Jun).
2. **Join on timestamp, not row order:** gen has 3,158 timestamps, weather 3,182; 106/82 missing slots. Inner join on ts after summing AC.
3. **Partial inverter sets:** summing AC when only 4-21 inverters report biases low. Filter to n_inverters == 22; log rows dropped.
4. **DC_POWER Plant 1 is x10:** never use DC_POWER for validation; AC only. Document it.
5. **Loss/capacity degeneracy** (S3) and loss argmin at range edge (Plant 2).
6. **Single Plant-1 date span of 34 days (May-Jun, pre-monsoon/monsoon onset):** no seasonality; state the caveat (SUMMARY C7).
7. **T1 BOM and degree-sign header:** use `encoding="utf-8-sig"` and rename columns positionally.
8. **Negative / >rated LV:** clip nothing in actuals; the sim is clipped by `simulate_wind`. Keep rows (57 negative, 2,881 slightly above 3600) in the metric.
9. **Windows console encoding** when printing `°`: avoid printing raw header.

## Code Examples (verified shapes)

```python
# Solar tail, same args as swf.physics.solar.simulate_solar (pvlib 0.16.1)
dc = pvsystem.pvwatts_dc(poa_w_m2, t_cell, dc_kwp*1000, gamma_pdc) * (1 - loss/100)
ac_kw = inverter.pvwatts(dc, dc_kwp*1000/dc_ac_ratio, eta_inv_nom=eta) / 1000

# nRMSE
def nrmse(sim, act, norm): return float(np.sqrt(np.mean((sim - act) ** 2)) / norm * 100)

# Wind without density effect
df = pd.DataFrame({"ws_hub": t1.ws, "pressure": 1013.25, "temp": 15.0}, index=t1.index)
sim = simulate_wind(df, s)   # uses config/power_curve.csv and availability_loss 0.035
```

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 9.2 (`pyproject` addopts excludes `network` and `realdata`) |
| Quick run | `uv run pytest tests/test_validate_*.py -x` |
| Full suite | `uv run pytest` (CLAUDE.md: run before declaring done) |

| Req | Behavior | Type | Test |
|-----|----------|------|------|
| VAL-01 | dayfirst parse correct (e.g. `05-06-2020` is 5 June), AC summed per ts, partial-inverter ts dropped | unit, synthetic CSV in tmp_path | `test_validate_solar_parse.py` |
| VAL-01 | loss grid recovers a known loss from a synthetic series generated by the chain (argmin == injected value), bounded to 8..20 | unit | `test_validate_solar_tune.py` |
| VAL-02 | nRMSE definition (known arrays), daytime mask, tune/held-out split by date | unit | same |
| VAL-03 | wind sim vs reference on synthetic frame; slice selection; density factor == 1 at 1013.25 hPa/15 C | unit | `test_validate_wind.py` |
| VAL-04 | `run` writes metrics.json (keys, JSON-valid) and PNGs into a tmp dir; AUTO block named `validation` replaced idempotently | unit (importorskip matplotlib; output dir injectable) | `test_validate_outputs.py` |
| VAL-01..04 | real files: Plant 1 nRMSE < 10, wind sim <= 14 and <= reference | `@pytest.mark.realdata` | `test_validate_real.py` |
| refactor | `simulate_solar` output unchanged after extracting `ac_from_poa` | existing `test_physics_solar.py` must stay green | - |

Wave 0 gaps: new test files only; fixtures are tiny hand-written CSV strings; no framework install. Per-task: quick command; per wave: full suite.

## Environment Availability

| Dependency | Needed | Available | Note |
|------------|--------|-----------|------|
| Kaggle CSVs in data/raw/kaggle | all | yes, row counts match config | read-only; never re-download |
| matplotlib | VAL-04 | yes, 3.11.2 (train extra) | lazy import |
| Python 3.12 / uv env | all | yes | - |
| Network | none | n/a | phase is fully offline |

## Security Domain

No network, auth, or untrusted-input surface beyond reading local CSVs. V5 input validation: pydantic-validate `config/validation.yaml`; fail loud on unexpected date span / column set. Do not execute or modify files under data/raw (CSV files are data only; read via pandas).

## Assumptions Log

| # | Claim | Risk if Wrong |
|---|-------|---------------|
| A1 | Kaggle plant timestamps are IST (UTC+5:30) | Only affects the UTC label; scores unaffected |
| A2 | Plant location ~14.8N 78.3E (Gandikota) | Used only for the GHI-vs-POA sanity ratio; conclusion (POA) also follows from max 1.22 kW/m2 |
| A3 | Adopting tuned loss (9) into plant.yaml is acceptable to the user | Changes simulated labels; user should confirm (S5) |
| A4 | Kaggle plant nameplate unknown; anchor rule S3 is a convention, not the true DC size | Tuned loss value is conditional on it; documented |
| A5 | IRRADIATION is POA (inferred from magnitude) | If GHI, sim would be conservative; fit would absorb in loss/anchor; state inference as such |

## Open Questions (RESOLVED)

1. Plant 2: worth a second variant that scales by number of active inverters? Recommendation: no; report the miss and the dropout statistics, it is a documented acceptable outcome.
   RESOLVED (user, 2026-11-03, D-L2): no second variant; Plant 2 is a documented non-gating miss with dropout statistics.
2. Whether to fold the tuned loss into plant.yaml (A3): planner should include a user-confirm checkpoint or lock "yes".
   RESOLVED (user, 2026-11-03, D-L1): keep plant.yaml loss_pct = 14; report the tuned loss alongside, never rewrite plant.yaml or energy_sim.parquet.

## Sources

- Direct inspection and prototyping against data/raw/kaggle/*.csv and the repo's chain (2026-11-03) - HIGH
- docs/PRD.md 4.2, 4.3, 5.3, 7.3, appendix (13.0% pre-project test); .planning/research/SUMMARY.md (pitfalls M4, M5, C7); 02-CONTEXT D-06/D-07; src/swf/physics/*.py, cli.py, coverage/report.py, core/settings.py - HIGH
- pvlib call signatures per CLAUDE.md stack facts (verified by introspection in Phase 1) - HIGH

## Metadata

**Confidence:** stack HIGH, results HIGH (reproducible numbers), nameplate/timezone/location LOW-ASSUMED (flagged).
**Research date:** 2026-11-03. Valid until: stable (static datasets).
