---
phase: 02-alignment-cleaning-physics
plan: 05
subsystem: physics
tags: [pvlib, solar, constraints]
requires: [02-01, 02-08]
provides: [swf.physics.solar, swf.physics.constraints]
key-files:
  created: [src/swf/physics/solar.py, src/swf/physics/constraints.py, tests/test_physics_solar.py, tests/test_physics_constraints.py]
completed: 2026-11-03
---

# Phase 2 Plan 05: Solar chain and constraint layer Summary

pvlib Perez/Faiman/PVWatts chain with a single config-derived AC cap (pdc0 = dc_kwp/dc_ac_ratio, cap = eta_inv_nom x pdc0 = 800 kW) shared by the inverter and a NaN-preserving, idempotent PRD 6 `enforce()` layer.

## Tasks
1. Solar chain (`pdc0_w`, `ac_cap_kw`, `poa_global`, `simulate_solar`): loss on DC side from config, POA zeroed only at night, NaN daytime inputs propagate. Tests: cap derivation, clear-sky 21 Mar peak 700-800, saturation, loss from config, S/N POA > 1.3, NaN propagation.
2. `TARGET_COLS`, `enforce()`: bounds for t1_kw, t5_kw, rh, ghi, ws10, ws_hub; night zeroing; absent columns ignored.

## Deviations
- Tests import `from synth import canon_frame` (repo convention; `tests` is not a package) instead of `tests.synth`.
- Commit trailer uses the attribution given by the harness (Claude Sonnet 5.5), not the plan's Opus text.

## Verification
Full suite: 149 passed, 14 skipped, 0 failed. ruff check clean on touched files (repo-wide `ruff format --check` has pre-existing unformatted files, out of scope). No hard-coded plant numbers in solar.py.

## Self-Check: PASSED
