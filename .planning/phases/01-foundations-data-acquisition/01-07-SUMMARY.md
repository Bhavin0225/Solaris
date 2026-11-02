---
phase: 01-foundations-data-acquisition
plan: 07
subsystem: coverage
tags: [coverage, integrity, decision-record, data_notes]
requires: [01-05]
provides:
  - swf.coverage.report (integrity_section, write_auto_block, run)
  - docs/data_notes.md (AUTO coverage block + D-06, D1, D2, D3, errata, timestamps)
affects: [phase-02, phase-04]
key-files:
  modified: [src/swf/coverage/report.py, tests/test_coverage.py, docs/data_notes.md]
key-decisions:
  - "gfs_seamless confirmed as the only eligible NWP model on a live probe (2026-11-02)"
  - "D3 records the D-19 lead mapping ceil(h/24) -> _previous_day1/2/3"
requirements-completed: [DATA-05]
completed: 2026-11-02
---

# Phase 1 Plan 07: Coverage command, probe run and decision record Summary

`swf coverage` now re-hashes cached files against sidecars, rewrites only the AUTO block of docs/data_notes.md (byte-stable on re-run), and the real probe numbers back the written NWP / D1-D3 decisions.

## Task commits
1. 4e11f0d integrity_section, write_auto_block, run + tests (15 coverage tests pass)
2. docs commit: probe + coverage run on real cache, hand-written decision sections

## Results
- Live probe succeeded (HTTP 200 throughout; it took about 30 min wall-clock due to client back-off, no failures). Eligibility: only gfs_seamless eligible; ecmwf_ifs025, ecmwf_ifs, icon_seamless fail as in RESEARCH. No start date moved by more than a month.
- Integrity: 74 files OK, 0 mismatched, 0 missing.
- Re-run of `swf coverage` is byte-identical; Kaggle section preserved.
- Gate: pytest all pass, check-gpu OK (RTX 4060, cu134), `uv lock --check` OK, cache-only re-runs of fetch nasa / era5 / historical / previous log no `fetch {` lines.

## Flagged findings (no config change)
- NASA ALLSKY_SFC_SW_DWN is 100% missing in the last 60 days (T2M current to 2026-10-31); NASA radiation lags more than other fields.
- ERA5 data-through 2026-10-27 (~6 d latency).

## Deviations from Plan
None. Minor: state.record-metric / state.add-decision were not retried per instructions if they error (see below).

## Self-Check: PASSED
