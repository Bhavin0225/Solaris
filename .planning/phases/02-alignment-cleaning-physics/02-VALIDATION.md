---
phase: 2
slug: alignment-cleaning-physics
status: planned
nyquist_compliant: true
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

Task IDs are `{plan}-T{n}` (plan 02-08 task 2 = `02-08-T2`). Rows are keyed by requirement.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T2 | 02-01 | 1 | ALIGN-01 | T-02-03 | Exact `CANON_COLS`, UTC, hourly labels, float64, sentinel guard; frozen tuple | unit | `uv run pytest -q tests/test_align_canon.py` | ❌ W0 (created by 02-01-T2) | ⬜ pending |
| 02-02-T1 | 02-02 | 2 | ALIGN-01 | T-02-05, T-02-06, T-02-07 | OM shift −1 h (radiation/instant/precip), NASA 0 h (radiation/met/precip), all six OFFSETS pinned (D-14/D-15); PR lead suffix; live uses same adapter; sha-verified reads | unit + realdata | `uv run pytest -q tests/test_align_adapters.py && uv run pytest -q -m realdata tests/test_align_adapters.py` | ❌ W0 (created by 02-02-T1) | ⬜ pending |
| 02-02-T2 | 02-02 | 2 | ALIGN-02 | T-02-07 | Verifier recovers known offset on a full synthetic year and rejects the +1 h shift (D-13 rule, night-masked onset); met_lag recovers a known lag | unit | `uv run pytest -q tests/test_align_timestamps.py` | ❌ W0 (created by 02-02-T2) | ⬜ pending |
| 02-02-T2, 02-07-T3 | 02-02, 02-07 | 2, 3 | ALIGN-02 | T-02-07, T-02-22 | Real data: pooled centroid ±0.15 h, onset {0,+1} h ≥90%, opposite convention <90% (≈0.67 night-masked); met-group lag reported; recorded in data_notes AUTO:timestamps | realdata | `uv run pytest -q -m realdata tests/test_align_timestamps.py` | ❌ W0 (created by 02-02-T2) | ⬜ pending |
| 02-03-T1, 02-03-T2 | 02-03 | 2 | ALIGN-03 | T-02-09, T-02-10, T-02-11 | ≤3 h fill (GHI via clear-sky index), no fill across sunrise/sunset, >3 h stays NaN, no back-fill, complete index, clip counts | unit | `uv run pytest -q tests/test_align_clean.py` | ❌ W0 (created by 02-03-T1) | ⬜ pending |
| 02-03-T1 | 02-03 | 2 | ALIGN-04 | T-02-10 | GHI/DNI/DHI = 0 where midpoint zenith > 90°; counts logged | unit | `uv run pytest -q tests/test_align_clean.py` | ❌ W0 (created by 02-03-T1) | ⬜ pending |
| 02-04-T1 | 02-04 | 2 | ALIGN-05 | T-02-14 | Monthly bias/RMSE/corr, sign ERA5 − NASA, daytime GHI mask, any-month decision | unit | `uv run pytest -q tests/test_align_consistency.py` | ❌ W0 (created by 02-04-T1) | ⬜ pending |
| 02-04-T2 | 02-04 | 2 | ALIGN-06 | T-02-12, T-02-13 | Fit recovers known a,b; train-years-only fit; one `apply_correction`; JSON round-trip; clips | unit | `uv run pytest -q tests/test_align_consistency.py` | ❌ W0 (created by 02-04-T1) | ⬜ pending |
| 02-05-T1 | 02-05 | 2 | PHYS-01/02 | T-02-15, T-02-16, T-02-17 | Clear-sky day 0 at night, 700 ≤ peak ≤ 800 (loss 14, DC side D-16); loss 0 → exactly 800.0 cap from config | unit | `uv run pytest -q tests/test_physics_solar.py` | ❌ W0 (created by 02-05-T1) | ⬜ pending |
| 02-05-T1 | 02-05 | 2 | PHYS-03 | — | Azimuth mapping (existing); S/N POA ratio > 1.3 on 21 Dec | unit | `uv run pytest -q tests/test_geometry.py tests/test_physics_solar.py` | ✅ / ❌ W0 (created by 02-05-T1) | ⬜ pending |
| 02-01-T1, 02-06-T1, 02-06-T2 | 02-01, 02-06 | 1, 2 | PHYS-04 | T-02-25, T-02-18, T-02-19, T-02-20 | α clip + 0.143 rule, density (kPa→hPa); power curve from T1 (BOM, `%d %m %Y %H:%M`, centre bins), cut-out, parametric fallback; `require_kaggle_files` before build; committed curve pinned | unit | `uv run pytest -q tests/test_physics_common.py tests/test_physics_wind.py` | ❌ W0 (created by 02-01-T1 / 02-06-T1) | ⬜ pending |
| 02-01-T1, 02-05, 02-06 | 02-01, 02-05, 02-06 | 1, 2 | PHYS-05 | — | Unit conversions (kPa/hPa, kW/W) + chain tests | unit | `uv run pytest -q tests/test_physics_common.py tests/test_physics_solar.py tests/test_physics_wind.py tests/test_physics_constraints.py` | ❌ W0 | ⬜ pending |
| 02-05-T2 | 02-05 | 2 | PHYS-06 | T-02-15 | Clamp T1 [0, cap], T1=0 night, RH [0,100], GHI ≥0 and 0 night, WS ≥0, T5 [0,3600]; NaN preserved; idempotent | unit | `uv run pytest -q tests/test_physics_constraints.py` | ❌ W0 (created by 02-05-T2) | ⬜ pending |
| 02-08-T1, 02-08-T2 | 02-08 | 1 | (config) | T-02-01, T-02-02, T-02-04 | New settings keys under `extra=forbid`; bad values rejected; named AUTO blocks; realdata marker opt-in | unit | `uv run pytest -q tests/test_config.py tests/test_coverage.py` | ✅ extend | ⬜ pending |
| 02-07-T1, 02-07-T2 | 02-07 | 3 | ALIGN-02/03/05/06, PHYS-01/02/04/06 | T-02-21, T-02-23, T-02-24 | Deterministic renderers; simulate() enforces bounds; CLI lists build-weather, simulate-energy | unit | `uv run pytest -q tests/test_pipeline.py tests/test_cli.py` | ❌ W0 (created by 02-07-T1) | ⬜ pending |
| 02-07-T3 | 02-07 | 3 | phase gate | T-02-21, T-02-22, T-02-23, T-02-24 | Real run: interim parquet valid + complete, energy_sim within caps and night 0, bias_correction.json fit_years [2001, 2023], byte-stable re-run | realdata + lint | `uv run python -m swf build-weather && uv run python -m swf simulate-energy && uv run pytest -q && uv run pytest -q -m realdata && uv run ruff check src tests` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All Wave 0 items are owned by the wave-1 plans 02-01 (code contracts) and 02-08 (config/tooling) or created test-first inside the wave-2 task that needs them:

