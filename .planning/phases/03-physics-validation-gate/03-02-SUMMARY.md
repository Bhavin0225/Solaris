---
phase: 03-physics-validation-gate
plan: 02
subsystem: validation
tags: [solar, kaggle, pvlib, nrmse]
requires: [03-01]
provides: [load_plant, heldout_start_utc, plant_settings, simulate_plant, tune_loss, validate_plant]
affects: [03-04]
key-files:
  created:
    - src/swf/validate/kaggle_solar.py
    - tests/test_validate_solar_parse.py
    - tests/test_validate_solar_tune.py
metrics:
  completed: 2026-11-03
---

# Phase 3 Plan 02: Solar validator Summary

Pure-function Kaggle solar validator: explicit-format parsing, all-22-inverter filter, single local-to-UTC conversion, capacity-anchored loss tuning (8..20) on 15-31 May, held-out scoring on 1-17 June via the shared `ac_from_poa`.

## Tasks
1. load_plant / heldout_start_utc with units, span, duplicate checks and dropout stats.
2. plant_settings / simulate_plant / tune_loss / validate_plant (JSON-ready dict).

## Real-data check (read-only, main checkout Kaggle files)
- Plant 1: tuned loss 9, tune 2.82%, held-out 3.36%, full 3.11%, full at configured 14% = 4.26%, hourly 2.07% (matches RESEARCH).
- Plant 2 (non-gating): tuned loss 17 (not at the edge; RESEARCH guessed 20), tune 10.04%, held-out 14.39%, full 13.25%, full at 14% = 13.79%, hourly 10.79%.

## Deviations
- Test fixtures use `date` objects for `span_local` because `model_copy` skips validation (test-only).
- `uv run` needed `--offline` (PyPI unreachable for hatchling build); no dependency changes.

## Self-Check: PASSED
Full suite: all 191 tests passed (quiet output, no failures); `ruff check src tests` clean.
