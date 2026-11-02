# Phase 2: Alignment, Cleaning & Physics - Research

**Researched:** 2026-11-03
**Domain:** time-series alignment of NASA POWER / Open-Meteo (ERA5, GFS) data; pvlib PV chain; empirical-curve wind chain
**Confidence:** HIGH on measured facts (all computed in this session from the cached data under `data/raw/`, no network); MEDIUM on the NASA meteorology timestamp interpretation

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** NASA is the reference (truth). Targets stay NASA per PRD §6 and Phase 1 D1. Any correction maps ERA5 (and later GFS, using the same function) into NASA space.
- **D-02:** Correct only where the bias is large. Compute a monthly bias / RMSE / correlation table for GHI, RH and WS10M (plus hub-height wind if available), write it to `docs/data_notes.md`. Fit a correction only for variables whose |bias| exceeds a threshold. Defaults (planner may tune with a stated rationale): wind > 0.5 m/s or > 10% of the mean; GHI > 20 W/m² (daytime); RH > 5 points. Record the decision per variable in `data_notes`.
- **D-03:** Granularity per variable, per calendar month. Fit y_NASA = a·x_ERA5 + b separately for each month. Store coefficients as a small JSON in `config/` or `models/`. Training and serving use the same `apply_correction()`.
- **D-04:** Fit on train years only (2001–2023). Apply unchanged to 2024 (validation) and 2025 (test).
- **D-05:** AC cap ≈ 800 kW. `pdc0` = 1000 / 1.2 ≈ 833 kW is the inverter DC input limit passed to `pvlib.inverter.pvwatts`; effective AC cap = eta_inv_nom × pdc0 = 0.96 × 833 ≈ 800 kW; one config-derived value drives both; PRD §6 bound becomes 0 ≤ T1 ≤ AC cap; the report states both numbers.
- **D-06:** Solar nRMSE normalized by the AC cap (≈ 800 kW); record in config/docs for Phase 4.
- **D-07:** Wind nRMSE normalized by the rated 3600 kW.
- **D-08:** Loss % uses `plant.yaml` `loss_pct` = 14 until Phase 3 calibrates it. Phase 2 code reads loss % from config, never hard-coded.
- **D-09:** Offset pass rule: after applying the chosen offset, both must hold, recorded per source × variable group × year in `docs/data_notes.md` (replacing the "preliminary" section): yearly-mean GHI diurnal centroid matches pvlib clear-sky (at the interval midpoint) within ±0.15 h; sunrise-onset hour matches on ≥ 90% of days.
- **D-10:** Per-variable-group offsets. If a NASA variable group (e.g. CERES radiation vs MERRA-2 meteorology) shows a different offset, the adapter applies an offset per group, each unit-tested and recorded.
- **D-11:** Gap fill ≤ 3 h (PRD). Met variables linearly; GHI via clear-sky index, never across sunrise or sunset; gaps > 3 h stay NaN (Phase 4 drops those windows).
- **D-12:** Cleaning report as a table in `docs/data_notes.md` (plus one structured log line per source). Per source × variable × year: % missing before/after fill, # clipped low/high, # night-GHI values zeroed.
- Carried forward: UTC internally; `-999` → NaN already in `nasa_to_frame`; NASA radiation start-of-hour and Open-Meteo radiation end-of-hour (to be verified with D-09); ERA5 requested with `models=era5`; GFS (`gfs_seamless`) is the single NWP model; azimuth pvlib 180 = south, Open-Meteo 0 = south via `to_openmeteo_azimuth`; pvlib 0.16.1 API (Perez needs `dni_extra` and `airmass`; `pvwatts_dc(effective_irradiance, ...)`; AC is `pvlib.inverter.pvwatts`); clean table range 2001-01-01 → 2025-12-31; site/plant values from `config/*.yaml` only.

### Claude's Discretion
- Wind power curve (PHYS-04): default per PRD §4.3, build `config/power_curve.csv` from Kaggle `T1.csv` as median of `Theoretical_Power_Curve (KWh)` per 0.5 m/s bin; keep parametric fallback (cut-in 3.5, rated 13, cut-out 25, cubic) when the file is absent; use `require_kaggle_files()` before building; handle BOM and day-first dates; availability loss 3.5%; air-density correction scales wind speed by (ρ/1.225)^(1/3), ρ from surface pressure and temperature.
- Hub-height wind: NASA α from WS10M and WS50M, clipped to [0.05, 0.40], α = 0.143 when WS10M < 0.5 m/s (PRD §5.1). Same α method for GFS/ERA5 from 10 m plus nearest upper level (Phase 1 D-09).
- Exact `CANON_COLS` names and dtypes, module layout (`swf.align`, `swf.physics`), interim parquet paths, CLI subcommand names, D-02 threshold fine-tuning (with rationale).
- Whether hub wind is corrected separately or derived after the 10 m correction.

### Deferred Ideas (OUT OF SCOPE)
- Non-linear or per-hour bias correction: v2 (EVAL2-03).
- Correcting GFS covariates toward NASA beyond reusing `apply_correction()`: measured in Phase 4.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ALIGN-01 | One adapter per source → `CANON_COLS` hourly UTC frame, documented unit-tested offset | Offsets measured (§Timestamp findings); CANON_COLS proposal; adapter layout |
| ALIGN-02 | Verify convention via sunrise onset and diurnal centroid vs pvlib clear-sky at midpoint; record in data_notes | Measured per source; rule needs a tolerance fix for onset (A1, A2) |
| ALIGN-03 | Complete hourly index, ≤3 h interpolation (GHI via clear-sky index, not across sunrise/sunset), clip, log counts | Gap stats: real NASA has ZERO gaps, so tests must be synthetic; clip ranges proposed |
| ALIGN-04 | Night GHI = 0 where midpoint zenith > 90° | 5,923 NASA night rows are non-zero (max 15 W/m²); DNI up to 138 W/m² at night |
| ALIGN-05 | NASA vs ERA5 monthly bias/RMSE/corr table | Full table below |
| ALIGN-06 | Linear per-variable correction if bias large, same function train/serve | Threshold verdicts + fitted-coefficient behaviour on 2024-25 |
| PHYS-01 | pvlib chain from config | Verified signatures + working chain code |
| PHYS-02 | One config value for pdc0 / AC cap | Verified: cap = 800.0 kW exactly |
| PHYS-03 | Azimuth conversion in one tested function | Already exists (`swf.core.geometry`); add S/N POA test |
| PHYS-04 | Empirical power curve, hub extrapolation, density, 3.5% availability | Curve table, density maths, CF sanity numbers |
| PHYS-05 | Unit-test suite | Validation Architecture map |
| PHYS-06 | Constraint layer | Needed: 967 night rows have AC > 0 without it |
</phase_requirements>

## Summary

All numbers below were computed this session from the cached raw files (NASA 2001-2025, ERA5 2001-2025, GFS HF 2021-2025, GFS PR 2024-2025, Kaggle `T1.csv`). The chain is simple: reindex, shift Open-Meteo labels by -1 h, clean, fit monthly linear corrections, run pvlib and the power curve. The risks are semantic, not volumetric.

