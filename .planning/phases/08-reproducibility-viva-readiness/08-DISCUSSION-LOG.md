# Phase 8: Reproducibility & Viva Readiness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-10
**Phase:** 8-reproducibility-viva-readiness
**Areas discussed:** Reproduce commands, README depth, Repo cleanup for GitHub

---

## Reproduce commands

| Option | Description | Selected |
|--------|-------------|----------|
| CLI subcommands | `uv run python -m swf data/train/evaluate/serve`; works on Windows, no extra tool | ✓ |
| Makefile + CLI | Also a Makefile for Linux/Mac; needs `make` on Windows | |
| PowerShell script | Windows-only `run.ps1` | |

| Option | Description | Selected |
|--------|-------------|----------|
| Retrain everything | `train` runs LightGBM, LSTM, TFT with fixed seeds; hours on GPU | ✓ |
| LightGBM only by default | `train --deep` for LSTM/TFT | |
| Skip-if-exists | `train --force` to retrain | |

| Option | Description | Selected |
|--------|-------------|----------|
| Real fresh clone, skip retrain | Temp-folder clone, cached raw data copied in, train checked on LightGBM only | ✓ |
| Real fresh clone, full retrain | Same plus hours of GPU retraining | |
| No clone, just document | Trust current checkout | |

| Option | Description | Selected |
|--------|-------------|----------|
| Re-render from saved results | Re-score val, rebuild test figures from stored Phase 6 run | ✓ |
| Full re-score including test | Re-touches the test year each run | |

**User's choice:** all recommended options.

---

## README depth

| Option | Description | Selected |
|--------|-------------|----------|
| Examiner + owner, plain language | Project intro, setup, commands, data sources, folder map, results table | ✓ |
| Developer-only, terse | Keep current short style | |

| Option | Description | Selected |
|--------|-------------|----------|
| 2-3 screenshots | Energy desktop, Performance, one phone view under `docs/screenshots/` | ✓ |
| No screenshots | Text only | |

| Option | Description | Selected |
|--------|-------------|----------|
| Separate `docs/viva.md` | Demo script, walkthrough order, likely questions | ✓ |
| Inside the README | One section at the end | |
| No written notes | Verbal only | |

**User's choice:** all recommended options; moved on after three questions.

---

## Repo cleanup for GitHub

| Option | Description | Selected |
|--------|-------------|----------|
| Delete videos from repo | Design reference only, not owner's to publish | ✓ |
| Keep locally, gitignore | `*.mp4` ignored | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep models tracked as today | Ignore `models/tft/darts/` and `models/tft/logs/`; verify serving in fresh clone | ✓ |
| Commit everything in models/ | +20 MB darts folder and logs | |

| Option | Description | Selected |
|--------|-------------|----------|
| Re-download via `swf data` | `data/` stays gitignored; README notes internet + Kaggle token | ✓ |
| Commit cached weather responses | +130 MB, redistribution concerns | |

| Option | Description | Selected |
|--------|-------------|----------|
| Push is last task of Phase 8, Claude runs after confirmation | Secret scan, size check, MIT LICENSE, push to Bhavin0225/Solaris | ✓ |
| Owner pushes later | Commands written in README | |

**User's choice:** all recommended options.

---

## Claude's Discretion

- Viva rehearsal details (docs/viva.md structure, 2026-11-15 dry run, offline fallback = cached forecast + stale banner) — owner agreed to Claude's proposal.
- README/viva.md wording, order of chained steps in `train`/`evaluate`, how the `reports/` audit is recorded, screenshot sizes.

## Deferred Ideas

- Cloud deployment (v2), wind band recalibration (already deferred in Phase 7).
