# Phase 8: Reproducibility & Viva Readiness - Context

**Gathered:** 2026-11-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the finished project reproducible from a fresh clone (four CLI commands + a README an examiner can follow), audit that every evaluation figure and table exists in `reports/`, write the viva demo/code-walkthrough notes and rehearse the laptop demo, clean the repo and push it to GitHub. No new models, no retraining of the served TFT, no new site features.

Requirements: DEPLOY-03, DEPLOY-04, DEPLOY-05 (ROADMAP Phase 8 success criteria 1-4).

</domain>

<decisions>
## Implementation Decisions

### Reproduction commands (owner, 2026-11-10)
- **D-49:** CLI subcommands only, no Makefile: `uv run python -m swf data`, `... train`, `... evaluate`, `... serve`. `data` and `serve` already exist; `train` and `evaluate` are thin wrappers that call the existing steps in order. Windows has no `make`; ROADMAP allows "CLI equivalents".
- **D-50:** `train` retrains everything (LightGBM, LSTM, TFT) with the fixed seeds; it needs the GPU and takes hours. The committed files under `models/` are what gets served; `train` overwrites them only when it is run.
- **D-51:** `evaluate` re-scores validation and regenerates every figure/table in `reports/` from the saved models. Test-year figures are rebuilt from the stored Phase 6 test run (`models/deployed/test_started.json` and saved test outputs), never re-scored. Keeps the "test touched once" promise.
- **D-52:** Proof of success criterion 1 = a real fresh clone into a temp folder on this laptop: `uv sync --extra train`, `data` (with the cached `data/raw/` copied in so NASA is not re-downloaded), `evaluate`, `serve`, `pytest`, frontend build. `train` is exercised on LightGBM only (quick); the full deep retrain is not repeated.
- **D-53:** `data/` stays gitignored. A fresh clone re-downloads NASA and Open-Meteo through `swf data` (cached, polite) and stops with instructions if the Kaggle files are missing (existing rule). README states first run needs internet, a few minutes, and a Kaggle token.

### README (owner, 2026-11-10)
- **D-54:** Audience = examiner and owner. Plain language: two paragraphs on what the project does, then setup, the four commands, data sources with licences, folder map, a "results at a glance" table from `reports/evaluation/leaderboard.csv`. Every abbreviation expanded on first use (owner is a beginner).
- **D-55:** 2-3 screenshots under `docs/screenshots/` taken with Playwright from the running site: Energy page (desktop), Performance page, one phone view. About 1 MB total.
- **D-56:** Viva notes live in `docs/viva.md`, separate from the README: demo script (what to click, in order), file-by-file code-walkthrough order with one line per file, likely examiner questions with short answers.

### Repo cleanup and GitHub (owner, 2026-11-10)
- **D-57:** The two reference videos in the repo root (`Arastoo___...mp4`, `WhatsApp Video 2026-11-09 ...mp4`) are deleted from the project folder; they were a Phase 7 design reference and are not the owner's to publish. `.playwright-mcp/` is gitignored.
- **D-58:** Model files stay tracked as today (LightGBM, LSTM, `tft.pt`, `tft.pt.ckpt`, `models/deployed/`). `models/tft/darts/` (20 MB) and `models/tft/logs/` are gitignored; the fresh-clone test must confirm serving works without them, otherwise commit them.
- **D-59:** The GitHub push is the last task of this phase: after the fresh-clone test passes, run a secret scan (no `kaggle.json`, tokens, `.env`) and a size check, add a LICENSE (MIT for the code; data credits stay in the README), then push `master` to `github.com/Bhavin0225/Solaris`. The owner confirms the exact push command before it runs.

### Viva rehearsal (Claude's discretion, owner agreed 2026-11-10)
- **D-60:** Rehearsal = walk through `docs/viva.md` with the owner on 2026-11-15 from a fresh browser profile against `uv run python -m swf serve`. Offline fallback is the existing behaviour: cached forecast with the stale banner. A pre-viva checklist (start server, open site, check "last updated", have `docs/viva.md` open) goes at the top of `docs/viva.md`.

### Claude's Discretion
- Exact wording and section order of README and `docs/viva.md`; which existing CLI steps `train`/`evaluate` chain and in which order; how the `reports/` audit is recorded (a checklist in the summary is enough); screenshot sizes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/ROADMAP.md` Phase 8 — success criteria 1-4
- `.planning/REQUIREMENTS.md` DEPLOY-03, DEPLOY-04, DEPLOY-05 (lines 108-110, 236)
- `docs/PRD.md` §13 reproducibility row (line 310: `make data/train/evaluate/serve` or equivalent CLI, fixed seeds) and the simulated-energy caveat (line 167)
- `.planning/research/SUMMARY.md` — errata that override the PRD

### Existing CLI and artifacts
- `src/swf/cli.py` — current subcommands: check-gpu, fetch, nasa, openmeteo, kaggle, probe, coverage, curve, build-weather, simulate-energy, validate, features, baselines, evaluate, train-lgbm, train-lstm, train-tft, serve, data
- `models/deployed/registry.json`, `models/deployed/test_started.json` — served model and the single test run
- `reports/evaluation/` and `reports/validation/` — figures/tables to audit against success criterion 3
- `README.md` — current short version to be rewritten (keep the `uv sync --extra train` warning and the Open-Meteo / NASA credit lines)
- `.gitignore` — `data/` already ignored; add `.playwright-mcp/`, `models/tft/darts/`, `models/tft/logs/`

### Prior decisions that constrain this phase
- `.planning/phases/07-frontend-full-local-site/07-CONTEXT.md` — D-30 (TFT served for all targets), D-36/D-45 (honest coverage reporting), D-37 (About page attribution)
- `.planning/phases/06-deep-models-selection-final-evaluation/06-CONTEXT.md` — test evaluated once

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `swf data` subcommand already exists as the data pipeline entry point; `swf serve` serves API plus `frontend/dist`.
- `swf evaluate` (Phase 6, with `--final`) and `train-lgbm` / `train-lstm` / `train-tft` are the building blocks for the `train` and `evaluate` wrappers.
- `python -m swf kaggle` stops with manual instructions when the Kaggle token or files are missing.
- Playwright MCP is available for screenshots (used in Phase 7).

### Established Patterns
- Config from `config/*.yaml`; raw API responses cached under `data/raw/`; UTC internally.
- `pytest` must be green before a phase closes.
- Commits per task with conventional-commit style.

### Integration Points
- New `train` / `evaluate` subcommands register in `src/swf/cli.py` next to the existing ones.
- README and `docs/viva.md` reference `/api/build` footer data (git SHA, data-through, model version) already exposed by the API.

</code_context>

<specifics>
## Specific Ideas

- README "results at a glance" copies the leaderboard numbers (TFT vs baseline 3 per target) so the honest comparison is visible on GitHub without running anything.
- Fresh-clone test runs in a temp folder on this laptop with `data/raw/` copied in (no 25-year NASA re-download).

</specifics>

<deferred>
## Deferred Ideas

- Cloud deployment (v2, DEPLOY-01).
- Wind band recalibration (reported as a limitation instead, Phase 7).

</deferred>

---

*Phase: 08-reproducibility-viva-readiness*
*Context gathered: 2026-11-10*
