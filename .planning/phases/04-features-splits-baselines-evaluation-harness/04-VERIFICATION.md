---
phase: 04-features-splits-baselines-evaluation-harness
verified: 2026-11-04
status: passed
score: 5/5
requirements: [FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07]
---

# Phase 4 Verification: Features, Splits, Baselines & Evaluation Harness

**Status: passed.** 5 of 5 success criteria verified, and all 13 requirement IDs are accounted for.

**Evidence:**
- **Full suite (04-07):** `uv run pytest -o addopts="" -m "not network"` gave 319 passed, 0 failed, 0 skipped.
- **Verifier run:** the leakage, parity, splits and spec tests gave 30 passed.
- **Committed outputs:** rerunning reproduces them byte for byte.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Features: lags, rolling stats, known-future covariates, solar geometry, cyclic calendar, direction sin/cos, no raw day-of-year; every artifact stores the FEATURE_SPEC hash | VERIFIED | (a) |
| 2 | Leakage and train/serve parity tests pass | VERIFIED | (b) |
| 3 | Split ranges logged per D2, with boundary origins purged | VERIFIED | (c) |
| 4 | Leaderboard has persistence, climatology and baseline 3 for all five targets; baseline 3 on lead-matched Previous Runs with the stitched variant alongside; solar scored daytime only | VERIFIED | (d) |
| 5 | MAE, RMSE, nRMSE and skill by horizon, season and target, from the common long format | VERIFIED | (e) |

**(a) Features and hash**
- `src/swf/features/{build,history,spec,splits,run}.py` exist.
- The calendar columns are `hour_sin/cos`, `doy_sin/cos` and `monsoon`. Day-of-year is used only to compute the sin/cos pair.
- `spec_hash()` = `bd5c6b0683036df5`. It is stamped into:
  - prediction parquets, checked by `read_long`/`assert_spec`;
  - `config/baseline3_choice.json`, checked by `load_choice`;
  - every `leaderboard.csv`, `breakdown.csv` and `gfs_bias_val.csv` row;
  - the AUTO:evaluation block.

**(b) Leakage and parity**
- `tests/test_features_leakage.py` covers truncation, perturbation, target-axis sensitivity, lead isolation, and a gap straddling the origin. The gap case shows that plain `clean()` would leak.
- `tests/test_features_parity.py` uses the committed Open-Meteo fixture, with exact equality on 24 origins.

**(c) Splits**
- The `docs/data_notes.md` AUTO:features block lists the splits, each with 72 h purged:
  - weather-only train: 2001–2023
  - covariate train: 2021-04 to 2023
  - val: 2024
  - test: 2025
- Origin counts are 201,360 / 24,048 / 8,712 / 8,688, asserted in tests.

**(d) Leaderboard**
- `reports/evaluation/leaderboard.csv` has 70 rows: 7 models × 5 targets × val/test.
- The models are persistence, climatology, `baseline3` (official per-target choice, D-03a), `baseline3_corrected`, `baseline3_raw`, `baseline3_stitched_corrected` and `baseline3_stitched_raw`.
- `t1_kw` and `ghi` have n_shared 283,701 against 596,268 for the other targets, about 48%, which matches the daytime mask (zenith < 85°).
- The choice was frozen from val (8d8131a) before any test scoring.

**(e) Breakdowns**
- `reports/evaluation/breakdown.csv` covers horizons 1/6/24/48/72/all × seasons monsoon/dry/all × target × model.
- Columns: mae, rmse, nrmse_pct, norm, norm_kind, skill_vs_baseline3, skill_vs_persistence.

## Requirements

- FEAT-01..06 and EVAL-01..07 are each backed by code and tests as above.
- EVAL-08..10 belong to Phase 6.

## Key result (for the report)

The official baseline 3 is the best baseline only for ws10 and t5_kw. GFS GHI is biased by +29 to +44 W/m² on val 2024. Because of that bias, persistence and climatology beat baseline 3 on daytime solar kW and GHI, and climatology also beats it on RH. The per-target D-03a choice is:

| Target | Choice |
|---|---|
| ghi | corrected (tie) |
| rh | corrected |
| t1_kw | raw |
| t5_kw | raw |
| ws10 | raw |

## Code review warnings (04-REVIEW.md, advisory)

None of these breaks a success criterion. Carry them into a fix pass before Phase 5.
- **WR-05:** the spec hash does not cover all inputs. SC1 requires only that the hash is stored, and it is.
- **WR-01:** a single-split evaluate run overwrites the combined CSVs. The committed CSVs are complete.
- **WR-03:** a NaN validation RMSE would freeze "corrected" silently.
- **WR-07:** the clear-sky index is unbounded near zenith 85°. Measured on real data: max 2.8, no inf.

## Not checked

- Network-marked tests were deselected.
- The verifier did not re-run the real-data suite. It relied on the 319-pass run and the byte-identical rerun from 04-07.
