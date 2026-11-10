---
phase: 08-reproducibility-viva-readiness
plan: 04
subsystem: docs
tags: [readme, viva, screenshots]
requires: [08-01, 08-02, 08-03]
provides: [fresh-clone README, viva notes, docs test]
key-files:
  created: [docs/viva.md, docs/screenshots/energy-desktop.png, docs/screenshots/performance-desktop.png, docs/screenshots/energy-phone.png, tests/test_docs.py]
  modified: [README.md]
decisions:
  - "README results table read from leaderboard.csv (test split, TFT vs baseline 3), asserted by test_readme_results_match_leaderboard"
metrics:
  completed: 2026-11-10
---

# Phase 8 Plan 04: README, screenshots and viva notes Summary

Examiner-facing README (setup, four commands, honest 2025 test results, SKIPPED explanation, credits and MIT licence), three screenshots of the live site, and docs/viva.md (pre-viva checklist, 12-step demo script, code walkthrough order, 12 questions), guarded by tests/test_docs.py.

## Commits
- c4a3a12: screenshots
- 759761a: README + tests/test_docs.py
- d521357: docs/viva.md

## Deviations from Plan
- [Rule 3 - Blocking] Playwright MCP tools were not available to this agent. Screenshots were taken with headless Edge driven over the Chrome DevTools protocol (a throwaway node script in the scratchpad, not committed). Plain `--screenshot` caught the count-up animation mid-way (+2.9% instead of +51.9%), so the CDP script waits 6 s. Viewports: 1280x720 desktop, 390x844 phone. Total 1.49 MB (limit 1.5 MB).
- Task 2 and 3 tests were committed together with README (test file reads viva.md at import), so viva.md was written before the README commit; commits are still separate.

## Findings
- TFT beats baseline 3 on all five test-year targets (+16.2% to +51.9%); viva Q3 was worded accordingly rather than "where it does not win".
- Test-year P10-P90 coverage for TFT: wind speed 66%, wind power 68%, humidity 74% (target 80%); stated in demo script and Q9.

## Known Stubs
None.

## Self-Check: PASSED (README.md, docs/viva.md, 3 screenshots, tests/test_docs.py exist; commits c4a3a12, 759761a, d521357 exist)
