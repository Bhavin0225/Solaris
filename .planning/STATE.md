# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-01)

**Core value:** Rigorous, honest model results: a leaderboard showing whether ML beats the Open-Meteo + physics baseline per target, backed by physics simulation validated against real Kaggle plant data.
**Current focus:** Phase 1: Foundations & Data Acquisition (Days 1-2)

## Current Position

Phase: 1 of 8 (Foundations & Data Acquisition)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-11-01 — Roadmap created (8 phases, 70/70 v1 requirements mapped)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Walking skeleton (baseline 3 live, public) by Day 6 is on the critical path (DEPLOY-02, Phase 5)
- [Roadmap]: TFT hard stop Day 11. Cut order: TFT, LSTM tuning, non-linear bias correction, About polish
- [Roadmap]: Contracts (CANON_COLS, FEATURE_SPEC, prediction format, registry schema, API schemas) frozen by Day 3-4 so frontend runs in parallel
- [Roadmap]: Select on validation, `evaluate --final` on test once (Phase 6)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1 -> 3]: USER ACTION Day 1: place Kaggle files (solar Plant 1/2, wind T1.csv) in `data/raw/kaggle/`. Phase 3 validation is blocked until they are present
- [Phase 1]: D1-D3 depend on live probes: Open-Meteo Historical Forecast start (2017 vs docs' 2022), Previous Runs coverage per model for 2024-2025, ERA5 archive start year
- [Phase 5]: Render Free RAM and sleep policy unverified (LOW confidence); fallback Railway or Fly.io
- [Phase 6]: TFT has no ONNX path; serving decision due Day 10-11
- [Phase 6]: Davanagere wind expected weak outside monsoon; plan honest "no ML win" reporting

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-11-01
Stopped at: Roadmap and state initialized; awaiting approval
Resume file: None
