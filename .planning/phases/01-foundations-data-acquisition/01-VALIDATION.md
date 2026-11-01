---
phase: 1
slug: foundations-data-acquisition
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-01
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `01-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 (dev group) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths=["tests"]`, `addopts="-q -m 'not network'"`, markers `network`, `gpu` (Wave 0 installs) |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest -q && uv run python -m swf check-gpu && uv lock --check` |
| **Estimated runtime** | ~10 seconds (network-free; MockTransport fixtures) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest -q && uv lock --check`
- **Before `/gsd:verify-work`:** Full suite green + `python -m swf check-gpu` exit 0 + second `python -m swf fetch ...` run logs only cache hits + `docs/data_notes.md` AUTO block present
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

Task IDs use `<plan>-T<n>` (e.g. `01-02-T1` = plan 01-02, Task 1). Rows are keyed by requirement.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1, 01-01-T2 | 01-01 | 1 | SETUP-01 | T-01-SC | Core export contains no torch/darts/kaggle | unit/smoke | `uv lock --check && uv run pytest tests/test_packaging.py` | ❌ W0 | ⬜ pending |
| 01-01-T1, 01-01-T2 | 01-01 | 1 | SETUP-02 | — | N/A | gpu | `uv run pytest -m gpu tests/test_gpu.py && uv run python -m swf check-gpu` | ❌ W0 | ⬜ pending |
| 01-06-T1 | 01-06 | 2 | SETUP-03 | T-01-02, T-01-03, T-01-22 | Bad YAML rejected at load (incl. best_match in nwp_model/probe_models, bad Kaggle slug/file name); no coordinate literals in `src/` | unit | `uv run pytest tests/test_config.py` | ❌ W0 | ⬜ pending |
| 01-01-T2, 01-06-T2 | 01-01, 01-06 | 1, 2 | SETUP-04 | — | N/A | meta | `uv run pytest` | ❌ W0 | ⬜ pending |
| 01-04-T1, 01-04-T2, 01-04-T3 | 01-04 | 3 | SETUP-05 | T-01-15..17 | Token never in repo; missing files → hard stop with instructions | unit | `uv run pytest tests/test_kaggle.py` | ❌ W0 | ⬜ pending |
| 01-02-T2, 01-02-T3 | 01-02 | 3 | DATA-01 | T-01-07, T-01-08 | 429/5xx retried with backoff; 422 not retried; no network on 2nd run | unit | `uv run pytest tests/test_nasa_fetch.py` | ❌ W0 | ⬜ pending |
| 01-03-T1, 01-03-T2 | 01-03 | 4 | DATA-02 | T-01-10, T-01-11 | `models` allow-list (rejects best_match); `models=era5`; GMT; ms units | unit | `uv run pytest tests/test_openmeteo_fetch.py` | ❌ W0 | ⬜ pending |
| 01-02-T2 | 01-02 | 3 | DATA-03 | — | -999 → NaN before any use; UTC-aware index | unit | `uv run pytest tests/test_parse.py` | ❌ W0 | ⬜ pending |
| 01-02-T1 | 01-02 | 3 | DATA-04 | T-01-04 | Sidecar url/status/rows/pct_missing; log line | unit | `uv run pytest tests/test_cache_meta.py` | ❌ W0 | ⬜ pending |
| 01-05-T1, 01-05-T2, 01-07-T1, 01-07-T2 | 01-05, 01-07 | 5, 6 | DATA-05 | T-01-18, T-01-21, T-01-23 | Coverage deterministic; preserves hand sections; eligibility picks gfs_seamless; integrity re-hash | unit | `uv run pytest tests/test_coverage.py` | ❌ W0 | ⬜ pending |
| 01-06-T2 | 01-06 | 2 | (azimuth) | — | N/A | unit | `uv run pytest tests/test_geometry.py` | ❌ W0 | ⬜ pending |
| 01-02-T1 | 01-02 | 3 | (cache atomicity) | T-01-05 | Truncated `.tmp` / missing sidecar is not a cache hit | unit | `uv run pytest tests/test_cache_atomic.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` with pytest config, markers, uv + cu134 index (`uv sync --extra train`)
- [ ] `tests/conftest.py`: MockTransport client factory, no-op sleep, `tmp_path` data root
- [ ] `tests/fixtures/`:
  - `nasa_sample.json` (includes a -999 value and the header)
  - `om_hf_sample.json`, `om_pr_sample.json`, `om_era5_sample.json`
  - `probe_summary.json`
  - 1–2 real live responses (D-13)
- [ ] Test files listed in the map above

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Kaggle files placed on dev box | SETUP-05 | Needs network + Kaggle account/token | `uv run python -m swf kaggle`; confirm 5 files and row counts |
| Real 2001–2025 pulls complete | DATA-01, DATA-02 | Long network jobs, not unit-testable | Run fetch commands; rerun, expecting cache hits only; `python -m swf coverage` |
| Coverage report matches reality | DATA-05 | Depends on live archive state | Read the `docs/data_notes.md` AUTO block; start dates match the probe |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
