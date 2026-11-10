---
phase: 08-reproducibility-viva-readiness
plan: 03
subsystem: repo-hygiene
tags: [gitignore, license, reports-audit]
requires: []
provides: [reports audit test, MIT LICENSE, gitignored scratch]
affects: [08-05 publish]
key-files:
  created: [tests/test_reports_audit.py, LICENSE]
  modified: [.gitignore]
decisions:
  - "Test-split horizon/skill figures not added: not required by success criterion 3"
metrics:
  completed: 2026-11-10
---

# Phase 8 Plan 03: Repo cleanup and reports audit Summary

A permanent test guards all 23 required evaluation files plus the site figure allowlist; reference videos deleted, scratch ignored, MIT LICENSE added.

## Tasks
1. reports audit test: commit e981bb1
2. videos deleted (never committed: `git log --all -- "*.mp4"` empty), `.gitignore` additions, LICENSE: commit a01846b. `models/tft/logs/timing/metrics.csv` stays tracked.

## Audit checklist (all present)
| Category | Files |
|---|---|
| validation scatters | solar_plant_1_scatter.png, solar_plant_2_scatter.png, wind_scatter.png, metrics.json: present |
| leaderboard | leaderboard.csv, breakdown.csv: present |
| skill charts | skill_val.png, skill_heatmap_test.png/.csv: present |
| error by horizon | rmse_by_horizon_val.png: present |
| probabilistic | prob_metrics.csv, reliability_val.png, reliability_test.png: present |
| interpretability | lgbm_gain_importance.png/.csv, tft_variable_selection.png/.csv, tft_training_curves.png: present |
| other | gfs_bias_val.csv/.png, wind_cf.csv/.png: present |

## Deviations
None. Extra figures not added (decision above).

## Self-Check: PASSED
