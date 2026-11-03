---
phase: 03-physics-validation-gate
plan: 01
subsystem: validation
tags: [pvlib, pydantic, config, metrics]
requires: []
provides: [ac_from_poa, ValidationCfg, load_validation_cfg, error_stats, REPORTS_DIR]
affects: [03-02, 03-03]
key-files:
  created: [config/validation.yaml, src/swf/validate/__init__.py, src/swf/validate/metrics.py, tests/test_validate_core.py]
  modified: [src/swf/physics/solar.py, src/swf/core/settings.py, src/swf/core/paths.py, tests/test_physics_solar.py]
decisions:
  - "Validation settings live in their own ValidationCfg; Settings, plant.yaml and site.yaml untouched (D-L1)"
metrics:
  completed: 2026-11-03
  tasks: 2
---

# Phase 3 Plan 01: Shared validation contracts Summary

Post-POA solar tail extracted into `ac_from_poa`, plus `config/validation.yaml` with a pydantic `ValidationCfg`/loader, `REPORTS_DIR`, and a single `error_stats` (nRMSE = RMSE/norm*100).

## Commits
- e9130dc refactor: extract ac_from_poa
- (task 2) feat: validation config, error_stats, REPORTS_DIR

## Deviations from Plan
None. Plan executed as written.

## Verification
`uv run pytest`: 177 passed, 21 deselected, 16 warnings. `uv run ruff check src tests`: all checks passed.

## Self-Check: PASSED
