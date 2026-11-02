---
phase: 01-foundations-data-acquisition
plan: 04
subsystem: data-acquisition
tags: [kaggle, subprocess]
requires: [01-01, 01-06]
provides:
  - swf.fetch.kaggle (download, check_files, manual_steps, require_kaggle_files, run)
  - data/raw/kaggle/*.csv (5 files, git-ignored)
key-files:
  created: [src/swf/fetch/kaggle.py, tests/test_kaggle.py, docs/data_notes.md]
key-decisions:
  - "swf never touches credentials; kaggle CLI inherits KAGGLE_API_TOKEN env var"
requirements-completed: [SETUP-05]
completed: 2026-11-02
---

# Phase 1 Plan 04: Kaggle acquisition Summary

`python -m swf kaggle [--check]` wraps the kaggle CLI via argv subprocess, verifies 5 CSVs by row count, prints manual steps on failure, and exposes `require_kaggle_files()` as a hard stop.

## Task commits
1. b518940 kaggle wrapper + tests (7 tests)
2. docs commit: data_notes.md `## Kaggle files`
3. Task 3 checkpoint: auto-satisfied, CLI download worked

## Real download
CLI worked using the token from the KAGGLE_API_TOKEN env var (no kaggle.json). Rows: Plant_1_Gen 68778, Plant_1_Weather 3182, Plant_2_Gen 67698, Plant_2_Weather 3259, T1.csv 50530; all exact. `--check` exit 0. `uv run pytest`: 51 passed.

## Deviations from Plan
- manual_steps text mentions `~/.kaggle/kaggle.json` and `KAGGLE_API_TOKEN` (per orchestrator instruction), so the plan's grep gate for those strings matches that one message line. swf does not read any credential or env var.

## Self-Check: PASSED
