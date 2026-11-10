# Phase 8: Reproducibility & Viva Readiness - Research

**Researched:** 2026-11-10
**Domain:** repo packaging, CLI orchestration, docs, fresh-clone verification (no new libraries)
**Confidence:** HIGH (all findings come from the local repo, tagged [VERIFIED: codebase])

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-49: CLI subcommands only, no Makefile: `uv run python -m swf data`, `train`, `evaluate`, `serve`. `train` and `evaluate` are thin wrappers over existing steps.
- D-50: `train` retrains everything (LightGBM, LSTM, TFT) with fixed seeds; GPU, hours. Committed `models/` is what is served; `train` overwrites only when run.
- D-51: `evaluate` re-scores validation and regenerates every figure/table in `reports/` from saved models. Test-year figures rebuilt from the stored Phase 6 test run (`models/deployed/test_started.json` + saved test outputs), never re-scored.
- D-52: Proof = real fresh clone into a temp folder: `uv sync --extra train`, `data` (cached `data/raw/` copied in), `evaluate`, `serve`, `pytest`, frontend build. `train` exercised on LightGBM only.
- D-53: `data/` stays gitignored. Fresh clone re-downloads via `swf data`, stops with instructions if Kaggle files missing. README says first run needs internet, minutes, Kaggle token.
- D-54: README for examiner + owner, plain language, two paragraphs, setup, four commands, data sources + licences, folder map, results-at-a-glance table from `leaderboard.csv`, abbreviations expanded.
- D-55: 2-3 Playwright screenshots in `docs/screenshots/` (Energy desktop, Performance, one phone), ~1 MB.
- D-56: `docs/viva.md`: demo script, file-by-file walkthrough order, likely examiner Q&A.
- D-57: Delete the two reference .mp4 files in repo root; gitignore `.playwright-mcp/`.
- D-58: Model files stay tracked. `models/tft/darts/` and `models/tft/logs/` gitignored; fresh-clone test must confirm serving works without them, else commit.
- D-59: Push is last task: secret scan, size check, MIT LICENSE, push `master` to github.com/Bhavin0225/Solaris. Owner confirms exact push command first.
- D-60: Rehearsal on 2026-11-15 from fresh browser profile vs `swf serve`; pre-viva checklist at top of `docs/viva.md`.

### Claude's Discretion
Wording/section order of README and viva.md; which CLI steps `train`/`evaluate` chain and order; how the reports audit is recorded; screenshot sizes.

### Deferred Ideas (OUT OF SCOPE)
Cloud deployment (v2, DEPLOY-01); wind band recalibration.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-03 | four commands reproduce everything from fresh clone | Gaps G1-G4 below: `data` does not build interim data; `evaluate` name clash; test predictions not in git |
| DEPLOY-04 | README documents setup, commands, sources, local run | README current state + required content list |
| DEPLOY-05 | all eval figures/tables in `reports/` | Audit table below: all 7 categories already present |
</phase_requirements>

## Summary

No new libraries. The work is wiring, docs and a verification run. Three real gaps exist that the CONTEXT decisions do not account for, and the planner must resolve them or the fresh-clone test (D-52) fails.

**Primary recommendation:** extend `swf data` to chain the offline build steps, make `train` a chain with an LGBM-only switch, keep `swf evaluate` as is and add a no-argument "reports regeneration" default, and decide (Open Question 1) how test predictions reach a fresh clone before writing any plan.

## Findings that change the plan

