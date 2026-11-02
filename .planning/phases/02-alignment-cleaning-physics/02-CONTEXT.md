# Phase 2: Alignment, Cleaning & Physics - Context

**Gathered:** 2026-11-02
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase turns every cached raw source into one canonical hourly UTC frame (`CANON_COLS`), with a verified, unit-tested timestamp offset per source and per variable group. The sources are:
- NASA POWER
- Open-Meteo ERA5 (`models=era5`)
- GFS Historical Forecast
- GFS Previous Runs (lead days 1–3)
- GFS live forecast

It then cleans the NASA (truth) table:
- complete hourly index
- ≤3 h gap fill
- physical clipping
- night GHI = 0

It also produces the NASA-vs-ERA5 consistency table (and a conditional linear correction).

Finally, it builds the physics chain:
- pvlib solar kW
- wind kW from an empirical power curve with hub-height extrapolation and air-density correction
- the PRD §6 physical-constraint layer

It also freezes the `CANON_COLS` contract.

Out of scope:
- Kaggle validation and loss-% calibration (Phase 3)
- features, splits and baselines (Phase 4)
- serving (Phase 5)

Requirements: ALIGN-01..06, PHYS-01..06.

</domain>

<decisions>
## Implementation Decisions

### NASA ↔ ERA5 bias correction (ALIGN-05, ALIGN-06)
- **D-01:** **NASA is the reference (truth).** Targets stay NASA per PRD §6 and Phase 1 D1. Any correction maps ERA5 (and later GFS, using the same function) into NASA space, so that lag features look like the targets.
- **D-02:** **Correct only where the bias is large.** Compute a monthly bias / RMSE / correlation table for GHI, RH and WS10M (plus hub-height wind if available) and write it to `docs/data_notes.md`. Fit a correction only for variables whose |bias| exceeds a threshold. Defaults are below; the planner may tune them with a stated rationale.
  - wind: > 0.5 m/s or > 10% of the mean
  - GHI: > 20 W/m² (daytime)
  - RH: > 5 points

  Record the decision per variable in `data_notes`.
- **D-03:** **Granularity: per variable, per calendar month.** Fit y_NASA = a·x_ERA5 + b separately for each month, which captures monsoon vs dry season. Store the coefficients as a small JSON in `config/` or `models/`. Training and serving use the same `apply_correction()` function.
- **D-04:** **Fit on train years only (2001–2023).** Apply unchanged to 2024 (validation) and 2025 (test). There is no leakage from the evaluation years.

### AC cap & capacity normalization (PHYS-02)
- **D-05:** **AC cap ≈ 800 kW.**
  - `pdc0` = DC nameplate / DC-AC ratio = 1000 / 1.2 ≈ 833 kW is the **inverter DC input** limit passed to `pvlib.inverter.pvwatts`.
  - The effective AC cap is eta_inv_nom × pdc0 = 0.96 × 833 ≈ 800 kW.
  - One config-derived value drives both numbers.
  - The PRD §6 bound becomes 0 ≤ T1 ≤ AC cap (≈ 800 kW).
  - The report states both numbers.
- **D-06:** **Solar nRMSE is normalized by the AC cap** (≈ 800 kW). Record this in config/docs for Phase 4.
- **D-07:** **Wind nRMSE is normalized by the rated 3600 kW.**
- **D-08:** **The loss % uses `plant.yaml` `loss_pct` = 14 until Phase 3 calibrates it.** Phase 3 overwrites the config value and regenerates the simulated targets. Phase 2 code must read loss % from config, never hard-code it.

### Timestamp verification & cleaning (ALIGN-01..04)
- **D-09:** **Offset pass rule:** after applying the chosen offset, both of these must hold. Record per source × variable group × year in `docs/data_notes.md`, replacing the "preliminary" section.
  - The yearly-mean GHI diurnal centroid matches pvlib clear-sky (computed at the interval midpoint) within **±0.15 h**.
  - The sunrise-onset hour matches on **≥ 90% of days**.
- **D-10:** **Per-variable-group offsets.** If a NASA variable group (for example CERES radiation vs MERRA-2 meteorology) shows a different offset, the adapter applies an offset per group, each unit-tested and recorded.
- **D-11:** **Gap fill ≤ 3 h (PRD).**
  - Meteorological variables are filled linearly.
  - GHI is filled via the clear-sky index, never across sunrise or sunset.
  - Gaps longer than 3 h stay NaN; Phase 4 drops those windows.
