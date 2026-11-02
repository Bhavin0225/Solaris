# Phase 2: Alignment, Cleaning & Physics - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-02
**Phase:** 2-Alignment, Cleaning & Physics
**Areas discussed:** NASA↔ERA5 bias fix, AC cap & capacity, Timestamp & gap rules

---

## NASA↔ERA5 bias fix

| Option | Description | Selected |
|--------|-------------|----------|
| NASA | Target truth per PRD/D1; correct ERA5/GFS into NASA space | ✓ |
| ERA5 | Treat ERA5 as truth | |

| Option | Description | Selected |
|--------|-------------|----------|
| Only if large | Threshold on monthly |bias| (ALIGN-06) | ✓ |
| Always, every variable | Correct GHI/RH/WS10M regardless | |
| Never, document only | Models learn offset | |

| Option | Description | Selected |
|--------|-------------|----------|
| Per variable, per month | 12 fits per variable | ✓ |
| Per variable, global | One fit per variable | |
| Per variable, per month × hour | 288 fits per variable | |

| Option | Description | Selected |
|--------|-------------|----------|
| Train years only | Fit 2001–2023, apply to 2024/2025 | ✓ |
| All years 2001–2025 | Leaks val/test | |

---

## AC cap & capacity

| Option | Description | Selected |
|--------|-------------|----------|
| ~800 kW AC | pdc0 833 kW DC × 0.96 | ✓ |
| 833 kW AC | PRD literal; pdc0 ≈ 868 kW | |

| Option | Description | Selected |
|--------|-------------|----------|
| AC cap | Solar nRMSE normalizer | ✓ |
| DC nameplate 1000 kWp | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Rated 3600 kW | Wind nRMSE normalizer | ✓ |
| Rated × (1 − availability) | ~3474 kW | |

| Option | Description | Selected |
|--------|-------------|----------|
| 14% from config | Until Phase 3 calibration | ✓ |
| Leave loss out | Lossless until Phase 3 | |

---

## Timestamp & gap rules

| Option | Description | Selected |
|--------|-------------|----------|
| Centroid within ±0.15 h | + sunrise onset match ≥90% days | ✓ |
| Centroid within ±0.25 h | Looser | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Per-variable offset | Per variable group, tested | ✓ |
| Single offset, flag it | | |
| Stop and ask me | | |

| Option | Description | Selected |
|--------|-------------|----------|
| ≤3 h as PRD | Linear met; GHI via clear-sky index | ✓ |
| ≤6 h | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Counts in data_notes | Table per source × variable × year + log | ✓ |
| Log only | | |

---

## Claude's Discretion

- Wind power curve (not selected for discussion): PRD default, median Kaggle `Theoretical_Power_Curve` per 0.5 m/s bin, parametric fallback.
- CANON_COLS names, module layout, interim paths, CLI names, D-02 threshold tuning, hub-wind correction order.

## Deferred Ideas

- Non-linear/per-hour bias correction (v2).
- GFS→NASA correction beyond reusing apply_correction() — Phase 4 skew analysis.
