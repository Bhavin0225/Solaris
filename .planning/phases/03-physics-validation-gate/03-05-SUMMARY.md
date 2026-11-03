---
phase: 03-physics-validation-gate
plan: 05
subsystem: physics-validation
tags: [docs, validation, wind, phase-gate]
requires: [03-04]
provides: [viva-facing validation notes, corrected curve wording]
affects: [docs/data_notes.md, REQUIREMENTS.md, ROADMAP.md]
key-files:
  modified: [docs/data_notes.md, src/swf/physics/wind.py, .planning/REQUIREMENTS.md, .planning/ROADMAP.md]
decisions:
  - "D-L1 kept: plant.yaml loss stays 14% (Plant 1 tuned 9%, both pass)"
  - "D-L4: power curve described as re-binned manufacturer curve everywhere"
metrics:
  completed: 2026-11-03
---

# Phase 3 Plan 05: Validation notes and phase gate Summary

Hand-written "Physics validation (Phase 3)" section in docs/data_notes.md (outside AUTO blocks) with numbers from metrics.json, plus "empirical curve" wording corrected to "re-binned manufacturer curve".

## Commits
- 7018b7a: docs(03-05): physics validation notes and re-binned manufacturer curve wording

## Headline numbers (metrics.json)
- Plant 1: tuned loss 9%, held-out 3.36%, full 3.11%; at configured 14%: held-out 4.34%, full 4.26% (pass, gating)
- Plant 2: tuned loss 17%, held-out 14.39% (non-gating miss); dropouts: 2355/3259 timestamps complete, median/worst inverter zero-AC 16.7%/29.7% (Plant 1: 0.0%/1.9%)
- Wind: full year sim 12.12% vs manufacturer 12.94%; ref slice (n=10098) 12.31% vs 13.08%; measured availability 3.54% vs 3.5% config; pass

## Phase gate
- `uv run pytest -o addopts=""`: 224 passed, 0 failed (16 warnings)
- `uv run ruff check src tests`: All checks passed
- `git diff --stat config/plant.yaml`: empty; `swf validate` rerun left metrics.json unchanged and the hand-written section intact

## Deviations from Plan
None to plan scope. Note: `ruff format --check` reports 38 files would be reformatted (pre-existing, outside this plan; deferred, not fixed). wind.py change is docstring only.

## Self-Check: PASSED
