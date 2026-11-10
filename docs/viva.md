# Viva notes

Plain-language notes for the viva (oral exam). The setup and results are in [README.md](../README.md); this file does not repeat them.

## Pre-viva checklist

- The day before: run `uv run python -m swf serve` once while online, so the forecast database `data/app.db` holds a fresh forecast. Stop it with Ctrl+C.
- On the day: laptop charged and plugged in, start `uv run python -m swf serve`, open http://127.0.0.1:8000 in a fresh browser profile (no stray tabs or extensions).
- Check the footer: the "last updated" time should be within the last hour or two.
- Keep this file and the code editor open (README.md, `src/swf/cli.py`, `reports/evaluation/leaderboard.csv`).
- If the internet fails: the site still shows the cached forecast with a stale banner. That is the designed behaviour, say so.
- Do not run `evaluate --final`. It refuses by design: the test year 2025 was scored once (2026-11-09) and must not be scored again.
- Do not retrain before the viva. `train` needs `--accept-stale-results` and replaces the models behind the official results.

## Demo script

1. Energy page (`/`): five cards, one per target (solar power, wind power, sunlight GHI (global horizontal irradiance), humidity, wind speed). Say: "Each card is the next-hour value with a P10-P90 range (80% of real values should fall inside it)."
2. Scroll to the 72-hour chart: five panels share one time axis. Hover one hour and all panels highlight the same hour. Say: "Middle line is the P50 (median) forecast, the shaded band is P10-P90. Times are shown in IST (Indian Standard Time); the code uses UTC (coordinated universal time) inside."
3. Point at the "Simulated energy" tag. Say: "Solar and wind power are simulated from weather with physics, then checked against real Kaggle plants."
4. Weather page (`/weather`): the weather inputs and their forecasts. Say: "These come from Open-Meteo, called directly over HTTP."
5. Performance page (`/performance`): the five skill cards. Say: "Skill is how much lower the RMSE (root mean square error) is than baseline 3, the weather service forecast turned into power with physics. Test year 2025, scored once."
6. Leaderboard tab: show all models side by side. Say: "TFT (Temporal Fusion Transformer) is best on all five targets on the test year, but wind speed and wind power gain the least."
7. Heatmap and By horizon tabs: skill by hour ahead and time of day. Say: "Skill shrinks the further ahead we forecast."
8. Coverage and Calibration tabs: P10-P90 coverage. Say honestly: "Solar and sunlight are close to the 80% target; wind speed and wind power are only about 66% and 68%, so their bands are too narrow."
9. Physics check tab: scatter plots of simulated against real Kaggle plant power. Say: "This is how I know the simulation is realistic."
10. About page (`/about`): data credits (Open-Meteo CC BY 4.0, NASA POWER, Kaggle datasets).
11. http://127.0.0.1:8000/docs: the API (application programming interface) documentation. Show `/api/forecast`.
12. Footer build info: git SHA (code version), data-through time, model version.

## Code walkthrough

Follow the data flow, one file at a time.

1. `config/*.yaml`: site location, plant specs, model settings. Nothing is hard-coded in the code.
2. `src/swf/cli.py`: entry point, the commands `data`, `train`, `evaluate`, `serve`.
3. `src/swf/fetch/` (`nasa.py`, `openmeteo.py`, `kaggle.py`, `cache.py`): download weather and plant data, cache raw responses in `data/raw/`.
4. `src/swf/align/`: clean, put everything on one UTC hourly table, fix known biases.
5. `src/swf/physics/`: solar (pvlib: sun position, panel temperature, power), wind (turbine power curve), and the simulation that turns weather into kW.
6. `src/swf/validate/`: compare simulated power with real Kaggle plant power; writes the scatter plots.
7. `src/swf/features/`: build model inputs without looking into the future; time-based splits (train, validation, test).
8. `src/swf/evaluate/baselines.py`: baseline 3 and the simple reference forecasts.
9. `src/swf/models/`: `lgbm.py` (LightGBM, tree model), `seq.py` (LSTM (long short-term memory) and GRU (gated recurrent unit) in plain PyTorch), `tft.py` (TFT).
10. `src/swf/evaluate/` (`report.py`, `final.py`, `figures.py`, `prob.py`): leaderboard, one-time test-year run, figures, interval coverage.
11. `src/swf/predict/`: turns the live Open-Meteo data into the 72-hour forecast with the deployed model.
12. `src/swf/api/main.py` (with `refresh.py`, `db.py`): FastAPI endpoints, hourly refresh, SQLite cache.
13. `frontend/src/App.tsx` and `frontend/src/pages/` (Energy, Weather, Performance, About): the website.
14. `tests/`: automated checks, including leakage and report-audit tests.

