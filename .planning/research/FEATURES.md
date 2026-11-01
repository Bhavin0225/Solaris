# Feature Landscape

**Domain:** Multivariate solar + wind 72 h forecasting web app (Davanagere), final-year project, viva-examined
**Researched:** 2026-11-01
**Audience:** (1) viva examiner (report + slides + code walkthrough + live site), (2) plant-operator persona
**Overall confidence:** MEDIUM. Feature expectations come from the PRD plus general knowledge of forecasting practice and a light web check (operator dashboards, probabilistic-verification metrics). No single authoritative "required features" list exists for this domain.

**Guiding principle:** The Core Value is rigorous, honest results. An examiner grades evaluation discipline (baselines, leakage, honesty about simulated targets) far above UI polish. Operators want "how much, when's the peak, can I trust it". Protect results and report figures over site polish if time slips.

Complexity key: L = under half a day, M = 0.5 to 1.5 days, H = 2 or more days.

---

## Table Stakes

Missing any of these and an examiner or operator dismisses the work.

### Data pipeline

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| NASA POWER + Open-Meteo fetchers with disk cache, backoff, 15-param/1-year chunking | Direct API use is goal G3; reproducibility | M | Cache raw JSON, never re-download. Sentinel -999 to NaN. |
| Structured fetch logging (URL, status, rows, % missing) | PRD NFR; examiners ask "how much data was missing?" | L | Feeds a missing-data table for the report. |
| Timestamp-convention verification (NASA start vs end of hour; Open-Meteo preceding-hour) documented | Misalignment silently wrecks solar skill; a classic viva question | M | Cross-correlate with pvlib clear-sky GHI. Output to `docs/data_notes.md`. |
| Complete hourly UTC table, gap fill ≤ 3 h, physical clipping, night GHI = 0, clip counts logged | Basic data hygiene | M | |
| Chronological train/val/test, full annual cycles, no shuffle, split dates logged | Any random split is an instant fail in time-series viva | L | |
| Automated leakage test | Explicit PRD requirement; answers "how do you know there's no leakage?" | M | Assert that no feature at t uses data after t, except known-future Open-Meteo covariates. |

### Physics / validation

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| pvlib solar chain (Perez, Faiman, PVWatts, clipping) from config | Targets T1/T5 are simulated, so the simulation must be credible | M | Faiman uses wind speed, which couples T4 to T1. |
| Wind chain: empirical power curve, hub-height extrapolation, air-density correction, availability loss | Same | M | Fallback parametric curve if Kaggle file missing. |
| Kaggle validation with pass thresholds, scatter plots and metrics saved (solar ≤ 10%, wind ≤ 14% nRMSE) | The single defence of simulated targets; this is the "acceptance gate" | M | Daytime-only for solar. Tune only the loss %. Document any threshold miss in writing. |
| Unit tests: unit conversions, hub-height, power-curve interpolation, clear-sky PV day, clipping | PRD §13 | M | |
| Physical-constraint enforcement on all outputs (0 ≤ T1 ≤ AC limit, T2 in [0,100], night GHI = 0, 0 ≤ T5 ≤ 3600) | A negative-solar or 120% RH output on the live site is embarrassing | L | Apply as a post-processing layer for every model. |
| Source-consistency check NASA vs ERA5 (bias, RMSE, corr for GHI, RH, WS10M) | Train/serve skew is the top technical risk; examiners probe it | M | Table in `docs/data_notes.md`, reusable in report. |

### Modelling

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Three baselines: persistence (plus same-hour-yesterday for solar), climatology (hour × month), NWP + physics | Without baselines, "ML skill" is meaningless; baseline 3 is the real benchmark | M | Build first. This is the report's backbone. |
| Feature set per PRD §8 with cyclic calendar and direction encodings (no raw day_of_year) | Appendix A lesson; examiners expect you to cite it | M | Lags, rolling stats, solar geometry, clear-sky index, horizon. |
| LightGBM direct multi-horizon | Strong tabular model, likely deployed | M | Horizon as a feature or 3 horizon buckets. |
| At least one deep multivariate model (LSTM/GRU seq2seq, 5 targets jointly) | "Multivariate" in the title; the deep-model question hangs over the viva | H | Planned by user choice. See Anti-Features for what to cut if time slips. |
| Fixed seeds, saved artifacts, `models/registry.json` | Reproducibility and the selection rule | L | |
| Honest model-selection rule (§9.4): deploy baseline 3 if ML doesn't beat it | Core Value; examiners reward honesty | L | UI must say which model serves each target. |

