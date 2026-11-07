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

Task IDs are filled in by the planner.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MODEL-02 | — | checkpoint load with `weights_only=True` | unit | `pytest tests/test_deep_seq.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-02 | — | N/A | realdata/gpu | `pytest -m realdata tests/test_deep_real.py::test_lstm` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-02 | — | N/A | unit (serve parity) | `pytest tests/test_deep_seq.py::test_serve_parity -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-03 | — | N/A | unit | `pytest tests/test_tft.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-03 | — | N/A | realdata | `pytest -m realdata tests/test_deep_real.py::test_tft` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-05 | — | selection never reads test | unit | `pytest tests/test_final_eval.py::test_select -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-05 | — | `--final` refuses re-run | unit | `pytest tests/test_final_eval.py::test_once_guard -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-06 | Path traversal | artifacts inside models/, runtime whitelisted | unit | `pytest tests/test_final_eval.py::test_registry_fields -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-06 | — | import hygiene (no torch/darts for baseline3/lightgbm registry) | unit | `pytest tests/test_predict_registry.py -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | MODEL-07 | — | N/A | unit/realdata | `pytest tests/test_final_eval.py::test_importance -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-08 | — | N/A | unit | `pytest tests/test_evaluate_prob.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-09 | — | N/A | unit | `pytest tests/test_final_eval.py::test_heatmap -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-10 | — | N/A | unit | `pytest tests/test_final_eval.py::test_wind_cf -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API (serving) | — | deployed registry preferred, fallback works | unit | `pytest tests/test_api_refresh.py -x` | ✅ extend | ⬜ pending |

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
