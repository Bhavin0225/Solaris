# Phase 5: Walking Skeleton & LightGBM - Context

**Gathered:** 2026-11-07
**Status:** Ready for planning

<domain>
## Phase Boundary

A locally run backend and minimal page serve live baseline-3 forecasts for all five targets end-to-end (live Open-Meteo → physics → SQLite → FastAPI → minimal page). LightGBM is trained as a direct multi-horizon model per target and scored against baseline 3 on the validation leaderboard. Serving dispatches per target through the registry, with lazy imports.

Requirements: API-01..07, DEPLOY-02, MODEL-01, MODEL-04 (ROADMAP Phase 5). DEPLOY-01 and all cloud parts are deferred to v2.

</domain>

<decisions>
## Implementation Decisions

### Locked earlier (do not re-decide)
- **D-01 (Phase 4):** Hourly origins for training and evaluation.
- **D-02 (Phase 4):** Lead-matched GFS mapping, horizon h uses `previous_day{ceil(h/24)}`.
- **D-03a (Phase 4):** Official baseline 3 per target = lower validation (2024) RMSE of corrected vs raw GFS. Frozen in `config/baseline3_choice.json`.
- **D-05 (Phase 4):** No GTI covariate.
- **D-06 (Phase 4):** Purge-only splits, no 168 h embargo.

### LightGBM target form
- **D-07:** LightGBM predicts the **residual** = observed target minus the official baseline-3 series for that target (per `config/baseline3_choice.json`). Serving adds the baseline-3 value back, then applies the physical clipping layer.

### Horizon handling
- **D-08:** Three bucket models per target, one per horizon bucket: 1–6 h, 7–24 h, 25–72 h (PRD 9.2 buckets). Each bucket model trains only on its own horizons. Horizon is not a row-expanding feature.

### Uncertainty bands
- **D-09:** P10–P90 bands come from **empirical validation residual quantiles by horizon bucket**. The same method applies to baseline 3 and LightGBM. No LightGBM quantile objective. Quantiles are sorted (no crossing) and clipped (MODEL-04).

### Startup and stale behaviour
- **D-10:** On startup, serve the cached forecast immediately if one exists, and fetch Open-Meteo right away in the background (no wait for the first hourly tick).
- **D-11:** The served forecast is marked `stale: true` with its age when the last successful refresh is more than **2 hours** old (two missed hourly refreshes). The forecast is still served from cache in every case.

### Resolved at plan-check (owner delegated to Claude, 2026-11-07)
- **D-12 (IST summary):** `/api/forecast/summary` covers the next full IST calendar day (00:00–24:00 Asia/Kolkata). The server computes only the UTC instants of those day bounds; every timestamp the API returns stays UTC (`Z`). This is consistent with CLAUDE.md: display conversion to IST happens only in the frontend. API-07 wording updated to match.
- **D-13 (served model in Phase 5):** the served runtime is pinned to `baseline3` for all five targets. LightGBM is trained, written to the validation leaderboard and its serving path is unit-tested, but `models/registry.json` selects `baseline3` everywhere. Per-target selection happens in Phase 6 (MODEL-05). A test asserts the served `model` value is `baseline3` for every target.
- **D-14 (early stopping):** LightGBM early-stops on a held-out tail of the training window (2023-07-01 to 2023-12-31, origins purged at the boundary), not on validation. Validation (2024) is used only for bands (D-09) and the leaderboard row.
- **Other locked choices:** `python -m swf serve` serves `frontend/dist` on 127.0.0.1 with 1 worker (`npm run dev` documented alternative); no LightGBM test-split file in Phase 5; live fetch `past_days` raised 7→8 (no origin clamp), with a 00:xx UTC test.

### Claude's Discretion
- LightGBM hyperparameters, feature subset (taken from the shared `FEATURE_SPEC`), and the search method (small grid or early stopping on validation, per the PRD anti-feature list). Fixed seeds are required.
- Minimal page scope for success criterion 1. Not discussed. Keep it a placeholder that shows the five targets with P50 and bands. The full dashboard is Phase 7.
- Module layout inside `swf.api` and `swf.predict`, following the research architecture (Predictor protocol, registry-dispatched lazy imports).