### Evaluation (ML side)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| MAE, RMSE, nRMSE (energy by capacity; weather by observed range) | Standard point metrics | L | State the normalization explicitly. |
| Skill score vs baseline 3: `1 − RMSE_model / RMSE_baseline3` (also vs persistence) | Standard in forecasting verification; the PRD's headline number | L | Persistence skill is the usual short-horizon reference. |
| Solar metrics on daytime hours only (zenith < 85°) | Night zeros inflate scores; an examiner will check | L | Say so in every solar table caption. |
| Error by horizon (1, 6, 24, 48, 72 h) curves for every model and baseline | Shows where ML helps (short horizon) and where NWP dominates (long) | L | Expect ML to win at 1 to 6 h and converge to baseline 3 later. |
| Breakdown by season (monsoon vs dry) and by target | Wind at Davanagere is monsoon-dominated; the finding must be honest | L | Include capacity factor by season. |
| Leaderboard CSV (model × target × metric) plus plots | PRD deliverable; feeds the report | L | |
| Forecast-vs-actual time-series plots for sample days (clear, cloudy, monsoon) | Examiners want to see the model, not just numbers | L | Include a failure-case day. |
| Predicted-vs-actual scatter plots per target | Standard figure in any forecasting report | L | |
| Test set touched once, at final evaluation | Methodological hygiene | L | State in report. |

### Backend API

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `/api/forecast`, `/forecast/summary`, `/history`, `/metrics`, `/site`, `/health` with typed schemas | Defined in PRD §10 | M | Pydantic schemas double as documentation. FastAPI gives free Swagger at `/docs`, a good live-demo asset. |
| Hourly scheduled refresh, SQLite cache, response under 500 ms from cache | NFR | M | |
| Stale fallback with `stale: true` and age | Public demo must not blank out when Open-Meteo is down | L | |
| Physical-constraint clipping applied server-side | See Physics | L | |

### Frontend

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Dashboard: 5 time-series panels over 72 h with hover synced across panels | The core product view | M | Recharts syncId or Plotly shared hover. |
| Summary cards: next-24 h solar kWh, wind kWh, peak generation hour, combined energy | The plant-operator question: "how much tomorrow, and when's the peak?" | L | |
| "Last updated" time and a visible stale warning | Trust signal; PRD requirement | L | |
| Times shown in IST with UTC internally; units on every axis | Wrong time zone is the most visible bug to an Indian user | L | |
| Model performance page: leaderboard, skill-vs-baseline bar chart, error-by-horizon line chart, validation scatters | PRD page 2; where examiners spend their time | M | |
| About page: site and plant specs, data sources with attribution, methodology diagram, simulated-energy caveat | Required for licensing and for honesty | L | |
| Mobile-responsive layout | Examiners may open it on a phone | M | Stack the panels. Check at 375 px. |
| Attribution (NASA POWER, Open-Meteo, Kaggle) | Licensing | L | Open-Meteo terms require attribution. |
| Visible "simulated energy" label on T1/T5 panels | Pre-empts the biggest examiner objection | L | Tooltip or badge, not buried on the About page only. |

### Deployment / Repro

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Public deployment (backend container + static frontend) | Project decision; examiner access | M | Verify it from a phone and a fresh browser the day before the viva. |
| `make data/train/evaluate/serve` (or CLI) reproducing results from scratch | Reproducibility NFR; "run it for me" is a plausible viva request | M | |
| README with fresh-clone instructions; pinned dependencies; config in YAML | Standard | L | |
| pytest suite passing | PRD §13 | M | |
| Report-ready figures auto-written to `reports/` | Report and slides depend on them | L | Regenerate by command, no hand-made plots. |

