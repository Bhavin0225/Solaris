"""Next-IST-day summary. ZoneInfo only finds the UTC instants of the day bounds; everything returned is UTC."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo


def ist_day_window(now: datetime, tz_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_name)
    tomorrow = now.astimezone(tz).date() + timedelta(days=1)
    start = datetime.combine(tomorrow, time(), tzinfo=tz)
    end = datetime.combine(tomorrow + timedelta(days=1), time(), tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def _t(v) -> datetime:
    return v if isinstance(v, datetime) else datetime.fromisoformat(v)


def summarize(rows: list[dict], start: datetime, end: datetime) -> dict:
    by: dict[str, list[tuple[datetime, float]]] = {}
    hours = set()
    for r in rows:
        t = _t(r["target_time"])
        if start <= t < end:
            hours.add(t)
            if r["p50"] is not None:
                by.setdefault(r["target"], []).append((t, r["p50"]))
    solar = by.get("t1_kw", [])
    rh = [v for _, v in by.get("rh", [])]
    ws = [v for _, v in by.get("ws10", [])]
    return {
        "n_hours": len(hours),
        "solar_kwh": float(sum(v for _, v in solar)),
        "wind_kwh": float(sum(v for _, v in by.get("t5_kw", []))),
        "peak_hour": max(solar, key=lambda x: x[1])[0] if solar else None,
        "mean_rh": sum(rh) / len(rh) if rh else None,
        "max_wind": max(ws) if ws else None,
    }