Key findings that change plans:
1. **A uniform -1 h shift of every Open-Meteo variable aligns it to NASA labels.** Radiation is physically justified (NASA start-of-hour, Open-Meteo end-of-hour; centroid agreement ≤ 0.06 h at the midpoint). NASA meteorology (MERRA-2) shows the same ~1 h lead vs instantaneous ERA5 (surface-pressure semidiurnal tide anchor: NASA 3.78 h vs ERA5 4.81 h vs physical ~4.9 h UTC). So the D-10 group offsets are the same size, but the met-group interpretation is MEDIUM confidence.
2. **The D-09 onset rule (≥ 90% exact-hour match) cannot pass for NASA** (59% exact, 100% within {0,+1} h) because NASA radiation is smoothed across the sunrise hour. It needs a tolerance reformulation (A1). The centroid rule passes everywhere pooled; GFS HF sits at -0.09..-0.20 h (afternoon-cloud effect, not a timestamp error; HF 2021 partial year fails by year) (A2).
3. **NASA has no gaps at all in 2001-2025** (0 NaN outside the structural `ALLSKY_KT` night NaN; 219,144 hourly rows, complete index). The ≤3 h fill code can only be tested with synthetic gaps. Real gaps exist only in GFS HF (one 1,944-1,945 h leading block in 2021; one 345 h precipitation block in 2022) and PR (leading blocks).
4. **True ERA5 vs NASA bias is large for wind and moderate for GHI/RH.** WS10M -0.74 m/s (-17.5%), hub wind -1.21 m/s (-18.5%), exceeding D-02 in all 12 months; GHI exceeds 20 W/m² in Jun-Sep; RH in Apr, Oct, Nov, Dec. All four variables get a correction under a "any month exceeds" rule.
5. **PV chain works as specified; the "~770 kW" peak is ~745 kW with 14% loss** (pvlib Ineichen clear-sky, 21 Mar, peak POA 1037 W/m²). The AC cap is exactly 800.0 kW and is reached in only ~8 h/yr with NASA irradiance. Tests must assert a range, not 770.
6. **Constraint layer is not redundant.** With NASA irradiance un-zeroed, 967 night-time rows have AC > 0 (POA up to 28 W/m²).
7. PRD claim "air density ~6% lower at 600 m" is wrong for this site: mean ρ = 1.102 kg/m³ = 0.900 × 1.225 (10% lower). Wind CF drops from 30.5% to 28.2% when density is applied.

**Primary recommendation:** Build `swf.align` (adapters + clean + consistency/correction) and `swf.physics` (solar, wind, constraints) as pure functions on UTC-indexed DataFrames; shift all Open-Meteo frames by -1 h at the adapter; fit monthly corrections for GHI (daytime), RH, WS10M and hub wind on 2001-2023; test the cleaner on synthetic gaps because the real data has none.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Raw → canonical frame (adapters, offsets) | Offline pipeline (`swf.align`) | — | Training and serving share the same adapter for GFS; no browser involvement |
| Cleaning (index, gaps, clip, night zero) | Offline pipeline | API (serving reuses the same function on live GFS) | One function, two callers (ARCHITECTURE.md) |
| NASA↔ERA5 consistency + correction | Offline pipeline (fit) | API (apply only, JSON coefficients) | Fit once on train years; serving loads JSON, no fitting at runtime |
| Solar / wind kW simulation | Offline pipeline (`swf.physics`) | API (baseline 3 runs physics on GFS at serve time) | Same code path guarantees baseline 3 = physics of the same chain |
| Constraint layer | `swf.physics` | API response boundary | Applied on every output; shared |
| Timestamp display (IST) | Browser | — | UTC internally per project rule; nothing in this phase |

## Standard Stack

No new dependencies. All needed packages are already in `pyproject.toml` (`pandas>=3.0.6,<3.1`, `numpy==2.5.4`, `pyarrow==26.0.0`, `pvlib==0.16.1`, `pyyaml`, `pydantic`). `uv run pytest` currently passes 83 tests.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pvlib | 0.16.1 [VERIFIED: installed, introspected] | solar position, clear-sky, Perez, Faiman, PVWatts DC/AC | project stack |
| pandas | 3.0.x [VERIFIED: pyproject] | UTC-indexed frames, interpolation | project stack |
| numpy | 2.5.4 | `np.interp` power curve (no scipy needed) | project stack |
| pyarrow | 26.0.0 | `data/interim/*.parquet` | project stack |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| numpy polyfit for the monthly linear fit | scikit-learn `LinearRegression` | sklearn is only in the `train` extra; serving image is torch/sklearn-free. Use `np.polyfit(x, y, 1)`. |
| `scipy` interpolation | `np.interp` | scipy only arrives transitively; not needed. |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed by this phase. Table not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Empirical Findings

### 1. Timestamp offsets (ALIGN-02) [VERIFIED: computed from cached data]

Method: yearly-mean diurnal profile; centroid (hour-weighted mean, UTC label hours) minus centroid of pvlib Ineichen clear-sky GHI evaluated at the interval midpoint implied by the hypothesised convention (start-label: label + 0.5 h; end-label: label − 0.5 h). Site: lat 14.4644, lon 75.9218, altitude 598 m.

| Source / group | Hypothesis | Centroid diff at midpoint (h), over years | Instant-label diff (h) | Verdict |
|---|---|---|---|---|
| NASA GHI/DNI/DHI/CLRSKY (CERES/SYN1deg) | start-of-hour | +0.017..+0.062 (25 yrs); DNI +0.06..+0.21 | -0.45 | start-of-hour confirmed; offset 0 (adapter keeps label); pvlib uses label + 30 min |
| ERA5 radiation | end-of-hour | -0.047..+0.003 (25 yrs) | +0.49 | end-of-hour confirmed; adapter: index − 1 h |
| GFS HF radiation | end-of-hour | -0.195 (2021, partial), -0.105, -0.150, -0.089, -0.110 | +0.35..+0.41 | end-of-hour; pooled ≈ -0.11; negative bias is GFS afternoon cloud (not timestamp) |
| GFS PR day1/2/3 radiation | end-of-hour | -0.095..-0.125 | +0.39..+0.42 | end-of-hour; same shift for all leads |

Cross-source lag check (best sub-hour shift of mean diurnal profile, NASA(t) = ERA5(t+s), 2001-2023):

| NASA variable | s (h) | Reading |
|---|---|---|
| ALLSKY_SFC_SW_DWN / DIFF / CLRSKY | 0.95 | clean 1 h = start- vs end-label |
| ALLSKY_SFC_SW_DNI | 0.85-0.90 | same |
| T2M | 1.50 | MERRA-2 vs ERA5 diurnal-phase differences blur this |
| RH2M | 1.65 | follows T2M |
| WS10M | 0.55 (0.40 in 2024) | weak diurnal cycle, noisy |
| PS | 1.30 | tide-anchored (below) |

Hourly-correlation lag check (NASA(t) vs ERA5(t+k), 2012 and 2024): k=+1 is best for GHI (0.981/0.973), DNI, DIFF, WS10M, PS (0.952/0.963); T2M and RH are marginally better at k=+2 (0.949 vs 0.944; 0.92 vs 0.914). So **k=+1 (index −1 h on ERA5) is the best single integer for every variable**.

