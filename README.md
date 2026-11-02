# Solar-Wind Forecast (Davanagere)

72-hour hourly forecasts of solar PV, wind turbine output and weather for Davanagere, Karnataka. See `docs/PRD.md`.

## Setup

```
uv sync --extra train        # the ONLY sync command: bare `uv sync` uninstalls torch
uv run python -m swf check-gpu
uv run pytest
```

If the cu134 torch index fails, change the index name/URL in `pyproject.toml` to cu132.
