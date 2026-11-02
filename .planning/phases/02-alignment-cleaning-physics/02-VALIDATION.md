---
phase: 2
slug: alignment-cleaning-physics
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-03
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `02-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2 (existing, 83 tests green) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]`; add marker `realdata` (skips when `data/raw/...` absent) |
| **Quick run command** | `uv run pytest -q tests/test_align_*.py tests/test_physics_*.py` |
| **Full suite command** | `uv run pytest -q && uv run pytest -q -m realdata && uv run ruff check src tests` |
| **Estimated runtime** | ~20 seconds unit; realdata ~1–2 min |

---

## Sampling Rate

- **After every task commit:** `uv run pytest -q tests/test_align_*.py tests/test_physics_*.py`
- **After every plan wave:** `uv run pytest -q`
- **Before `/gsd:verify-work`:** full suite green + `-m realdata` + ruff
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Task IDs are filled by the planner. Rows are keyed by requirement.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | ALIGN-01 | — | Exact `CANON_COLS`, UTC, hourly, units; frozen tuple | unit | `uv run pytest -q tests/test_align_canon.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-01 | — | OM shift −1 h, NASA 0 h (D-14/D-15); PR lead suffix; live uses same adapter | unit | `uv run pytest -q tests/test_align_adapters.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-02 | — | Verifier recovers known offset on synthetic series and rejects the wrong one (D-13 rule) | unit | `uv run pytest -q tests/test_align_timestamps.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-02 | — | Real data: pooled centroid ±0.15 h, onset {0,+1} h ≥90%, opposite convention <90% | realdata | `uv run pytest -q -m realdata tests/test_align_timestamps.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-03 | — | ≤3 h fill (GHI via clear-sky index), no fill across sunrise/sunset, >3 h stays NaN, no back-fill, clip counts | unit | `uv run pytest -q tests/test_align_clean.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-04 | — | GHI/DNI/DHI = 0 where midpoint zenith > 90°; counts logged | unit | `uv run pytest -q tests/test_align_clean.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-05 | — | Monthly bias/RMSE/corr, sign ERA5 − NASA, daytime GHI mask | unit | `uv run pytest -q tests/test_align_consistency.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ALIGN-06 | — | Fit recovers known a,b; any-month threshold rule (D-17); train-years-only fit; one `apply_correction`; JSON round-trip; clips | unit | `uv run pytest -q tests/test_align_consistency.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PHYS-01/02 | — | Clear-sky day 0 at night, 700 ≤ peak ≤ 800 (loss 14, DC side D-16); loss 0 → exactly 800.0 cap from config | unit | `uv run pytest -q tests/test_physics_solar.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PHYS-03 | — | Azimuth mapping; S/N POA ratio > 1.3 on 21 Dec | unit | `uv run pytest -q tests/test_geometry.py tests/test_physics_solar.py` | ✅ / ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PHYS-04 | T-2-kaggle | Power curve from T1 (BOM, `%d %m %Y %H:%M`, centre bins), cut-out, density (kPa→hPa), α clip + 0.143 rule, parametric fallback; `require_kaggle_files` before build | unit | `uv run pytest -q tests/test_physics_wind.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PHYS-05 | — | Unit conversions (kPa/hPa, kW/W) + chain tests | unit | `uv run pytest -q tests/test_physics_*.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PHYS-06 | — | Clamp T1 [0, cap], T1=0 night, RH [0,100], GHI ≥0 and 0 night, WS ≥0, T5 [0,3600]; NaN preserved; idempotent | unit | `uv run pytest -q tests/test_physics_constraints.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | (config) | — | New settings keys under `extra=forbid`; bad values rejected | unit | `uv run pytest -q tests/test_config.py` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/synth.py` synthetic generators (clear-sky interval means, controllable label convention, gaps, night leakage)
- [ ] `tests/test_align_canon.py`, `test_align_adapters.py`, `test_align_timestamps.py`, `test_align_clean.py`, `test_align_consistency.py`
- [ ] `tests/test_physics_solar.py`, `test_physics_wind.py`, `test_physics_constraints.py`
- [ ] `realdata` marker registered in `pyproject.toml`
- [ ] Settings schema + `config/*.yaml` physics keys (clip bounds, gap limit, correction thresholds, rho0, albedo, curve path, normalisation capacities)
- [ ] `write_auto_block(name=...)` generalisation, default behaviour unchanged (`tests/test_coverage.py`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docs/data_notes.md` timestamp, consistency and cleaning tables read sensibly | ALIGN-02, ALIGN-05, ALIGN-03 | Content review for the report | Run the align/physics CLI; read the new AUTO blocks |
| Clear-sky PV curve shape is physically plausible | PHYS-01 | Visual sanity | Inspect generated plot or table for a clear day |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
