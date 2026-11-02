---
phase: 01-foundations-data-acquisition
plan: 01
subsystem: infra
tags: [uv, torch-cu134, cli, pytest]
requires: []
provides:
  - uv env with core/train split and universal uv.lock
  - "python -m swf CLI contract (lazy-import handlers)"
  - check-gpu command and packaging/CLI/GPU tests
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07]
tech-stack:
  added: [uv, hatchling, torch 2.15.0+cu134, darts 0.48.1, pytest 9.2]
  patterns: [lazy import_module dispatch, explicit PyTorch index]
key-files:
  created: [pyproject.toml, uv.lock, .python-version, .gitignore, README.md, src/swf/__init__.py, src/swf/__main__.py, src/swf/cli.py, src/swf/fetch/__init__.py, src/swf/coverage/__init__.py, tests/test_cli.py, tests/test_packaging.py, tests/test_gpu.py]
  modified: []
key-decisions:
  - "cu134 index worked; no cu132 fallback needed"
  - "All exact pins resolved as specified; none relaxed"
requirements-completed: [SETUP-01, SETUP-02, SETUP-04]
duration: 15min
completed: 2026-11-02
---

# Phase 1 Plan 01: uv/CUDA environment and swf CLI skeleton Summary

uv-locked Python 3.12 env (139 packages, torch 2.15.0+cu134 seeing the RTX 4060) with a core/train extras split and a `python -m swf` argparse CLI whose handlers lazy-import later plans' modules.

## Task commits
1. Task 1 (env, lock, hygiene): 316506e
2. Task 2 (CLI, check-gpu, tests): 415dca3

## Verification
- `uv run pytest -q`: 7 passed (including the gpu test, not skipped)
- `uv run python -m swf check-gpu`: `torch 2.15.0+cu134 cuda 13.4 device NVIDIA GeForce RTX 4060 Laptop GPU`
- `uv lock --check`: OK

## Deviations from Plan
None. uv 0.11.8 was already installed. Handlers for modules from plans 02-05/07 raise ModuleNotFoundError until those plans land (expected).

## Self-Check: PASSED