---

## Differentiators

Not expected of a student project, but valued. Pick the cheap ones.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Probabilistic evaluation of TFT: PICP at 80% (target ≈ 80%), mean interval width (sharpness), pinball loss, reliability diagram | Calibration claims backed by numbers. Standard probabilistic-verification toolkit (coverage and sharpness together; pinball loss per quantile; reliability diagram of empirical vs nominal coverage). Point metrics like RMSE cannot judge a band. | M | High value per hour. Report coverage by horizon as well. Winkler/interval score is optional. |
| Coverage tracked on the UI (a "were the bands right?" number on the performance page) | Operators trust bands only if they are calibrated | L | A static number from the test set is enough. |
| Skill-score heatmap (target × horizon bucket × season) | One figure replaces many tables; makes the "ML wins short, NWP wins long" story | L | |
| TFT interpretability: variable-selection weights and attention over past time steps, plus LightGBM SHAP or gain importance | Directly answers "explain why" (examiner persona); TFT's selling point (Lim et al.) | M | Put one figure on a slide. The TFT built-in interpretation outputs are cheap if the library exposes them. |
| Physics-consistency diagnostics: forecast-implied T1 vs pvlib(forecast T3, T2, T4) residual | Shows the multivariate coupling is respected, which justifies "multivariate" | M | Optional. Only if the deep model gets time. |
| Ablation: ML with and without Open-Meteo covariates; with and without lags | Shows where the skill comes from (NWP covariates vs persistence) | M | Cheap with LightGBM. A strong viva answer. |
| Ablation: cyclic vs raw day_of_year (reproduce Appendix A) | Closes the loop on the pre-project lesson | L | One LightGBM run. |
| Bootstrap confidence intervals or Diebold-Mariano test on RMSE difference vs baseline 3 | "Is the improvement statistically meaningful?" is a classic examiner question | M | Block bootstrap on the test set is simpler than DM. Flag as optional. |
| Learned bias-correction of NASA vs Open-Meteo (train/serve skew) with before/after metrics | Turns the top risk into a result | M | Only if §7.4 shows a large bias. |
| Capacity-factor and monsoon-vs-dry story for wind, with an honest "weak site" finding | Original, domain-aware insight | L | Mostly a free by-product of seasonal breakdowns. |
| Live "forecast vs what actually happened" archive: store past forecasts, later overlay observed (reanalysis) values | The operator trust feature. Operator dashboards typically show forecast and actuals on the same axis. | M | Needs the SQLite run_time/target_time schema (already planned). Observed values come from Open-Meteo ERA5/analysis, with a lag. Weather targets only is acceptable. |
| Forecast-run history ("how did the forecast made yesterday change?") | Shows forecast revisions | M | Defer unless the archive above is built. |
| Model-used-per-target badge ("T4: LightGBM, skill +12% vs NWP") with link to performance page | Makes the selection rule visible live | L | Cheap, high examiner value. |
| Methodology diagram (data → physics → features → models → API) on the About page and slides | Walkthrough aid | L | Draw once, reuse in the report. |
| Peak-hour highlight and a simple "best hour" band on the dashboard | Operator-centric | L | Uses `summary` endpoint. |
| CSV download of forecast | Operators export | L | One endpoint. Fine if there is spare time. |
| Dated metrics snapshot / run provenance (git commit, data-through date, model version shown in the footer) | Reproducibility signal | L | Write a small `meta.json` at train time. |

---

## Anti-Features

