---
phase: 01-foundations-data-acquisition
plan: 05
subsystem: coverage
tags: [probe, eligibility, report, open-meteo]
requires: [01-02, 01-03, 01-06]
provides:
  - swf.coverage.probe (first_valid, last_valid, is_eligible, collect, run)
  - swf.coverage.report (build_report)
  - tests/fixtures/probe_summary.json
affects: [01-07]
key-files:
  created: [src/swf/coverage/probe.py, src/swf/coverage/report.py, tests/test_coverage.py, tests/fixtures/probe_summary.json]
key-decisions:
  - "Eligibility rule (a)-(d) encoded as a pure function; recorded fixture passes only gfs_seamless"
  - "End-date retry for ERA5/NASA tails lives at the probe call site (400/422 -> end-1 once)"
requirements-completed: [DATA-05]
completed: 2026-11-02
---

# Phase 1 Plan 05: Coverage probe and report Summary

Cached coverage probe with the encoded NWP eligibility rule, plus an offline deterministic markdown report builder over sidecars + probe.

## Task commits
1. d542a96 probe, eligibility rule, fixture, tests
2. 6da6956 build_report and report tests

## Notes
- `python -m swf probe` was NOT run against the live API in this plan (the real run and decision record belong to plan 01-07; Open-Meteo had an outage earlier on 2026-11-02). All probe behavior is verified with MockTransport tests.
- Fixture probe_summary.json is built from the 01-RESEARCH measured numbers; gfs_seamless is the only eligible model, best_match rejected as alias.
- `uv run pytest -q`: all pass.

## Deviations from Plan
None - plan executed as written. The probe uses the shared `min_interval_s` (2.0 s) for the PR smoke request (inside `pr_accepts_all_leads`) and 3.0 s for the other probe requests.

## Self-Check: PASSED