- **D-12:** **Cleaning report** as a table in `docs/data_notes.md` (plus one structured log line per source). Per source × variable × year it gives:
  - % missing before and after the fill
  - # clipped low and high
  - # night-GHI values zeroed

### Post-research decisions (2026-11-03, user-confirmed; supersede where they conflict)
- **D-13 (refines D-09, A1/A2):** The timestamp pass rule now has three parts:
  - Sunrise onset within {0, +1} h on ≥ 90% of days.
  - The opposite label convention must score < 90%, which proves the direction.
  - Centroid within ±0.15 h, judged on **pooled full years**. Partial years, such as GFS HF 2021, are reported but don't gate.

  Rationale: with hourly data, every exact-hour miss is exactly +1 h, so the original rule can't pass for any source.
- **D-14 (A3):** **NASA meteorology (MERRA-2) uses a 0 h shift, the same as NASA radiation.**
  - Record it as medium confidence in `data_notes`.
  - A unit test pins the choice.
  - Revisit only if Phase 3/4 errors suggest a lag.
- **D-15 (offsets, from research):** **All Open-Meteo variables (ERA5, GFS HF, GFS PR, live) take a −1 h index shift. NASA takes 0 h.**
- **D-16 (A4):** **The 14% system loss is applied on the DC side**, before the inverter (PVWatts convention). Clipping acts on post-loss DC.
  - The clear-sky peak is ≈ 745 kW.
  - Tests assert a peak of 700–800 kW, plus a separate loss = 0 test that reaches the 800 kW cap.
- **D-17 (A5, refines D-02):** **Correct all four variables: `ghi` (daytime only), `rh`, `ws10`, `ws_hub`.**
  - Hub wind is fitted separately.
  - A variable is corrected if **any** month exceeds its threshold.
  - Coefficients go in `config/bias_correction.json`.

### Carried forward (locked earlier, not re-decided)
- UTC internally. The `-999` → NaN conversion already happens in `nasa_to_frame`.
- Phase 1 found these timestamp conventions (Phase 2 verifies them with D-09):
  - NASA radiation is labelled at the start of the hour.
  - Open-Meteo radiation is the mean over the preceding hour, labelled at the end.
- ERA5 must be requested with `models=era5`. GFS (`gfs_seamless`) is the single NWP model.
- Azimuth: pvlib 180 = south and Open-Meteo 0 = south. Use the existing `to_openmeteo_azimuth`.
- pvlib 0.16.1 API:
  - Perez transposition needs `dni_extra` and `airmass`.
  - `pvwatts_dc(effective_irradiance, ...)`.
  - AC uses `pvlib.inverter.pvwatts`; `pvsystem.pvwatts_ac` does not exist.
- Clean table range is 2001-01-01 → 2025-12-31. NASA radiation's 60-day tail gap falls outside the training range and is irrelevant here.
- Site and plant values come from `config/*.yaml` only.

### Claude's Discretion
- **Wind power curve (PHYS-04):**
  - Default per PRD §4.3: build `config/power_curve.csv` in this phase from Kaggle `T1.csv` as the median of `Theoretical_Power_Curve (KWh)` per 0.5 m/s bin. Keep the parametric fallback (cut-in 3.5, rated 13, cut-out 25, cubic) for when the file is absent.
  - Use `require_kaggle_files()` before building.
  - Kaggle quirks to handle: `T1.csv` has a UTF-8 BOM and day-first dates (see `docs/data_notes.md` § Kaggle files).
  - Availability loss is 3.5%. Air-density correction scales wind speed by (ρ/1.225)^(1/3), with ρ from surface pressure and temperature.
- **Hub-height wind:** NASA α from WS10M and WS50M, clipped to [0.05, 0.40], with α = 0.143 when WS10M < 0.5 m/s (PRD §5.1). Use the same α method for GFS/ERA5 from 10 m plus the nearest upper level (Phase 1 D-09).
- Exact `CANON_COLS` names and dtypes (research suggests `ghi, dni, dhi, temp, rh, pressure, ws10, ws_hub, wd10, wd_hub, precip, cloud`), module layout (`swf.align`, `swf.physics`), interim parquet paths (`data/interim/weather_nasa.parquet`, `data/interim/energy_sim.parquet`, per PRD §7.1), CLI subcommand names, and the threshold fine-tuning in D-02 (with rationale).
- Whether hub wind is corrected separately or derived after the 10 m correction.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec
- `docs/PRD.md`: §4.2 solar plant, §4.3 wind turbine, §5.1 hub-height formula and timestamp check, §5.2 Open-Meteo quirk, §6 target construction and physical bounds, §7.1 stage paths, §7.2 cleaning rules, §7.4 source consistency, §13 tests
- `.planning/REQUIREMENTS.md`: ALIGN-01..06, PHYS-01..06
- `.planning/ROADMAP.md`: Phase 2 goal, success criteria and the contract-freeze note
- `.planning/PROJECT.md`: Key Decisions (dual window, GFS, select-on-val, adaptive profile)