### G1: `swf data` only downloads
[VERIFIED: src/swf/cli.py `_data`] It runs fetch nasa, fetch openmeteo all, fetch kaggle. It does NOT run `build-weather`, `curve`, `simulate-energy`, `validate`, `features`, `baselines`. In a fresh clone `data/interim/` (17 MB: weather_*.parquet, energy_sim.parquet) is absent, and the API (`/api/...` correlation, extras) needs it (`api/extras.py` reads `energy_sim.parquet`, `weather_nasa.parquet`). So `data` must append: `curve` (config/power_curve.csv is already tracked, so optional), `build-weather`, `simulate-energy`, `validate`, `features`, `baselines`. Order follows the CLI help order in cli.py. Each handler is `_run(module, Namespace)`; reuse the `_data` pattern (list of `(module, Namespace)`; check the argparse defaults each module's `run` reads, e.g. `evaluate` needs `split`/`final`).

### G2: `evaluate` already exists with different meaning
[VERIFIED: cli.py lines 89-95, tests/test_cli.py `test_evaluate_split_choices`] `swf evaluate --split {val,test,all} [--final]`. `--final` refuses if `models/deployed/test_started.json` or `registry.json` exists (final.py MARKERS), which is the "test touched once" guard and is already true in the repo. `--split test` also needs the frozen baseline-3 choice (`config/baseline3_choice.json`, tracked). D-49 says `evaluate` is a thin wrapper; do NOT rename or break the existing flags (test_cli asserts `{val,test,all}`). Recommended: keep `--split` default behaviour, never pass `--final` from the wrapper, and document that `--final` is a one-time owner action already done. Add a test that `evaluate` on a repo with `test_started.json` does not call run_final.

### G3: Predictions that `evaluate` needs are not in git
[VERIFIED: du/ls] `data/processed/predictions/{val,test}/*.parquet` is 192 MB, gitignored. `evaluate` scores from these files, they are produced by `baselines` (baselines only), `train-lgbm`, `train-lstm`, `train-tft` (val) and by `evaluate --final` (test, ML models). A fresh clone has none, and re-scoring test is forbidden by D-51. Per-file sizes: test lightgbm 24 MB, lstm 30 MB, tft 31 MB, val similar, baselines 2-3 MB each. So `evaluate` in a fresh clone cannot reproduce test figures, and val figures need either predictions from `train` or re-prediction from saved models (no existing CLI does re-predict without retraining; `train-tft` retrain is hours). See Open Question 1.

### G4: 20+ models trained, but `train` has no wrapper and TFT is a time-boxed multi-flag command
[VERIFIED: cli.py] `train-tft` has `--timing-only`/`--stop` flags and the D-19 time box. `train` chain: `train-lgbm` -> `train-lstm` -> `train-tft` (full, no flags). Add `--lgbm-only` (used by D-52 check) so the fresh-clone proof does not need a switch of code. Seeds: grep each trainer for the seed constant and state it in README (not verified here: confirm seeds are config-driven in `config/lgbm.yaml` / `config/deep.yaml`).

## Repo state to fix

| Item | State | Action |
|------|-------|--------|
| Two .mp4 files in root | untracked | delete (D-57) |
| `.playwright-mcp/` | untracked | add to .gitignore |
| `models/tft/darts/`, `models/tft/logs/run/`, `logs/timing/hparams.yaml` | untracked; but `models/tft/logs/timing/metrics.csv` is TRACKED | gitignore the dirs; `git rm --cached models/tft/logs/timing/metrics.csv` or keep it ignored-exception; check whether `swf serve` / `predict` / `tft.json` read it |
| Serving without `darts/` | unverified | D-52 fresh clone covers it; serve path is `models/tft/tft.pt` + `.ckpt` (tft.py line 314, 395). If the clone fails to load, commit darts/ (20 MB) |
| LICENSE | absent | add MIT |
| .git size | 14 MB; models 37 MB tracked | OK for GitHub (no file >100 MB; largest model file to check with `git ls-files -z | xargs -0 du -k | sort -n | tail`) |
| Makefile | none, `make` not installed | none (D-49) |
| `.env`, `kaggle.json`, `access_token` | already in .gitignore | secret scan still required (grep for `token`, `KGAT`, `api_key` over `git ls-files`) |
| `graphify-out/` | gitignored | fine |
| README | short, has 4-line setup | rewrite per D-54, keep the `uv sync --extra train` warning and credit lines |

## reports/ audit vs success criterion 3

[VERIFIED: ls reports/] Everything required exists:

| Required | File(s) |
|----------|---------|
| validation scatters | reports/validation/solar_plant_1_scatter.png, solar_plant_2_scatter.png, wind_scatter.png (+ metrics.json, *_points.json) |
| leaderboard | reports/evaluation/leaderboard.csv, breakdown.csv |
| skill charts | skill_val.png, skill_heatmap_test.png/.csv |
| error by horizon | rmse_by_horizon_val.png |
| probabilistic metrics | prob_metrics.csv, reliability_val.png, reliability_test.png |
| interpretability | lgbm_gain_importance.png/.csv, tft_variable_selection.png/.csv, tft_training_curves.png |
| other | gfs_bias_val.*, wind_cf.* |

Audit task = a checklist run, plus a test that asserts these filenames exist (cheap, `tests/test_reports_audit.py`, skip if `reports/` absent). Note: there is no `rmse_by_horizon_test.png` or `skill_test.png` (only a test heatmap and reliability); decide whether test-split horizon figures are wanted (PRD §9 only requires val-based selection; test appears on the heatmap). Flag, do not add unprompted.

## Standard Stack

None to add. Use existing: uv 0.11.8, Python 3.12, pytest 9.2, ruff 0.17.3, Node/npm, Playwright MCP for screenshots. [VERIFIED: pyproject.toml, `uv --version`]

## Architecture Patterns

- New `train`/`evaluate`/extended `data` live in `src/swf/cli.py` next to existing parsers. Use the existing `_run(module, Namespace)` list pattern from `_data`; stop at first nonzero return code (current `max(...)` runs all steps even after a failure; for the longer chain use fail-fast).
- Keep handlers lazy-imported (module docstring: serving set must never load torch; `tests/test_packaging.py::test_serve_export_is_torch_free` guards it). `train` must not import torch at module level.
- Tests: extend `tests/test_cli.py` `test_help_lists_commands` with `train`; add tests that `data`/`train` chain order is as expected using monkeypatched `_run` (no network, no GPU).

## Don't Hand-Roll

| Problem | Use instead |
|---------|-------------|
| Makefile on Windows | `swf` subcommands (D-49) |
| Screenshots | Playwright MCP, as in Phase 7 |
| Secret scan | `git grep -nIE "(kaggle|KGAT|api[_-]?key|secret|token)"` over tracked files plus `git ls-files | grep -iE "kaggle.json|\.env|access_token"`; no new tool |
| Fresh clone | `git clone` of the local repo into scratch dir (uses committed state only; commit first) |

## Common Pitfalls

1. **Fresh clone of the local repo sees only committed files.** Uncommitted README/CLI changes are absent. Commit before the fresh-clone test; `git status` must be clean.
2. **Bare `uv sync` uninstalls torch** (README warning). In the fresh clone use `uv sync --extra train`, and the cu134 index may fail (README fallback: cu132).
3. **`models/deployed/registry.json` git_sha is `...+dirty`**; `/api/build` footer shows it. Expected, mention in viva.md so it is not a surprise question.
4. **`evaluate --final` guard.** Never invoke with `--final` in fresh clone; it refuses by design.
5. **Kaggle files absent in fresh clone**: `data` stops at the kaggle step. Copy `data/raw/` fully (includes `kaggle/`) into the clone for D-52; otherwise `validate`/`curve` fail. `~/.kaggle/kaggle.json` stays outside the repo.
6. **Windows path with spaces** (`F:\Claude first project`): quote paths in README commands and in the fresh-clone script; clone to a no-space temp path to prove the README, plus note long path risk for `models/tft/darts`.
7. **`data/app.db`** is created on first `serve`; a fresh clone shows no cached forecast until the startup refresh succeeds (needs internet). Offline fresh clone shows an empty page, not the stale banner. State in README and viva.md: run `serve` online once the day before.
8. **frontend/dist is gitignored**: fresh clone must run `npm --prefix frontend ci && npm --prefix frontend run build` before `serve` or the page is missing. Put this inside README steps (or have `serve` print a clear message if dist is missing; check `swf.api.run` for current behaviour).
9. **pytest default addopts** skip `network`/`realdata`; "pytest green" means the default set. Optionally run `pytest -m realdata` once in the fresh clone after `data` to prove the pipeline.

## Environment Availability

| Dependency | Available | Note |
|------------|-----------|------|
| uv | yes 0.11.8 | |
| node/npm | yes | |
| make | NO | by design (D-49) |
| NVIDIA GPU, CUDA | yes (CUDA 13.3 toolkit on PATH) | needed only for full `train` |
| Kaggle token | assumed at ~/.kaggle/kaggle.json | not verified in this session (do not read it) |
| Internet | needed for `data`, `serve` refresh | |

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 9.2 (`tests/`, config in pyproject.toml) |
| Quick run | `uv run pytest -x -q` |
| Full suite | `uv run pytest` ; opt-in `uv run pytest -m realdata` |

| Req | Behavior | Test | Command |
|-----|----------|------|---------|
| DEPLOY-03 | `train` in help; data/train chains call steps in order, fail-fast | unit (monkeypatch `_run`) | `uv run pytest tests/test_cli.py` (extend) |
| DEPLOY-03 | evaluate wrapper never runs `--final` when test_started.json exists | unit | `tests/test_final_eval.py` / test_cli |
| DEPLOY-03 | fresh clone works end to end | manual script, documented in summary | see D-52 |
| DEPLOY-04 | README mentions the four commands and credits | unit (string asserts), cheap | new `tests/test_docs.py` |
| DEPLOY-05 | required report files exist | unit (skip if absent) | new `tests/test_reports_audit.py` |

Wave 0 gaps: the two new test files. No framework install needed.

## Security Domain

ASVS relevant: V14 config/secrets only. Controls: gitignore of `kaggle.json`/`.env`/`access_token` exists; run the tracked-file secret scan before push (D-59); confirm `data/app.db` and `data/` are untracked; do not publish the two .mp4 files (third-party content). Keep Open-Meteo CC BY 4.0, NASA POWER and Kaggle dataset credits in README (PRD §13 licensing; the Kaggle dataset names are in `docs/data_notes.md` / config, pull from there).

## Assumptions Log

| # | Claim | Risk |
|---|-------|------|
| A1 | Seeds are fixed and config-driven in trainers (not grepped) | README claim "fixed seeds" must be checked before writing it |
| A2 | `swf.api.run` handles missing `frontend/dist` gracefully (not read) | fresh-clone serve may 404 the page |
| A3 | Serving does not read `models/tft/darts/` (inferred from tft.py lines 314/395 only) | else commit darts/ per D-58 |
| A4 | Kaggle token present on this laptop | `data` step in the fresh-clone test would stop |

## Open Questions

1. **How do test predictions and ML val predictions reach a fresh clone? (blocks D-51/D-52)**
   - Known: predictions are 192 MB, gitignored, only produced by training (val) and `evaluate --final` (test, forbidden to repeat). Reports (CSV/PNG) are committed.
   - Options: (a) commit a compact, compressed predictions set for val+test of the deployed models only (parquet with float32 and only needed columns may drop below ~40 MB total; GitHub accepts it); (b) make `evaluate` skip regeneration when predictions are absent and say "reports already committed; run `train` first to regenerate" (honest but fresh-clone `evaluate` regenerates only baselines); (c) add a `predict` step that re-scores val from saved models (new code, not in scope). Recommendation: (b) as default plus (a) only if the owner wants a full-green fresh-clone `evaluate`. Ask the owner; this is a scope decision, so surface it before planning.
2. **Test-split horizon/skill figures**: add `rmse_by_horizon_test.png` / `skill_test.png`? Only if owner wants (not required by success criterion 3).
3. **`models/tft/logs/timing/metrics.csv` is tracked while its siblings become ignored**: untrack or keep? Check whether `evaluate`'s `tft_training_curves.png` regeneration reads it (figures.py).

## Suggested plan split (about 4 plans, 1 day)

1. CLI: extend `data`, add `train` (`--lgbm-only`), settle `evaluate` wrapper, tests (DEPLOY-03).
2. Repo hygiene: delete mp4s, .gitignore, LICENSE, reports audit test + checklist (DEPLOY-05).
3. Docs: README rewrite + screenshots + `docs/viva.md` (DEPLOY-04), results table from leaderboard.csv (test-split TFT vs baseline 3 rows; leaderboard.csv has both `val` and `test` splits, use the `test` rows for the final claim and say so).
4. Fresh-clone proof (D-52), secret/size scan, owner-confirmed push (D-59), rehearsal 2026-11-15 (D-60; owner-attended, cannot be automated).

## Sources

All HIGH, local: src/swf/cli.py, tests/test_cli.py, src/swf/evaluate/{report,final}.py, pyproject.toml, .gitignore, `ls`/`du` of data/, models/, reports/, docs/PRD.md §13, 08-CONTEXT.md, REQUIREMENTS.md, ROADMAP.md Phase 8.

**Research date:** 2026-11-10. **Valid until:** end of phase (repo-local facts).
