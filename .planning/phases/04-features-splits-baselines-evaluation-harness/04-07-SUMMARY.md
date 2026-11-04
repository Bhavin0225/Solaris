---
phase: 04-features-splits-baselines-evaluation-harness
plan: 07
subsystem: evaluation
tags: [baselines, leaderboard, d-03a, realdata]
requires: ["04-01", "04-03", "04-04", "04-05", "04-06"]
provides:
  - frozen D-03a baseline-3 choice (config/baseline3_choice.json)
  - committed real-data leaderboard/breakdown/GFS-bias CSVs and plots
  - realdata feature-assembly smoke test
affects: [phase-05-models]
key-files:
  created:
    - config/baseline3_choice.json
    - reports/evaluation/leaderboard.csv
    - reports/evaluation/breakdown.csv
    - reports/evaluation/gfs_bias_val.csv
    - reports/evaluation/rmse_by_horizon_val.png
    - reports/evaluation/skill_val.png
    - reports/evaluation/gfs_bias_val.png
    - tests/test_features_real.py
  modified:
    - docs/data_notes.md
key-decisions:
  - "D-03a choice (val 2024 RMSE): ghi corrected, rh corrected, t1_kw raw, t5_kw raw, ws10 raw"
metrics:
  completed: 2026-11-04
---

# Phase 4 Plan 07: Real-data run, D-03a freeze, phase gate Summary

Real-data Phase 4 pipeline run with the D-03a baseline-3 choice frozen from validation only before any test scoring, 70-row leaderboard committed, reruns byte-identical, full suite green.

## Commits
- 8d8131a: freeze D-03a choice (written by `evaluate --split val`, committed before `evaluate --split all`)
- artifacts commit: reports/evaluation/*, docs/data_notes.md (AUTO:features, AUTO:evaluation, hand-written "Phase 4 feature and split decisions" section)
- e876452: tests/test_features_real.py

## D-03a choice (per target) and RMSE, official baseline 3 vs persistence

| target | choice | val b3 | val persist | test b3 | test persist |
|---|---|---|---|---|---|
| t1_kw | raw (val corr 139.07 vs raw 137.33) | 137.33 | 96.00 | 132.19 | 90.03 |
| rh | corrected (11.22 vs 12.56) | 11.22 | 24.14 | 11.41 | 25.71 |
| ghi | corrected (tie, 155.91) | 155.91 | 110.60 | 148.82 | 99.64 |
| ws10 | raw (1.446 vs 1.698) | 1.446 | 2.01 | 1.38 | 2.01 |
| t5_kw | raw (580.5 vs 697.8) | 580.52 | 800.12 | 689.96 | 925.21 |

Climatology RMSE (val/test): t1 91.13/88.56, rh 9.75/9.29, ghi 103.13/101.97, ws10 1.63/1.58, t5 760.37/816.01.
Best baseline: baseline3 wins ws10 and t5_kw (val and test). Persistence/climatology beat baseline 3 on all-hours RMSE for t1_kw, ghi, rh (persistence wins rh only at h=1 and h=24 ish; its RMSE oscillates with horizon).
Skill of persistence vs baseline3 (1 - RMSE_p/RMSE_b3), val/test: t1 +0.30/+0.32, ghi +0.29/+0.33, rh -1.15/-1.25, ws10 -0.39/-0.46, t5 -0.38/-0.34.

## Sanity vs RESEARCH magnitudes
- ws10 baseline-3 test 1.38 (raw) fits ~1.3-1.6; corrected d1 val 1.70 vs raw 1.45 matches the expected corrected-worse pattern.
- wind kW: raw 580 val / 690 test, corrected 698 val; inside ~620-750 band.
- solar kW all-hours 132-137, consistent with ~132 (RESEARCH quoted daytime-ish). Persistence solar RMSE 90-96 (all hours) versus RESEARCH ~55 (daytime, 24 h): different slicing, not an order-of-magnitude gap. Not forced.
- Notable: all-hours GHI/solar baseline 3 is worse than persistence and climatology (GFS GHI bias +29..+44 W/m2 on val, see gfs_bias_val.png). This is a real finding for the report, not a bug.
- Leaderboard: 70 rows, 7 models, no NaN rmse, shared_frac >= 0.5 everywhere, single feature_spec_hash.

## W-W2b gap-fill look-ahead measurement
For the sampled origins (train_covariate stride 500 on gfs_hf: 3528 rows; val stride 200 on pr_d1/d2/d3 per lead: 1056 rows each), the share of (origin, h) rows reading a covariate cell filled by clean() interpolation is 0.0000% for gfs_hf, pr_d1, pr_d2, pr_d3 (threshold 0.5%). Across all of gfs_hf the only cells clean() changes are 973 night-radiation zeros (ghi/dni/dhi, a function of time, excluded as in history_input); zero interpolated meteorological gaps. No mask fix needed. Val sample NaN rate per covariate column 2.8%-13.6% (genuine missing early-2024 Previous Runs / wind-hub cells); history columns NaN rate 0 on train_covariate. Test asserts share <= 0.5%.

## Determinism
`python -m swf features` and `python -m swf evaluate` rerun: `git diff --exit-code -- config/baseline3_choice.json reports/evaluation docs/data_notes.md` exits 0. `git ls-files reports/evaluation | wc -l` = 6; data/processed untracked (0).

## Requirement -> test map
FEAT-01 test_features_spec; FEAT-02/03 test_features_build, test_features_history, test_features_leakage; FEAT-04 test_splits; FEAT-05 test_features_parity; FEAT-06 test_features_real (realdata); EVAL-01..02 test_evaluate_baselines (incl. realdata identity); EVAL-03 test_evaluate_longfmt and test_evaluate_report; EVAL-04..06 test_evaluate_metrics; EVAL-07 test_evaluate_report (incl. realdata end-to-end). (Mapping from file names per 04-VALIDATION; fine-grained ID assignment approximate.)

## Test gate
- `uv run --offline ruff check src tests`: All checks passed!
- `uv run --offline pytest -o addopts="" -m "not network"`: `319 passed, 16 warnings in 966.41s (0:16:06)` (0 failed, 0 skipped; includes realdata and the e2e report test). Network-marked tests deselected (offline).

## Deviations from Plan
- [Rule 1] test_features_real.py initial skipif looked for data/raw/era5 (wrong path); fixed to data/raw/openmeteo before commit. Ruff fix/format applied to the new test.
- A first unfiltered `pytest -o addopts=""` run (network tests not deselected) hung with no output and was killed; rerun with `-m "not network"` per the plan's offline allowance.

## Known Stubs
None.

## Self-Check: PASSED
Files and commits 8d8131a, e876452 verified present; artifacts commit made in-session.
