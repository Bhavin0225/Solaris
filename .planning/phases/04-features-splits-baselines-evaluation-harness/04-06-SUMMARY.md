---
phase: 04-features-splits-baselines-evaluation-harness
plan: 06
subsystem: evaluation
tags: [leaderboard, breakdown, gfs-bias, d-03a]
requires: [04-02, 04-04]
provides: [swf.evaluate.report]
key-files:
  created: [src/swf/evaluate/report.py, tests/test_evaluate_report.py]
requirements-completed: [EVAL-03, EVAL-05, EVAL-06, EVAL-07]
completed: 2026-11-04
---

# Phase 4 Plan 06: Evaluation report Summary

`python -m swf evaluate`: scores val, freezes the per-target baseline-3 corrected/raw choice (never overwrites), then scores test (refused with exit 1 and nothing written if the choice file is missing); writes leaderboard.csv, breakdown.csv, gfs_bias_val.csv (all with feature_spec_hash), three PNGs and the AUTO:evaluation block.

## Tasks
Tasks 1 and 2 share one file and were committed together in a single commit (scoring/ordering, D-04 bias, plots and AUTO block were written as one module).

## Deviations
- Installed `matplotlib` (a declared project dependency in the `train` extra) into the worktree venv with `uv pip install` so plots could run; no pyproject change.
- Realdata test could not be executed here: the main checkout has no `data/processed/predictions` yet (plan 04-07 produces it). It skips cleanly.

## Verification
`uv run pytest`: 285 passed, 1 skipped, 25 deselected. `uv run ruff check src tests`: All checks passed.
Synthetic tests cover ordering (frozen ws10/t5_kw = raw despite test favouring corrected), refusal, 70-row leaderboard, byte-identical reruns (CSV, PNG, notes), stale-hash rejection, frozen-file retention with warning, extra model auto-joining.

## Self-Check: PASSED
