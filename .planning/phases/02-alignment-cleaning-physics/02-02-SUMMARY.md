---
phase: 02-alignment-cleaning-physics
plan: 02
subsystem: align
tags: [adapters, timestamps, offsets]
requires: [02-01, 02-08]
provides:
  - swf.align.adapters (OFFSETS, SOURCES, nasa_canon, openmeteo_canon, load_source)
  - swf.align.timestamps (onset_rates, centroid_diff, verify, met_lag)
key-files:
  created:
    - src/swf/align/adapters.py
    - src/swf/align/timestamps.py
    - tests/test_align_adapters.py
    - tests/test_align_timestamps.py
metrics:
  completed: 2026-11-03
---

# Phase 2 Plan 02: Adapters and timestamp verifier Summary

Two adapters map all seven sources onto the canonical frame via a pinned six-key OFFSETS table (NASA 0 h, Open-Meteo -1 h), and a D-13 verifier proves the convention on real data.

## Commits
- c5be765: adapters + tests
- 389be45: timestamp verifier + tests

## Real-data results (D-13)
| source | passed | onset_tol | opposite | pooled h |
|---|---|---|---|---|
| nasa | yes | 1.0 | 0.672 | 0.038 |
| era5 | yes | 1.0 | 0.672 | -0.013 |
| gfs_hf | yes | 1.0 | 0.702 | -0.114 |
| gfs_pr_d1/d2/d3 | yes | 1.0 | 0.691/0.692/0.693 | -0.103/-0.100/-0.096 |

met_lag (NASA vs ERA5, fit years 2001-2023): temp 0 h, pressure 0 h (reported, not gating).

## Deviations from Plan
None. Test imports use `from synth import ...` (matches existing tests; no tests package). Full suite passes; realdata tests pass (13); ruff clean. gfs_live realdata test skips if no live file is cached.

## Self-Check: PASSED
