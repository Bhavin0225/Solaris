---
phase: 06-deep-models-selection-final-evaluation
plan: 02
subsystem: evaluation library
tags: [prob-metrics, figures, reliability, gain-importance]
requires: []
provides: [pinball, prob_metrics, reliability, prob_rows, heatmap_table, plot_heatmap, wind_cf_table, plot_wind_cf, gain_importance, plot_gain, plot_reliability]
affects: [06-07]
key-files:
  created: [src/swf/evaluate/prob.py, src/swf/evaluate/figures.py, tests/test_evaluate_prob.py, tests/test_eval_figures.py]
requirements: [EVAL-08, EVAL-09, EVAL-10, MODEL-07]
completed: 2026-11-09
---

# Phase 6 Plan 02: Probabilistic metrics and evaluation figures Summary

Pure, tested library for coverage/width/pinball/3-point reliability on one shared daytime-aware sample, exact-horizon skill heatmap, wind capacity-factor table, LightGBM summed-gain importance, and deterministic PNG plots whose panel titles name the model (plus the D-23 marker).

## Commits
- ffa7bce: prob.py + tests (EVAL-08)
- abf0c03: figures.py + tests (EVAL-09/10, MODEL-07)

## Deviations
- [Test fix] The plan's hand value for reliability P10 was wrong; recomputed to (0.25, 0.75, 0.75) for y=[0,1,2,3].
- Plot functions all return the list of panel titles; plot_heatmap and plot_gain are 1x5 per the plan.

## Notes
- Default suite and ruff pass. STATE.md / ROADMAP.md untouched.
- Matplotlib and lightgbm imported lazily only.

## Self-Check: PASSED
