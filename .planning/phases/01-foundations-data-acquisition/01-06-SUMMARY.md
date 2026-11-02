---
phase: 01-foundations-data-acquisition
plan: 06
subsystem: config
tags: [pydantic, yaml, pytest-fixtures]
requires: [01-01]
provides:
  - config/site.yaml and config/plant.yaml
  - swf.core.settings (Settings, load_settings), swf.core.paths, swf.core.geometry
  - shared fixtures settings, no_sleep, mock_client, fixtures_dir
affects: [01-02, 01-03, 01-04, 01-05, 01-07]
key-files:
  created: [config/site.yaml, config/plant.yaml, src/swf/core/paths.py, src/swf/core/settings.py, src/swf/core/geometry.py, tests/conftest.py, tests/test_config.py, tests/test_geometry.py]
key-decisions:
  - "D-06 enforced at load: best_match and non-[a-z0-9_] model names rejected"
  - "D-08 leads 1-3 configured"
requirements-completed: [SETUP-03, SETUP-04]
completed: 2026-11-02
---

# Phase 1 Plan 06: Config and settings Summary

Site/plant values load from YAML into extra-forbid pydantic Settings that reject typos, 16 NASA params, best_match, bad Kaggle slugs and non-.csv keys; plus the azimuth converter and shared test fixtures.

## Task commits
1. Config, settings, fixtures: see git log "feat(01-06): config yamls"
2. Azimuth helper and tests: see git log "feat(01-06): pvlib to Open-Meteo azimuth"

## Verification
- `uv run pytest`: 27 passed; no coordinate literals in src/.

## Deviations from Plan
None. conftest.py landed in the task 1 commit because test_config uses the `settings` fixture.

## Self-Check: PASSED
