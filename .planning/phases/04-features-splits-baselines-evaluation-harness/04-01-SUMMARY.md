---
phase: 04-features-splits-baselines-evaluation-harness
plan: 01
subsystem: features
tags: [feature-spec, splits, config, cli]
requires: []
provides: [FeaturesCfg, load_features_cfg, feature_spec, spec_hash, artifact_meta, assert_spec, lead_k, origins_for, split_table, features CLI]
affects: [04-02..04-07, phase 5, phase 6]
key-files:
  created: [config/features.yaml, src/swf/features/__init__.py, src/swf/features/spec.py, src/swf/features/splits.py, src/swf/features/run.py, tests/test_features_spec.py, tests/test_splits.py]
  modified: [src/swf/core/settings.py, src/swf/cli.py, tests/test_cli.py]
decisions:
  - "bias_correction.json hashed after CRLF->LF normalisation so the golden hash is stable across checkouts"
  - "GOLDEN_HASH = bd5c6b0683036df5"
metrics:
  tasks: 3
  completed: 2026-11-03
requirements: [FEAT-01, FEAT-04]
---

# Phase 4 Plan 01: Feature spec, splits, CLI wiring Summary

Pydantic-validated config/features.yaml, a hashed FEATURE_SPEC (86 weather-only / 101 covariate columns, golden hash pinned, assert_spec with diff), purged chronological origin sets (201360 / 24048 / 8712 / 8688) and the features/baselines/evaluate CLI subcommands.

## Commits
- 15e77a0 config + FeaturesCfg
- 4db1e8d spec.py + splits.py + tests
- def1b3e features run handler + CLI

## Deviations from Plan
None, except the CRLF normalisation noted above (Rule 2, robustness of the hash). Origin counts matched the plan's pandas-computed values.

## Verification
`uv run pytest`: 227 passed, 3 skipped, 21 deselected. `ruff check src tests`: clean.
`python -m swf evaluate --help` shows `{val,test,all}`. Baselines/evaluate modules do not exist yet (Plans 04/06); the commands fail at import until then.
Note: the AUTO:features block in docs/data_notes.md was not written (CLI not run against the real file; only tested on tmp_path).

## Known Stubs
None.

## Self-Check: PASSED
