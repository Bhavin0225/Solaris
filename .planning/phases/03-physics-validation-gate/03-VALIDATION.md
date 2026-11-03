---
phase: 3
slug: physics-validation-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-03
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 (`pyproject.toml` addopts deselect `network` and `realdata`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_validate_*.py -x` |
| **Full suite command** | `uv run pytest -o addopts=""` (includes realdata) |
| **Estimated runtime** | ~180 seconds full, <15 s quick |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds (quick)

---

## Per-Task Verification Map

| Requirement | Behavior | Test Type | Test file |
|-------------|----------|-----------|-----------|
| VAL-01 | dayfirst parse (`05-06-2020` = 5 June), AC summed per timestamp, partial-inverter timestamps dropped | unit, synthetic CSV in tmp_path | `tests/test_validate_solar_parse.py` |
| VAL-01 | loss grid recovers an injected loss from a chain-generated series, bounded 8..20 | unit | `tests/test_validate_solar_tune.py` |
| VAL-02 | nRMSE definition on known arrays, daytime mask, tune/held-out split by date | unit | `tests/test_validate_solar_tune.py` |
| VAL-03 | wind sim vs reference on identical rows, PRD slice selection, density factor == 1 at 1013.25 hPa / 15 C | unit | `tests/test_validate_wind.py` |
| VAL-04 | `run` writes valid `metrics.json` and PNGs to an injectable dir; AUTO block `validation` replaced idempotently | unit (importorskip matplotlib) | `tests/test_validate_outputs.py` |
| VAL-01..04 | real files: Plant 1 held-out nRMSE < 10%, wind sim ≤ 14% and ≤ reference | `@pytest.mark.realdata` | `tests/test_validate_real.py` |
| refactor | `simulate_solar` output unchanged after extracting the post-POA helper | existing | `tests/test_physics_solar.py` stays green |

*Status per task is filled during execution.*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (pytest, realdata marker, synthetic builders). New test files only; fixtures are tiny hand-written CSV strings.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scatter plots are report-ready (labels, units, 1:1 line) | VAL-04 | visual quality | open `reports/validation/*.png` |
| Plant 2 miss justification reads as a defensible viva argument | VAL-02 | judgement | read the hand-written section in `docs/data_notes.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
