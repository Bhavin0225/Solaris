---
phase: 02-alignment-cleaning-physics
verified: 2026-11-03
status: passed
score: 5/5
requirements: [ALIGN-01, ALIGN-02, ALIGN-03, ALIGN-04, ALIGN-05, ALIGN-06, PHYS-01, PHYS-02, PHYS-03, PHYS-04, PHYS-05, PHYS-06]
---

# Phase 02 Verification: Alignment, Cleaning & Physics

**Status: passed (with advisory warnings).** 5/5 roadmap success criteria verified; all 12 requirement IDs accounted for.

Evidence: `uv run pytest -o addopts=""` gave 183 passed (realdata included), run independently by the verifier and the orchestrator. The code and `docs/data_notes.md` were read. The source contains no TBD, FIXME or XXX markers.

## Success criteria

1. **VERIFIED: adapters + timestamps.**
   - `docs/data_notes.md` AUTO:timestamps records the per-group offsets: NASA 0 h, Open-Meteo -1 h.
   - All six gating sources (nasa, era5, gfs_hf, gfs_pr_d1..d3) PASS the D-13 check:
     - sunrise onset within {0,+1} h on 100% of days;
     - pooled diurnal centroid within ±0.15 h;
     - pvlib evaluated at label + 30 min.
   - The offsets live in `swf.align.adapters.OFFSETS` and are tested in `tests/test_align_adapters.py` and `tests/test_align_timestamps.py`.
2. **VERIFIED: cleaning.**
   - `tests/test_align_clean.py` covers:
     - the complete reindex;
     - filling of gaps of 3 h or less;
     - no fill across sunrise or sunset;
     - long gaps staying NaN;
     - clip counts;
     - night zeroing.
   - AUTO:cleaning logs `clipped_low`, `clipped_high` and `night_zeroed` per source, variable and year.
3. **VERIFIED: consistency + correction.**
   - AUTO:consistency holds the monthly NASA vs ERA5 bias, RMSE and correlation for ghi, rh, ws10 and ws_hub. Temperature and pressure are log-only.
   - The D-17 decision is recorded: ghi, rh, ws10 and ws_hub are corrected.
   - `apply_correction()` is the single train/serve function.
   - The coefficients in `config/bias_correction.json` are fitted on 2001-2023 only, and the held-out 2024-2025 diagnostics are reported.
4. **VERIFIED: physics chain.**
   - Solar:
     - The 21 March clear-sky peak is 788.4 kW at 14% DC-side loss, inside the 700-800 kW range.
     - `test_saturates_at_cap`: exactly 800 kW at zero loss, never above it.
     - `test_cap_derived`: pdc0 = 833.3 kW.
     - Night output is 0.
     - `test_south_vs_north` passes, and the azimuth conversion is tested in `tests/test_geometry.py`.
   - Wind: the config-driven empirical curve gives about 1,527 kW at 8 m/s; the plan's 1,675 kW was the wrong bin and has been corrected in the docs.
5. **VERIFIED: constraint layer.**
   - `swf.physics.constraints.enforce` clips:
     - t1 to the AC cap and t5 to 3600 kW;
     - rh to 0-100;
     - ghi, ws10 and ws_hub to ≥ 0;
     - t1 and ghi to 0 at night.
   - `tests/test_physics_constraints.py::test_bounds` proves it.

## Requirements coverage

ALIGN-01..06 and PHYS-01..06 are all Complete in REQUIREMENTS.md and mapped to Phase 2, each with supporting code and tests. None are orphaned.

## Code review findings (02-REVIEW.md): advisory, none break a criterion

- **CR-01:** the GHI correction `a*x+b` adds the monsoon intercept (about 60-86 W/m², Jun-Sep) at low daytime irradiance.
  - Measured on real ERA5: 22 daytime hours in 2001-2025 have ref GHI < 5 W/m²; their corrected mean is 40 W/m² (July 86 W/m²).
  - The intercept also lifts other low-irradiance hours.
  - **Fix before Phase 4 training**: fit GHI through the origin, or gate the correction on x > 0.
- **WR-01:** `build.run` writes the coefficients and parquets before the timestamp gate, and the writes are not atomic. This is a robustness risk; it doesn't fail today.
- **WR-02 / WR-03:** night gaps longer than 3 h stay NaN, and filled radiation is not re-clipped. Both are minor.
- **WR-04:** settings range checks are missing.
- **WR-05:** the onset test masks one-hour-early label errors. The centroid check still constrains the offset.

## Human judgement (non-blocking)

- Is the 788 kW clear-sky peak physically plausible? It is inside the criterion range of 700-800 kW. Flagged in data_notes for verify-work.

## Not checked

- `build-weather` and `simulate-energy` were not re-run during verification. The real-data numbers come from the committed AUTO blocks and the realdata tests.
