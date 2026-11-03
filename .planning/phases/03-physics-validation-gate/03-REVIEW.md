---
phase: 03-physics-validation-gate
reviewed: 2026-11-03
depth: standard
files_reviewed: 21
findings: {critical: 0, warning: 5, info: 3, total: 8}
status: issues_found
---

# Phase 3 Code Review

No blockers.

What checked out:
- **Refactor:** `ac_from_poa` is equivalent to the old inline chain in `simulate_solar`.
- **Plotting:** matplotlib is imported lazily.
- **Locked files:** nothing in `swf.validate` writes `config/plant.yaml` or `energy_sim.parquet`.
- **Time handling:** the only `tz_localize`/`tz_convert` in `swf.validate` is in `load_plant` (kaggle_solar.py:93), plus the one-off `heldout_start_utc` conversion.
- **Wind gate:** matches the spec: ≤14%, ≤ the same-row reference and ≤13.0%, on both `full_year` and `ref_slice`.
- **nRMSE denominator:** the same AC cap for sim and actual. `plant_settings` sets the cap to the observed peak.

## Warnings

### WR-01: Held-out data leaks into the tuning anchor
**File:** `src/swf/validate/kaggle_solar.py:84, 152-157`

`peak_ac_kw` is the maximum over the whole span, which includes the 1-17 June held-out window. It sets `dc_kwp`, the AC clip and the nRMSE denominator. The loss is tuned only on 15-31 May, but plant size and denominator already carry held-out information.

**Fix:** compute the peak from the tune mask only (daytime, before `start_utc`) and pass it to `plant_settings` / `tune_loss`. Alternatively, document the anchor as nameplate-like rather than tuned.

### WR-02: Plant 2 failures can still change the exit status (D-L2)
**File:** `src/swf/validate/run.py:101-112`

`gate()` ignores non-gating plants. But `validate_all` runs Plant 2 through `load_plant` and `validate_plant`, so either of these aborts the whole run before any outputs are written:
- a `ValueError` (span, units, missing inverters, empty frame);
- a `SystemExit` from `_file`.

**Fix:** for `not pc.gating`, wrap the load and validate in try/except, log the error, and record `{"gating": False, "error": str(e)}`. `render_validation` then skips those rows.

### WR-03: Silent parametric power-curve fallback during validation
**File:** `src/swf/validate/kaggle_wind.py:29-32` (via `swf/physics/wind.py:37-42`)

If `config/power_curve.csv` is missing, `simulate_t1` calls `simulate_wind` with `curve=None`. That falls back to the parametric curve with only a log warning, so the gate would be judged against a non-manufacturer curve.

**Fix:** in `simulate_t1`, load the CSV explicitly and raise `FileNotFoundError` if it is absent.

### WR-04: Duplicate or NaN generation rows are not guarded
**File:** `src/swf/validate/kaggle_solar.py:58-61`

- Duplicate `(DATE_TIME, SOURCE_KEY)` rows in the generation file would double-count AC, while `nunique` still reads 22.
- `sum` skips NaN, so a missing `AC_POWER` counts as 0 instead of dropping the timestamp.

**Fix:** reject duplicates, and count inverters with `count` (which excludes NaN) rather than `nunique`.

### WR-05: Solar CSVs read without `encoding="utf-8-sig"`
**File:** `src/swf/validate/kaggle_solar.py:28, 34`

A BOM would make `usecols` fail with a confusing error. The wind loader already handles this; the solar loaders fail loud, so this is robustness only.

**Fix:** add `encoding="utf-8-sig"` to both `read_csv` calls.

## Info

### IN-01: Wind table "pass" column disagrees with the gate
**File:** `src/swf/validate/run.py:61-62`

The table marks the non-gated `jan_to_ref` slice yes or no, and it re-implements the pass formula. Store a per-slice `pass` in `wind_metrics` and show "n/a" for non-gated rows.

### IN-02: NaN-unsafe `min` in `tune_loss`
**File:** `src/swf/validate/kaggle_solar.py:141`

If the tune mask is empty or all NaN, every curve value is NaN and `min` silently returns the first key. Raise when any curve value is NaN.

### IN-03: `energy_ratio` uses mismatched row sets; `mbe_pct` divides by mean(act)
**File:** `src/swf/validate/kaggle_wind.py:71`, `src/swf/validate/metrics.py:16`

- `energy_ratio`: mask both sums to rows where both values are valid.
- `mbe_pct`: guard against all-zero actuals.

---

Not checked: pytest and the real `validate` run were not executed by the reviewer, and the test files were only spot-checked.
