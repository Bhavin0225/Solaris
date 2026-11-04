---
phase: 04-features-splits-baselines-evaluation-harness
plan: 04
subsystem: evaluate
tags: [baselines, persistence, climatology, baseline3, long-format, feature-spec-hash]
requires: [04-01, 04-02]
provides: [swf.evaluate.baselines, spec-stamped prediction parquets, baseline3 choice helpers]
affects: [src/swf/evaluate/longfmt.py]
key-files:
  created: [src/swf/evaluate/baselines.py, tests/test_evaluate_baselines.py]
  modified: [src/swf/evaluate/longfmt.py, tests/test_evaluate_longfmt.py]
decisions:
  - Same-hour persistence for t1_kw and ghi; last-observation persistence for rh, ws10, t5_kw (on the truth series).
  - Choice file stores feature_spec_hash; load_choice re-raises with a re-freeze instruction.
metrics:
  tasks: 3
  completed: 2026-11-04
---

# Phase 4 Plan 04: Baselines Summary

Persistence, climatology and baseline 3 (four variants: lead-matched/stitched x corrected/raw, all via `history_frame`) in the common long format, plus D-03a val-only selection helpers and FEATURE_SPEC hash stamping on prediction parquets and the choice file.

## Commits
- 2c80441 feat(04-04): persistence, climatology, baseline 3 variants, D-03a selection helpers (Tasks 1 and 2, same file)
- Task 3 commit: feat(04-04): stamp and check FEATURE_SPEC hash on prediction parquets (see git log)

## Verification
- `uv run pytest`: 267 passed, 3 skipped, 23 deselected; `ruff check src tests`: all passed.
- Realdata (run with SWF_REAL_INTERIM pointing at the main checkout's data/interim, read-only): 2 passed. Baseline 3 on NASA weather with coefs=None reproduces energy_sim t1_kw/t5_kw exactly; build_split("val") yields six validated models of 8712*72*5 rows. In the worktree these tests skip; the orchestrator should rerun `uv run pytest -o addopts="" -m realdata tests/test_evaluate_baselines.py` in the main tree.

## Deviations
- Test-only env hook `SWF_REAL_INTERIM` (defaults to INTERIM_DIR) so realdata tests can run from a worktree.
- `python -m swf baselines` end-to-end (`run`) was not executed on real data (writes ~GB of parquet); only build_split and the missing-input path were tested.

## Known Stubs
None.

## Self-Check: PASSED
