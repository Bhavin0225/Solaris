# Phase 5: Walking Skeleton & LightGBM - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-07
**Phase:** 05-walking-skeleton-lightgbm
**Areas discussed:** LightGBM target form, Horizon handling, P10-P90 band method, Stale and cold-start behaviour, Stale threshold

---

## LightGBM target form

| Option | Description | Selected |
|--------|-------------|----------|
| Raw target | Predict kW / W/m² / RH / ws directly | |
| Residual on baseline 3 | Predict observed minus baseline 3, add back at serve time | ✓ |

**User's choice:** Predict the residual on top of baseline 3.
**Notes:** Residual base is the official baseline-3 series per target (D-03a).

## Horizon handling

| Option | Description | Selected |
|--------|-------------|----------|
| One model, horizon as feature | Rows expand by 72 horizons | |
| Three bucket models | 1–6, 7–24, 25–72 h per target | ✓ |

**User's choice:** Use 3 bucket models for different time ranges.

## P10-P90 band method

| Option | Description | Selected |
|--------|-------------|----------|
| LightGBM quantile objective | Three extra models per target | |
| Empirical residual quantiles by horizon bucket | Validation residuals, same method for baseline 3 | ✓ |

**User's choice:** Empirical residual quantiles by horizon bucket.

## Stale and cold-start behaviour

| Option | Description | Selected |
|--------|-------------|----------|
| Wait for first hourly tick | Serve nothing until the scheduler fires | |
| Immediate fallback and fetch on startup | Serve cache immediately, fetch right away | ✓ |

**User's choice:** Provide an immediate fallback on startup and fetch data right away.

## Stale threshold

| Option | Description | Selected |
|--------|-------------|----------|
| 1 h | Flags after one missed refresh | |
| 2 h (Recommended) | Flags after two missed refreshes | ✓ |
| 6 h | Tolerates longer outages | |

**User's choice:** Stale after 2 h.

---

## Claude's Discretion

- LightGBM hyperparameters, feature subset from the shared FEATURE_SPEC, search method, fixed seeds
- Minimal page scope for success criterion 1 (not discussed; placeholder only)
- Module layout inside `swf.api` and `swf.predict`

## Deferred Ideas

- Lazy refresh on request (>60 min), seed snapshot, torch-free image, ONNX, Render/Vercel deployment, keep-alive, "waking up" UI (v2)
- LSTM/GRU and TFT (Phase 6)
- Full dashboard and performance pages (Phase 7)
