from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from swf.api.schemas import Point
from swf.api.summary import ist_day_window, summarize

TZ = "Asia/Kolkata"


def test_window_before_ist_midnight():
    s, e = ist_day_window(datetime(2026, 11, 2, 16, 20, tzinfo=UTC), TZ)
    assert (s, e) == (datetime(2026, 11, 2, 18, 30, tzinfo=UTC), datetime(2026, 11, 3, 18, 30, tzinfo=UTC))


def test_window_after_ist_midnight():
    s, e = ist_day_window(datetime(2026, 11, 2, 19, 0, tzinfo=UTC), TZ)
    assert (s, e) == (datetime(2026, 11, 3, 18, 30, tzinfo=UTC), datetime(2026, 11, 4, 18, 30, tzinfo=UTC))


def test_summarize_window_only():
    s, e = ist_day_window(datetime(2026, 11, 2, 16, 20, tzinfo=UTC), TZ)
    rows = []
    for i in range(-5, 30):
        t = s + timedelta(hours=i)
        inside = 0 <= i < 24
        for tgt, v in [("t1_kw", 100.0 if inside else 0.0), ("t5_kw", 100.0 if inside else 0.0),
                       ("rh", 50.0 if inside else 99.0), ("ws10", 3.0 if inside else 20.0)]:  # fmt: skip
            rows.append({"target": tgt, "target_time": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "p50": v})
    out = summarize(rows, s, e)
    assert out["n_hours"] == 24
    assert out["solar_kwh"] == 2400 and out["wind_kwh"] == 2400
    assert out["mean_rh"] == 50 and out["max_wind"] == 3
    assert out["peak_hour"] == s  # first of equal maxima


def test_summarize_peak_and_empty():
    s, e = ist_day_window(datetime(2026, 11, 2, 16, 20, tzinfo=UTC), TZ)
    rows = [{"target": "t1_kw", "target_time": (s + timedelta(hours=h)).isoformat(), "p50": v} for h, v in [(3, 1.0), (7, 9.0)]]
    assert summarize(rows, s, e)["peak_hour"] == s + timedelta(hours=7)
    assert summarize([], s, e)["peak_hour"] is None


def test_naive_rejected_and_z_suffix():
    with pytest.raises(ValidationError):
        Point(time=datetime(2026, 1, 1), p10=None, p50=None, p90=None)
    assert '"2026-01-01T00:00:00Z"' in Point(time=datetime(2026, 1, 1, tzinfo=UTC), p10=1, p50=1, p90=1).model_dump_json()
