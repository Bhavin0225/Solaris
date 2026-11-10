---
phase: 08-reproducibility-viva-readiness
plan: 01
subsystem: cli
tags: [cli, reproducibility, deadlines]
requires: []
provides:
  - "`swf data` builds everything (fetch, curve, build-weather, simulate-energy, validate, features, baselines), fail-fast"
  - "`swf train [--lgbm-only] [--accept-stale-results]` with STALE_HELP guard"
  - "`swf serve` hint when frontend/dist is missing"
  - "training deadlines off by default (D-62)"
affects: [08-02, 08-04, 08-05]
key-files:
  modified:
    - src/swf/cli.py
    - src/swf/api/run.py
    - src/swf/core/settings.py
    - config/deep.yaml
    - src/swf/models/tft.py
    - tests/test_cli.py
    - tests/test_config.py
    - tests/test_tft.py
decisions:
  - "D-62 implemented: stable_by_utc / hard_stop_utc are datetime | None, null in config"
metrics:
  completed: 2026-11-10
---

# Phase 8 Plan 01: CLI reproduction commands and deadlines off Summary

`data` now chains nine steps fail-fast via `_chain`, `train` retrains LightGBM, LSTM/GRU and TFT (refusing while `models/deployed/test_started.json` exists unless `--accept-stale-results`), `serve` explains a missing frontend build, and the D-18/D-19 wall-clock deadlines are null by default.

## Commits
- 5a4307a: deadlines off (Task 3, done first because train depends on it)
- 3a51e77: data chain, train, serve hint (Tasks 1 and 2)

## Notes
- seq.py needed no change: `train` was already None-safe and `run` passes `lc.stable_by_utc`; covered by the existing `deadline=None` call in test_deadline_minimal.
- Assumption A1 resolved: `seed: 42` in config/deep.yaml and config/lgbm.yaml, used at src/swf/models/lgbm.py:71, src/swf/models/seq.py:137-141, src/swf/models/tft.py:128.
- `uv run python -m swf train --lgbm-only` on this laptop exits 1 with the STALE_HELP text (verified).
- tests/test_deep_seq.py was not edited (existing test already covers None).

## Deviations from Plan
None for code. Tests for tasks 1-3 were written alongside the code rather than strictly RED-first, and Tasks 3 was committed before Tasks 1-2.

## Deferred Issues
`tests/test_eval_figures.py::test_gain` fails with `ModuleNotFoundError: No module named 'tests'` (no tests/__init__.py); it lives in a file this plan did not touch. Logged in deferred-items.md. All other tests pass, so `uv run pytest -q` is not fully green.

## Self-Check: PASSED
