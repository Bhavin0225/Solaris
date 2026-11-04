---
phase: 04-features-splits-baselines-evaluation-harness
fixed_at: 2026-11-04
review_path: .planning/phases/04-features-splits-baselines-evaluation-harness/04-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Source review:** 04-REVIEW.md, iteration 1, scope critical_warning (Info items IN-01..03 not attempted).

**Summary:** 7 in scope, 7 fixed, 0 skipped. Worked in the main tree on orchestrator instruction (no worktree).

## Fixed Issues

### WR-01: Single-split evaluate overwrote combined CSVs
**Files:** `src/swf/evaluate/report.py`, `tests/test_evaluate_report.py` (commit 9f6472a)
**Fix:** new `_merge` keeps the other split's existing rows (same spec hash only) and re-sorts; the AUTO:evaluation block is re-rendered whenever the merged leaderboard has val rows. Test: `--split test` and `--split val` after `all` leave CSVs and notes byte-identical.

### WR-02: Stale hash on frozen choice crashed with a traceback
**Files:** same commit. `run` now catches `(FileNotFoundError, ValueError)`, prints, returns 1, writes nothing. Test added.

### WR-03: select_baseline3 silently chose "corrected" on NaN
**Files:** `src/swf/evaluate/baselines.py`, `tests/test_evaluate_baselines.py` (commit b01448f)
**Fix:** raises `ValueError` if either RMSE is non-finite. Tie rule unchanged. Test added.

### WR-04: Hard-coded 72, horizons, season text
**Files:** `src/swf/evaluate/longfmt.py`, `src/swf/evaluate/report.py` (commit 9f6472a)
**Fix:** `validate_long` uses `horizon_max`; sort order uses `cfg.eval.horizons`; notes text uses horizon_max, monsoon months and daytime zenith from config.

### WR-05: Spec hash omitted plant/curve/splits
**Files:** `src/swf/features/spec.py`, `tests/test_features_spec.py` (commit 8e2db8e)
**Fix:** inputs now include sha256 of solar+wind plant values, sha256 of the power-curve CSV (CRLF to LF), and `cfg.splits` in the spec. `GOLDEN_HASH` is now `3bd1a73d99093287`. Test: changing tilt, rated_kw, val window or the curve changes the hash.
Status: fixed (logic-level; hash coverage verified by test).

### WR-06: Naive origins failed
**Files:** `src/swf/features/build.py`, `tests/test_features_build.py` (commit 1448e47)
**Fix:** `_utc` helper (localize if naive, else convert) used in `assemble` and `serve_features`. Test: naive and aware origins give identical frames.

### WR-07: Unbounded csi
**Files:** `src/swf/features/build.py`, `src/swf/core/settings.py`, `config/features.yaml`, `tests/test_evaluate_metrics.py`, `tests/test_features_build.py` (commit 1448e47)
**Fix:** `eval.csi_min_clearsky_wm2: 1.0` (required field); csi is 0 where clear-sky <= threshold or at night, and clipped to [0, 2]. `spec_version` bumped 1 to 2; threshold also in the spec. Status: fixed, requires human verification (logic change; test checks bounds only).

## Artifact regeneration (D-03a order)
1. `swf baselines` rewrote prediction parquets (gitignored).
2. `config/baseline3_choice.json` deleted and re-frozen from val only (commit separate). Choices unchanged: ghi corrected, rh corrected, t1_kw raw, t5_kw raw, ws10 raw; val RMSEs identical.
3. `swf features` + `swf evaluate --split all`; reports/evaluation/* and docs/data_notes.md committed.
4. Rerun of both: `git diff --exit-code` clean (deterministic).

Before/after RMSE for official baseline3 and persistence on every target, val and test: no change at displayed precision (diff 0.0 in all 20 rows). Only the feature_spec_hash column changed in the CSVs and notes.

## Skipped Issues
None.

---

_Fixer: Claude (gsd-code-fixer), iteration 1_

## Orchestrator follow-ups

- WR-02 completed in 71b6339: the val-branch `elif load_choice(...)` comparison sat outside the guard; moved after the guarded load (found by the new `test_stale_choice_hash_returns_1`).
- `test_hash_covers_plant_curve_splits` no longer rewrites the committed `config/power_curve.csv`; it monkeypatches `paths.CONFIG_DIR` to a tmp copy (safe under crashes and parallel runs).
- Final gate (orchestrator): `uv run pytest -o addopts="" -m "not network"` → 325 passed; ruff clean.
- Effect on results: GOLDEN_HASH bd5c6b0683036df5 → 3bd1a73d99093287; D-03a choice re-frozen from val (dacbf86) — unchanged per target; official baseline-3 and persistence RMSE unchanged on all 5 targets for val and test; only the feature_spec_hash column changed in committed CSVs.
