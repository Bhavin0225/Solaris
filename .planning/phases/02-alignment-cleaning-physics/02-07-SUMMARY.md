---
phase: 02-alignment-cleaning-physics
plan: 07
subsystem: align-physics-pipeline
tags: [pipeline, cli, data_notes, bias-correction, physics]
requires: [02-02, 02-03, 02-04, 02-05, 02-06, 02-08]
provides: [build-weather, simulate-energy, data/interim weather+energy parquet, config/bias_correction.json]
affects: [phase-03, phase-04]
key-files:
  created: [src/swf/align/build.py, src/swf/physics/simulate.py, tests/test_pipeline.py, config/bias_correction.json]
  modified: [src/swf/cli.py, tests/test_cli.py, docs/data_notes.md]
decisions:
  - "ghi, rh, ws10, ws_hub all corrected (months exceed thresholds); temp, pressure log-only"
  - "Held-out 2024-2025 GHI bias not reduced (-6.7 to +10.0 W/m2) though RMSE improves; documented honestly"
metrics:
  completed: 2026-11-03
  tasks: 3
---

# Phase 2 Plan 07: build-weather and simulate-energy Summary

Two CLI commands turn the raw cache into six verified, cleaned canonical parquet tables plus a constrained simulated T1/T5 table, and write timestamps, cleaning, consistency and physics AUTO blocks into docs/data_notes.md.

## Results
- All six gating sources PASS the D-13 timestamp rule; met-group lag best 0 h for temp and pressure.
- Correction coefficients fitted 2001-2023, committed to config/bias_correction.json.
- energy_sim: max t1 800.0 kW, t5 within 3600 kW, zero solar at night; clear-sky 21 March peak about 788 kW at the 07:00 UTC hour in the table. Mean solar yield about 1,500 kWh/kWp, wind CF about 28%.
- Two consecutive runs gave byte-identical data_notes.md and bias_correction.json.
- Power curve value at 8.0 m/s is 1,527 kW (not 1,675); recorded as such.
- PHYS-02 numbers (833.3 kW pdc0, 800.0 kW AC cap) stated in data_notes.md.

## Commits
- b76e7cb feat(02-07): build-weather and simulate-energy commands with renderers (tasks 1 and 2)
- docs(02-07) commit: data_notes and bias_correction.json (task 3)

## Deviations from Plan
- Tasks 1 and 2 committed together (shared cli.py/test files).
- Used `from synth import canon_frame` (tests have no package) instead of `tests.synth`.
- Clear-sky peak in the 21 March table is about 788 kW, higher than the "about 745 kW" quoted in the plan text; data_notes states the measured 788 kW and notes the 745 estimate was for other conditions. Needs a check at verify-work.

## Known Stubs
None.

## Gate
pytest default 162 passed (21 deselected); realdata 21 passed; full `-o addopts=` 183 passed, 0 failed, 0 skipped; ruff clean.

## Self-Check: PASSED
