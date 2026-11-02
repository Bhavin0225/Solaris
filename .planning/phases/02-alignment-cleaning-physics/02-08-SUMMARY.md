---
phase: 02-alignment-cleaning-physics
plan: 08
subsystem: config/tooling
tags: [config, pytest, auto-blocks]
requires: []
provides:
  - AlignCfg, SolarCfg.albedo, WindCfg.power_curve_csv in swf.core.settings
  - write_auto_block(path, block, name="coverage")
  - realdata pytest marker (opt-in) and raw_root fixture
key-files:
  modified:
    - src/swf/core/settings.py
    - config/site.yaml
    - config/plant.yaml
    - tests/test_config.py
    - pyproject.toml
    - tests/conftest.py
    - src/swf/coverage/report.py
    - tests/test_coverage.py
metrics:
  completed: 2026-11-03
---

# Phase 2 Plan 08: Config and tooling Summary

Validated `align` config (max gap 3 h, fit years 2001-2023, four thresholds, 10% wind rule), solar albedo, power-curve filename (bare CSV name, traversal-safe), named AUTO blocks, and an opt-in `realdata` marker with a skipping `raw_root` fixture.

## Commits
- 65ca32e: config keys and tests
- 915504b: realdata marker, raw_root, named AUTO blocks

## Deviations from Plan
None. Full suite and ruff pass.

## Self-Check: PASSED
