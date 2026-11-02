"""NASA POWER hourly fetcher (DATA-01). stdlib-only parsing; pandas lives in parse.py."""

import argparse
import json
import logging
import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import httpx

from swf.core.paths import RAW_DIR
from swf.core.settings import Settings, load_settings
from swf.fetch.cache import fetch_to_cache, make_client

logger = logging.getLogger("swf.fetch")

NASA_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"


def build_params_range(s: Settings, start: date, end: date, parameters: list[str] | None = None) -> dict:
    return {
        "parameters": ",".join(parameters or s.data.nasa.parameters),
        "community": s.data.nasa.community,
        "latitude": s.site.latitude,
        "longitude": s.site.longitude,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }


def build_params(s: Settings, year: int) -> dict:
    return build_params_range(s, date(year, 1, 1), date(year, 12, 31))


def summarize(raw: bytes) -> dict:
    d = json.loads(raw)
    fill = d["header"]["fill_value"]
    params = d["properties"]["parameter"]
    rows = len(next(iter(params.values())))
    if not rows:
        raise ValueError("NASA payload has no rows")
    pct = {
        k: round(100 * sum(1 for v in col.values() if v is None or v == fill) / rows, 2)
        for k, col in params.items()
    }
    return {
        "rows": rows,
        "columns": list(params),
        "pct_missing": pct,
        "fill_value": fill,
        "time_standard": d["header"]["time_standard"],
        "coordinates": d["geometry"]["coordinates"],
    }


def fetch_years(
    client: httpx.Client,
    s: Settings,
    years: Iterable[int],
    *,
    root: Path,
    force: bool = False,
    sleep=time.sleep,
) -> list[str]:
    return [
        fetch_to_cache(
            client,
            NASA_URL,
            build_params(s, y),
            root / "nasa" / f"{y}.json",
            summarize=summarize,
            force=force,
            min_interval=s.data.nasa.min_interval_s,
            sleep=sleep,
        )
        for y in years
    ]


def run(args: argparse.Namespace) -> int:
    s = load_settings()
    years = range(s.data.nasa.start_year, s.data.nasa.end_year + 1)
    try:
        with make_client() as client:
            fetch_years(client, s, years, root=RAW_DIR, force=args.force)
    except (httpx.HTTPError, ValueError, KeyError, StopIteration) as e:
        logger.error("NASA fetch failed: %s", e)
        return 1
    return 0
