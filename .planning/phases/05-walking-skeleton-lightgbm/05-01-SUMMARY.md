---
phase: 05-walking-skeleton-lightgbm
plan: 01
subsystem: predict
tags: [lightgbm, pydantic, registry, bands, baseline3, cli]
requires:
  - phase: 04-features-evaluation
    provides: history_frame, enforce, assert_spec, baseline3_choice.json
provides:
  - config/lgbm.yaml and LgbmCfg/load_lgbm_cfg
  - MODELS_DIR, DB_PATH, FRONTEND_DIST paths
  - "`train-lgbm` and `serve` CLI subcommands (lazy handlers)"
  - swf.predict package (bands, live baseline 3, registry, lazy LightGBM runtime)
affects: [05-02, 05-03, 05-04]
tech-stack:
  added: []
  patterns: [whitelisted runtime dispatch, lazy lightgbm import, text-only boosters with spec-hash sidecar]
key-files:
  created: [config/lgbm.yaml, src/swf/predict/__init__.py, src/swf/predict/bands.py, src/swf/predict/baseline.py, src/swf/predict/registry.py, src/swf/predict/lgbm.py, tests/test_predict_bands.py, tests/test_predict_baseline.py, tests/test_predict_registry.py]
  modified: [src/swf/core/settings.py, src/swf/core/paths.py, src/swf/cli.py, tests/test_cli.py, tests/test_config.py, tests/synth.py]
key-decisions:
  - "Bands use p10=min(p50+q10,p50), p90=max(p50+q90,p50) then enforce(): p50 stays fixed and order survives clipping"
  - "Registry runtime names are checked against a fixed RUNTIMES whitelist before importlib"
requirements-completed: [API-05, MODEL-04]
duration: 20min
completed: 2026-11-07
---

# Phase 5 Plan 01: Serving-safe contracts Summary

**LightGBM config, `train-lgbm`/`serve` CLI, and a torch-free `swf.predict` package: sorted+clipped residual bands, live baseline 3 identical to the Phase 4 chain, whitelisted registry dispatch, lazy text-booster runtime.**

## Accomplishments
- `config/lgbm.yaml` + strict `LgbmCfg` (contiguous buckets, UTC `es_tail_start`, quantile order); spec hash unchanged (3bd1a73d99093287).
- Live baseline 3 matches `b3_table` exactly on the committed live fixture.
- Registry rejects path traversal and unknown runtimes; import-hygiene subprocess test proves an all-baseline3 registry loads no lightgbm/torch/evaluate modules.

## Task Commits
1. Task 1 config/paths/CLI: 90b5ed4
2. Task 2 bands + live baseline 3: ab4d8a9
3. Task 3 registry + lgbm runtime: c3677c0

## Deviations from Plan
- Tests import the synth helpers as `from synth import ...` (the repo's existing convention; tests/ has no package). No other deviations.

## Known Stubs
None. `swf.models.lgbm` and `swf.api.run` (CLI targets) arrive in Plans 02 and 04; `--help` works without them.

## Self-Check: PASSED
Full default suite: 313 passed.
