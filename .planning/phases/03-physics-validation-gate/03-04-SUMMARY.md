---
phase: 03-physics-validation-gate
plan: 04
subsystem: validation
tags: [cli, metrics, plots, gate]
requires: [03-02, 03-03]
provides: [swf validate, reports/validation/metrics.json, scatter PNGs, AUTO:validation block]
key-files:
  created: [src/swf/validate/plots.py, src/swf/validate/run.py, tests/test_validate_outputs.py, tests/test_validate_real.py, reports/validation/metrics.json, reports/validation/solar_plant_1_scatter.png, reports/validation/solar_plant_2_scatter.png, reports/validation/wind_scatter.png]
  modified: [src/swf/cli.py, tests/test_cli.py, docs/data_notes.md]
requirements-completed: [VAL-01, VAL-02, VAL-03, VAL-04]
completed: 2026-11-03
---

# Phase 3 Plan 04: validate command Summary

`python -m swf validate` runs both validators on the real Kaggle files, writes rounded sorted metrics.json, three scatter PNGs (lazy Agg matplotlib) and the AUTO:validation block; exit 0 iff Plant 1 (tuned and configured loss) and wind pass; Plant 2 is ignored by the gate.

## Real run
- Plant 1: tuned loss 9%, held-out 3.36%, full 3.11%, held-out at configured 14% = 4.34%, full at 14% = 4.26%. Pass.
- Plant 2 (non-gating): tuned 17%, held-out 14.39%, fails; does not affect exit code (D-L2).
- Wind: full_year 12.12% vs curve 12.94%; ref_slice 12.31% vs 13.08% (n=10098). Pass. All within 1 pp of RESEARCH.
- Re-run: sha256 of metrics.json, PNGs and data_notes.md identical. config/plant.yaml untouched (hash asserted in realdata test, D-L1).

## Deviations
None. Ruff ISC004/RUF100 fixes applied to new files.

## Verification
`uv run pytest -o addopts=""`: 224 passed, 16 warnings (includes realdata). `uv run ruff check src tests`: All checks passed.

## Self-Check: PASSED
