---
phase: 8
slug: reproducibility-viva-readiness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-10
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled by the planner per task. Requirement coverage from research:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| DEPLOY-03 | `data` / `train` chain existing CLI steps in order, fail-fast | unit (monkeypatch) | `uv run pytest tests/test_cli.py` | ✅ (extend) | ⬜ pending |
| DEPLOY-03 | `evaluate` never runs `--final`; prints skip list when predictions absent (D-61) | unit | `uv run pytest tests/test_cli.py tests/test_final_eval.py` | ✅ (extend) | ⬜ pending |
| DEPLOY-04 | README names the four commands and data credits | unit (string asserts) | `uv run pytest tests/test_docs.py` | ❌ W0 | ⬜ pending |
| DEPLOY-05 | Required `reports/` figures and tables exist | unit | `uv run pytest tests/test_reports_audit.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_docs.py` — README / docs/viva.md string checks (DEPLOY-04)
- [ ] `tests/test_reports_audit.py` — required report files exist (DEPLOY-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fresh clone reproduces data → train → evaluate → serve | DEPLOY-03 | Needs network, Kaggle token, GPU, long runtime | Clone to a temp folder, copy `data/raw/` (incl. kaggle), run the commands from README, open the site |
| Viva rehearsal from fresh browser profile | DEPLOY-05 | Owner-attended (D-60) | Walk `docs/viva.md` on 2026-11-15 |
| GitHub push | — | Owner confirms command (D-59) | After secret + size scan |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
