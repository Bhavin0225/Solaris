"""Open-Meteo fetchers: ERA5 archive, Historical Forecast, Previous Runs, live forecast (DATA-02). stdlib only."""

import argparse
import json
import logging
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

import httpx

from swf.core.geometry import to_openmeteo_azimuth
from swf.core.paths import RAW_DIR
from swf.core.settings import Settings, load_settings
from swf.fetch.cache import fetch_to_cache, is_cached, make_client, safe_part

logger = logging.getLogger("swf.fetch")

ENDPOINTS = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "previous_runs": "https://previous-runs-api.open-meteo.com/v1/forecast",
    "forecast": "https://api.open-meteo.com/v1/forecast",
}


def base_params(s: Settings, model: str) -> dict:
    return {
        "latitude": s.site.latitude,
        "longitude": s.site.longitude,
        "timezone": "GMT",
        "wind_speed_unit": "ms",
        "tilt": s.solar.tilt_deg,
        "azimuth": to_openmeteo_azimuth(s.solar.azimuth_pvlib_deg),
        "models": model,
    }


def _model_for(s: Settings, api: str) -> str:
    if api not in ENDPOINTS or api == "forecast":
        raise ValueError(f"unknown api {api!r}")
    om = s.data.openmeteo
    return om.era5_model if api == "archive" else om.nwp_model


def _hourly(s: Settings, api: str, lead: int | None = None) -> list[str]:
    om = s.data.openmeteo
    if api != "previous_runs":
        return list(om.hourly)
    leads = om.previous_day_leads if lead is None else [lead]
    return [f"{v}_previous_day{n}" for v in om.hourly for n in leads]


def year_params(s: Settings, api: str, year: int, lead: int | None = None) -> dict:
    p = base_params(s, _model_for(s, api))
    p["hourly"] = ",".join(_hourly(s, api, lead))
    p["start_date"] = f"{year}-01-01"
    p["end_date"] = f"{year}-12-31"
    return p


def live_params(s: Settings) -> dict:
    om = s.data.openmeteo
    p = base_params(s, om.nwp_model)
    p["hourly"] = ",".join(om.hourly)
    p["past_days"] = om.live.past_days
    p["forecast_days"] = om.live.forecast_days
    return p


def summarize(raw: bytes) -> dict:
    d = json.loads(raw)
    h = d["hourly"]
    times = h["time"]
    rows = len(times)
    if not rows:
        raise ValueError("Open-Meteo payload has no rows")
    pct = {
        k: round(100 * sum(1 for v in col if v is None) / rows, 2) for k, col in h.items() if k != "time"
    }
    return {
        "rows": rows,
        "columns": [k for k in h if k != "time"],
        "pct_missing": pct,
        "latitude": d.get("latitude"),
        "longitude": d.get("longitude"),
        "elevation": d.get("elevation"),
        "first_time": times[0] if times else None,
        "last_time": times[-1] if times else None,
    }


def pr_accepts_all_leads(client, s: Settings, model: str, dest: Path, *, sleep=time.sleep) -> bool:
    om = s.data.openmeteo
    p = base_params(s, model)
    p["hourly"] = ",".join(_hourly(s, "previous_runs"))
    day = f"{om.previous_runs_years[0]}-03-01"
    p["start_date"] = p["end_date"] = day
    try:
        fetch_to_cache(
            client, ENDPOINTS["previous_runs"], p, dest,
            summarize=summarize, min_interval=om.min_interval_s, sleep=sleep,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return False
        raise
    return True


def fetch_years(
    client,
    s: Settings,
    api: str,
    years: Iterable[int],
    *,
    root: Path,
    force: bool = False,
    sleep=time.sleep,
    split_leads: bool = False,
) -> list[str]:
    model = safe_part(_model_for(s, api))
    d = root / "openmeteo" / safe_part(api) / model
    gap = s.data.openmeteo.min_interval_s
    out = []
    for y in years:
        jobs = [(None, f"{y}")]
        if split_leads and api == "previous_runs":
            jobs = [(n, f"{y}_day{n}") for n in s.data.openmeteo.previous_day_leads]
        for lead, stem in jobs:
            out.append(
                fetch_to_cache(
                    client, ENDPOINTS[api], year_params(s, api, y, lead), d / f"{stem}.json",
                    summarize=summarize, force=force, min_interval=gap, sleep=sleep,
                )
            )
    return out


def fetch_live(
    client, s: Settings, *, root: Path, now: datetime | None = None, force=False, sleep=time.sleep
) -> Path:
    now = now or datetime.now(timezone.utc)
    dest = root / "openmeteo" / "forecast" / safe_part(s.data.openmeteo.nwp_model) / f"{now:%Y%m%dT%H}.json"
    fetch_to_cache(
        client, ENDPOINTS["forecast"], live_params(s), dest,
        summarize=summarize, force=force, min_interval=s.data.openmeteo.min_interval_s, sleep=sleep,
    )
    return dest


def _pr_cached(s: Settings, root: Path, years: list[int]) -> bool:
    d = root / "openmeteo" / "previous_runs" / s.data.openmeteo.nwp_model
    leads = s.data.openmeteo.previous_day_leads
    return all(
        is_cached(d / f"{y}.json") or all(is_cached(d / f"{y}_day{n}.json") for n in leads) for y in years
    )


def run(args: argparse.Namespace) -> int:
    s = load_settings()
    om = s.data.openmeteo
    rng = lambda t: range(t[0], t[1] + 1)  # noqa: E731
    which = ["era5", "historical", "previous", "live"] if args.api == "all" else [args.api]
    try:
        with make_client() as client:
            for w in which:
                if w == "era5":
                    fetch_years(client, s, "archive", rng(om.era5_years), root=RAW_DIR, force=args.force)
                elif w == "historical":
                    fetch_years(client, s, "historical_forecast", rng(om.historical_forecast_years), root=RAW_DIR, force=args.force)
                elif w == "previous":
                    years = list(rng(om.previous_runs_years))
                    split = False
                    if args.force or not _pr_cached(s, RAW_DIR, years):
                        smoke = RAW_DIR / "openmeteo" / "previous_runs" / om.nwp_model / "smoke.json"
                        split = not pr_accepts_all_leads(client, s, om.nwp_model, smoke)
                        logger.info("previous_runs mode: %s", "split-lead" if split else "all-leads")
                    fetch_years(client, s, "previous_runs", years, root=RAW_DIR, force=args.force, split_leads=split)
                elif w == "live":
                    fetch_live(client, s, root=RAW_DIR, force=args.force)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error("Open-Meteo fetch failed: %s", e)
        return 1
    return 0
