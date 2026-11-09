---
phase: 06-deep-models-selection-final-evaluation
plan: 01
subsystem: deep-model foundation
tags: [config, sequence-windows, parity]
requires: []
provides: [DeepCfg, load_deep_cfg, SEQ_COLS, DEC_COLS, sequence_table, encoder_windows, decoder_windows, serve_sequence]
affects: [06-02, 06-03]
key-files:
  created: [config/deep.yaml, tests/test_deep_seq.py]
  modified: [src/swf/core/settings.py, src/swf/features/build.py, tests/synth.py, tests/test_config.py]
requirements: [MODEL-02, MODEL-03]
completed: 2026-11-09
---

# Phase 6 Plan 01: Deep config and shared sequence windows Summary

Strict `DeepCfg` (config/deep.yaml, train_stride 3, encoder 168 h, UTC stable/hard-stop deadlines) plus one sequence-window builder shared by training and serving, with exact serve parity on all 24 fixture origins.

## Commits
- 963493e: config/deep.yaml + DeepCfg/LstmCfg/TftCfg/load_deep_cfg + config tests
- 577328f: sequence_table/encoder_windows/decoder_windows/serve_sequence, `_serve_hist` refactor, synth.seq_inputs, tests/test_deep_seq.py

## Deviations
- [Rule 3] `covariate_table` cannot take `coefs=None`; `synth.seq_inputs` and the decoder test use `load_coefs()`.
- Used a shared `_utc_only` validator function for both datetime fields instead of two copies.

## Notes
- Parity proves code-path equality only (ERA5 vs live source skew accepted, to be stated in 06-07).
- Spec hash unchanged: 3bd1a73d99093287. Full default suite passes.
- STATE.md / ROADMAP.md untouched.

## Self-Check: PASSED