Do not build these. Several are tempting and would burn the 15-day budget.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Location picker / multi-site | Out of scope. Needs per-site data pulls and retraining. | Keep code config-driven (`config/site.yaml`) and state it as future work. |
| User accounts, auth, saved views, alerts / email / SMS notifications | No requirement; adds security and ops surface | Public read-only demo. |
| Real-time SCADA ingestion | No physical plant | Say it explicitly in the limitations section. |
| Financial / dispatch / price / revenue modelling | Outside the forecasting question | Mention as downstream use. |
| Using Kaggle data as ML training targets | Different sites and climates; destroys the clean validation story | Use for validation and calibration only. |
| Hyperparameter-search mega-sweeps (Optuna 500 trials per model) | Eats days for small gains; harms the schedule | Small fixed grid or about 30 trials for LightGBM. Early stopping for neural nets. Document the budget. |
| Many extra model families (XGBoost, N-BEATS, Informer, ensembles of everything) | Dilutes the story; the ladder is already 3 models | Keep LightGBM, LSTM/GRU, TFT. A simple LightGBM + deep blend only if time is left over. |
| Per-target bespoke deep architectures | Time sink | One joint seq2seq, with output-head masking if needed. |
| Training deep models on the live server / online retraining | Complexity and fragility | Retrain offline, ship artifacts. |
| Re-labelling or "improving" the test set after seeing results | Invalidates evaluation | Freeze the test split, evaluate once. |
| Smoothing or post-hoc tuning of forecasts to look better on the test set | Hidden leakage | Tune on validation only. |
| Fancy frontend: 3D, maps, animations, dark-mode theming, i18n, PWA/offline | Low marginal value for the viva | One clean theme; spend the time on figures. |
| Websocket / live streaming updates | Hourly refresh is enough | Poll or refetch every few minutes. |
| Interactive model-comparison playground (user picks model, re-runs inference) | Heavy, and lets the examiner break it | Static leaderboard plus the model-used badge. |
| Weather-radar / satellite imagery cloud-motion nowcasting | Different problem (intra-hour), needs imagery pipelines | Out of scope; mention as future work. |
| Exposing raw `day_of_year`, wind direction in degrees, or unconstrained outputs | Known pitfalls (Appendix A) | Cyclic encodings and clipping layer. |
| Reporting solar scores over all 24 h | Inflates results | Daytime-only (zenith < 85°). |
| Claiming measured generation | The energy targets are simulated | Label "simulated" in the UI, report and slides. |
| Generic AI-sounding methodology prose with no figures | Examiners notice | Every claim paired with a figure or table from `reports/`. |

---

## Feature Dependencies

```
Fetchers + cache
  -> Timestamp alignment check -> Clean hourly UTC table
        -> NASA vs ERA5 consistency check (-> optional bias correction)
        -> Physics sim (solar, wind) -> Kaggle validation (GATE)
              -> Simulated T1/T5 targets
                    -> Feature build + chronological splits + leakage test
                          -> Baselines 1-3 (baseline 3 needs Open-Meteo forecasts + physics chain)
                                -> LightGBM -> LSTM/GRU -> TFT
                                      -> Evaluation (metrics, skill, horizon, season, daytime)
                                            -> Leaderboard + registry.json (selection rule)
                                                  -> Backend /metrics, serving model choice
                                                  -> Report figures / slides

TFT quantiles -> PICP / pinball / reliability diagram -> UI bands + coverage number
TFT / LightGBM -> interpretability figures
Physical-constraint layer -> used by baselines, models, API (build once, reuse)
SQLite forecast archive (run_time, target_time) -> stale fallback
                                                -> optional forecast-vs-actual overlay
Open-Meteo live fetch + features + registry.json -> /api/forecast -> Dashboard
/api/metrics + reports figures -> Performance page
Deployment depends on: backend container, model artifacts (TFT weights size), frontend env var for API URL
```

Critical notes:
- Baseline 3 gates everything: the historical-forecast data window (Open-Meteo) also determines the length of the usable ML evaluation period. Check the earliest available date in the data phase.
- Physics validation is an acceptance gate before any ML.
- The physical-constraint layer should exist before baselines, so every leaderboard row obeys it.
- Frontend can start in parallel with models once `/api/forecast` schemas are fixed (mock with baseline 3).

---

## MVP Recommendation

Ordered to protect the Core Value (results and report) if time slips.

**Must land (results-first):**
1. Fetch, align, clean (with `data_notes.md`)
2. Physics sim and Kaggle validation (the gate)
3. Features, splits, leakage test
4. Three baselines and the leaderboard skeleton
5. LightGBM, with skill-by-horizon/season and daytime-only solar
6. Backend with baseline 3 / LightGBM serving, stale fallback
7. Dashboard + performance + about, honest labelling, public deploy

