# Domain Pitfalls

**Domain:** Multivariate solar + wind 72 h forecasting (NASA POWER + Open-Meteo, pvlib, LightGBM/LSTM/TFT, FastAPI + React, free-tier public deploy), solo 15-day build
**Researched:** 2026-11-01
**Overall confidence:** MEDIUM. API semantics were verified against official Open-Meteo and NASA pages. Library and hosting behaviour partly rests on training knowledge and is tagged.

Phase names follow PRD section 14.2: P0 Setup, P1 Data fetch, P2 Alignment, P3 Physics, P4 Validation, P5 Dataset, P6 Baselines, P7 Models, P8 Backend, P9 Frontend, P10 Polish.

Confidence tags: [V] verified in official docs this session, [M] multiple or secondary sources, [K] training knowledge, verify before relying on it.

---

## Critical Pitfalls

Mistakes that invalidate results, force a rewrite, or break the live site.

### C1. The "Historical Forecast API" is a stitched series of short-lead forecasts, not 1-72 h forecasts
**What goes wrong:** The PRD (section 5.2, section 16) trains the known-future covariates on `historical-forecast-api`. Open-Meteo documents that API as a concatenation of the first hours of consecutive model runs (hour 0 is initialised from measurements). So the training covariates look like near-analysis quality. At serving time the same covariates are day-1 to day-3 forecasts with much larger errors. [V: openmeteo.substack "Introducing the Historical Forecast API"]
**Why it happens:** The name suggests "archived forecasts at the lead time you will use."
**Consequences:**
- The model over-trusts the covariates and live accuracy collapses.
- Baseline 3 (NWP + physics), if scored on stitched data, is also unrealistically good, or unrealistically weak if you compare unlike things. Either way the skill scores are wrong.
- This is the central train/serve skew in the project.
**Prevention:**
- For anything scored as "forecast at lead h", use the **Previous Runs API** (`*_previous_day1..7`, fixed lead times) or the **Single Runs API** (`run=`). Previous Runs is archived mostly from **January 2024** [V]. Single Runs coverage is reportedly Sep 2025, with ECMWF from March 2024 [LOW, secondary source].
- Probe real coverage for Davanagere in P1: first valid date per variable and per model, and the lead times available. Log it in `docs/data_notes.md`.
- Then design splits around actual coverage. Realistically that is val = 2024, test = 2025 for the NWP-covariate model, while weather-only models can use NASA 2001+.
- Never build baseline 3 or covariates from ERA5 and call it a "forecast". ERA5 is a reanalysis, effectively a perfect forecast.
**Detection:** The ML model has strong skill at 48-72 h that decays at serve time. Covariate RMSE in training is far below the published day-3 forecast error. Baseline 3 skill is implausibly near 0 error on 72 h.
**Phase:** P1 (probe coverage), P2 (document), P5 (split design), P6 (baseline 3 built from the same lead-time source).

### C2. Lag features come from NASA in training but NASA is not available live
**What goes wrong:** Lags (t-1 ... t-168) and rolling stats are trained on NASA POWER values. At serving, "recent observed" has to come from somewhere. NASA hourly lags real time by days, and it is a different product (CERES/MERRA-2) from Open-Meteo's analysis blend. Simulated T1/T5 lags must also be recomputed from whichever source is live. [K; the NRT lag should be checked in P1]
**Consequences:** The lag distribution differs between train and serve. Persistence-like features become systematically biased. The live site gives odd forecasts that no offline metric predicted.
**Prevention:**
- Decide the live "history" source in P1: Open-Meteo `past_days=7` (analysis hours of the forecast API) or ERA5T.
- Build training lags from the closest equivalent source (ERA5 or stitched historical-forecast). Use NASA for long-history pre-training or climatology only.
- Run the section 7.4 NASA vs Open-Meteo check on **lag-feature level**, not just raw variables.
- Add a P8 test that replays a past date through the exact serving code path with only data that would have existed then, and compares to the offline prediction.
**Detection:** Offline test RMSE is much lower than live-replay RMSE.
**Phase:** P1/P2 (decision), P5 (feature source), P8 (replay test).

