---
phase: 6
slug: deep-models-selection-final-evaluation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 (`addopts = -q -m 'not network and not realdata'`) |
| **Config file** | `pyproject.toml` (markers `gpu`, `realdata`) |
| **Quick run command** | `.venv/Scripts/python -m pytest tests/test_deep_seq.py tests/test_final_eval.py -x` |
| **Full suite command** | `.venv/Scripts/python -m pytest` (plus `-m realdata` for Phase 6 real runs at the gate) |
| **Estimated runtime** | ~90 seconds default suite; realdata deep runs are long (GPU) |

---

## Sampling Rate

- **After every task commit:** quick run for the touched module
- **After every plan wave:** full default suite
- **Before `/gsd:verify-work`:** full suite green plus `-m realdata` Phase 6 tests
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

Task IDs filled in by the planner (2026-11-08). Test files are created inside the listed tasks (no separate Wave 0 plan): test_deep_seq.py (06-01), test_evaluate_prob.py / test_eval_figures.py (06-02), test_deep_real.py (06-03), test_tft.py (06-04), test_final_eval.py (06-07), test_final_real.py (06-08).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-T2 | 06-01 | 1 | MODEL-02 | T-06-02 | encoder ends at origin; serve window == train window | unit | `pytest tests/test_deep_seq.py -x` | ❌ W0 | ⬜ pending |
| 06-03-T1 | 06-03 | 2 | MODEL-02 | T-06-06 | checkpoint load with `weights_only=True` | unit | `pytest tests/test_deep_seq.py -x` | ❌ W0 | ⬜ pending |
| 06-03-T3 | 06-03 | 2 | MODEL-02 | T-06-08 | no test file written by train-lstm | realdata/gpu | `pytest -m realdata tests/test_deep_real.py::test_lstm` | ❌ W0 | ⬜ pending |
| 06-01-T2 | 06-01 | 1 | MODEL-02 | T-06-02 | N/A | unit (serve parity) | `pytest tests/test_deep_seq.py::test_serve_parity -x` | ❌ W0 | ⬜ pending |
| 06-04-T1/T2 | 06-04 | 3 | MODEL-03 | T-06-10, T-06-13 | darts loaded only via artifact_path; hard-stop refusal | unit | `pytest tests/test_tft.py -x` | ❌ W0 | ⬜ pending |
| 06-05-T3 | 06-05 | 4 | MODEL-03 | T-06-14 | no test file written by train-tft | realdata | `pytest -m realdata tests/test_deep_real.py::test_tft` | ❌ W0 | ⬜ pending |
| 06-07-T1 | 06-07 | 4 | MODEL-05 | T-06-20 | selection never reads test | unit | `pytest tests/test_final_eval.py::test_select -x` | ❌ W0 | ⬜ pending |
| 06-07-T2 | 06-07 | 4 | MODEL-05 | T-06-21 | `--final` refuses re-run | unit | `pytest tests/test_final_eval.py::test_once_guard -x` | ❌ W0 | ⬜ pending |
| 06-07-T1 | 06-07 | 4 | MODEL-06 | T-06-22 | artifacts inside models/, runtime whitelisted | unit | `pytest tests/test_final_eval.py::test_registry_fields -x` | ❌ W0 | ⬜ pending |
| 06-06-T2 | 06-06 | 4 | MODEL-06 | T-06-17 | import hygiene (no torch/darts for baseline3/lightgbm registry) | unit | `pytest tests/test_predict_registry.py -x` | ❌ W0 | ⬜ pending |
| 06-02-T2 / 06-07-T3 | 06-02, 06-07 | 1, 4 | MODEL-07 | T-06-04 | text boosters only | unit | `pytest tests/test_eval_figures.py tests/test_final_eval.py::test_write_reports -x` | ❌ W0 | ⬜ pending |
| 06-02-T1 | 06-02 | 1 | EVAL-08 | T-06-05 | shared sample | unit | `pytest tests/test_evaluate_prob.py -x` | ❌ W0 | ⬜ pending |
| 06-07-T3 | 06-07 | 4 | EVAL-09 | — | N/A | unit | `pytest tests/test_final_eval.py::test_heatmap -x` | ❌ W0 | ⬜ pending |
| 06-07-T3 | 06-07 | 4 | EVAL-10 | — | N/A | unit | `pytest tests/test_final_eval.py::test_wind_cf -x` | ❌ W0 | ⬜ pending |
| 06-06-T1 | 06-06 | 4 | API (serving) | T-06-18 | deployed registry preferred, fallback works | unit | `pytest tests/test_api_refresh.py -x` | ❌ W0 | ⬜ pending |
| 06-08-T3 | 06-08 | 5 | MODEL-05/06/07, EVAL-08..10 | T-06-24 | test evaluated once; served = deployed | realdata | `pytest -m realdata tests/test_final_real.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_deep_seq.py`, `tests/test_tft.py`, `tests/test_final_eval.py`, `tests/test_evaluate_prob.py`, `tests/test_deep_real.py`
- [ ] `config/deep.yaml` + `DeepCfg` / `load_deep_cfg` in `swf.core.settings`
- [ ] Synthetic helpers in `tests/synth.py` for tiny hist/cov tables

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TFT Day-11 stop decision | MODEL-03 | Depends on measured time vs calendar | Check the D-27 timing note in the SUMMARY; confirm stop or continue with the owner |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