Physical anchor for the met group: the S2 semidiurnal pressure tide peaks at ~10 h local solar time = ~4.9 h UTC at this longitude. Measured S2 maxima (UTC hours, 2010-2023): NASA PS 3.78, ERA5 PS (instantaneous label) 4.81, GFS HF 4.48 (vs ERA5 4.78 same years). So NASA PS(t) corresponds to the physical instant ≈ t + 1.0 h, the same ~1 h that radiation shows. GFS met matches ERA5 within ~0.3 h, so no separate GFS met offset.

Sunrise-onset (first non-zero hour vs the interval containing geometric sunrise at minute resolution, 2024):

| Source | Expected label rule | Exact match | Within {0,+1} h | Opposite convention within {0,+1} h |
|---|---|---|---|---|
| NASA GHI | start: floor(sunrise) | 59.3% | 100% | 41% (assuming end-label) |
| ERA5 | end: floor(sunrise)+1 | 86.6% (thr 0), 88.8% (2012) | 100% | 0% |
| GFS HF | end | 85.8% | 100% | 0% |
| GFS PR1 | end | 84.8% | 100% | 0% |

The remaining mismatch is always exactly +1 h (the first sunrise hour holds a tiny value that NASA/ERA5 round to zero). **Strict D-09 (≥ 90% exact) fails for every source**; a tolerance form passes cleanly and still discriminates the wrong convention (see A1).

**Recommended adapter rule (D-10), all "shift" values applied as `index = index + shift`:**

| Source | Radiation (ghi, dni, dhi) | Instantaneous (temp, rh, pressure, ws, wd, cloud) | Precip |
|---|---|---|---|
| NASA | 0 h | 0 h (apparent instant = label + 1 h, recorded; MEDIUM) | 0 h |
| ERA5 / GFS HF / PR / live | −1 h | −1 h | −1 h |

Net effect: every canonical label is the start of the hour interval for radiation and the NASA convention for everything else. pvlib is always called at `label + 30 min`.

### 2. NASA vs ERA5 consistency (ALIGN-05/06) [VERIFIED: computed]

ERA5 (`models=era5`) shifted −1 h; bias = ERA5 − NASA; train years 2001-2023; GHI on daytime rows only (midpoint zenith < 90°); hub wind = NASA α-extrapolated vs ERA5 native `wind_speed_80m`.

Annual summary:

| Variable | NASA mean | Bias (ERA5−NASA) | RMSE | Corr | D-02 threshold | Verdict |
|---|---|---|---|---|---|---|
| GHI (day) W/m² | 461.5 | -14.95 | 92.1 | 0.950 | 20 | annual below, but Jun-Sep exceed |
| RH % | 68.2 | -2.22 | 11.05 | 0.911 | 5 pts | annual below, Apr/Oct/Nov/Dec exceed |
| WS10M m/s | 4.206 | -0.738 | 1.348 | 0.858 | 0.5 or 10% | **exceeds every month** |
| Hub wind m/s | 6.552 | -1.214 | 2.004 | 0.839 | 0.5 or 10% | **exceeds every month** |
| T2M °C | 24.94 | +0.69 | 2.06 | 0.939 | not in D-02 | log only |
| PS hPa | 942.7 | +1.46 | 1.63 | 0.963 | not in D-02 | log only (≈0.15% density) |

Monthly bias (ERA5 − NASA) and correlation (train 2001-2023):

| Month | GHI bias | GHI r | RH bias | RH r | WS10 bias | WS10 r | Hub bias | Hub r |
|---|---|---|---|---|---|---|---|---|
| 1 | +10.1 | 0.985 | -3.5 | 0.871 | -0.57 | 0.750 | -1.17 | 0.758 |
| 2 | +7.1 | 0.990 | +0.9 | 0.873 | -0.61 | 0.731 | -1.10 | 0.753 |
| 3 | +4.6 | 0.983 | +4.0 | 0.893 | -0.65 | 0.668 | -0.95 | 0.717 |
| 4 | -6.9 | 0.969 | **+5.7** | 0.877 | -0.54 | 0.579 | -0.66 | 0.641 |
| 5 | -10.0 | 0.947 | +0.9 | 0.913 | -0.77 | 0.741 | -0.82 | 0.783 |
| 6 | **-34.0** | 0.878 | -3.3 | 0.838 | -1.08 | 0.818 | -1.37 | 0.819 |
| 7 | **-35.3** | 0.858 | -3.2 | 0.780 | -1.22 | 0.838 | -1.59 | 0.836 |
| 8 | **-37.6** | 0.886 | -3.8 | 0.809 | -0.96 | 0.864 | -1.45 | 0.856 |
| 9 | **-40.1** | 0.913 | -4.7 | 0.846 | -0.56 | 0.842 | -1.14 | 0.838 |
| 10 | -19.6 | 0.933 | **-5.6** | 0.857 | -0.55 | 0.723 | -1.31 | 0.678 |
| 11 | -12.8 | 0.946 | **-7.8** | 0.856 | -0.63 | 0.794 | -1.44 | 0.735 |
| 12 | -3.4 | 0.968 | **-6.1** | 0.880 | -0.71 | 0.832 | -1.55 | 0.800 |

(Bold = exceeds D-02. Full RMSE per month is produced by the code; GHI RMSE 45-123 W/m², RH 8-13 pts, WS10 1.1-1.8 m/s, hub 1.7-2.2 m/s.)

Earlier "34% wind gap" was the default-archive (IFS from 2017) artefact; the true `models=era5` gap is -17.5% (WS10M) and -18.5% (hub).

Per-month fit y_NASA = a·x_ERA5 + b on 2001-2023, evaluated on 2024-25 (diagnostic only, not for selection):
- WS10M: RMSE 1.01-2.22 → 0.81-1.48 (about −20% on average); bias shrinks to ±0.4 in all months. Clear win.
- Hub wind: RMSE 1.44-2.66 → 1.13-1.87 (about −25%); bias to ±0.67. Clear win.
- RH: RMSE improves in 9/12 months (largest: Mar 14.8 → 12.1, Nov 12.0 → 9.9); slightly worse in Jun/Jul/Dec.
- GHI: RMSE improves 0-10% in 10/12 months (e.g. Jun 127 → 114, Aug 118 → 107); bias is NOT reliably reduced (Jul +29, Dec +21, Mar +15 after correction), because 2024-25 monsoon bias differs from the 23-year mean. Keep the correction (RMSE gain, monotone) but report this honestly.
- PS (not corrected): fit would cut RMSE 1.6 → 0.7 hPa; irrelevant to the density term (0.15%).
- Fitted coefficients are in the sane range: wind a ≈ 0.79-1.21, b ≈ 0.0-1.0; RH a ≈ 0.91-1.19; GHI a ≈ 0.85-1.0, b ≈ 0-83 W/m².

**Recommendation (D-02 decision rule):** a variable is corrected if at least one calendar month exceeds its threshold on the train years; then all 12 months are fitted (avoids discontinuities at month edges). Result: correct `ghi` (daytime only), `rh`, `ws10`, `ws_hub`. Fit `ws_hub` separately (ERA5 native 80 m vs NASA α-extrapolation has a structurally different bias from the 10 m one), not derived from the corrected 10 m wind. `temp` and `pressure` are logged, not corrected. Thresholds as defaults need no tuning: every flagged variable is flagged by a wide margin, and none sits within 10% of its threshold except GHI Oct (−19.6 vs 20), which is not needed because Jun-Sep already trigger.

