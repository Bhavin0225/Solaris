---
phase: 02-alignment-cleaning-physics
fixed_at: 2026-11-03T00:00:00Z
review_path: .planning/phases/02-alignment-cleaning-physics/02-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 5
skipped: 1
status: partial
---

# Phase 2: Code Review Fix Report

**Source review:** .planning/phases/02-alignment-cleaning-physics/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, WR-01..WR-05)
- Fixed: 5
- Skipped: 1 (WR-05, stopped per instruction)

## Fixed Issues

### CR-01: GHI bias correction adds irradiance where the reference is near zero
**Files modified:** `src/swf/align/consistency.py`, `tests/test_align_consistency.py`, `config/bias_correction.json`, `docs/data_notes.md`
**Commits:** 0bc6cc9 (code, test), eae04c9 (regenerated coefficients and data_notes)
**Applied fix:** `fit_correction` fits GHI through the origin (b = 0, a = sum(xy)/sum(x^2), fit_years only, daytime pairs). Other variables keep a*x+b. Night re-zero in `apply_correction` kept. New test checks b == 0 for all months and that zero reference GHI stays 0.
**Held-out 2024-2025 GHI (all months), before vs after:**
- Raw: bias -6.710, RMSE 95.565 W/m2 (unchanged by the fix)
- Corrected before fix: bias +9.963, RMSE 90.824
- Corrected after fix: bias -2.307, RMSE 95.623, corr 0.943 -> 0.942
- Result: bias magnitude improved (-6.71 vs -2.31), but the earlier RMSE gain (90.8) is gone; the corrected RMSE is level with raw (95.6). That RMSE gain was partly an artefact of the intercept. GHI now has no measurable skill gain on held-out data.
**D-17 decision for ghi:** unchanged ("abs bias > 20", months 6,7,8,9, corrected = yes). New monthly a: 0.979 to 1.058, b = 0.
**Note:** `data_notes.md` hand-written held-out prose (outside the AUTO block) was updated to match the new numbers.
**Status:** fixed: requires human verification (logic change).

### WR-01: build.run wrote outputs before the timestamp gate
**Files modified:** `src/swf/align/build.py`, `src/swf/align/consistency.py`
**Commit:** b009caf
**Applied fix:** All sources are loaded and verified first; any failure prints and returns 1 before any write. Parquets and `bias_correction.json` are written to a `.tmp` path and moved with `os.replace`. Side effect: on a failing run the data_notes timestamps block is no longer rewritten.

### WR-02: Night NaN radiation not zeroed
**Files modified:** `src/swf/align/clean.py`, `tests/test_align_clean.py`
**Commit:** 22981d0
**Applied fix:** After gap fill, radiation at night rows is set to 0. `test_sunrise_sunset_stay_nan` updated: night hours in the gap are now 0, daylight hours stay NaN. Added a long-night-gap test.

### WR-03: Filled radiation not clipped
**Files modified:** `src/swf/align/clean.py`, `tests/test_align_clean.py`
**Commit:** 22981d0
**Applied fix:** kt capped at `KT_MAX = 1.5` and filled values clipped to `PHYS_RANGES[c]`.

### WR-04: Settings validation gaps
**Files modified:** `src/swf/core/settings.py`, `tests/test_config.py`
**Commit:** d6a77c3
**Applied fix:** `dc_kwp`, `dc_ac_ratio` > 0; `eta_inv_nom` in (0,1]; `loss_pct` in [0,100) (config uses percent, 14); `rated_kw`, `hub_height_m` > 0; `availability_loss` in [0,1); `0 <= cut_in < rated < cut_out`; NASA `start_year <= end_year`; `fit_years` inside both NASA and ERA5 year ranges. Parametrized rejection test added.

## Skipped Issues

### WR-05: Onset test partly masks early-label errors
**File:** `src/swf/align/timestamps.py:14`, `:42`
**Reason:** Stopped per instruction, because the strengthened check changes PASS results on real data. I added a night-leak check to `verify` (fraction of raw night rows, zenith(mid) > 90, above 5 W/m2 must be <= 1%) plus a one-hour-early test. The synthetic test passed, but all 6 real-data sources (`test_real_convention`) then failed. Measured night leak on real data: nasa 2.54%, era5 2.38%, gfs_hf 2.87%, gfs_pr_d1 2.73% (mean positive 7-9 W/m2, max 16). These are genuine twilight hours straddling sunrise/sunset whose midpoint zenith is just over 90. A one-hour-early label would leak roughly 15%+ (about 2 of ~12 night hours a day). A threshold near 5% would separate the cases, but picking it is a decision about the test, so I reverted all WR-05 changes (nothing committed). Alternatives for the owner: threshold ~5%, or count only rows with zenith(mid) > ~92 so twilight is excluded.
**Original issue:** Both tests zero every row with zenith(mid) > 90 first, so spurious early positives are removed and the first positive hour still matches sunrise; "PASS" is weak evidence against early shifts.

## Verification

- `uv run pytest -o addopts=""` (includes realdata): 190 passed, 16 warnings in 184.71s
- `uv run ruff check src tests`: All checks passed!

---

_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
