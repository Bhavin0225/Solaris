---
phase: 02-alignment-cleaning-physics
reviewed: 2026-11-03T00:00:00Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - src/swf/align/__init__.py
  - src/swf/align/adapters.py
  - src/swf/align/build.py
  - src/swf/align/canon.py
  - src/swf/align/clean.py
  - src/swf/align/consistency.py
  - src/swf/align/timestamps.py
  - src/swf/cli.py
  - src/swf/core/settings.py
  - src/swf/coverage/report.py
  - src/swf/physics/__init__.py
  - src/swf/physics/common.py
  - src/swf/physics/constraints.py
  - src/swf/physics/simulate.py
  - src/swf/physics/solar.py
  - src/swf/physics/wind.py
  - config/site.yaml
  - config/plant.yaml
  - config/bias_correction.json
  - pyproject.toml
  - tests/conftest.py
  - tests/synth.py
  - tests/test_align_adapters.py
  - tests/test_align_canon.py
  - tests/test_align_clean.py
  - tests/test_align_consistency.py
  - tests/test_align_timestamps.py
  - tests/test_cli.py
  - tests/test_config.py
  - tests/test_coverage.py
  - tests/test_physics_common.py
  - tests/test_physics_constraints.py
  - tests/test_physics_solar.py
  - tests/test_physics_wind.py
  - tests/test_pipeline.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-11-03
**Depth:** standard
**Files Reviewed:** 36 (the tests/ files other than test_pipeline.py and test_physics_constraints.py were not read in detail; see Summary)
**Status:** issues_found

## Summary

The pvlib 0.16.1 API usage is correct (`inverter.pvwatts`, Perez with `dni_extra` and `airmass`, azimuth 180 = south). NASA -999 is masked before anything else. The bias-correction fit uses `fit_years` only, so there is no time leakage. Nothing in the reviewed code shuffles data. The main defect is in the ghi bias correction: its intercept injects irradiance at sunrise and sunset. The other findings concern pipeline ordering, unclipped fill output, and weak validation.

This review is read-only. I did not run the code or the tests. The ghi finding rests on the committed `config/bias_correction.json` and on reading `apply_correction`.

## Critical Issues

### CR-01: GHI bias correction adds up to ~83 W/m2 where the reference is near zero in daylight

**File:** `src/swf/align/consistency.py:106-113` (coefficients in `config/bias_correction.json`)
**Issue:** The correction is an unconstrained affine map `a*x + b`, applied to every row whose midpoint zenith is 90 degrees or less. `b` is large for ghi: about 83.0 in month 7, 74.9 in month 6, 68.7 in month 8, and 59.2 in month 9. At sunrise and sunset (zenith just under 90, ref GHI of 0-5 W/m2) the corrected GHI becomes 60-90 W/m2. The night mask uses `zenith > 90`, so it does not catch these rows. The clip to `PHYS_RANGES` only bounds the range. The corrected frame is the Phase 4/5 model input. It also feeds the "held-out corrected" diagnostics and the Perez/PV chain, so a spurious ~80 W/m2 appears at the first and last daylight hours of every day in the monsoon months.
**Fix:** Preserve zero, and avoid the dilution of a free intercept. Either fit through the origin (`a = sum(x*y)/sum(x*x)`, `b = 0`), or apply the correction multiplicatively and keep the intercept off the low end:
```python
if var == "ghi":
    y = y.where(x > 0, 0.0).mask(night & x.notna(), 0.0)  # never create irradiance where ref is 0
```
Re-run `build-weather` and check the held-out table afterwards.

## Warnings

### WR-01: `build.run` overwrites committed coefficients and parquets before the timestamp gate

**File:** `src/swf/align/build.py:175-229`
**Issue:** `save_coefs(...)` writes `config/bias_correction.json` and the interim parquets are written inside the loop. The `failed` check, which returns 1, comes last. A run where a source fails timestamp verification still replaces the committed coefficients. The coefficients are then fitted from data whose alignment was just shown to be wrong. Writes are also not atomic: an exception partway through leaves a mix of new parquets and an old JSON.
**Fix:** Run `verify` for all sources first. If any fails, print the failure and `return 1` before any write. Then do the clean, fit and write steps. Write `bias_correction.json` last, via a temp file and `os.replace`.

### WR-02: Night-time NaN radiation is not zeroed unless it is a short interior gap

**File:** `src/swf/align/clean.py:80-82` and `src/swf/align/clean.py:46-55`
**Issue:** Night zeroing only touches `night & notna()`. A NaN at night is filled with 0 only if it sits in an interior run of at most `max_gap_h` hours. A missing night longer than 3 hours (all 12 hours of a missing day, or a source that starts or ends at night) stays NaN. Radiation at night is physically 0, and `simulate_solar` has to cope with the NaN.
**Fix:** After the gap fill, add `d.loc[night, list(RADIATION)] = 0.0`. This also removes the need for the `allnight` logic for the night part.

