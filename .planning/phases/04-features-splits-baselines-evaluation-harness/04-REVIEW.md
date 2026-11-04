---
phase: 04-features-splits-baselines-evaluation-harness
reviewed: 2026-11-04
depth: standard
files_reviewed: 13
findings: {critical: 0, warning: 7, info: 3, total: 10}
status: issues_found
---

# Phase 4: Code Review Report

The source modules were read in full. Test files were not read and no tests were run.

No blockers on causality, purge or D-03a:
- **Lead map:** `lead_k` is correct. Persistence's same-hour source `t+h-24*ceil(h/24)` is always ≤ t.
- **Purge:** `hi = end - 72h` is correct, because split ends are inclusive 23:00 stamps.
- **D-03a:** the frozen file is written only when absent, and test scoring is refused without it.
- **Spec hash:** stamped and checked on every parquet and on the choice file.
- **Imports:** matplotlib is imported lazily, and there is no sklearn in the serving modules.
- **Time zones:** the only tz call is `tz_convert(None)` (see WR-06).

## Warnings

### WR-01: Single-split `evaluate` overwrites the combined leaderboard and breakdown CSVs
**File:** `src/swf/evaluate/report.py:231-239`

`leaderboard.csv`, `breakdown.csv` and the AUTO:evaluation block are rewritten from only the requested splits. So `--split test` after `--split all` drops the val rows.

**Fix:** write per-split files, or merge by `split` before writing, or refuse a single split once both exist.

### WR-02: A stale feature-spec hash on an existing frozen choice crashes with a traceback
**File:** `src/swf/evaluate/report.py:217-225`

`load_choice` can raise `ValueError` on a hash mismatch. It is called outside any `try`, and the `except` catches only `FileNotFoundError`.

**Fix:** catch `(FileNotFoundError, ValueError)`, print the message and return 1.

### WR-03: `select_baseline3` silently picks "corrected" on NaN or tied RMSE
**File:** `src/swf/evaluate/baselines.py:161`

The comparison is false when either RMSE is NaN. An empty validation shared sample therefore freezes "corrected", and the file is never overwritten.

**Fix:** raise `ValueError` when either RMSE is not finite.

### WR-04: Hard-coded 72, horizon labels and season text drift from config
**File:** `src/swf/evaluate/longfmt.py:108`, `src/swf/evaluate/report.py:21-22, 166, 171`

- `validate_long` uses `between(1, 72)` instead of `cfg.horizon_max`.
- `_HORIZONS` duplicates `cfg.eval.horizons`.
- The notes text hard-codes "months 6-9" and "zenith < 85".

**Fix:** derive all of these from `load_features_cfg()`.

### WR-05: The spec hash omits inputs that change the history features
**File:** `src/swf/features/spec.py:72-76`

- The hash covers only `solar_loss_pct`, `dc_ac_ratio` and the bias coefficients.
- It misses values that also feed the `t1_kw`/`t5_kw` history and baseline 3: the wind power curve, rated kW, tilt/azimuth and other plant values.
- It also misses `cfg.splits`, so moving the val window does not invalidate the frozen D-03a choice.

**Fix:** add a hash of the plant config, the power curve file and `cfg.splits`.

### WR-06: `assemble` and `serve_features` fail on naive origins
**File:** `src/swf/features/build.py:111, 148`

- `origins.tz_convert(None)` raises on a naive index.
- `serve_features` does not enforce UTC on `origin`.

**Fix:** normalise to UTC explicitly (`tz_localize("UTC")` if naive, else `tz_convert("UTC")`).

### WR-07: `_csi` is unbounded where clear-sky GHI is near zero
**File:** `src/swf/features/build.py:50-55`

- At zenith 84-85° the Ineichen clear-sky GHI is tiny, so the ratio can become very large or `inf`.
- Those values are fed to models as `csi_hist` and `cov_csi`.
- Where clear-sky and GHI are both 0, the result is NaN.

**Fix:** zero the ratio where clear-sky ≤ a config threshold (for example 1 W/m²) and clip it to [0, 2].

## Info

### IN-01: Private `_table` from `coverage.report` is imported by three modules
**Files:** `features/splits.py`, `features/run.py`, `evaluate/report.py`

Make it public.

### IN-02: `serve_features` runs `clean` twice
Reuse the first result.

### IN-03: `_gather` casts the whole table to float32 on every call
Hoist `to_numpy()` out of the loop.

_Reviewer: gsd-code-reviewer (standard depth). Saved by the orchestrator, because the reviewer cannot write files._
