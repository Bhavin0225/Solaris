---
phase: 08-reproducibility-viva-readiness
plan: 05
subsystem: reproducibility
tags: [fresh-clone, secret-scan, size-scan]
requires: [08-04]
provides: [clone proof, publish-safety scan]
key-files:
  created: [08-05-clone-log.tsv, 08-05-clone-reports-status.txt, 08-05-clone-info.txt, 08-05-clone-git-status.txt]
decisions:
  - "A3 resolved: serving works without models/tft/darts/ (not committed); A4 resolved: Kaggle files came from the copied data/raw cache"
metrics:
  completed: 2026-11-10
---

# Phase 8 Plan 05: Fresh-clone proof and secret/size scan Summary

A real clone at C:/swf-clone (README commands only, raw cache copied in) reproduced the site: all 8 logged commands exit 0, the TFT served all five targets without `models/tft/darts/`, and the tracked files and history hold no secrets and nothing near 50 MB. Nothing was pushed.

## Clone log (08-05-clone-log.tsv)

| Command | Exit | Seconds |
|---|---|---|
| uv sync --extra train | 0 | 37 |
| uv run python -m swf data | 0 | 205 |
| uv run python -m swf evaluate | 0 | 92 |
| uv run python -m swf train --lgbm-only --accept-stale-results | 0 | 221 |
| npm --prefix frontend ci | 0 | 14 |
| npm --prefix frontend run build | 0 | 2 |
| uv run pytest -q | 0 | 243 |
| serve-check (port 8010) | 0 | ~60 |

Evaluate SKIPPED block (first run, before train; only ML models named):
```
SKIPPED val rows for lightgbm, lstm, tft: missing data/processed/predictions/val/<model>.parquet; ...
SKIPPED test rows for lightgbm, lstm, tft: missing data/processed/predictions/test/<model>.parquet; ...
Committed rows kept unchanged; ...
```
Exit 0, no MISMATCH: all baselines reproduced. Post-train evaluate (08-05-clone-info.txt): exit 0, LightGBM val rows no longer skipped (only lstm, tft), so retrained own-sample rows matched the committed ones.

## Serve check (A3)
- /api/health: first call `{"status":"empty",...}` (first refresh runs in the background at startup), then `{"status":"ok","last_success":"2026-11-10T14:29:47Z","run_time":"2026-11-10T13:00:00Z","stale":false,"age_minutes":0}`.
- /api/forecast: 200, 5 targets (ghi, rh, t1_kw, t5_kw, ws10), each `model: "tft"` with 72 points; log "refresh ok: 360 forecast rows". The clone had no `models/tft/darts/`, so it is not needed; `.gitignore` unchanged.
- / returned 200 (built frontend served). Clone server stopped; the owner's server on 8000 is still up (200).
- A4: Kaggle files were in the copied data/raw/kaggle/; the token was never read.

## Finding: reports-status file is not empty (stat-only, not a content change)
08-05-clone-reports-status.txt contains ` M reports/evaluation/gfs_bias_val.csv`. `git diff` on it is empty (exit 0) and the file is byte-identical to the main repo's copy: the file is rewritten with LF while the clone has `core.autocrlf=true`, so git shows it as modified by stat. The same applies to config/bias_correction.json, config/power_curve.csv, docs/data_notes.md and reports/validation/*.json (no diff under `--ignore-space-at-eol`). The plan's automated check `test ! -s` therefore fails strictly; content reproduces exactly. Decision for the owner: accept as an end-of-line artifact of Windows, or ask to set `* text=auto eol=lf` in .gitattributes.

## Tracked files changed in the clone after data/train (08-05-clone-git-status.txt, 40 lines)
- models/lightgbm/*.json/.txt and models/registry.json: expected, `train --lgbm-only` retrained LightGBM (registry diff is 1 line; model files rewritten).
- Other entries (config/*, docs/data_notes.md, reports/*): end-of-line only, see finding above.

## Secret and size scan (Task 2, read-only)
- Secret-named tracked files (kaggle.json, .env, access_token, .pem, id_rsa, .mp4, app.db): none. History additions of those names: none.
- `git grep` content hits: 3, all in documentation text, not secrets: 08-05-PLAN.md:92 and 08-RESEARCH.md:72,108 quote the scan regex itself.
- 10 largest tracked files (KB): tft.pt.ckpt 5052, lstm.pt 1688, ws10_1-6.txt 1308, ws10_7-24.txt 1172, rh_25-72.txt 980, t5_kw_7-24.txt 872, rh_7-24.txt 864, rh_1-6.txt 808, ws10_25-72.txt 792, performance-desktop.png 620. Largest 5 MB, far under 51200 KB.
- size-pack 12.22 MiB, 413 loose objects, 3 packs.

## Deviations from Plan
- Removal of C:/swf-clone was blocked by the safety check (path outside project) and I did not work around it. The clone folder, with its .venv, is still there: owner may delete C:/swf-clone.
- Task 2 produced no files so has no commit; its results are above.
- Per-run stdout was written to the scratchpad (C: root is not writable), not into the clone.

## Known Stubs
None.

## Self-Check: PASSED (log, status, info, git-status files exist; commit 046177f exists)