### C3. Timestamp labelling offsets (NASA start-of-hour vs Open-Meteo end-of-hour)
**What goes wrong:**
- NASA POWER's FAQ says the hourly stamp marks the **start** of the hour [M: NASA POWER FAQ via search; pvlib's `get_nasa_power` also treats the index as the left edge].
- Open-Meteo radiation is the **mean over the preceding hour**, so its label is the **end** of the interval. Instantaneous variables (temperature, RH, wind, pressure, cloud) are instants at the label. [V]
- Joining on identical timestamps shifts radiation by 1 h against NASA. Daily correlation stays around 0.95, so the bug hides. Sunrise and sunset timing and the PV diurnal peak are what move.
- Within NASA, MERRA-2 variables (T2M, RH2M, WS10M) may be hourly averages while CERES-derived irradiance has its own convention. Per-variable offsets are not documented on the hourly API page. [V: page does not say; K: MERRA-2 tavg1 is centred at :30]
**Prevention:**
- Do not rely on cross-correlation of hourly series alone, which cannot resolve 30 min. Use sunrise onset (first non-zero GHI hour) and the centroid of the diurnal curve against pvlib clear-sky computed at the **interval midpoint**.
- Normalise everything to one convention internally, for example "interval start, UTC". Shift Open-Meteo radiation by -1 h once, in one function, with a test.
- Check per variable family (irradiance, T2M/RH2M, wind) against ERA5 via Open-Meteo, since ERA5 instants are well defined. Record offsets in `docs/data_notes.md`.
- For pvlib, compute solar position at the **midpoint** of the averaging interval (start + 30 min), not at the label.
**Detection:** Solar-sim vs Kaggle or vs ERA5 residuals show a systematic morning or evening sign flip. Open-Meteo GHI is non-zero in the hour before NASA's first non-zero hour.
**Phase:** P2 (verify), P3 (midpoint zenith), P5 (feature join).

