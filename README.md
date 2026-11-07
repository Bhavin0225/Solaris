# Solar-Wind Forecast (Davanagere)

72-hour hourly forecasts of solar PV, wind turbine output and weather for Davanagere, Karnataka. See `docs/PRD.md`.

## Setup

```
uv sync --extra train        # the ONLY sync command: bare `uv sync` uninstalls torch
uv run python -m swf check-gpu
uv run pytest
```

If the cu134 torch index fails, change the index name/URL in `pyproject.toml` to cu132.

## Run locally

One-time frontend build:

```
npm --prefix frontend ci
npm --prefix frontend run build
```

The one command, then open http://127.0.0.1:8000 (API docs at `/docs`):

```
uv run python -m swf serve
```

It serves the cached forecast at once and refreshes from Open-Meteo on startup and hourly. The SQLite cache lives at `data/app.db`. If Open-Meteo is unreachable the page shows the cached forecast with a stale banner.

Dev mode: keep `uv run python -m swf serve` running and run `npm --prefix frontend run dev` (Vite proxies `/api` to 127.0.0.1:8000).

LightGBM training: `uv run python -m swf train-lgbm`, then `uv run python -m swf evaluate --split val` (writes `models/` and refreshes the leaderboard).

Weather data by Open-Meteo.com (CC BY 4.0); NASA POWER data courtesy of NASA Langley Research Center.
