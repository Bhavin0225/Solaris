---
phase: 4
slug: features-splits-baselines-evaluation-harness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-03
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 (`pyproject.toml` addopts deselect `network` and `realdata`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_features_*.py tests/test_splits.py tests/test_evaluate_*.py -x` |
| **Full suite command** | `uv run pytest -o addopts=""` (includes realdata parquet-backed checks) |
| **Estimated runtime** | quick < 30 s (synthetic); full ~3–5 min |

---

## Sampling Rate

- **After every task commit:** quick run command (synthetic data only)
- **After every plan wave:** `uv run pytest` (default suite)
- **Before `/gsd:verify-work`:** full suite incl. realdata green; run `python -m swf features`, `baselines`, `evaluate` twice and diff `reports/evaluation/*.csv` (determinism)
- **Max feedback latency:** 30 seconds (quick)

---

## Per-Task Verification Map

| Requirement | Behavior | Test Type | Test file |
|-------------|----------|-----------|-----------|
| FEAT-01 | golden FEATURE_SPEC hash; load-time check raises on mismatch; hash changes when a lag param changes | unit | `tests/test_features_spec.py` |
| FEAT-02 | column names/count/order match spec; no raw day-of-year/degree columns; sin²+cos²=1; monsoon flag months | unit | `tests/test_features_build.py` |
| FEAT-03 | history frame identical from ERA5 path and serving adapter path; kW columns = enforce(simulate(apply_correction)) | unit | `tests/test_features_history.py` |
| FEAT-04 | origin counts per split asserted (201,384 / 24,048 / 8,712 / 8,688), no target crosses a boundary, ranges logged | unit | `tests/test_splits.py` |
| FEAT-05 | truncation + perturbation leakage test; sensitivity check (covariate at t+h does change) | unit | `tests/test_features_leakage.py` |
| FEAT-06 | train vs serve path identical on committed `tests/fixtures/om_live_gfs_seamless.json` | unit | `tests/test_features_parity.py` |
| EVAL-01 | persistence (value at t; same hour yesterday for solar kW and GHI) on hand-computed case | unit | `tests/test_evaluate_baselines.py` |
| EVAL-02 | climatology = hour×month mean over training years only | unit | `tests/test_evaluate_baselines.py` |
| EVAL-03 | lead map k=ceil(h/24) at h=1,24,25,48,49,72; baseline 3 on NASA weather reproduces energy_sim; corrected vs raw; per-target official choice (D-03a) frozen from val | unit + realdata | `tests/test_evaluate_baselines.py` |
| EVAL-04 | long-format validator rejects bad columns / duplicate keys / target_time ≠ issue_time+h | unit | `tests/test_evaluate_longfmt.py` |
| EVAL-05 | metrics by hand; skill on shared index; daytime mask (zenith < 85°); stated normalisation | unit | `tests/test_evaluate_metrics.py` |
| EVAL-06 | breakdown by horizons {1,6,24,48,72,all}, season (monsoon Jun–Sep), target | unit | `tests/test_evaluate_metrics.py` |
| EVAL-07 | leaderboard.csv lists all baseline rows × 5 targets × {val,test}; byte-identical on rerun | realdata | `tests/test_evaluate_report.py` |

*Status per task is filled during execution.*

---

## Wave 0 Requirements

- [ ] New test files above; extend `tests/synth.py` with a synthetic 5-target history frame and a fake Previous Runs trio
- [ ] `config/features.yaml` + own pydantic model and loader (Phase 3 `validation.yaml` pattern)
- No framework install needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Leaderboard plots readable for the report | EVAL-07 | visual quality | open `reports/evaluation/*.png` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
