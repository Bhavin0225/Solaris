---
phase: 04-features-splits-baselines-evaluation-harness
plan: 03
subsystem: features
tags: [features, causal, serving]
requires: [04-01, 04-02]
provides: [swf.features.build]
key-files:
  created: [src/swf/features/build.py, tests/test_features_build.py]
  modified: [tests/synth.py]
metrics:
  completed: 2026-11-04
---

# Phase 4 Plan 03: Feature builder Summary

Two-axis causal feature builder (origin-axis history, target-axis calendar/geometry/covariates, integer-gather assemble, chunked iter_features, single-origin serve_features) with exact history-independent trailing windows via sliding_window_view.

## Tasks
- Task 1 + 2 (committed together, 0eacb60): check_hourly, origin_table, target_table, covariate_table, assemble (stitched and lead-matched D-02), iter_features, history_input, serve_features; synth helpers hist_frame / pr_trio; 9 tests.

## Deviations
- Both tasks went into one commit (shared single file).
- Test fix only: night/daytime indices in history_input test chosen from actual Davanagere sun times; night radiation of a dropped row stays 0 by design.

## Verification
- `uv run pytest`: 264 passed, 3 skipped, 21 deselected. `ruff check src tests`: all passed.
- Golden spec hash unchanged.

## Self-Check: PASSED