### Data facts (Phase 1 output)
- `docs/data_notes.md`: NWP choice, D1–D3, errata, preliminary timestamp conventions, coverage and % missing tables, Kaggle files (BOM, day-first dates)
- `.planning/phases/01-foundations-data-acquisition/01-CONTEXT.md`: Phase 1 decisions (D-06 GFS, D-09 hub-wind α method, D-19 lead mapping)
- `.planning/phases/01-foundations-data-acquisition/01-REVIEW-FIX.md`: parser and cache fixes (`nasa_to_frame` aligns on timestamp keys)

### Research (errata override PRD)
- `.planning/research/SUMMARY.md`: errata (pvlib `inverter.pvwatts`, AC cap, azimuth), Phase 2 delivers
- `.planning/research/STACK.md`: pvlib 0.16.1 API facts (Perez inputs, Faiman, `pvwatts_dc` signature)
- `.planning/research/PITFALLS.md`: C3/M1 timestamps, C6 sentinel, C7 PV chain, M2/M3/M5/M10
- `.planning/research/ARCHITECTURE.md`: `swf.align` adapters, canonical frame, `swf.physics` shared by training, baseline 3 and serving

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `swf.fetch.parse.nasa_to_frame`: NASA JSON → UTC-indexed frame with `-999` → NaN (WR-01/02 hardened). The NASA adapter builds on it.
- `swf.core.settings.load_settings` (pydantic, `extra=forbid`) and `config/site.yaml` / `config/plant.yaml` (solar: dc_kwp, tilt, azimuth_pvlib, dc_ac_ratio, eta_inv_nom, gamma_pdc, loss_pct, transposition; wind: rated_kw, hub_height_m, availability_loss, cut_in/rated/cut_out). New physics config keys go here.
- `swf.core.geometry.to_openmeteo_azimuth`: azimuth convention mapping (tested).
- `swf.core.paths`: RAW_DIR, INTERIM_DIR, DOCS_DIR constants.
- `swf.fetch.kaggle.require_kaggle_files`: hard-stop before building the power curve.
- `swf.coverage.report.write_auto_block`: updates a marked block in `docs/data_notes.md` without touching hand-written sections. Reuse it for the timestamp, consistency and cleaning tables, with distinct block names.
- `swf.cli`: lazy subcommand dispatch. Add `align`, `physics` (or `build-weather`, `simulate-energy`) subcommands.

### Established Patterns
- Raw JSON is cached verbatim with sidecars. Parsing happens only in adapters (no parsing in fetch).
- Network-free tests with fixtures under `tests/fixtures/`. pytest markers `network` and `gpu`.
- One commit per task, with the Co-Authored-By trailer.

### Integration Points
- Phase 3 reads the physics chain plus `config/power_curve.csv` and recalibrates loss %.
- Phase 4 reads `CANON_COLS` frames and the correction function (features, splits).
- Phase 5 serving reuses the GFS adapter, `apply_correction()` and physics on live data.

</code_context>

<specifics>
## Specific Ideas

- Redo the NASA-vs-ERA5 comparison with `models=era5`. The preliminary 34% wind gap came from the default archive (ERA5 → IFS from 2017), so the true gap may differ.
- The clear-sky-day PV check should peak around 770 kW and never exceed the ≈ 800 kW AC cap.
- The south-vs-north POA ratio test catches azimuth-convention bugs.
- GHI closure check on NASA components (GHI ≈ DNI·cos z + DHI) is a sanity log, not a gate.

</specifics>

<deferred>
## Deferred Ideas

- Non-linear or per-hour bias correction: v2 (EVAL2-03).
- Correcting GFS covariates toward NASA beyond reusing `apply_correction()`: measured in Phase 4 (train/serve skew).

</deferred>

---

*Phase: 2-Alignment, Cleaning & Physics*
*Context gathered: 2026-11-02*
