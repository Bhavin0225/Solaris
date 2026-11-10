---
phase: 8
slug: reproducibility-viva-readiness
status: draft
nyquist_compliant: true
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


| Task ID | Plan | Wave | Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|----------|-----------|-------------------|-------------|--------|
| 08-01-T1 | 01 | 1 | DEPLOY-03 | `data` chains 9 steps fail-fast; `train` / `--lgbm-only`; stale guard (`--accept-stale-results`); deadline guard | unit (monkeypatch `_run`) | `uv run pytest tests/test_cli.py -q` | ✅ (extend) | ⬜ pending |
| 08-01-T2 | 01 | 1 | DEPLOY-03 | `serve` prints npm build hint when frontend/dist missing; torch-free serve | unit | `uv run pytest tests/test_cli.py tests/test_packaging.py -q` | ✅ (extend) | ⬜ pending |
| 08-02-T1 | 02 | 1 | DEPLOY-03, DEPLOY-05 | baselines re-scored, committed ML rows kept, SKIPPED list, MISMATCH exit 2, never `--final` | unit | `uv run pytest tests/test_evaluate_report.py -q` | ✅ (extend) | ⬜ pending |
| 08-02-T2 | 02 | 1 | DEPLOY-05 | test-year outputs rebuilt from stored run only when test_started.json exists; no re-selection | unit + owner-laptop run | `uv run pytest tests/test_evaluate_report.py tests/test_final_eval.py -q` | ✅ (extend) | ⬜ pending |
| 08-03-T1 | 03 | 1 | DEPLOY-05 | all 22 required reports/ files exist; FIGURES subset of audit list | unit | `uv run pytest tests/test_reports_audit.py -q` | ❌ W0 (created in task) | ⬜ pending |
| 08-03-T2 | 03 | 1 | DEPLOY-03 | videos deleted, scratch ignored, metrics.csv tracked, MIT LICENSE | shell + suite | `git check-ignore -q models/tft/darts .playwright-mcp && git ls-files --error-unmatch models/tft/logs/timing/metrics.csv && uv run pytest -q` | n/a | ⬜ pending |
| 08-04-T1 | 04 | 2 | DEPLOY-04 | 3 screenshots, ≤ 1500 KB total | shell | `du -ck docs/screenshots/*.png \| tail -1` | n/a | ⬜ pending |
| 08-04-T2 | 04 | 2 | DEPLOY-04 | README commands, credits, results = leaderboard test rows, DEADLINE_HELP verbatim, stale flag | unit (string asserts) | `uv run pytest tests/test_docs.py -q` | ❌ W0 (created in task) | ⬜ pending |
| 08-04-T3 | 04 | 2 | DEPLOY-04 | viva.md sections, ≥ 10 `### Q` questions | unit | `uv run pytest tests/test_docs.py -q && uv run pytest -q` | ❌ W0 (created in 08-04-T2) | ⬜ pending |
| 08-05-T1 | 05 | 3 | DEPLOY-03 | fresh clone: 8 logged commands all exit 0; clone reports/evaluation unchanged | shell (log check) | `awk -F'	' '$2 != 0 {bad=1} END {exit bad}' .planning/phases/08-reproducibility-viva-readiness/08-05-clone-log.tsv` | n/a | ⬜ pending |
| 08-05-T2 | 05 | 3 | DEPLOY-03 | no secrets tracked or in history; largest file < 51200 KB | shell | see 08-05 Task 2 verify | n/a | ⬜ pending |
| 08-06-T1 | 06 | 3 | DEPLOY-04, DEPLOY-05 | server, pages, endpoints, figures respond; suite green | shell + suite | `uv run pytest -q && curl -sf http://127.0.0.1:8000/api/health` | n/a | ⬜ pending |
| 08-06-T2 | 06 | 3 | DEPLOY-04 | owner rehearsal (checkpoint) | manual + docs test | `uv run pytest tests/test_docs.py -q` | n/a | ⬜ pending |
| 08-07-T1 | 07 | 4 | DEPLOY-03 | re-scan final HEAD, suite green | shell + suite | see 08-07 Task 1 verify | n/a | ⬜ pending |
| 08-07-T2 | 07 | 4 | DEPLOY-04 | single owner-confirmed push; remote SHA = local SHA | shell | `test "$(git ls-remote origin master \| cut -f1)" = "$(git rev-parse master)"` | n/a | ⬜ pending |

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
| GitHub push | DEPLOY-03/04 | Owner confirms command (D-59) | 08-07, after the 08-06 rehearsal and a re-scan |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
