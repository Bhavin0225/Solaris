---
phase: 04-features-splits-baselines-evaluation-harness
plan: 02
subsystem: features-evaluation
tags: [history, long-format, metrics]
requires: [swf.align.consistency, swf.physics]
provides: [swf.features.history.history_frame, swf.evaluate.longfmt, swf.evaluate.metrics, PROCESSED_DIR]
affects: [04-03, 04-04, 04-06]
key-files:
  created: [src/swf/features/history.py, src/swf/evaluate/__init__.py, src/swf/evaluate/longfmt.py, src/swf/evaluate/metrics.py, tests/test_features_history.py, tests/test_evaluate_longfmt.py, tests/test_evaluate_metrics.py]
  modified: [src/swf/core/paths.py]
requirements: [FEAT-03, EVAL-04, EVAL-05, EVAL-06]
completed: 2026-11-03
---

# Phase 4 Plan 02: history_frame, long prediction format, metrics

history_frame composes apply_correction + simulate + enforce into the five target columns; longfmt defines/validates/stores the common prediction table (zstd parquet, path-safe names); metrics computes shared-index MAE/RMSE/MBE/nRMSE, daytime masking, stated norms, skill and horizon x season breakdowns.

## Commits
- 863ab5c feat: history_frame + PROCESSED_DIR
- 3a69ca6 feat: long format (later reformatted by ruff in the final commit)
- final commit: metrics, ruff format/lint fixes, summary

## Deviations
- [Rule 1] pandas 3 infers datetime64[us] for date ranges; make_long/_cast pin datetime64[ns, UTC] to match the contract.
- Tests import `from synth import ...` (repo convention), not `tests.synth`.
- `swf/features/__init__.py` not created (Plan 01 owns it). Metrics tests use SimpleNamespace cfg; no dependency on Plan 01 code.
- ruff format applied to the new files (line-length differs from my initial style).

## Verification
`uv run pytest`: 231 passed, 3 skipped, 21 deselected. `uv run ruff check src tests`: All checks passed.

## Known Stubs
None.

## Self-Check: PASSED
