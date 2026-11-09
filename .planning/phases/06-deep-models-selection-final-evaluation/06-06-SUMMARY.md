---
phase: 06-deep-models-selection-final-evaluation
plan: 06
subsystem: serving
tags: [refresh, registry, lstm, tft, d-29]
requires: [06-01, 06-03, 06-04]
provides: [default_registry_path, joint-runtime build_run, registry schema 2]
key-files:
  modified: [src/swf/api/refresh.py, src/swf/predict/registry.py, tests/synth.py, tests/test_api_refresh.py, tests/test_predict_registry.py]
requirements: [MODEL-06, MODEL-02, MODEL-03]
completed: 2026-11-09
---

# Phase 6 Plan 06: Deep-runtime serving Summary

refresh now serves lstm/gru/tft through the unchanged build_run loop and prefers models/deployed/registry.json (D-29); registry contract bumped to schema 2.

## Commits
- 9053903: joint-runtime wiring (serve_sequence only when a joint runtime is selected, X.attrs["seq"] = {enc, b3}), native-quantile path (`predict_quantiles` -> sort -> enforce per column), `default_registry_path`, synth `make_registry(runtimes=)`, 5 new refresh tests
- 78bf114: SCHEMA_VERSION 2 docstring with deployed fields, remedy text names train-lgbm and evaluate --final, runtime_module tests for lstm/gru/tft, subprocess hygiene test for a tabular registry

## Verification
Full default pytest green (Phase 5 test_served_model / test_deploy_skeleton unchanged and passing). Hygiene: a fresh interpreter importing swf.api.refresh and resolving baseline3/lightgbm runtimes has no torch, darts, matplotlib, swf.evaluate or swf.models loaded. refresh.py has no top-level torch/darts import.

## Deviations
None. API schema, DB row tuple and HISTORY_HOURS unchanged. STATE.md / ROADMAP.md untouched.

## Notes
- Until `evaluate --final` writes models/deployed/registry.json the served registry stays models/registry.json (baseline3 for all targets).
- Tiny-artifact tests prove wiring and shape, not forecast quality.

## Self-Check: PASSED