### WR-03: Filled radiation is not re-clipped to physical limits

**File:** `src/swf/align/clean.py:52-55`
**Issue:** `filled = (_interp(kt) * cs).clip(lower=0)` has no upper bound. `kt = x/cs` is evaluated wherever `cs > 5`, so kt near the horizon can be very large. Interpolating it and multiplying by a larger `cs` can exceed `PHYS_RANGES` (1400, or 800 for dhi). `validate_canon` does not check ranges, so nothing catches this.
**Fix:** Clip the filled values to `PHYS_RANGES[c]` (and cap kt, for example at 1.5) before assigning.

### WR-04: Settings validation misses values that cause ZeroDivision, NaN or nonsense

**File:** `src/swf/core/settings.py:181-200`
**Issue:** `dc_ac_ratio` has no `gt=0` (`pdc0_w` divides by it). `eta_inv_nom` and `availability_loss` have no range. `loss_pct` has no range. Nothing enforces `cut_in < rated < cut_out`. `rated_kw` and `hub_height_m` are not required to be positive. `NasaCfg.end_year >= start_year` is not checked. `fit_years` is not checked against the NASA or ERA5 year ranges, so a bad fit window makes `polyfit` fail or silently use nothing. The project's stated pattern is that a bad config should fail at load.
**Fix:** Add `Field(gt=0)` and `Field(ge=0, lt=1)` bounds, and a `model_validator` on `Settings` that checks `cut_in < rated < cut_out`, `start_year <= end_year`, and `fit_years` inside the NASA and ERA5 ranges.

### WR-05: The onset test partly masks early-label errors it is meant to catch

**File:** `src/swf/align/timestamps.py:14` and `src/swf/align/timestamps.py:42`
**Issue:** Both tests first zero every row with `zenith(mid) > 90`, then look at the first positive hour. If the data were labelled one hour too early, the spurious early positives fall in the night mask and are removed. The first positive hour then equals the sunrise hour, so `onset_tol` still passes. Only the opposite-convention check (positives one hour late) and the centroid test, which uses the same masked series, can see the error. The "PASS" is therefore weaker evidence for early shifts than the report implies.
**Fix:** Run `onset_rates` and `centroid_diff` on the unmasked series (night values only forced to 0 for NaN), or add a check that counts positive raw values inside the night mask, for example "more than 1% of rows with zenith > 90 are > 5 W/m2 means FAIL".

## Info

### IN-01: Last label of each Open-Meteo source is NaN after the -1 h shift

**File:** `src/swf/align/adapters.py:57-64`
**Issue:** Shifting labels by -1 h moves the final raw row to the hour before it. `clean` reindexes to `[y0-01-01 00:00, y1-12-31 23:00]`, so the label `y1-12-31 23:00` has no source row and is NaN. It sits at the edge, so the gap fill (interior only) leaves it NaN.
**Fix:** Log it, or exclude the final hour from the reindexed range for Open-Meteo sources.

### IN-02: Dead and fragile code in the GHI closure log

**File:** `src/swf/align/build.py:187-202`
**Issue:** `mid` is only used as `mid[0]` in a log line, where it labels nothing meaningful. `solar_position(nasa.index, s)` is computed twice. `np.nanpercentile(ratio, ...)` raises on an empty `ratio` if `day` selects nothing.
**Fix:** Compute `zen` once, drop `mid`, and guard on `len(ratio)`.

### IN-03: OLS regression of NASA on ERA5 attenuates the slope

**File:** `src/swf/align/consistency.py:78`
**Issue:** Fitting y = NASA on x = ERA5 with noise in x biases the slope low. The a values for ghi in June to August (0.85-0.89) and the lack of variance preservation shrink the variability of the corrected inputs. This is a design choice, but it is not documented as a limitation.
**Fix:** Note it in `docs/data_notes.md`. Consider mean/std matching or fitting through the origin for ghi (see CR-01).

### IN-04: Tests are coupled to specific config values

**File:** `tests/test_pipeline.py:68` and `tests/test_pipeline.py:106`
**Issue:** `"833.3" in out and "800.0" in out` and `d["fit_years"] == [2001, 2023]` hard-code values that come from `config/*.yaml`. This conflicts with the "values come from config" rule, and the tests break if the plant config changes.
**Fix:** Format the expected strings from `ac_cap_kw(S)` and `S.align.fit_years`.

---

_Reviewed: 2026-11-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