- [ ] `tests/synth.py` synthetic generators (clear-sky interval means, controllable label convention): 02-01-T2
- [ ] `tests/test_align_canon.py` (02-01-T2), `test_align_adapters.py` (02-02-T1), `test_align_timestamps.py` (02-02-T2), `test_align_clean.py` (02-03-T1), `test_align_consistency.py` (02-04-T1)
- [ ] `tests/test_physics_common.py` (02-01-T1), `test_physics_solar.py` (02-05-T1), `test_physics_constraints.py` (02-05-T2), `test_physics_wind.py` (02-06-T1), `test_pipeline.py` (02-07-T1)
- [ ] `realdata` marker registered in `pyproject.toml` and excluded from default addopts; `raw_root` skip fixture in `tests/conftest.py`: 02-08-T2
- [ ] Settings schema + `config/*.yaml` keys (`align` section: max_gap_h, fit_years, thresholds, wind_rel_threshold; `solar.albedo`; `wind.power_curve_csv`): 02-08-T1. Clip bounds live in `swf.align.canon.PHYS_RANGES` (physical limits, not site values); rho0 is a physical constant in `swf.physics.common`; AC cap is derived by `ac_cap_kw(s)`; nRMSE capacities (D-06/D-07) recorded in data_notes by 02-07-T3
- [ ] `write_auto_block(name=...)` generalisation, default behaviour unchanged (`tests/test_coverage.py`): 02-08-T2

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docs/data_notes.md` timestamp, consistency and cleaning tables read sensibly | ALIGN-02, ALIGN-05, ALIGN-03 | Content review for the report | Run the align/physics CLI; read the new AUTO blocks |
| Clear-sky PV curve shape is physically plausible | PHYS-01 | Visual sanity | Inspect generated plot or table for a clear day |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (unit commands; realdata and the 02-07-T3 gate run ~1-2 min by design)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned 2026-11-03 (execution pending)