## Likely questions

### Q1. Why time-based splits and never shuffling?
Forecasting means predicting the future from the past. Shuffling would let the model see tomorrow while training on yesterday, which inflates scores. Here training is the early years, validation 2024, and test 2025, in order, each a full year so every season is covered.

### Q2. What is baseline 3 and why compare every model to it?
It is the Open-Meteo weather forecast converted to power with the same physics formulas (a bias-corrected version is used where that helped on validation). It is what you would get without any machine learning, so a model is only worth having if it beats it.

### Q3. Why is TFT served for all five targets?
Every target is served by TFT (decision D-30) so the website uses one model and one honest leaderboard. On the 2025 test year TFT also had the lowest RMSE on all five targets, but the margin is small for wind speed (+16.2%) and wind power (+19.9%), and the leaderboard shows that openly.

### Q4. How was the test year protected?
It was never used to choose models or settings; selection used validation 2024 only (`models/deployed/selection_val.json`). The file `models/deployed/test_started.json` records that the one-time test run happened on 2026-11-09, and `evaluate --final` refuses to run again.

### Q5. Why is energy simulated, and how was it validated?
We have no live meter at Davanagere. So solar and wind power are computed from weather with physics (pvlib for solar, a power curve for wind). The simulation was checked against real data: two Kaggle solar plants and one Kaggle wind turbine. The scatter plots on the Physics check tab show the match.

### Q6. Why UTC inside and IST only in the browser?
Mixing time zones is a classic source of off-by-5.5-hour bugs. All code, files and the database use UTC; only the frontend converts to IST (UTC+5:30) for display.

### Q7. Why are NASA POWER and Open-Meteo called directly with httpx?
It was a project rule: no wrapper libraries, so I control caching, retries and rate limits and can explain every request. Raw responses are saved under `data/raw/` and never downloaded twice.

### Q8. What is the train/serve skew of Open-Meteo's historical forecasts?
The history is a stitched series of the first hours of each forecast run, while at serving time we use forecasts one to three days ahead, which are less accurate. Models trained on the first could be over-confident on the second. Open-Meteo's Previous Runs data (fixed lead times, available from 2024) is the way to measure and reduce this gap.

### Q9. What does the P10-P90 band mean and how well does it work?
It is a range where the real value should fall 80% of the time. Measured on the test year, coverage was about 81% for solar power, 79% for sunlight, 74% for humidity, but only about 66% for wind speed and 68% for wind power, so the wind bands are too narrow. This is a known limitation.

### Q10. Why does the footer git SHA end in "+dirty"?
The model registry records the code version at training time, and the working folder had uncommitted changes then. "+dirty" is that honest flag, not an error.

### Q11. How can someone reproduce the results?
Follow the README: `data`, `train --accept-stale-results`, `evaluate`, then build and serve. On a fresh clone `evaluate` prints a SKIPPED list because the 192 MB prediction files are not in git; it re-scores the baselines and keeps the committed machine-learning rows. Retrains are not bit-identical (GPU nondeterminism), so numbers move slightly, which is why the committed `reports/` are the official results.

### Q12. What would you do next?
Deploy publicly (cloud hosting with a smaller model image), and recalibrate the wind P10-P90 bands so their coverage reaches 80%.