Application rules for `apply_correction()`: clip results to physical ranges afterwards (GHI ≥ 0 and re-zero at night, RH to [0,100], wind ≥ 0); GHI correction fitted and applied on daytime rows only; unknown/NaN inputs stay NaN; coefficients JSON at `config/bias_correction.json` with keys `{variable: {month: {a, b, n}}}` plus fit-year metadata. The same coefficients are later applied to GFS (Phase 4 measures that skew).

### 3. pvlib 0.16.1 chain [VERIFIED: introspected + executed]

Signatures (exact):
- `irradiance.get_total_irradiance(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth, dni, ghi, dhi, dni_extra=None, airmass=None, albedo=0.25, surface_type=None, model='isotropic', model_perez='allsitescomposite1990', diffuse_components=False)`
- `temperature.faiman(poa_global, temp_air, wind_speed=1.0, u0=25.0, u1=6.84)`
- `pvsystem.pvwatts_dc(effective_irradiance, temp_cell, pdc0, gamma_pdc, temp_ref=25.0, k=None, cap_adjustment=False)`
- `inverter.pvwatts(pdc, pdc0, eta_inv_nom=0.96, eta_inv_ref=0.9637)`
- `irradiance.get_extra_radiation(datetime_or_doy, solar_constant=1366.1, method='spencer', epoch_year=2014, **kwargs)`

Results with `dc_kwp=1000`, `loss_pct=14`, `dc_ac_ratio=1.2`, tilt 15, azimuth 180, Perez, albedo 0.25, NASA DNI/GHI/DHI evaluated at the interval midpoint:
- AC cap: `inverter.pvwatts(dc, 1e6/1.2)` saturates at exactly 800.0 kW (0.96 × 833,333 W). [VERIFIED]
- pvlib Ineichen clear-sky, 21 Mar: peak POA 1037 W/m², AC peak 745 kW with 14% loss; 800 kW (cap) with 0% loss (DC peak 902 kW before inverter). The CONTEXT/SUMMARY "≈770 kW" corresponds to a smaller loss or different day; assert `700 ≤ peak ≤ 800` and run a separate loss=0 clip test.
- NASA-driven 2024: max AC = 800.0 kW (reached in 2 hours in 2024; mean ~8 h/yr over 25 years), max DC 902 kW. Clearest NASA day (15 Jan 2024, kt ratio 0.9996): peak AC 651 kW (winter).
- Annual yield 1,470 kWh/kWp, CF 16.8% (plausible for Karnataka).
- South vs north POA: 21 Dec clear-sky daily POA ratio S/N = 1.60; 21 Mar = 1.13. Test: S/N > 1.3 on 21 Dec.
- Perez needs `dni_extra` and `airmass`; `Location.get_airmass(solar_position=sp)["airmass_relative"]` is NaN for ~50% of rows (night), so POA is NaN at night. Do `fillna(0)` **only** where midpoint zenith > 90°, never blanket: a blanket fillna would hide real NaN inputs (long gaps).
- With NASA components un-zeroed, 967 night-time rows have AC > 0 (night POA up to 28.6 W/m²) → ALIGN-04 must also zero DNI and DHI at night, and PHYS-06 clamps T1 = 0 for zenith > 90° regardless.
- Input handling gotcha: pass pandas Series on a common index (the DatetimeIndex of the midpoint times) to `get_total_irradiance`, not raw numpy; the returned object is then a DataFrame. With numpy it returns arrays and `.fillna` fails.
- Time handling: NASA label t is the start-of-hour mean, so call solar position and extra radiation at `t + 30 min` and write results back on label `t`.
- Faiman input: `WS10M`; `temp_air`: `T2M` (°C).
- `pdc0` for `pvwatts_dc` is in W (1e6 for 1000 kWp); loss multiplier `(1 - loss_pct/100)` applied to DC before the inverter. [ASSUMED: placement of loss factor on DC side — matches PRD "system losses (soiling, wiring, mismatch, availability)"; Phase 3 calibrates it against the same chain.]

NASA component sanity [VERIFIED]: GHI max 1072, DNI max 1209, DHI max 571 W/m², none negative. Closure (DNI·cos z + DHI)/GHI for zenith < 80°: median 0.943, 5-95% = 0.73-1.04 (sanity log only, per CONTEXT).

### 4. Kaggle `T1.csv` and the power curve (PHYS-04) [VERIFIED: computed]

- File: UTF-8 BOM (`encoding="utf-8-sig"`), columns `Date/Time, LV ActivePower (kW), Wind Speed (m/s), Theoretical_Power_Curve (KWh), Wind Direction (°)`; the degree sign in the last header is mis-encoded, so select columns by name excluding it. 50,530 rows.
- Date format is `"01 01 2018 00:00"` (space-separated, day-first): `pd.to_datetime(..., format="%d %m %Y %H:%M")`. Range 2018-01-01 → 2018-12-31 23:50, monotonic. (Not needed for the curve itself, but Phase 3 needs it.)
- Wind speed 0..25.206 m/s; theoretical max 3600.0; measured max 3618.7; 57 negative-power rows; 3.54% of rows have ws > 4 and power ≤ 0 (matches PRD 3.5%).
- **Binning convention matters.** Median per `floor(w/0.5)*0.5` (left edge) gives a curve shifted ~0.25 m/s high. Use **centre-bins**: `c = round(w*2)/2`, median of the theoretical curve per `c`, which gives the interpolation knot at c itself.
- Curve (centre-bin medians, kW): 3.0 → 16.3, 3.5 → 51.5, 4.0 → 126.3, 5 → ~404, 6 → ~711, 7 → ~1135, 8 → ~1675, 9 → ~2304, 10 → ~2939, 11 → ~3354, 12 → 3520.4, 12.5 → 3580.3, **13.0 → 3600** and 3600 flat to 25.0. Zero below 3.0 (bins 0-2.5 all exactly 0). The theoretical curve is a deterministic function of wind speed (within-bin spread ≤ 352 kW arises only from the floor-bin width; centre-bin spread is small).
- Missing bins: only 25.5 (no data above 25.2). Bins 24.5 and 25.0 have a single row each; the curve is flat 3600 there, so no NaN handling is needed beyond `dropna`. The curve has no cut-out: it stays at 3600 up to 25. **Apply cut-out explicitly** from config (`cut_out_ms` = 25): `v ≥ cut_out → 0`, and `np.interp(..., left=0, right=…)` for v beyond the table.
- Parametric fallback in the PRD ("cubic between cut-in and rated") is a poor match: P = rated·((v−3.5)/(13−3.5))³ gives 382 kW at 8 m/s vs 1,675 kW real. Use the standard form `rated·(v³−vin³)/(vr³−vin³)` (still 784 kW at 8 m/s, which is less wrong) and state in docs that it is only a fallback; tests may pin it with a tolerance only at rated and cut-in/out.
- Air density: ρ = (PS·1000) / (287.05·(T2M+273.15)) with NASA `PS` in kPa. Site mean 1.102 kg/m³ (min 1.035, max 1.168), mean ρ/1.225 = 0.900, so effective speed scale (ρ/1.225)^(1/3) ≈ 0.965 (mean). PRD's "~6% lower" is wrong; the real figure is ~10%. Dry-air formula is adequate (humidity effect ≈ <1%); do not add a humidity term. Apply density **once**, on the hub-height speed.
- Sanity numbers for the NASA 25-year run (hub 80 m, density, curve, 3.5% availability): CF 28.2%, mean hub ws 6.57 m/s, max 3,474 kW; without density CF 30.5%. Monthly CF: Jan .240, Feb .209, Mar .134, Apr .089, May .218, Jun .469, Jul .595, Aug .467, Sep .272, Oct .153, Nov .233, Dec .297 (monsoon-dominated, consistent with PRD §4 expectation).
- α statistics: NASA α = ln(WS50/WS10)/ln5 has median 0.195; clipped low (< 0.05) in 4.0% of hours and **clipped high (> 0.40) in 15.0%**; WS10M < 0.5 in 0.84% of hours; WS50M < WS10M in 0.9%. The clip is therefore active often; do not treat it as a rare safeguard (log counts).
- One hub function for all sources: `hub_wind(ws_low, z_low, ws_up, z_up, z_hub)` with α = ln(ws_up/ws_low)/ln(z_up/z_low), clipped, 0.143 when ws_low < 0.5, result `ws_up·(z_hub/z_up)^α`. NASA: (10 m, 50 m) → 80 m. Open-Meteo: (10 m, 80 m) → 80 m is the identity `ws_up` when `hub_height_m` equals the upper level, so `ws_hub = wind_speed_80m` and the config-driven formula still handles a different hub height.

