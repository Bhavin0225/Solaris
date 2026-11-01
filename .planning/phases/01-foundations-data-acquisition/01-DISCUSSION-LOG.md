# Phase 1: Foundations & Data Acquisition - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-01
**Phase:** 1-Foundations & Data Acquisition
**Areas discussed:** Env & task runner, NWP model choice, Cache & storage layout, Kaggle acquisition

---

## Env & task runner

| Option | Description | Selected |
|--------|-------------|----------|
| uv | Fast, lockfile, CUDA torch index via pyproject sources | ✓ |
| venv + pip | Stdlib, pinned requirements files | |
| conda | Good CUDA, heavier, bigger image | |

| Option | Description | Selected |
|--------|-------------|----------|
| Python CLI | `python -m swf data\|train\|evaluate\|serve`, cross-platform | ✓ |
| Makefile | PRD wording; needs make on Windows | |
| Both | CLI + thin Makefile | |

| Option | Description | Selected |
|--------|-------------|----------|
| pyproject extras | Core = serve, `[train]` extra | ✓ |
| Two requirements files | requirements.txt + requirements-serve.txt | |

| Option | Description | Selected |
|--------|-------------|----------|
| 3.12 | Installed; numpy 2.5 needs ≥3.12 | ✓ |
| 3.13 | Newer; wheel availability risk | |

---

## NWP model choice

| Option | Description | Selected |
|--------|-------------|----------|
| One model, probe picks | Single model everywhere; Day-1 probe (ECMWF IFS preferred, GFS, best_match) | ✓ |
| best_match | Open-Meteo picks; may change silently | |
| ECMWF IFS fixed | Lock now; 100 m wind not 80 m | |

| Option | Description | Selected |
|--------|-------------|----------|
| No, one model only | Simpler, less fetching | ✓ |
| Archive 2 models | NWP comparison figure, double calls | |

| Option | Description | Selected |
|--------|-------------|----------|
| Days 1, 2, 3 | Covers 72 h horizon | ✓ |
| Days 0–3 | Adds analysis-like day 0 | |

| Option | Description | Selected |
|--------|-------------|----------|
| Same as NASA | Power-law α from 10 m + upper level | ✓ |
| Use 100 m directly | Fixed α=0.143 scaling | |
| You decide | Planner picks after probe | |

---

## Cache & storage layout

| Option | Description | Selected |
|--------|-------------|----------|
| Verbatim JSON | Body + sidecar meta; parse later | ✓ |
| JSON + parquet copy | Parsed copy at fetch time | |

| Option | Description | Selected |
|--------|-------------|----------|
| One file per year | Mirrors NASA, resumable | ✓ |
| One file per month | Smaller, more calls | |
| You decide | Per-API choice | |

| Option | Description | Selected |
|--------|-------------|----------|
| Never, unless --force | Past years immutable | ✓ |
| Re-fetch incomplete year | Auto-refresh last 30 days | |

| Option | Description | Selected |
|--------|-------------|----------|
| Save a few fixtures | 1–2 live responses in tests/fixtures | ✓ |
| Archive every live fetch | Own forecast archive | |

---

## Kaggle acquisition

| Option | Description | Selected |
|--------|-------------|----------|
| Manual download | Browser, no token | |
| kaggle CLI | Token in ~/.kaggle, repeatable | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Hard stop + instructions | Dependent commands exit with guidance | ✓ |
| Skip with warning | Use fallback curve, skip validation | |

| Option | Description | Selected |
|--------|-------------|----------|
| Names + row counts | Files exist, T1 ≈ 50,530 rows | ✓ |
| Existence only | | |
| Checksums | SHA-256 pinned | |

| Option | Description | Selected |
|--------|-------------|----------|
| ~/.kaggle/kaggle.json | Standard location, outside repo | ✓ |
| Env vars | .env, git-ignored | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, document both | CLI first, print manual steps on failure | ✓ |
| CLI only | | |

---

## Claude's Discretion

- CLI subcommand names, config schema shape, logging format, coverage-report layout, module layout, per-API chunk size if a year exceeds limits.

## Deferred Ideas

- Own live-forecast archive (PROD-02).
- Multi-model NWP comparison figure.