### C4. Leakage in lag, rolling and multi-horizon features
**What goes wrong:**
- Direct multi-horizon rows have a forecast origin `t0` and a target `t0+h`. Computing `lag_k` or rolling stats relative to the **target** time, or `shift(k)` on the target-aligned frame, leaks any information after `t0` whenever `h > k`.
- `rolling(..., center=True)`, or a rolling window that includes the current row, leaks.
- Scalers or normalisers fit on the full series leak.
- Samples near split boundaries leak because their 72 h target window extends into the next split.
- Linear `interpolate()` uses future values across a gap.
- Peeking at the test leaderboard to tune hyperparameters leaks indirectly.
**Prevention:**
- Build features per origin `t0` only. Lags and rolls are functions of data at or before `t0`. Known-future covariates are the only items indexed at `t0+h`.
- Purge or embargo: drop training origins whose `t0+72h` falls inside val (and val into test). Add a 168 h embargo for lag windows.
- Fit scalers on train only, and store them in the artifact.
- The PRD section 13 test is not enough if it only checks column names. Use a **truncation test**: recompute the feature row for `t0` from data cut at `t0` and assert equality with the production feature row. Add a **perturbation test**: change data after `t0` and assert features are unchanged.
- Freeze the test set until the final run. Tune only on val.
**Detection:** R2 above 0.99 on solar, skill that does not decay with horizon, or val score better than the 1 h persistence baseline at 72 h.
**Phase:** P5 (tests), P7 (don't tune on test).

### C5. Night zeros, capacity normalisation and weak wind site inflate metrics
**What goes wrong:**
- Around half of hourly solar values are zero, so all-hours RMSE or R2 looks great.
- nRMSE normalised by 1 MW or 3.6 MW capacity is tiny when output sits near zero. Davanagere wind will be near zero for most of Oct-May [PRD section 4.3].
- Persistence at 24-72 h for solar is a strawman unless it is "same hour yesterday" or clear-sky-index persistence.
- MAPE explodes near zero.
**Prevention:**
- Score solar on daytime only (zenith at interval midpoint < 85 degrees), and keep that mask identical across all models and baselines.
- Report capacity factor, MAE relative to mean daytime output, and skill vs baseline 3. Do not rely on capacity-normalised nRMSE alone.
- For wind, break out by season (Jun-Sep vs rest) and report the fraction of hours below cut-in.
- Define nRMSE for weather targets once (range from train set) and reuse it.
- Evaluate all models on the **same index intersection**. TFT/LSTM drop the first 168 h and gaps, so the leaderboard rows must share samples.
- Never use MAPE.
**Detection:** Solar R2 is far higher than the GHI R2. The deep model "wins" only because it is scored on a different subset.
**Phase:** P6 (metrics module), P7 (leaderboard).

### C6. `-999` sentinel silently becomes valid data
**What goes wrong:** NASA returns `-999` for missing. If it is not converted to NaN **first**, then clipping to physical range turns GHI to 0 (looks like night or heavy cloud), RH -999 clips to 0, rolling means are poisoned, and interpolation fills across a "real" low. The latest days or months of the newest year are typically all `-999`. [K for fill-value location; the hourly API page does not state it, so read `header.fill_value` in the response]
**Prevention:**
- Replace the sentinel at the fetch boundary, using the response header value, before any other step. Assert `df.min() > -900`.
- Report % missing per column and per year (the P1 deliverable).
- Interpolate only short gaps (at most 3 h). Do not interpolate GHI across sunrise or sunset. Interpolate clear-sky index instead, then rebuild GHI.
- Drop the incomplete final year from training and test. Set the end year deliberately (last complete year is 2025 as of today).
**Detection:** Spikes of exact zeros in RH. GHI zero at noon in dry season.
**Phase:** P1/P2.

### C7. PV chain mistakes: azimuth convention, inverter clipping and irradiance consistency
**What goes wrong:**
- **Azimuth:** pvlib `surface_azimuth` is 180 = south, with 0 = north. Open-Meteo GTI `azimuth` is 0 = south, -90 east, 90 west. [V for Open-Meteo] Passing 180 to Open-Meteo gives a north-facing panel. Passing 0 to pvlib gives a north-facing panel. Both look "plausible", just 20-30% low.
- **Open-Meteo GTI is not an input to the physics chain.** Use it only as a sanity cross-check, since the transposition model differs (expect a few % difference).
- **Inverter clip:** `pvlib.inverter.pvwatts_ac(pdc, pdc0, eta_inv_nom)` treats `pdc0` as the inverter's **DC input rating**, and AC is capped at roughly `pdc0 * eta_inv_nom`. [K; confirm in docs in P3] With PRD values (1000 kWp, DC/AC 1.2, AC limit 833 kW, eta 0.96), passing `pdc0=833` gives a cap near 800 kW, which contradicts the section 6 constraint "T1 <= 833". Decide the AC limit definition once and test it with a clear-sky day that clips.
- **Perez inputs:** needs `dni_extra` and `airmass`. Missing them gives NaN or errors.
- **Component consistency:** NASA GHI, DNI and DHI may not satisfy GHI = DNI*cos(z) + DHI. Feeding inconsistent triples overstates POA. Check closure. If poor, use GHI alone with a decomposition model (Erbs or DIRINT) and compare. [K]
- **Faiman wind input:** 10 m wind cools modules too much. It is acceptable, but state it.
- **Loss % tuned on 34 days** of one plant masks soiling and module-spec mismatch. The tuned number is a calibration constant, not a physical truth.
**Prevention:** Unit tests: south-facing vs north-facing clear-sky POA ratio; clipping at the cap; night = 0; closure check on NASA components. Use a single config key `azimuth_pvlib` and derive the Open-Meteo value with a tested function `to_openmeteo_azimuth(az) = az - 180` (wrapped to [-180, 180]).
**Detection:** PV peak too low and shifted. Clear-sky simulated output differs from Open-Meteo GTI * area by more than about 10%.
**Phase:** P3 (tests), P4 (calibration).

### C8. Free-tier container asleep means no scheduler, no fresh forecast, and an empty cache
**What goes wrong:**
- Render free web services spin down after 15 min idle, with a cold start of roughly 30-60 s, 512 MB RAM and 0.1 CPU [M: Render community, aggregator pages; confirm at render.com/docs/free].
- An in-process APScheduler job never runs while the process is asleep.
- The filesystem is ephemeral, so the SQLite file is wiped on each restart or redeploy. The "stale fallback" then has nothing to serve, so the first visitor sees an error exactly when the API is also slow.
- Multiple Uvicorn workers each start their own scheduler.
**Prevention:**
- Make the API **lazy-refresh**: on request, if the cache is older than 60 min, refresh (with a lock) or serve stale and refresh in the background.
- Add an external trigger (GitHub Actions cron or cron-job.org hitting a token-protected `/api/refresh`), as a bonus not as the only mechanism.
- Seed the DB at container start from a committed `seed_forecast.json` (a recent real run) so a cold start always has a stale answer.
- One worker only. Guard the job with `max_instances=1` and `coalesce=True`.
- Warm the service 5-10 minutes before the viva, and add a frontend "waking server" state with a retry (about 60 s), not a hard error.
**Detection:** `/api/health` shows `last_refresh` older than 1 h. The first request after idle takes more than 30 s.
**Phase:** P8, P10.

### C9. Deploying PyTorch to a 512 MB free host
**What goes wrong:**
- `pip install torch` pulls CUDA wheels (multi-GB images). A CPU wheel is far smaller, but importing torch plus pandas, pvlib, lightgbm and FastAPI can still approach or exceed 512 MB RSS. [K]
- Build time-outs and OOM kills show up as a restart loop, not a clear error.
- TFT weights saved with a CUDA device mapping fail to load on CPU.
**Prevention (opinionated):**
- **Keep torch out of the serving image.** Per PRD section 9.4 the deployed model is whichever wins. LightGBM is likely to win on at least wind and humidity. For a torch model, export to ONNX and serve with `onnxruntime` (small), or run inference in a scheduled GitHub Action that writes forecast JSON consumed by the API.
- If torch must be served: `--index-url https://download.pytorch.org/whl/cpu`, `torch.load(..., map_location="cpu")`, `model.eval()`, `torch.set_num_threads(1)`, and measure RSS in P8 before choosing the host.
- Consider a host with more memory for the Docker image, such as Hugging Face Spaces (Docker, large free CPU RAM; sleeps after long idle) [K, LOW confidence, verify]. Decide in P8, not on deploy day.
- Do not ship training dependencies (`darts`, `pytorch-forecasting`, `lightning`) in the serving requirements. Keep `requirements-serve.txt` separate from `requirements-train.txt`.
**Detection:** Image over about 1 GB. RSS over 400 MB at idle. Deploy logs show "Killed" or exit code 137.
**Phase:** P8 (measure), P10 (deploy).

### C10. Schedule: 15 days, 11 phases, three model families, public deploy
**What goes wrong:** Today is 2026-11-01 and the viva is about 2026-11-16. The ladder (LightGBM, LSTM, TFT) plus physics validation plus site plus report cannot all be built serially. Typical failure: TFT consumes the final five days and nothing deploys. Kaggle files are missing on day 1 and P4 stalls. The report figures are made last-minute.
**Prevention:**
- Kaggle login and download on **day 1** (the manual step blocks P4).
- Build a **walking skeleton by about day 6**: FastAPI + SQLite + baseline 3 + a React page deployed. LightGBM drops in later through the registry.
- Run contract-first: define `schemas.py` and a mock JSON in P0/P1, so P9 front-end work can proceed while the GPU trains in the background.
- Time-box TFT with a hard cut at about day 11. If not converged, report it as "attempted, did not beat baseline 3" with the training curves. That is a legitimate result under PRD section 9.4.
- Produce report figures as part of each phase's exit (P4 scatter plots, P6/P7 leaderboards), not in P10.
- Protect, in order: physics validation and baselines, LightGBM, the leaderboard, then the site, LSTM and TFT.
**Detection:** Day 8 with no end-to-end deployed baseline. TFT still not training stably by day 10.
**Phase:** all, especially P0 and P7.

---

## Moderate Pitfalls

### M1. UTC / IST bugs
**What goes wrong:**
- NASA POWER defaults to **LST**, not UTC. Omitting `time-standard=UTC` shifts everything by the longitude-based offset [V]. The PRD passes it, so assert it in the fetcher.
- IST is UTC+5:30, so half-hour logic breaks assumptions. "Tomorrow" in the UI is an IST calendar day, which is not a UTC day. IST 00:00-05:30 falls in the previous UTC date.
- JS `new Date("2026-11-01T06:00:00")` without a trailing `Z` is parsed as local time.
- Naive vs tz-aware pandas indexes: pvlib raises or silently localises.
**Prevention:** Keep every DataFrame index tz-aware UTC and assert it at module boundaries. The API emits ISO-8601 with `Z`. The frontend formats with `Intl.DateTimeFormat('en-IN', {timeZone: 'Asia/Kolkata'})`. Compute "tomorrow" totals server-side using explicit IST day bounds in UTC. Add a unit test for the summary endpoint at 18:30 UTC.
**Detection:** Summary card totals differ from the sum of visible bars. The solar bell peaks at about 06:00 IST.
**Phase:** P1, P8, P9.

### M2. Open-Meteo wind height and unit mismatches
**What goes wrong:** The forecast API offers 10/80/120/180 m. The archive (ERA5) offers 100 m rather than 80/120 [PRD note; verify]. NASA offers 10/50 m. Mixing sources gives different hub-height methods in training vs serving (PRD section 16 risk). Open-Meteo defaults to km/h unless `wind_speed_unit=ms`. Surface pressure is hPa in Open-Meteo and kPa in NASA (`PS`), so air density is wrong by 10x if mixed. Gridded wind is smoothed relative to turbine-point wind.
**Prevention:** One unit-normalisation function with tests. Pass `wind_speed_unit=ms` and `timezone=GMT` explicitly. Use one hub-height method on all sources (log-law/power-law from 10 m + a higher level), or train a per-source correction. Document the exact heights per source in `data_notes.md`.
**Phase:** P1, P3.

### M3. Power curve, air density and Jensen's inequality
**What goes wrong:**
- The Kaggle `Theoretical_Power_Curve (KWh)` column is a manufacturer curve against nacelle-measured wind at a Turkish site, labelled KWh but actually kW. Binning it by median is a deterministic lookup, so the "calibration" mostly confirms itself.
- Applying a point-turbine curve to hourly grid-cell-mean wind underestimates mean power (the curve is convex below rated). The gridded wind variance is too low. Expect negative bias at mid speeds.
- Air-density scaling `(rho/1.225)^(1/3)` is valid for the cubic region. Applying it above rated speed or at cut-in is wrong, and applying it twice (once when building the curve, again at use) is a classic double-correction.
- Availability loss of 3.5% from Kaggle is a Turkish-site property, not Davanagere's.
- `alpha = ln(WS50M/WS10M)/ln(5)` is unstable at low wind and at night; clipping to [0.05, 0.40] is a patch, not physics.
**Prevention:** Unit tests for interpolation at bin edges, cut-in/out, rated plateau, and density scaling applied once. Report the simulated bias vs Kaggle in the bias-vs-speed plot, not only nRMSE. State that T5 is a "turbine-equivalent" simulation. Keep the density correction in the physics layer, and log mean rho (about 1.15 at 600 m).
**Phase:** P3, P4.

### M4. Kaggle dataset quirks
**What goes wrong:**
- **Solar Plant 1:** `DC_POWER` is about 10x `AC_POWER` (the PRD notes this). The generation file has `DATE_TIME` as day-first (`dd-mm-yyyy HH:MM`) while the weather sensor file is ISO. Default pandas parsing merges to almost nothing or swaps day and month. [K, well-known; verify on the file]
- Summing `AC_POWER` over `SOURCE_KEY` per timestamp understates output when inverters are missing in some intervals. Require all inverters present, or normalise by count.
- `IRRADIATION` is in kW/m2 (max about 1.2), not W/m2. The sensor type (GHI vs plane-of-array) is not stated. Check against pvlib clear-sky at the site to decide.
- 34 days (mid-May to mid-June 2020) is one narrow slice of one season and not the monsoon peak.
- **Wind T1:** `Date/Time` is `dd mm yyyy HH:MM`, 10-min, local Turkish time. 3.9% of timestamps are missing; resampling with `ffill` fabricates data. 57 negative-power rows.
- Validation fed with **measured on-site irradiance** validates the conversion chain only, not NASA input quality. Say so in the report.
**Prevention:** An explicit schema-and-units check script (`validate_kaggle.py` head) that asserts units, parse formats and inverter count, and prints distributions. Use `dayfirst=True`/explicit `format=`. Do not resample-fill. Put these assumptions into the report.
**Phase:** P4.

### M5. NASA spatial resolution and product mix
**What goes wrong:** CERES-derived irradiance is about 1 degree and MERRA-2 meteorology about 0.5 x 0.625 degrees (the PRD notes 0.5 degree). One cell covers Davanagere and surroundings, so the nominal "site point" is a regional average with no terrain detail. NASA all-sky GHI can differ from ERA5 by a bias that varies with season (monsoon cloud). [K]
**Prevention:** Run the section 7.4 comparison per month. Prefer a bias-correction feature or model rather than assuming NASA is truth. Write the "targets are reanalysis/satellite products" caveat next to the "simulated energy" caveat.
**Phase:** P2.

### M6. LSTM / TFT training pitfalls on Windows with a local GPU
**What goes wrong:**
- On Windows, `pip install torch` from PyPI typically installs a **CPU-only** build. Training runs silently on CPU. [K] Install from the CUDA index URL and assert `torch.cuda.is_available()` at start.
- DataLoader `num_workers > 0` uses spawn on Windows. Without `if __name__ == "__main__":` you get recursive process spawns or hangs. Start with `num_workers=0`.
- `pytorch-forecasting` imports `lightning.pytorch` in current docs [V: docs search]. Mixing `pytorch_lightning` and `lightning` versions yields obscure errors. Pin versions together in a lock file in P0 and run a 1-epoch smoke test immediately.
- Multi-target TFT in pytorch-forecasting needs `MultiNormalizer` + `MultiLoss`. In darts it requires a consistent covariate layout (past vs future). Both are fiddly; the five-target joint setup is where time disappears. [K]
- Mixed precision with attention can produce NaNs. Use gradient clipping (about 0.1) and check the first batches.
- Solar zeros plus a log or softplus normaliser cause NaN or infinite values. Use a plain standard scaler per target, fit on train.
- Quantile outputs can cross (P10 > P50), and quantile coverage is rarely 80%. Sort quantiles, clip to physical bounds, and report empirical coverage on val; optionally widen with a conformal adjustment.
- Roughly 200k hourly origins x 168-step encoders is large. Subsample origins (stride 3-6 h) to fit time and VRAM. Windows laptops thermal-throttle and sleep; disable sleep and checkpoint every epoch.
- Seeds: set Python, NumPy, torch and CUDA seeds; accept small run-to-run variance and report it.
**Prevention:** A single training entrypoint with `--smoke` (1 epoch, 1% of data) used before any long run. Early stopping on val. Log curves to `reports/`. Cap LSTM at about 1 day and TFT at about 1.5 days of wall time.
**Phase:** P0 (environment pin), P7.

### M7. CORS and frontend-to-backend wiring
**What goes wrong:**
- `allow_origins=["*"]` together with `allow_credentials=True` is invalid, and the browser rejects it. Origins must match exactly, with no trailing slash.
- Vercel and Netlify preview URLs change per deploy, so a fixed allow-list breaks.
- Unhandled 500s and gateway time-outs from a cold-starting backend carry no CORS headers, so the browser reports a "CORS error" and hides the real failure.
- `VITE_API_URL` is baked in at **build** time. Setting it only in the host UI after the build does nothing.
- HTTPS frontend to HTTP backend is blocked as mixed content. A 307 redirect from a missing trailing slash behind a proxy can downgrade to `http://`.
**Prevention:** Prefer a same-origin rewrite (`/api/*` proxied to the backend via Vercel/Netlify rewrites), so CORS is not needed in production. Keep `CORSMiddleware` with an explicit origin list (plus `allow_origin_regex` for previews) for local dev. Run Uvicorn with `--proxy-headers`. Define routes without trailing-slash ambiguity. The frontend shows "backend waking up" on network errors.
**Detection:** Console shows CORS errors while `curl` works.
**Phase:** P8, P9, P10.

### M8. Multi-horizon LightGBM data volume and horizon framing
**What goes wrong:** Horizon-as-feature stacks 72 rows per origin x 5 targets x about 200k origins, which is 70M+ rows and exhausts RAM. Training one model per target with shared horizon feature lets near-term and far-term errors interact. Evaluating only on average RMSE hides that skill vanishes at 1-6 h to persistence.
**Prevention:** Use horizon buckets (1-6, 7-24, 25-72 h, as the PRD allows) and subsample origins (stride 3 h). Report RMSE by horizon (1, 6, 24, 48, 72 h). Include a persistence-blend feature at short horizons.
**Phase:** P5, P7.

### M9. Open-Meteo availability, rate limits and terms
**What goes wrong:** The free tier allows 600 calls/min, 5,000/hour, 10,000/day, is non-commercial, comes with no uptime guarantee, and requires CC BY 4.0 attribution [V: open-meteo.com/en/pricing]. Shared PaaS egress IPs can be rate-limited by other tenants. Bulk historical-forecast downloads by long date ranges can time-out or be refused.
**Prevention:** Chunk by quarter or year, cache each response, and back off on 429/5xx. Fetch server-side with one call per hour (about 24 a day is trivial). Show attribution on the About page and footer. Never loop live API calls per page view.
**Phase:** P1, P8.

### M10. Interpolation and cleaning artefacts
**What goes wrong:** Linearly interpolating GHI over a 3-hour gap crossing dawn invents energy. Clipping silently hides data errors. Forcing night GHI = 0 using the zenith at the label time kills real sunrise or sunset-hour irradiance for interval-mean data.
**Prevention:** Use the midpoint zenith for the night mask. Log counts of every clipped or interpolated value per column (already in PRD section 7.2). Fail loudly if more than a threshold fraction is touched.
**Phase:** P2.

---

## Minor Pitfalls

### m1. Raw `day_of_year` or hour integers
**What goes wrong:** The pre-project test showed LightGBM at 17.5% vs 14.0% nRMSE with a raw `day_of_year`.
**Prevention:** Use sin/cos only. Add a P5 test that bans raw calendar integers from the feature list.

### m2. Wind direction as raw degrees
**Prevention:** sin/cos only. Never average angles linearly in rolling features; roll the sin and cos components.

### m3. Clear-sky mismatch between train and serve
**What goes wrong:** NASA `CLRSKY_SFC_SW_DWN` is not available live, and pvlib Ineichen with default turbidity gives clear-sky index above 1 in dry months.
**Prevention:** Compute clear-sky from pvlib in both train and serve. Clip clear-sky index to [0, 1.5]. Do not use NASA `ALLSKY_KT` as a feature unless it is also computable live.

### m4. Registry / model-per-target deployment complexity
**What goes wrong:** Deploying a different model per target multiplies artifacts and dependencies.
**Prevention:** Registry maps target to `{model, path, feature_set}`. A single `predict(target, features)` interface. Unit test that each registry entry loads on CPU in the serving image.

### m5. Stale flag logic
**What goes wrong:** A stale flag based on server wall-clock only misses the case where the cache is fresh but the upstream returned old data.
**Prevention:** Compute age from the `run_time` of the forecast issuance, and expose both `last_refresh` and `forecast_issued_at`.

### m6. Reproducibility drift
**What goes wrong:** Cached raw responses are not versioned, so `make data` yields different data later (NASA reprocesses recent data, and Open-Meteo model versions change).
**Prevention:** Store retrieval date and request URL with each cache file. Record the dataset hash in the leaderboard.

### m7. Report credibility traps
**What goes wrong:** The viva challenges the simulated targets (circular), and "ML beats baseline" claims are made on a different subset than the baseline.
**Prevention:** State the caveat, show Kaggle validation, give skill on a common index with confidence intervals (block bootstrap by week), and keep the "no ML win" outcome as an honest finding.

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|---------------|------------|
| P0 Setup | CPU-only torch on Windows; lightning/pytorch-forecasting version clashes; Kaggle files not downloaded | Pin CUDA torch + lightning together, run a smoke test; download Kaggle data on day 1; split serve/train requirements |
| P1 Data fetch | `-999` handling (C6); LST default (M1); Historical-Forecast coverage and meaning (C1); NRT lag for lags source (C2) | Convert sentinel at the boundary; assert `time-standard=UTC`; probe and log coverage; decide live history source |
| P2 Alignment | Start vs end of hour (C3); per-variable offsets; NASA vs ERA5 bias (M5); night-mask (M10) | Sunrise-onset + midpoint-zenith test; per-variable offsets in `data_notes.md`; per-month bias table |
| P3 Physics | Azimuth convention and inverter cap (C7); wind heights/units and density (M2, M3) | Tested conversion helpers; clear-sky clipping day test; density applied once |
| P4 Validation | Kaggle parsing/units (M4); 34-day calibration; validation does not test NASA input | Schema check script; document limits; scatter + bias-vs-speed plots |
| P5 Dataset | Leakage (C4); split design vs covariate coverage (C1); lag source (C2); raw calendar ints (m1) | Truncation + perturbation tests; embargo; splits designed around actual coverage |
| P6 Baselines | Strawman persistence; baseline 3 built from wrong forecast type (C1); metrics on different subsets (C5) | Smart persistence; baseline 3 from lead-time-faithful data; shared metrics module and index |
| P7 Models | Windows DataLoader; NaNs in TFT; quantile crossing; test-set peeking; time sink (C10, M6, M8) | `--smoke` runs; time-box; sort/clip quantiles; lock test; stop rule on day 11 |
| P8 Backend | Sleeping scheduler, ephemeral SQLite, multi-worker (C8); torch memory (C9); rate limits (M9) | Lazy refresh, seed DB, one worker; torch-free serving or ONNX; measure RSS |
| P9 Frontend | IST day bounds and `Z` parsing (M1); cold-start UX and CORS (M7) | Server-side IST summaries; "waking up" state; same-origin proxy |
| P10 Polish | Deploy-day surprises; attribution; report figures last-minute (C10) | Deploy skeleton by day 6; footer attribution; figures produced per phase |

## Phases Likely to Need Deeper Research Later

- **P1/P5:** Exact coverage and lead-time semantics of Previous Runs, Single Runs and Historical Forecast for Davanagere. This decides the split design and baseline 3. High impact, so probe it empirically on day 1-2.
- **P2:** Per-variable NASA timestamp semantics, which the hourly API page does not state. Resolve empirically.
- **P7:** Multi-target TFT in `darts` vs `pytorch-forecasting`. Do a spike with a 1-epoch run before committing.
- **P8/P10:** Current free-tier limits of the chosen host (memory, sleep policy, ephemeral disk). Check at decision time.

## Sources

- Open-Meteo Historical Forecast API docs (coverage starts about 2022, radiation is preceding-hour mean, azimuth 0 = south): https://open-meteo.com/en/docs/historical-forecast-api [V]
- Open-Meteo Forecast API docs (azimuth, preceding-hour mean, instant vs mean variables, wind 80/120 m): https://open-meteo.com/en/docs [V]
- Open-Meteo "Introducing the Historical Forecast API" (stitching of early hours of each run): https://openmeteo.substack.com/p/introducing-the-historical-forecast [V]
- Open-Meteo Previous Runs API (fixed lead times, most models archived from Jan 2024): https://open-meteo.com/en/docs/previous-runs-api [V]
- Open-Meteo Single Runs API: https://open-meteo.com/en/docs/single-runs-api [LOW, coverage from secondary mention]
- Open-Meteo pricing and terms (600/min, 5,000/h, 10,000/day, non-commercial, CC BY 4.0): https://open-meteo.com/en/pricing [V]
- NASA POWER hourly API (15 parameter limit, default LST, `time-standard=UTC`, 2001 start): https://power.larc.nasa.gov/docs/services/api/temporal/hourly/ [V]
- NASA POWER FAQ and pvlib `get_nasa_power` (hourly stamp is start of hour): https://power.larc.nasa.gov/docs/faqs/other/ , https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_nasa_power.html [M]
- Render free tier (15 min spin-down, 512 MB, 750 h): https://community.render.com/t/why-is-my-service-shutting-down-after-only-a-couple-of-minutes-and-all-data-is-lost/17760 , https://livemy.app/blog/render-pricing [M, aggregator]
- pytorch-forecasting docs (lightning import path): https://pytorch-forecasting.readthedocs.io/en/stable/getting-started.html [M]
- Kaggle datasets (quirks from PRD section 5.3 and general knowledge): https://www.kaggle.com/datasets/anikannal/solar-power-generation-data , https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset [K, verify on files]
- Items tagged [K] (pvlib `pvwatts_ac` semantics, Windows torch wheel default, DataLoader spawn, CORS/Starlette behaviour, Kaggle date formats, HF Spaces limits) come from training knowledge and should be confirmed when the phase starts.
