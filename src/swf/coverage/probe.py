"""Coverage probe (the only networked part of DATA-05) and the NWP-model eligibility rule (D-06)."""

import argparse
import json
import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from swf.core.paths import INTERIM_DIR, RAW_DIR
from swf.core.settings import Settings, load_settings
from swf.fetch import nasa, openmeteo
from swf.fetch.cache import fetch_to_cache, make_client, safe_part

logger = logging.getLogger("swf.coverage")

HF_PROBE_START = "2016-01-01"  # before any candidate's archive start
PR_PROBE_START = "2024-01-01"
ELIGIBILITY = {"pr_day1_by": "2024-02-28", "pr_upper_wind_by": "2024-03-01", "hf_by": "2021-12-31"}
ALIASES = frozenset({"best_match"})
GAP = 3.0  # probe spacing, seconds


def first_valid(times: list[str], values: list) -> str | None:
    return next((t for t, v in zip(times, values) if v is not None), None)


def last_valid(times: list[str], values: list) -> str | None:
    return next((t for t, v in zip(reversed(times), reversed(values)) if v is not None), None)


def _upper(var: str) -> bool:
    return "_80m" in var or "_120m" in var


def is_eligible(model: str, m: dict) -> tuple[bool, list[str]]:
    if model in ALIASES:
        return False, [f"{model} is an unstable alias"]
    why = []
    for var, t in sorted(m["hf"].items()):
        if t is None or t[:10] > ELIGIBILITY["hf_by"]:
            why.append(f"HF {var} first valid {t} > {ELIGIBILITY['hf_by']}")
    for var, t in sorted(m["pr"].items()):
        if not var.endswith("_previous_day1"):
            continue
        by = ELIGIBILITY["pr_upper_wind_by" if _upper(var) else "pr_day1_by"]
        if t is None or t[:10] > by:
            why.append(f"PR day1 {var} first valid {t} > {by}")
    return not why, why


def _fetch_tail(client, url, make_params: Callable[[date], dict], dest, *, today: date, summarize, force, sleep):
    """End-date=today can be rejected for not-yet-available data; retry once with yesterday (I-6)."""
    try:
        end = today
        fetch_to_cache(client, url, make_params(end), dest, summarize=summarize, force=force, min_interval=GAP, sleep=sleep)
    except httpx.HTTPStatusError as e:
        if e.response.status_code not in (400, 422):
            raise
        logger.warning("tail request rejected (%s) for end=%s, retrying with end-1", e.response.status_code, end)
        fetch_to_cache(
            client, url, make_params(end - timedelta(days=1)), dest,
            summarize=summarize, force=force, min_interval=GAP, sleep=sleep,
        )


def _hourly(path: Path) -> tuple[dict, list[str], dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    h = d["hourly"]
    return d, h["time"], {k: v for k, v in h.items() if k != "time"}


def _firsts(path: Path) -> dict:
    _, times, cols = _hourly(path)
    return {k: first_valid(times, v) for k, v in cols.items()}


def collect(client, s: Settings, *, raw_root: Path, today: date, force: bool = False, sleep=time.sleep) -> dict:
    om = s.data.openmeteo
    root = raw_root / "probe" / f"{today:%Y%m%d}"
    ep = openmeteo.ENDPOINTS
    models = {}
    for model in om.probe_models:
        mp = safe_part(model)
        p = openmeteo.base_params(s, model)
        hf = {**p, "hourly": ",".join(om.hourly), "start_date": HF_PROBE_START,
              "end_date": f"{om.historical_forecast_years[1]}-12-31"}
        fetch_to_cache(client, ep["historical_forecast"], hf, root / f"hf_{mp}.json",
                       summarize=openmeteo.summarize, force=force, min_interval=GAP, sleep=sleep)
        all_leads = openmeteo.pr_accepts_all_leads(client, s, model, root / f"pr_smoke_{mp}.json", sleep=sleep)
        end = f"{om.previous_runs_years[1]}-12-31"
        leads = [None] if all_leads else list(om.previous_day_leads)
        pr = {}
        for lead in leads:
            names = openmeteo._hourly(s, "previous_runs", lead)
            dest = root / (f"pr_{mp}.json" if lead is None else f"pr_{mp}_day{lead}.json")
            fetch_to_cache(client, ep["previous_runs"], {**p, "hourly": ",".join(names), "start_date": PR_PROBE_START,
                           "end_date": end}, dest, summarize=openmeteo.summarize, force=force, min_interval=GAP, sleep=sleep)
            pr.update(_firsts(dest))
        d, _, _ = _hourly(root / f"hf_{mp}.json")
        models[model] = {
            "grid": {k: d.get(k) for k in ("latitude", "longitude", "elevation")},
            "hf": _firsts(root / f"hf_{mp}.json"),
            "pr": pr,
        }

    era5 = {**openmeteo.base_params(s, om.era5_model), "hourly": ",".join(om.hourly)}
    f1940 = root / "era5_1940.json"
    fetch_to_cache(client, ep["archive"], {**era5, "start_date": "1940-01-01", "end_date": "1940-01-02"}, f1940,
                   summarize=openmeteo.summarize, force=force, min_interval=GAP, sleep=sleep)
    tail = root / "era5_tail.json"
    _fetch_tail(client, ep["archive"],
                lambda e: {**era5, "start_date": (today - timedelta(days=14)).isoformat(), "end_date": e.isoformat()},
                tail, today=today, summarize=openmeteo.summarize, force=force, sleep=sleep)
    ntail = root / "nasa_tail.json"
    _fetch_tail(client, nasa.NASA_URL,
                lambda e: nasa.build_params_range(s, today - timedelta(days=60), e, ["T2M", "ALLSKY_SFC_SW_DWN"]),
                ntail, today=today, summarize=nasa.summarize, force=force, sleep=sleep)

    _, tt, tc = _hourly(tail)
    cached = raw_root / "openmeteo" / "archive" / safe_part(om.era5_model) / f"{om.era5_years[0]}.json"
    nd = json.loads(ntail.read_text(encoding="utf-8"))
    fill = nd["header"]["fill_value"]
    nasa_tail = {
        k: max((t for t, v in col.items() if v != fill and v is not None), default=None)
        for k, col in nd["properties"]["parameter"].items()
    }
    stamps = [json.loads(m.read_text(encoding="utf-8"))["retrieved_utc"] for m in root.glob("*.meta.json")]
    return {
        "probe_date": today.isoformat(),
        "retrieved_utc": max(stamps),
        "models": models,
        "era5": {
            "first_valid_1940": _firsts(f1940),
            "first_valid_cached": _firsts(cached) if cached.exists() else {},
            "last_valid": {k: last_valid(tt, v) for k, v in tc.items()},
        },
        "nasa_tail": nasa_tail,
    }


def run(args: argparse.Namespace) -> int:
    s = load_settings()
    try:
        with make_client() as client:
            probe = collect(client, s, raw_root=RAW_DIR, today=datetime.now(timezone.utc).date(), force=args.force)
    except httpx.HTTPError as e:
        logger.error("probe failed: %s", e)
        return 1
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    (INTERIM_DIR / "coverage_probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True), encoding="utf-8")
    for name, m in probe["models"].items():
        ok, why = is_eligible(name, m)
        logger.info("eligibility %s: %s %s", name, ok, why[:2])
    return 0
