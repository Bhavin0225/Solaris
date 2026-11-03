# Phase 4: Features, Splits, Baselines & Evaluation Harness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-03
**Phase:** 04-features-splits-baselines-evaluation-harness
**Areas discussed:** Forecast origins, Baseline 3 correction

---

## Forecast origins

| Option | Description | Selected |
|--------|-------------|----------|
| Every hour | Matches live hourly refresh; ~8,760 origins/year; tight val/test metrics | ✓ |
| Once a day, 00 UTC | Simplest; ~365 origins/year; noisier metrics; fixed clock hour per horizon | |
| 4×/day (00/06/12/18 UTC) | Aligned to GFS runs; mid sample count; doesn't match hourly serving | |

**User's choice:** Every hour

| Option | Description | Selected |
|--------|-------------|----------|
| Day-k = ceil(h/24) | h 1–24 → day1, 25–48 → day2, 49–72 → day3; simple, slightly pessimistic early | ✓ |
| You decide | Researcher reproduces what the live site would have had per origin | |

**User's choice:** Day-k = ceil(h/24)

---

## Baseline 3 correction

| Option | Description | Selected |
|--------|-------------|----------|
| Report both, gate on corrected | Official row uses apply_correction (same inputs as ML); raw-GFS row alongside | ✓ |
| Corrected only | One row per target | |
| Raw GFS only | Pure NWP; ML with corrected covariates gets an extra edge | |

**User's choice:** Report both, gate on corrected

| Option | Description | Selected |
|--------|-------------|----------|
| Re-use ERA5 fit, measure skew | Per Phase 2 plan; report GFS-vs-NASA bias after correction on val | ✓ |
| Fit GFS→NASA on 2021-04–2023 | Better matched but short stitched record; second coefficients file | |

**User's choice:** Re-use ERA5 fit, measure skew

---

## Claude's Discretion

- Covariate skew: train on stitched GFS, quantify the gap on 2024; lead-age feature only if research shows a material gap.
- Scoring conventions: nRMSE by capacity for kW targets, by mean of actuals for GHI/RH/wind speed; monsoon = Jun–Sep.

## Deferred Ideas

None.