### Folded Todos
None. No pending todos matched this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec and requirements
- `docs/PRD.md` §9.1–9.4 (baselines, model ladder, evaluation, selection rule), §10 (backend and endpoints), §12 (repository structure)
- `.planning/research/SUMMARY.md` — Phase 5 delivery list, architecture patterns 1 and 4 (one feature function, registry-dispatched Predictor), registry shape, pitfalls C3, C9 and the train/serve skew notes
- `.planning/REQUIREMENTS.md` — API-01..07, DEPLOY-02, MODEL-01, MODEL-04
- `.planning/ROADMAP.md` §Phase 5 — success criteria 1–5
- `.planning/PROJECT.md` Key Decisions table

### Prior-phase decisions and artifacts
- `.planning/phases/04-features-splits-baselines-evaluation-harness/04-CONTEXT.md` — D-01 to D-06 and the carried-forward splits
- `config/baseline3_choice.json` — official per-target baseline-3 choice and `feature_spec_hash`
- `config/bias_correction.json`, `config/site.yaml`, `config/plant.yaml`, `config/features.yaml`
- `docs/data_notes.md` — timestamp conventions, coverage, physics chain

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `swf.features` (`build`, `spec`, `history`, `splits`): the shared feature builder. Serving must call the same code (FEAT-01, FEAT-06).
- `swf.evaluate.baselines`, `swf.evaluate.metrics`, `swf.evaluate.longfmt`: baseline 3, metrics and the long prediction format. LightGBM rows write the same format.
- `swf.align.consistency.apply_correction` and `load_coefs`: the single train/serve correction function.
- `swf.physics.*` (`simulate`, `solar`, `wind`, `constraints.enforce`): the physics chain for baseline 3 and the clipping layer.
- `swf.fetch.openmeteo`: live forecast fetch (`past_days=7`, `forecast_days=4`) with the disk cache under `data/raw/`.
- `swf.core.settings` and `config/*.yaml`: all site and plant values.
- `swf.cli` `_run("swf.<pkg>.run", args)` pattern for the new `serve` subcommand.

### Established Patterns
- Pydantic models with `extra=forbid` for config. New config goes in its own yaml file.
- Deterministic committed outputs (no timestamps in artifacts). Fixed seeds.
- Synthetic test builders in `tests/synth.py`. Realdata tests marked `realdata`.
- UTC internally, no `tz_convert` in pipeline logic.

### Integration Points
- New `swf.predict` (registry loader, Predictor protocol, clipping) and `swf.api` (FastAPI app, APScheduler 3 job, sqlite3 WAL repository, Pydantic schemas). The API imports only core, fetch, adapters, physics, features and predict. It never imports `evaluate`, `validate`, torch, darts or matplotlib at module load.
- New `models/` artifacts and `models/registry.json` (per the research registry shape).

</code_context>

<specifics>
## Specific Ideas

- The residual-on-baseline-3 design means the leaderboard's LightGBM row is directly comparable to the official baseline-3 row (same inputs and same correction).
- The SQLite cache schema follows API-03: (run_time, target_time, target, model, p10, p50, p90).

</specifics>

<deferred>
## Deferred Ideas

- Lazy refresh on request when cache is older than 60 min (v2 cloud, API-02)
- Committed seed snapshot for ephemeral-disk restarts (v2, API-03)
- Torch-free serving image and ONNX runtime (v2, API-05)
- Public deployment on Render and Vercel/Netlify, `VITE_API_URL`, keep-alive pinger, "waking up" UI state (v2, DEPLOY-01, UI-03 cloud parts)
- Deep models LSTM/GRU and TFT (Phase 6)
- Full dashboard and performance pages (Phase 7)

### Reviewed Todos (not folded)
None.

</deferred>

---

*Phase: 05-walking-skeleton-lightgbm*
*Context gathered: 2026-11-07*
</content>