### 5. Gap statistics [VERIFIED: computed]

| Source | Finding |
|---|---|
| NASA 2001-2025 | 219,144 rows, unique, complete hourly index (0 missing timestamps), **0 NaN** in every column except `ALLSKY_KT` (105,254 NaN = structural night). No physical violations: RH 4.0-100, WS ≥ 0, PS 92.96-95.27 kPa, PREC ≥ 0, T2M 9.2-42.2. Longest run of identical values: 3 h (RH2M: 9 h, high humidity saturation) |
| ERA5 2001-2025 | 219,144 rows, 0 NaN in 14 variables |
| GFS HF | 2021: one leading NaN block of 1,944-1,945 h (to 2021-03-23); precipitation has a second block of 345 h in 2022 (3.9%). No short gaps |
| GFS PR day1 | one leading block of 444 h (10 m variables) or 1,110 h (80/120 m wind); analogous for days 2-3. No short gaps |
| NASA radiation tail | last ~60 days absent (outside 2001-2025, irrelevant) |
| Night nonzero | NASA GHI > 0 at 5,923 of 111,177 night rows (zenith > 90° at midpoint), max 15.35 W/m²; DNI > 0 at 2,320 rows, max 138.4 W/m²; DHI > 0 at 5,923, max 18.0 W/m² |

Consequences for planning: (1) gap-fill must be unit-tested on synthetic gaps (≤3 h inside day, ≤3 h straddling sunrise and sunset, 4 h, leading block); (2) the real cleaning report will show 0.0% missing before and after for NASA, which is a legitimate outcome, but the night-zero and clip counts are real; (3) GFS leading blocks are > 3 h and stay NaN by rule (Phase 4 windows).

## Architecture Patterns

### System Architecture Diagram

```
data/raw/nasa/{y}.json ──nasa_to_frame──> adapters.nasa ─┐
data/raw/openmeteo/archive/era5/{y}.json ───> adapters.openmeteo(shift -1h) ─┤
data/raw/openmeteo/historical_forecast/gfs_seamless/{y}.json ─> (same) ──────┤
data/raw/openmeteo/previous_runs/gfs_seamless/{y}.json (lead 1-3 suffix) ────┤  CANON_COLS frames (UTC, hourly,
data/raw/openmeteo/forecast/gfs_seamless (live, hour-keyed) ────> (same) ────┘  radiation = interval start)
                                          │
              verify_offsets (pvlib midpoint clear-sky) ──> data_notes AUTO:timestamps
                                          │
   NASA frame ──clean(reindex, gaps≤3h, clip, night=0)──> weather_nasa.parquet ──> data_notes AUTO:cleaning
   ERA5 frame ──clean──> weather_era5.parquet
                 │
   NASA vs ERA5 (train 2001-2023) ──consistency──> data_notes AUTO:consistency
                 └─fit monthly a,b (flagged vars)──> config/bias_correction.json
                                          │
   weather_nasa.parquet ──physics.solar (pvlib @ label+30min)──┐
                        ──physics.wind (hub, density, curve)───┴─> constraints ──> energy_sim.parquet (t1_kw, t5_kw)
```

### Recommended Project Structure
```
src/swf/
├── align/
│   ├── canon.py        # CANON_COLS, dtypes, units, validate_canon(df)
│   ├── nasa.py         # NASA adapter (per-group offsets table), uses fetch.parse.nasa_to_frame
│   ├── openmeteo.py    # one adapter for era5 / historical / previous(lead) / live; shift -1h; unit normalisation
│   ├── hub.py          # hub_wind() shared with physics
│   ├── clean.py        # reindex, fill_gaps, clip, zero_night, CleanReport
│   ├── timestamps.py   # centroid/onset verification vs pvlib at midpoint; writes AUTO block
│   ├── consistency.py  # NASA vs ERA5 table; fit_correction(); apply_correction(); JSON io
│   └── cli.py          # run(args) for `align` (or split into build-weather)
├── physics/
│   ├── solar.py        # simulate_solar(df, settings) -> kW
│   ├── wind.py         # load_power_curve(), simulate_wind(df, settings)
│   ├── constraints.py  # enforce(df_or_series, settings) PRD §6
│   └── cli.py          # `physics` / simulate-energy
config/power_curve.csv      # committed, built by `python -m swf curve`
config/bias_correction.json # committed
data/interim/{weather_nasa,weather_era5,weather_gfs_hf,weather_gfs_pr_d1,_d2,_d3,energy_sim}.parquet
```
`write_auto_block` in `swf.coverage.report` is hard-coded to the marker `AUTO:coverage`. Extend it with a `name="coverage"` parameter (default keeps the existing call and `tests/test_coverage.py::test_write_auto_block` working) and use blocks `timestamps`, `consistency`, `cleaning`. The hand-written "Timestamp conventions (preliminary...)" section is replaced by a hand-written final paragraph plus the `timestamps` block.

### CANON_COLS proposal (freeze)

All float64, UTC tz-aware `DatetimeIndex` named `time`, freq `h`.

| Column | Unit | NASA source | Open-Meteo source | Note |
|---|---|---|---|---|
| ghi | W/m² (interval mean, start-labelled) | ALLSKY_SFC_SW_DWN | shortwave_radiation | |
| dni | W/m² | ALLSKY_SFC_SW_DNI | direct_normal_irradiance | |
| dhi | W/m² | ALLSKY_SFC_SW_DIFF | diffuse_radiation | |
| temp | °C | T2M | temperature_2m | |
| rh | % | RH2M | relative_humidity_2m | |
| pressure | hPa | PS × 10 (kPa → hPa) | surface_pressure | unit trap: NASA kPa, Open-Meteo hPa |
| ws10 | m/s | WS10M | wind_speed_10m | requested with `wind_speed_unit=ms` |
| ws_hub | m/s at `hub_height_m` | hub_wind(WS10M, WS50M) | wind_speed_80m via hub_wind | config-driven height |
| wd10 | ° | WD10M | wind_direction_10m | circular: never interpolate linearly |
| wd_hub | ° | WD50M (50 m proxy) | wind_direction_80m | document the proxy |
| precip | mm/h | PRECTOTCORR | precipitation | |
| cloud | % | NaN (NASA has none) | cloud_cover | NaN column in NASA frame |

