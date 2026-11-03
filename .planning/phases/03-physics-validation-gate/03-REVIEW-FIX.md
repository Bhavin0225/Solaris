---
phase: 03-physics-validation-gate
fixed_at: 2026-11-03
review_path: .planning/phases/03-physics-validation-gate/03-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

Scope: critical and warning findings (IN-01..03 not in scope). All five fixed in b85c143; validation outputs and docs regenerated in 7af8d14.

| Finding | Fix | Files |
|---|---|---|
| WR-01 held-out leaks into anchor | `peak_ac_kw` = max over rows before the held-out start (22-inverter filter); all-rows peak kept as `peak_ac_kw_all_rows` | kaggle_solar.py, test_validate_solar_parse.py |
| WR-02 Plant 2 failure aborts run | non-gating plants wrapped in try/except (ValueError, SystemExit), recorded as `{"gating": false, "error": ...}`; gating plants still raise | run.py, test_validate_outputs.py |
| WR-03 silent parametric fallback | `simulate_t1` reads `config/power_curve.csv` explicitly, FileNotFoundError if absent | kaggle_wind.py, test_validate_wind.py |
| WR-04 duplicate / NaN rows | duplicate (DATE_TIME, SOURCE_KEY) raises; inverter count uses `count` of AC_POWER so NaN drops the timestamp | kaggle_solar.py, test_validate_solar_parse.py |
| WR-05 BOM | `encoding="utf-8-sig"` on both solar reads | kaggle_solar.py |

## Effect on results (metrics.json)

- Plant 1 (gating): unchanged. Its tune-window peak is the full-span peak (29150.2 kW): held-out 3.36%, 4.34% at configured 14%, tuned loss 9%.
- Plant 2 (non-gating): AC cap 25979.8 → 25409.6 kW, tuned loss 17 → 15%, held-out 14.39 → 14.74%. Still a documented miss.
- Wind: unchanged.

Verification: `uv run pytest -o addopts=""` 229 passed; ruff clean; `swf validate` exit 0. config/plant.yaml untouched, simulate-energy not run.
