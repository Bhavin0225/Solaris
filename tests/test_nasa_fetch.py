import json
from datetime import date

import httpx

from swf.fetch.nasa import (
    NASA_URL,
    build_params,
    build_params_range,
    fetch_years,
    summarize,
)


def test_params_range(settings):
    p = build_params_range(settings, date(2026, 9, 1), date(2026, 11, 1), ["T2M"])
    assert p["parameters"] == "T2M" and p["start"] == "20260901" and p["end"] == "20261101"
    assert p["time-standard"] == "UTC"


def test_params_year(settings):
    p = build_params(settings, 2024)
    assert len(p["parameters"].split(",")) == 14
    assert p["community"] == "RE" and p["format"] == "JSON"
    assert p["latitude"] == settings.site.latitude and p["longitude"] == settings.site.longitude
    assert p["start"] == "20240101" and p["end"] == "20241231" and p["time-standard"] == "UTC"


def test_fetch_years_cache(tmp_path, settings, mock_client, no_sleep, fixtures_dir):
    body = (fixtures_dir / "nasa_sample.json").read_bytes()
    reqs = []

    def handler(request):
        reqs.append(request)
        return httpx.Response(200, content=body)

    c = mock_client(handler)
    kw = {"root": tmp_path, "sleep": no_sleep}
    assert fetch_years(c, settings, [2001, 2002], **kw) == ["fetched", "fetched"]
    assert len(reqs) == 2
    assert str(reqs[0].url).startswith(NASA_URL) and "start=20010101" in str(reqs[0].url)
    for y in (2001, 2002):
        assert (tmp_path / "nasa" / f"{y}.json").exists()
        assert (tmp_path / "nasa" / f"{y}.meta.json").exists()
    assert no_sleep.calls == [settings.data.nasa.min_interval_s] * 2
    assert fetch_years(c, settings, [2001, 2002], **kw) == ["hit", "hit"]
    assert len(reqs) == 2
    fetch_years(c, settings, [2001, 2002], force=True, **kw)
    assert len(reqs) == 4


def test_summarize(fixtures_dir):
    raw = (fixtures_dir / "nasa_sample.json").read_bytes()
    s = summarize(raw)
    n = len(next(iter(json.loads(raw)["properties"]["parameter"].values())))
    assert s["rows"] == n
    assert s["pct_missing"]["ALLSKY_KT"] > 0 and s["pct_missing"]["T2M"] == 0
    assert s["fill_value"] == -999.0 and s["time_standard"] == "UTC"


def test_summarize_empty_payload_raises_valueerror():
    import pytest

    raw = json.dumps({"header": {"fill_value": -999.0, "time_standard": "UTC"},
                      "properties": {"parameter": {"T2M": {}}}}).encode()
    with pytest.raises(ValueError):
        summarize(raw)