Dropped on purpose: ALLSKY_KT, CLRSKY_SFC_SW_DWN (recompute clear-sky with pvlib for every source), QV2M, WS50M/WD50M/gti. Phase 4 derives any feature from these. Add a `validate_canon(df)` check (columns exact, order, dtype, tz UTC, hourly freq, no duplicate index) used by every adapter and by the tests; the contract is frozen in this phase by a test that asserts the exact tuple.

### Pattern: offset table in code, verified against data
Keep the offsets in one dict (`OFFSETS = {("nasa","radiation"): 0h, ("nasa","met"): 0h, ("openmeteo","radiation"): -1h, ("openmeteo","instant"): -1h, ("openmeteo","precip"): -1h}`) and write a verifier that, for each cached year, computes centroid and onset *after* applying the offset and fails the build if a candidate offset of ±1 h scores better than the chosen one.

### Pattern: GHI gap fill via clear-sky index
```python
# pvlib at interval midpoint; fill only gaps <=3 h whose whole span + both neighbours are daytime
cs = loc.get_clearsky(idx + pd.Timedelta(minutes=30), model="ineichen")["ghi"].set_axis(idx)
kt = (ghi / cs).where(cs > 5)                       # NaN at night / twilight
kt_f = kt.interpolate(limit=3, limit_area="inside") # only inside valid kt, never across night
ghi_f = ghi.fillna(kt_f * cs)
```
Because kt is NaN at night, a gap that touches sunrise or sunset has no daytime neighbour on one side and `limit_area="inside"` leaves it NaN. Do the same for DNI/DHI with their own clear-sky components. Use pvlib clear-sky (not NASA CLRSKY) as the denominator: NASA CLRSKY shares the gap with GHI and differs from pvlib in magnitude.

Met variables: `interpolate(method="time", limit=3, limit_area="inside")`; direction columns via sin/cos components; leave leading/trailing NaN. `limit=3` fills the first 3 hours of a longer gap, so mask runs > 3 explicitly (compute run lengths and restore NaN where run > 3). This is the common pandas trap.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Solar position, clear-sky, extra-terrestrial, airmass | own ephemeris | `pvlib.location.Location`, `irradiance.get_extra_radiation` | site-validated, already a dependency |
| Plane-of-array transposition | own tilt maths | `irradiance.get_total_irradiance(model="perez")` | needs `dni_extra`/`airmass` |
| Cell temperature, DC, AC | own formulas | `temperature.faiman`, `pvsystem.pvwatts_dc`, `inverter.pvwatts` | AC clip semantics are subtle |
| Power-curve lookup | own loops | `np.interp` on the CSV | vectorised; explicit cut-out |
| Atomic doc updates | rewriting data_notes | `write_auto_block` (extended with `name`) | preserves hand-written sections |
| Config validation | ad-hoc dict reads | pydantic models in `swf.core.settings` (`extra="forbid"`) | bad config fails at load |
| Azimuth mapping | inline `% 360 - 180` | `swf.core.geometry.to_openmeteo_azimuth` | already tested |
| Monthly linear fit | sklearn | `np.polyfit(x, y, 1)` | serving image has no sklearn |

**Key insight:** the deceptively complex parts are semantic (labels, units, conventions); the arithmetic is small. Tests should target conventions.

## Common Pitfalls

### Pitfall 1: Strict onset test rejects the correct convention
**What goes wrong:** applying D-09 as written (≥ 90% exact-hour onset) fails for every source (NASA 59%, ERA5 87%).
**Why:** NASA radiation is smoothed across the sunrise hour; ERA5/GFS round tiny first-hour values to 0.
**How to avoid:** gate on "within {0,+1} h of the interval containing geometric sunrise on ≥ 90% of days AND the opposite convention scores < 90% within the same tolerance", and report the exact-match rate as information. Requires user sign-off as a D-09 refinement (A1).

### Pitfall 2: Per-year centroid on partial years
GFS HF 2021 only has Mar-Dec: centroid diff -0.195 h. Cloud asymmetry also gives HF a -0.09..-0.15 h bias in full years. Gate on pooled full-year values, report per year (A2).

### Pitfall 3: ≤3 h gap fill that fills 3 h of a longer gap
`interpolate(limit=3)` partially fills long gaps. Restore NaN on any run > 3 h. Also leading gaps (GFS HF 2021) must not be back-filled.

### Pitfall 4: Blanket `fillna(0)` on POA
Airmass is NaN at night; blanket fill hides real missing-data NaN. Fill only where zenith > 90°.

### Pitfall 5: Night radiation leaks into PV
5,923 NASA night rows non-zero; zero GHI, DNI **and** DHI at night (using geometric `zenith`, midpoint), then still clamp T1 in the constraint layer.

### Pitfall 6: Pressure units
NASA PS is kPa, Open-Meteo hPa. Canonical = hPa; density formula needs Pa (`hPa·100`). A 10x error here silently gives ρ ≈ 0.11.

### Pitfall 7: Left-edge power-curve bins
Left-edge median biases the curve ~0.25 m/s high (cut-in appears at 3.0 with 28 kW instead of 16 kW). Use centre bins.

### Pitfall 8: Curve has no cut-out
`np.interp` clamps at the right end. Enforce `cut_out_ms` explicitly.

### Pitfall 9: Correction across day/night and clipping
Fit and apply the GHI correction on daytime only, clip and re-zero afterwards; wind/RH clip to physical ranges. Otherwise negative GHI and RH > 100 reappear.

### Pitfall 10: Direction columns
Interpolate/average wind direction via unit vectors; never linear.

### Pitfall 11: Pandas 3 copy-on-write
Never rely on chained assignment (`df[col][mask] = x`); use `df.loc[mask, col] = x`. Default `str` dtype in pandas 3 affects any string column handling (none expected here).

### Pitfall 12: Test data must not depend on gitignored `data/`
`data/` is gitignored. Tests that read real caches must `pytest.skip` when absent; core tests use synthetic frames.

## Code Examples

### Open-Meteo adapter shape
```python
# Source: this research; keys from src/swf/fetch/openmeteo.py (_hourly, previous_day suffix)
def openmeteo_to_canon(raw: bytes, *, lead: int | None = None) -> pd.DataFrame:
    d = json.loads(raw); h = d["hourly"]
    sfx = f"_previous_day{lead}" if lead else ""
    df = pd.DataFrame({k: h[k + sfx] for k in OM_VARS})        # fail loud on missing keys
    df.index = pd.to_datetime(h["time"], utc=True)
    df.index = df.index - pd.Timedelta(hours=1)               # end-of-hour -> start-of-hour (all vars, see §Timestamp)
    ...  # rename to CANON_COLS, hub via hub_wind(), assert freq
```