**Then (ladder, in order of value for the viva):**
8. TFT with P10/P50/P90, PICP and pinball, one interpretability figure
9. LSTM/GRU seq2seq (the multivariate deep model). If time is critically short, run a minimal version with one config and no tuning; report it honestly.
10. Cheap differentiators: ablations (covariates, cyclic encoding), skill heatmap, model-used badge, provenance footer

**Defer unless there is spare time:** bootstrap/DM significance, bias-correction model, forecast-vs-actual archive overlay, CSV download, physics-consistency diagnostics.

**Cut-line advice:** If at day 10 the deep models are not training stably, deploy the best honest option per §9.4, and put the failure analysis in the report. That is a legitimate finding, not a gap.

---

## Examiner-Facing Checklist (what a good viva answer needs on a slide)

| Likely question | Feature that answers it |
|-----------------|------------------------|
| "Your targets are simulated. Why trust them?" | Kaggle validation scatters and nRMSE, UI caveat |
| "Does ML beat the weather forecast?" | Skill vs baseline 3 by target, horizon, season |
| "How do you know there's no leakage?" | Leakage test, chronological splits, test touched once |
| "Why do solar numbers look so good?" | Daytime-only metrics, night zeros excluded |
| "Why does wind perform worse?" | Seasonal breakdown, capacity factor at Davanagere |
| "Are your uncertainty bands right?" | PICP ≈ 80%, reliability diagram, width |
| "Why does the model predict that?" | TFT variable importance, LightGBM importance |
| "What if the API is down?" | Stale flag and cached fallback |
| "Can I reproduce it?" | `make` targets, seeds, README, pinned deps |
| "NASA and Open-Meteo disagree. What then?" | §7.4 consistency table and any bias correction |

---

## Sources

- Project specification: `docs/PRD.md` (§3, §7, §8, §9, §11, §13), `.planning/PROJECT.md` (HIGH for scope; the PRD is AI-drafted, so *(verify)* tags apply)
- Probabilistic forecast evaluation (pinball loss, PICP/MPIW, reliability diagrams, PIT, Winkler score): [Smooth Pinball Neural Network for Probabilistic Forecasting of Wind Power](https://arxiv.org/pdf/1710.01720), [Evaluating Probabilistic Forecasts (k-diagram docs)](https://k-diagram.readthedocs.io/en/v1.2.2/user_guide/probabilistic.html) (MEDIUM; no solar/wind-specific best-practice standard found)
- Operator dashboard patterns (forecast vs actual on the same axis, curtailment caveat, percentile bands, uncertainty classes): [ERCOT combined wind and solar dashboard](https://ercot.com/gridmktinfo/dashboards/combinedwindandsolar), [PJM uncertainty quantification review (2025)](https://www.pjm.com/-/media/DotCom/committees-groups/task-forces/rcstf/2025/20250917/20250917-item-02---uncertainty-quantification-review.pdf), [Amperon probabilistic forecasting tool](https://pv-magazine-usa.com/2026/04/21/amperon-launches-probabilistic-forecasting-tool-for-solar-and-wind-assets/) (MEDIUM; vendor and ISO examples, not student-project norms)
- TFT interpretability: Lim et al., IJF 2021 (cited in PRD §18; not re-fetched, MEDIUM)
- Skill-score, nRMSE, and daytime-only solar conventions are community practice from forecasting-verification literature, taken from training knowledge (LOW to MEDIUM; the choices here follow the PRD, which is the governing spec)

## Gaps

- Did not verify TFT library (darts vs pytorch-forecasting) support for built-in variable-importance and attention outputs. Check in the modelling phase.
- Did not verify the Open-Meteo historical-forecast earliest date, which decides the length of the baseline 3 evaluation window and therefore the credibility of skill scores.
- Viva norms at the user's institution (guide expectations, report format) are unknown. Ask whether a statistical significance test or a deployed deep model is expected (PRD §17 open questions 1 and 3).
