---
phase: 02-alignment-cleaning-physics
plan: 06
subsystem: physics
tags: [wind, power-curve, air-density]
requires: [02-01, 02-08]
provides: [swf.physics.wind, config/power_curve.csv, "swf curve"]
key-files:
  created: [src/swf/physics/wind.py, tests/test_physics_wind.py, config/power_curve.csv]
  modified: [src/swf/cli.py, tests/test_cli.py]
completed: 2026-11-03
---

# Phase 2 Plan 06: Wind chain Summary

Empirical centre-bin power curve from Kaggle T1.csv (51 bins, committed), parametric fallback with warning, and `simulate_wind` (density once on hub speed, cut-out, availability loss), plus `python -m swf curve`.

**Commits:** feat(02-06) wind chain; feat(02-06) curve command + committed CSV.

## Deviations from Plan

**1. [Rule 1 - Bug in plan numbers] Curve value at 8.0 m/s is 1527 kW, not ~1675.**
Research's 1675 is the left-edge bin [8.0, 8.5) median (verified: 1674.8). The centre-bin median, which the plan itself mandates, is 1527.0 (3.0 -> 16.3, 13.0 -> 3600 match). Pinning test range changed from 1600-1750 to 1450-1600. Also the fallback-curve rationale quoting 1,675 should be read as ~1,527 in data_notes (plan 02-07).

## Verification
Full suite: 148 passed, 1 skipped, 13 deselected (ruff clean). Run in the worktree venv; data/raw/kaggle copied from main checkout (gitignored).

## Self-Check: PASSED
