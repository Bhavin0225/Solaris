---
phase: 7
slug: frontend-full-local-site
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-10
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 07-RESEARCH.md "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 (backend); Node 24 built-in `node:test` (frontend helpers, no install); `tsc -b && vite build`, oxlint |
| **Config file** | `pyproject.toml` (pytest); `frontend/package.json` script `"test": "node --test \"tests/**/*.test.ts\""` (Wave 0) |
| **Quick run command** | `.venv/Scripts/python -m pytest tests/test_api_endpoints.py tests/test_api_extras.py tests/test_api_summary.py -x` (backend) / `cd frontend && npm run lint && npm run build && npm test` (frontend) |
| **Full suite command** | `.venv/Scripts/python -m pytest` && `cd frontend && npm run lint && npm run build && npm test` |
| **Estimated runtime** | ~90 s backend default suite, ~30 s frontend |

---

## Sampling Rate

- **After every task commit:** quick command for the touched side (backend or frontend)
- **After every plan wave:** full suite
- **Before `/gsd:verify-work`:** full suite green, plus Playwright MCP screenshots of all 4 pages x {1440x900, 375x812} x {light, dark} under `.playwright-mcp/`, compared with the reference frames
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| UI-01 | 72 equal-length rows, band null on null quantile, 24/48/72 slices | unit (node) | `node --test tests/forecast.test.ts` | ❌ W0 | ⬜ pending |
| UI-02 | `/api/forecast/summary?day=today|tomorrow`, bad value 422, default unchanged | API | `pytest tests/test_api_summary.py tests/test_api_endpoints.py -x` | ✅ extend | ⬜ pending |
| UI-03 | IST formatting (h23, :30 labels), IST ticks, greeting by IST hour | unit (node) | `node --test tests/time.test.ts` | ❌ W0 | ⬜ pending |
| UI-04/05 | per-target tags/badges, model display-name map | unit (node) | `node --test tests/targets.test.ts` | ❌ W0 | ⬜ pending |
| UI-06 | `/api/performance` shapes; `/api/figures` allowlist 200/404 | API | `pytest tests/test_api_extras.py -x` | ❌ W0 | ⬜ pending |
| UI-07 | `/api/site` + wind CF rows | API | `pytest tests/test_api_extras.py -x` | ❌ W0 | ⬜ pending |
| UI-08 | `/api/build` keys; git failure -> null sha; missing registry handled | API | `pytest tests/test_api_extras.py -x` | ❌ W0 | ⬜ pending |
| D-35 | weather condition rule + day aggregation | unit (node) | `node --test tests/weather.test.ts` | ❌ W0 | ⬜ pending |
| D-35 | `/api/weather` from fixture, Z times, is_day, 503 when file missing | API | `pytest tests/test_api_extras.py -k weather` | ❌ W0 | ⬜ pending |
| D-33 | `/api/correlation` symmetric, diag 1, 503 when missing; sentence builder | API + unit | `pytest -k correlation`; `node --test tests/corr.test.ts` | ❌ W0 | ⬜ pending |
| SPA | `/performance` -> index.html; `/api/nope` -> 404 JSON | API | `pytest -k spa` | ❌ W0 | ⬜ pending |
| hygiene | `swf.api.main` stays torch/darts/matplotlib/lightgbm/evaluate-free | existing | `pytest tests/test_api_endpoints.py::test_import_hygiene` | ✅ | ⬜ pending |
| perf | `/api/forecast` < 500 ms | existing | `pytest tests/test_api_perf.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api_extras.py`: weather, correlation, performance, figures, build, SPA fallback
- [ ] extend `tests/test_api_summary.py` for `day="today"`
- [ ] `frontend/tests/{time,weather,forecast,corr,targets}.test.ts`
- [ ] `frontend/package.json` `test` script

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Hover on one of five panels highlights the same hour on all | UI-01 | visual interaction | Playwright MCP hover + screenshot |
| Stale banner when `stale: true` | UI-03 | needs stale DB state | seed a stale run_time, load Energy |
| 375 px layout: bottom nav, no horizontal scroll, 44 px targets | UI-09 | visual | `browser_resize 375 812`, screenshot, `document.documentElement.scrollWidth <= 375` |
| Look matches the reference video | D-31 | visual | side-by-side with `.playwright-mcp/v2_zoom.png` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
