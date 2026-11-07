---
phase: 5
slug: walking-skeleton-lightgbm
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-07
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 (`addopts = -q -m 'not network and not realdata'`) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `.venv/Scripts/python -m pytest tests/test_api_*.py tests/test_predict_*.py tests/test_lgbm_*.py -x` |
| **Full suite command** | `.venv/Scripts/python -m pytest` (plus `-m realdata tests/test_lgbm_real.py` at the phase gate) |
| **Estimated runtime** | ~60 seconds (default suite); realdata LightGBM run longer |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the touched module
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite green plus the `-m realdata` LightGBM run
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner; each task maps to one of these requirement checks.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | API-01 | — | Pydantic response models, `Query(ge,le)` on hours/days | unit (TestClient, seeded DB) | `pytest tests/test_api_endpoints.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-02 | — | N/A | unit (scheduler job inspect, mocked refresh) | `pytest tests/test_api_scheduler.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-03 | SQL injection | Parameterized sqlite3 only; atomic replace | unit | `pytest tests/test_api_db.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-04 | — | N/A | unit (MockTransport ConnectError/503, sleep injected) | `pytest tests/test_api_stale.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-05 | Path traversal via registry | Artifact paths resolved inside `models/`; text boosters only | unit + subprocess import hygiene | `pytest tests/test_predict_registry.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-06 | — | N/A | unit (timing) | `pytest tests/test_api_perf.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-07 | — | N/A | unit (fixed `now`, IST bounds) | `pytest tests/test_api_summary.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DEPLOY-02 | Bind 127.0.0.1 | uvicorn bound to localhost, 1 worker | integration (live fixture, mocked transport) | `pytest tests/test_api_refresh.py tests/test_cli.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-01 | — | N/A | unit (synthetic, seeds, spec hash) | `pytest tests/test_lgbm_train.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-01 | — | N/A | realdata (val parquet, leaderboard row) | `pytest -m realdata tests/test_lgbm_real.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MODEL-04 | — | N/A | unit (sorted, clipped, ~80% coverage) | `pytest tests/test_predict_bands.py` | ❌ W0 | ⬜ pending |

Additional checks: baseline-3 serve parity (live baseline 3 equals Phase 4 `baseline3` values on the same canon frame) and the residual identity `y_res + b3 == y_true` on train rows.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test files listed above (`tests/test_api_*.py`, `tests/test_predict_*.py`, `tests/test_lgbm_*.py`)
- [ ] Shared fixtures: seeded temp SQLite DB; mock Open-Meteo client returning `tests/fixtures/om_live_gfs_seamless.json`
- [ ] `tests/synth.py` helper for a small synthetic ERA5/GFS/truth set (tiny boosters, `num_boost_round` ~5)
- [ ] No framework install needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Minimal page shows live 72 h forecast for 5 targets | DEPLOY-02 | Needs browser and live Open-Meteo | Run `python -m swf serve`, open `http://127.0.0.1:8000/`, confirm 5 targets x 72 rows with P10/P50/P90 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