### PV chain skeleton
```python
# Source: verified in this session against pvlib 0.16.1
mid = df.index + pd.Timedelta(minutes=30)
sp = loc.get_solarposition(mid)
S = lambda c: df[c].set_axis(mid)
poa = irradiance.get_total_irradiance(
    tilt, az, sp.apparent_zenith, sp.azimuth, S("dni"), S("ghi"), S("dhi"),
    dni_extra=irradiance.get_extra_radiation(mid),
    airmass=loc.get_airmass(solar_position=sp)["airmass_relative"],
    albedo=0.25, model="perez")["poa_global"]
night = sp.zenith > 90
poa = poa.where(~night, 0.0).clip(lower=0)                    # NaN stays NaN in daytime
tc = temperature.faiman(poa, S("temp"), S("ws10"))
dc = pvsystem.pvwatts_dc(poa, tc, dc_kwp * 1e3, gamma_pdc) * (1 - loss_pct / 100)
ac_kw = inverter.pvwatts(dc, dc_kwp * 1e3 / ratio, eta_inv_nom=eta) / 1e3
ac_kw = ac_kw.set_axis(df.index)
```
Config-derived cap: `ac_cap_kw = dc_kwp / dc_ac_ratio * eta_inv_nom` (= 800.0). Expose one function `ac_cap_kw(settings)` used by both the inverter call and the constraint layer.

### Wind chain skeleton
```python
rho = df.pressure * 100 / (287.05 * (df.temp + 273.15))
v = df.ws_hub * (rho / 1.225) ** (1 / 3)
p = np.interp(v, curve.speed, curve.kw, left=0.0, right=curve.kw.iloc[-1])
p = np.where(v >= cut_out, 0.0, p) * (1 - availability_loss)
```

