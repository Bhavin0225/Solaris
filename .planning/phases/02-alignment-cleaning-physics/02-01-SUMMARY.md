---
phase: 02-alignment-cleaning-physics
plan: 01
subsystem: align/physics
tags: [canon, pvlib, hub-wind, air-density]
requires: []
provides:
  - swf.align.canon (CANON_COLS, UNITS, PHYS_RANGES, validate_canon)
  - swf.physics.common (location, midpoints, solar_position, is_night, clearsky, hub_wind, air_density)
  - tests/synth.py (clearsky_hourly, canon_frame)
affects: [02-02..02-07]
key-files:
  created:
    - src/swf/align/canon.py
    - src/swf/physics/common.py
    - tests/synth.py
    - tests/test_align_canon.py
    - tests/test_physics_common.py
metrics:
  completed: 2026-11-03
---

# Phase 2 Plan 01: Shared contracts Summary

Frozen 12-column `CANON_COLS` contract with a strict validator, plus midpoint (label + 30 min) sun/atmosphere helpers and exact-interval-mean synthetic builders for wave-2 plans.

## Commits
- a148c4c: swf.physics.common + tests
- 9a5b1d2: swf.align.canon, tests/synth.py + tests

## Deviations from Plan
None. Full suite passes (97 tests). Ruff is clean on the new files; 14 pre-existing ruff findings in older files are out of scope. A blanket `ruff format` briefly reformatted unrelated files; these were reverted before committing.

## Self-Check: PASSED
