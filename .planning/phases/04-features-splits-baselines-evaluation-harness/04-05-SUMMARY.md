---
phase: 04-features-splits-baselines-evaluation-harness
plan: 05
subsystem: features
tags: [leakage, parity, testing]
requires: [04-03]
provides: [FEAT-05 leakage tests, FEAT-06 train/serve parity test]
key-files:
  created: [tests/test_features_leakage.py, tests/test_features_parity.py]
  modified: []
metrics:
  completed: 2026-11-04
---

# Phase 4 Plan 05: Leakage and parity tests Summary

Exact-equality (check_exact=True) tests proving the feature builder is causal (truncation, 1e6 perturbation, gap straddling origin, target-axis sensitivity, lead isolation) and that training loader path and `serve_features` give identical features on the committed live fixture.

## Commits
- 7798aea: leakage tests (6 tests)
- parity test commit (see git log): 1 test, 24 valid origins x 72 horizons

## Notes
- The stitched-covariate exemption is documented in the leakage test docstring as a train/serve skew quantified in Plan 06, not a causal proof.
- Gap test includes a sensitivity check: plain `clean()` interpolation does leak (rh_lag1 differs), `history_input` does not.

## Deviations from Plan
None. No defect found; src/swf/features/build.py was not modified.

## Verification
`pytest`: 284 passed, 25 skipped. `ruff check src tests`: All checks passed.

## Self-Check: PASSED