### Power-curve builder
```python
t1 = pd.read_csv(path, encoding="utf-8-sig", usecols=["Wind Speed (m/s)", "Theoretical_Power_Curve (KWh)"])
c = (t1["Wind Speed (m/s)"] * 2).round() / 2
curve = t1.groupby(c)["Theoretical_Power_Curve (KWh)"].median()   # centre bins; 51 bins 0.0..25.0
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `pvsystem.pvwatts_ac` (PRD) | `pvlib.inverter.pvwatts` | function absent in 0.16.1 |
| `pvwatts_dc(g_poa_effective=...)` | `effective_irradiance=` positional | keyword removed in 0.16.0 |
| default archive call | `models=era5` | else IFS regime break from 2017 |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | D-09 onset rule must be reformulated as "within {0,+1} h on ≥ 90% of days AND opposite convention < 90%" because the strict exact-match criterion fails for all sources | Pitfall 1 / Empirical 1 | User rejects: Phase 2 cannot ever pass the literal gate; ask at plan time |
| A2 | Gate the centroid rule on pooled full-year values; per-year reported (HF 2021 partial = -0.195 h) | Pitfall 2 | Literal per-year rule fails for HF 2021 |
| A3 | NASA meteorology label t represents an instant ≈ t + 1 h (relative to instantaneous ERA5); basis is the S2 pressure tide (1.0 h) plus lag correlations; temperature/RH evidence is blurred by model phase differences (±0.7 h between ERA5 and GFS) | Empirical 1 | A different met offset (0 h or 2 h) changes lag-feature alignment by 1 h; effect mostly absorbed by the D-02 correction/ML |
| A4 | Loss factor applied on the DC side before the inverter | Empirical 3 | Phase 3 recalibration absorbs it; clipping behaviour near cap changes slightly |
| A5 | Correct all four of ghi/rh/ws10/ws_hub under an "any month exceeds" rule; hub fitted separately | Empirical 2 | If the user prefers per-month trigger only, some months get no correction (discontinuity) |
| A6 | Canonical pressure unit hPa; CANON_COLS names | CANON_COLS | Renames cost Phase 4 only trivially, but the contract is frozen at the end of this phase |
| A7 | PRD's "~6% lower density" is wrong (measured 10%) | Empirical 4 | None; documentation correction |

## Open Questions (RESOLVED)

1. **Accept the A1/A2 refinement of D-09?** The plan should state it and the verifier should log both exact and tolerance rates. Recommendation: accept.
   - **RESOLVED (2026-11-03):** user accepted A1/A2 — see 02-CONTEXT.md D-13. A3 → D-14 (NASA met 0 h, pinned by test), A4 → D-16 (loss on DC side), A5 → D-17 (correct ghi/rh/ws10/ws_hub, any-month rule).
2. **Does GHI correction help Phase 4?** In 2024-25 it improves RMSE modestly but not bias in every month. Recommendation: apply as D-02 says, report diagnostics, let Phase 4 compare lag features raw vs corrected.
   - **RESOLVED:** apply GHI correction (D-17); report diagnostics; Phase 4 compares raw vs corrected.
3. **GFS vs ERA5 consistency** is out of scope here (deferred) but the adapter must make GFS HF frames comparable (same shift), so Phase 4 can measure it.
   - **RESOLVED:** out of scope; GFS adapters apply the same −1 h shift (D-15).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + uv | everything | ✓ | uv env | — |
| pvlib | physics, alignment verifier | ✓ | 0.16.1 | — |
| pandas / numpy / pyarrow | frames, parquet | ✓ | pandas 3.0.x | — |
| `data/raw/nasa`, `data/raw/openmeteo/*` | adapters | ✓ | 25 yr / 25 yr / 5 yr / 2 yr | — |
| `data/raw/kaggle/T1.csv` | power curve | ✓ | 50,530 rows | parametric curve |
| Network | none | not needed | — | — |

No blocking missing dependencies. The pvlib Ineichen Linke-turbidity table ships with pvlib (ran offline).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2 (existing, 83 tests green) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "-q -m 'not network'"`) |
| Quick run command | `uv run pytest -q tests/test_align_*.py tests/test_physics_*.py` |
| Full suite command | `uv run pytest` |

Add marker `realdata` (skips when `data/raw/...` absent) next to `network` and `gpu`.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ALIGN-01 | Each adapter returns exact `CANON_COLS`, tz UTC, hourly, units (hPa, hub col); frozen tuple | unit | `uv run pytest -q tests/test_align_canon.py` | ❌ Wave 0 |
| ALIGN-01 | Open-Meteo shift is -1 h for radiation, instantaneous and precip; NASA 0 h; PR lead suffix handled; live frame same adapter | unit (fixtures `om_*_sample.json`, `nasa_sample.json`) | `uv run pytest -q tests/test_align_adapters.py` | ❌ Wave 0 |
| ALIGN-02 | Verifier recovers a known offset on a synthetic series built from pvlib clear-sky (start- and end-labelled) and rejects the wrong one | unit | `uv run pytest -q tests/test_align_timestamps.py` | ❌ Wave 0 |
| ALIGN-02 | Real data: pooled centroid within ±0.15 h and onset-tolerance ≥ 90% for NASA, ERA5, HF, PR | realdata | `uv run pytest -q -m realdata tests/test_align_timestamps.py` | ❌ Wave 0 |
| ALIGN-03 | Gaps ≤3 h inside daytime filled (GHI via clear-sky index), gaps straddling sunrise/sunset not filled, 4 h gap stays NaN entirely, leading block not back-filled, index complete, clip counts reported | unit (synthetic) | `uv run pytest -q tests/test_align_clean.py` | ❌ Wave 0 |
| ALIGN-04 | GHI, DNI, DHI are 0 where midpoint zenith > 90°; counts logged | unit | same file | ❌ Wave 0 |
| ALIGN-05 | Consistency table columns (bias, RMSE, corr by month), sign convention ERA5 − NASA, daytime GHI mask | unit (synthetic known bias) | `uv run pytest -q tests/test_align_consistency.py` | ❌ Wave 0 |
| ALIGN-06 | Fit recovers known a,b on synthetic data; threshold decision per variable; `apply_correction` identical call from training and serving paths; clips (GHI ≥ 0, RH ≤ 100); JSON round-trip; train-years-only fit | unit | same file | ❌ Wave 0 |
| PHYS-01/02 | Clear-sky day: 0 at night, 700 ≤ peak ≤ 800 with loss 14; loss 0 and huge irradiance → exactly `ac_cap_kw`==800.0; cap derived from config | unit | `uv run pytest -q tests/test_physics_solar.py` | ❌ Wave 0 |
| PHYS-03 | Azimuth mapping (exists); S/N POA ratio > 1.3 on 21 Dec | unit | `uv run pytest -q tests/test_geometry.py tests/test_physics_solar.py` | ✅ / ❌ |
| PHYS-04 | Power curve builder (BOM, `%d %m %Y %H:%M`, centre bins, 0 below 3.0, 3600 at ≥13); interpolation; cut-out; density factor (pressure kPa→hPa trap); hub α clip and 0.143 rule; hub identity for 80 m source; parametric fallback when file absent | unit (tiny synthetic T1.csv with BOM) | `uv run pytest -q tests/test_physics_wind.py` | ❌ Wave 0 |
| PHYS-05 | Unit conversions (kPa/hPa, kW/W), the above | unit | `uv run pytest -q tests/test_physics_*.py` | ❌ Wave 0 |
| PHYS-06 | Constraint layer clamps T1 [0, cap], T1=0 at night, RH [0,100], GHI ≥ 0 and 0 at night, WS ≥ 0, T5 [0, 3600]; NaN preserved; idempotent | unit | `uv run pytest -q tests/test_physics_constraints.py` | ❌ Wave 0 |
| config | New settings keys parsed with `extra=forbid`; bad values rejected | unit | `uv run pytest -q tests/test_config.py` | ✅ extend |

### Network-free fixtures
- Synthetic builder in `tests/synth.py` (or `conftest.py`): `make_nasa_like(start, days, convention="start")` that integrates pvlib clear-sky over each hour (minute resolution) so interval means are exact; `make_om_like` is the same series labelled at the interval end. Add controllable cloud factor, gaps and night leakage. This gives ground-truth offsets without any cached data.
- Existing fixtures: `nasa_sample.json`, `om_era5_sample.json`, `om_hf_sample.json`, `om_pr_sample.json`, `om_live_gfs_seamless.json` for adapter shape tests.
- Tiny `T1_sample.csv` with a BOM and `dd mm yyyy` dates written to `tmp_path` in the test (do not commit large files).
- The existing `no_sleep`/`mock_client` fixtures are not needed (no HTTP in this phase).

### Sampling Rate
- **Per task commit:** quick command above
- **Per wave merge:** `uv run pytest`
- **Phase gate:** full suite green plus `uv run pytest -m realdata`, and `uv run ruff check src tests`, before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/synth.py` synthetic generators (clear-sky interval means, controllable convention)
- [ ] `tests/test_align_canon.py`, `test_align_adapters.py`, `test_align_timestamps.py`, `test_align_clean.py`, `test_align_consistency.py`
- [ ] `tests/test_physics_solar.py`, `test_physics_wind.py`, `test_physics_constraints.py`
- [ ] `realdata` marker registration in `pyproject.toml`
- [ ] Config schema extension in `swf.core.settings` + `config/plant.yaml`/`site.yaml`: physics keys (clip bounds, gap limit hours, correction thresholds, rho0, albedo, curve path, normalisation capacities `ac_cap` derived)
- [ ] `write_auto_block(name=...)` generalisation + updated `tests/test_coverage.py` expectations (default behaviour unchanged)
- [ ] No new package installs

## Security Domain

`security_enforcement` not disabled; the phase is offline file processing with no network, auth, or user input.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2/V3/V4 | no | no auth/session/access control in this phase |
| V5 Input Validation | yes | pydantic config models (`extra=forbid`); `validate_canon`; reject malformed Kaggle/raw files with explicit errors |
| V6 Cryptography | no | SHA-256 sidecars already handled in Phase 1 |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Corrupted/tampered raw cache | Tampering | adapters read via the existing sidecar-verified cache; fail on missing keys instead of defaulting |
| Path traversal in config paths (`power_curve` path) | Tampering | resolve under `CONFIG_DIR` only |
| Silent NaN/sentinel propagation | Integrity | `validate_canon` asserts no sentinel values; constraint layer preserves NaN but never emits out-of-bound values |

## Project Constraints (from CLAUDE.md)
- `docs/PRD.md` is the source of truth; `.planning/research/SUMMARY.md` errata override it (AC function, cap, azimuth).
- Weather data via httpx directly; cache under `data/raw/`; no network in this phase.
- UTC internally; IST only in the frontend.
- Time-based splits only (no shuffling) — not touched here.
- Every model compared against baseline 3 — Phase 4+; this phase's physics module is the shared baseline-3 code path.
- Site/plant values from `config/*.yaml`, never hard-coded (loss %, tilt, azimuth, hub height, cap, availability).
- Run pytest before declaring any phase done.
- Kaggle files from `python -m swf kaggle`; stop and ask if missing (`require_kaggle_files`).
- Stack: Python 3.12, pandas 3.0.x, pvlib 0.16.1; serving image torch-free (so `swf.align`/`swf.physics` must import neither torch nor sklearn).
- One commit per task with the Co-Authored-By trailer.

## Sources

### Primary (HIGH confidence)
- Cached data under `data/raw/{nasa,openmeteo,kaggle}` analysed locally with pandas 3.0 / pvlib 0.16.1 (this session): all numeric findings above.
- pvlib 0.16.1 introspected signatures and executed chain.
- `docs/PRD.md` §4-§7, `docs/data_notes.md`, `.planning/research/{STACK,SUMMARY,PITFALLS}.md`, Phase 1 context and research.

### Secondary (MEDIUM confidence)
- S2 pressure-tide phase (~10 h local solar time maxima) as a physical anchor for the NASA met timestamp: standard atmospheric-tide knowledge [ASSUMED from training; the measured NASA/ERA5 phase difference of 1.0 h is data].

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no new packages; versions from pyproject)
- Architecture: HIGH for shapes; MEDIUM for CLI names (discretion)
- Timestamp offsets: HIGH for radiation; MEDIUM for NASA met
- Consistency/correction: HIGH (computed) with the GHI-bias caveat
- Pitfalls: HIGH (each reproduced)

**Research date:** 2026-11-03
**Valid until:** stable until the cached data or pvlib version changes (30+ days)
