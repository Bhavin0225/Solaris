---
phase: 03-physics-validation-gate
verified: 2026-11-03T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
gaps: []
---

# Phase 3: Physics Validation Gate Verification Report

**Phase Goal:** Simulated energy targets shown credible against real plant data.
**Status:** passed. **Re-verification:** No.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Kaggle solar parses correctly; loss tuned in 8-20% on daytime rows | VERIFIED | metrics.json: Plant 1 loss_pct_tuned 9, grid [8,20], loss_edge false, daytime rows only (IRRADIATION > 0.02 kW/m2, n_rows 1603). data_notes.md documents dayfirst, AC summed per timestamp (101 partial timestamps dropped), IRRADIATION kW/m2 (max 1.222). |
| 2 | Solar daytime nRMSE vs <=10% target, or written justification | VERIFIED | Plant 1 (gating) held-out 3.357%, full 3.107%, at config 14% 4.338%: pass. Plant 2 (non-gating, D-L2) 14.39% miss, justified in data_notes.md (inverter dropouts: median 16.7% zero-AC daytime vs 0.0% for Plant 1). |
| 3 | Wind nRMSE (re-binned manufacturer curve x availability vs LV ActivePower) <=14% and no worse than 13.0% | VERIFIED | wind.pass true; full_year sim 12.123%, ref_slice 12.307% (<= 13.0 and < same-row manufacturer reference 13.081%). |
| 4 | Scatter plots and metrics.json in reports/validation/ | VERIFIED | Present: metrics.json, solar_plant_1_scatter.png, solar_plant_2_scatter.png, wind_scatter.png. Orchestrator viewed plots: readable. |

**Score:** 4/4

## Requirements Coverage

All four IDs are claimed by PLAN frontmatter (03-01: VAL-01..03; 03-02: VAL-01,02; 03-03: VAL-03; 03-04: VAL-02..04; 03-05: VAL-01..04). REQUIREMENTS.md marks VAL-01..04 Complete. No orphaned Phase 3 requirements.

| Req | Status | Evidence |
|-----|--------|----------|
| VAL-01 | SATISFIED | Truth 1 |
| VAL-02 | SATISFIED | Truth 2 |
| VAL-03 | SATISFIED | Truth 3 |
| VAL-04 | SATISFIED | Truth 4 |

## Behavioral Checks (run by verifier)

| Check | Result |
|-------|--------|
| `uv run pytest -o addopts=""` | 224 passed |
| `python -m swf validate` rerun | Exit OK; git status clean afterwards, so output is byte-identical (deterministic) |
| Locked decisions D-L1..D-L4 | D-L1: config loss 14 kept, tuned 9 reported alongside, results at 14% also reported. D-L2: Plant 2 gating false, documented. D-L3/D-L4: wind wording corrected in data_notes.md. |

## Review Findings (03-REVIEW.md)

- WR-01 (peak anchor over full span): Plant 1 peak (29150.2 kW) lies in the tune window, so the gating held-out result is not leaked. Plant 2 is non-gating. Does not break any criterion. Worth a caveat in the report.
- WR-02 (Plant 2 load error aborts run): robustness issue only; the real run succeeds. Does not break any criterion.
- Remaining warnings and info items are advisory.

## Anti-Patterns / Minor Notes (non-blocking)

- Scatter plots have no nRMSE annotation and the wind hexbin has no colorbar (cosmetic; numbers live in metrics.json and data_notes.md).
- Plant 1 tuned loss depends on the dc_kwp anchor convention and a different site; this caveat is already stated in data_notes.md.
- Plant 2 miss is a written-justification case, allowed by criterion 2.

## Gaps Summary

None. The phase goal is achieved: all four criteria are verified against metrics.json, the docs and a fresh test and validate run.
