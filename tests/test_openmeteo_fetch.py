import json
from datetime import UTC, datetime

import httpx
import pytest

from swf.fetch import openmeteo as om


def _handler(fixtures_dir, name, seen):
    body = (fixtures_dir / name).read_bytes()

    def h(req):
        seen.append(req)
        return httpx.Response(200, content=body)

    return h


def test_year_params(settings):
    a = om.year_params(settings, "archive", 2010)
    assert a["models"] == "era5" and a["start_date"] == "2010-01-01" and a["end_date"] == "2010-12-31"
    assert a["timezone"] == "GMT" and a["wind_speed_unit"] == "ms" and a["tilt"] == 15 and a["azimuth"] == 0
    assert "wind_speed_80m" in a["hourly"] and "global_tilted_irradiance" in a["hourly"]
    h = om.year_params(settings, "historical_forecast", 2022)
    assert h["models"] == "gfs_seamless" and len(h["hourly"].split(",")) == 14
    names = om.year_params(settings, "previous_runs", 2024)["hourly"].split(",")
    assert len(names) == 42 and "shortwave_radiation_previous_day1" in names
    assert "wind_speed_80m_previous_day3" in names and all("_previous_day" in n for n in names)
    lp = om.live_params(settings)
    assert lp["models"] == "gfs_seamless" and lp["past_days"] == 8 and lp["forecast_days"] == 4
    assert "start_date" not in lp
    with pytest.raises(ValueError):
        om.year_params(settings, "bogus", 2020)


def test_fetch_years_and_cache(settings, mock_client, no_sleep, fixtures_dir, tmp_path):
    seen = []
    c = mock_client(_handler(fixtures_dir, "om_hf_sample.json", seen))
    for api, yr, rel in [
        ("archive", 2010, "archive/era5/2010.json"),
        ("historical_forecast", 2022, "historical_forecast/gfs_seamless/2022.json"),
        ("previous_runs", 2024, "previous_runs/gfs_seamless/2024.json"),
    ]:
        om.fetch_years(c, settings, api, [yr], root=tmp_path, sleep=no_sleep)
        dest = tmp_path / "openmeteo" / rel
        assert dest.exists()
        meta = json.loads(dest.with_suffix(".meta.json").read_text())
        assert "timezone=GMT" in meta["url"] and "models=" in meta["url"] and meta["retrieved_utc"]
    assert [r.url.host for r in seen] == [
        "archive-api.open-meteo.com", "historical-forecast-api.open-meteo.com", "previous-runs-api.open-meteo.com"
    ]
    n = len(seen)
    om.fetch_years(c, settings, "archive", [2010], root=tmp_path, sleep=no_sleep)
    assert len(seen) == n
    assert set(no_sleep.calls) == {2.0}


def test_split_leads(settings, mock_client, no_sleep, fixtures_dir, tmp_path):
    seen = []
    c = mock_client(_handler(fixtures_dir, "om_pr_sample.json", seen))
    om.fetch_years(c, settings, "previous_runs", [2024], root=tmp_path, sleep=no_sleep, split_leads=True)
    d = tmp_path / "openmeteo/previous_runs/gfs_seamless"
    assert len(seen) == 3 and all((d / f"2024_day{n}.json").exists() for n in (1, 2, 3))
    for n, r in enumerate(seen, 1):
        hourly = r.url.params["hourly"].split(",")
        assert len(hourly) == 14 and all(x.endswith(f"_previous_day{n}") for x in hourly)


def test_live(settings, mock_client, no_sleep, fixtures_dir, tmp_path):
    seen = []
    c = mock_client(_handler(fixtures_dir, "om_hf_sample.json", seen))
    now = datetime(2026, 11, 1, 15, 20, tzinfo=UTC)
    p = om.fetch_live(c, settings, root=tmp_path, now=now, sleep=no_sleep)
    assert p == tmp_path / "openmeteo/forecast/gfs_seamless/20261101T15.json"
    om.fetch_live(c, settings, root=tmp_path, now=now, sleep=no_sleep)
    assert len(seen) == 1


def test_summarize(fixtures_dir):
    raw = (fixtures_dir / "om_hf_sample.json").read_bytes()
    d = json.loads(raw)
    s = om.summarize(raw)
    assert s["rows"] == len(d["hourly"]["time"]) == 24
    assert s["pct_missing"]["temperature_2m"] == round(100 / 24, 2)
    assert s["elevation"] == 598.0 and s["first_time"].endswith("00:00") and s["last_time"].endswith("23:00")


def test_pr_smoke(settings, mock_client, no_sleep, fixtures_dir, tmp_path):
    seen = []
    dest = tmp_path / "smoke.json"
    c = mock_client(_handler(fixtures_dir, "om_pr_sample.json", seen))
    assert om.pr_accepts_all_leads(c, settings, "gfs_seamless", dest, sleep=no_sleep)
    assert len(seen[0].url.params["hourly"].split(",")) == 42 and dest.exists()
    bad = tmp_path / "bad.json"
    c400 = mock_client(lambda r: httpx.Response(400, json={"error": True}))
    assert om.pr_accepts_all_leads(c400, settings, "gfs_seamless", bad, sleep=no_sleep) is False
    assert not bad.exists()


def test_best_match_rejected(settings):
    from pydantic import ValidationError

    from swf.core.settings import Settings

    d = settings.model_dump()
    d["data"]["openmeteo"]["nwp_model"] = "best_match"
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_live_fixture(settings, fixtures_dir):
    s = om.summarize((fixtures_dir / "om_live_gfs_seamless.json").read_bytes())
    p = json.loads((fixtures_dir / "om_live_gfs_seamless.meta.json").read_text())["params"]  # recorded with past_days=7
    assert s["rows"] == 24 * (p["past_days"] + p["forecast_days"])
    assert set(settings.data.openmeteo.hourly) <= set(s["columns"])


def test_summarize_empty_payload_raises_valueerror():
    import pytest

    from swf.fetch.openmeteo import summarize

    with pytest.raises(ValueError):
        summarize(b'{"hourly": {"time": [], "temperature_2m": []}}')
