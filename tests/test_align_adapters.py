import hashlib
import json

import pandas as pd
import pytest

from swf.align.adapters import (
    OFFSETS,
    SOURCES,
    load_source,
    nasa_canon,
    openmeteo_canon,
)
from swf.align.canon import validate_canon
from swf.physics.common import hub_wind

NASA_PARAMS = ["ALLSKY_SFC_SW_DWN", "ALLSKY_SFC_SW_DNI", "ALLSKY_SFC_SW_DIFF", "CLRSKY_SFC_SW_DWN", "ALLSKY_KT",
               "T2M", "RH2M", "QV2M", "WS10M", "WS50M", "WD10M", "WD50M", "PS", "PRECTOTCORR"]  # fmt: skip
OM_VARS = ["shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation", "global_tilted_irradiance",
           "temperature_2m", "relative_humidity_2m", "surface_pressure", "cloud_cover", "precipitation",
           "wind_speed_10m", "wind_speed_80m", "wind_speed_120m", "wind_direction_10m", "wind_direction_80m"]  # fmt: skip


def nasa_json(day="20240301", over=None):
    over = over or {}
    vals = {p: 1.0 for p in NASA_PARAMS} | {"PS": 94.5, "WS10M": 3.0, "WS50M": 5.0} | over
    par = {p: {f"{day}{h:02d}": vals[p] for h in range(24)} for p in NASA_PARAMS}
    par["ALLSKY_SFC_SW_DWN"][f"{day}06"] = 500.0
    return json.dumps({"header": {"fill_value": -999.0, "time_standard": "UTC"}, "properties": {"parameter": par}}).encode()


def om_json(date="2024-03-01", suffix="", over=None, drop=None):
    times = [f"{date}T{h:02d}:00" for h in range(24)]
    vals = {v: 10.0 for v in OM_VARS} | {"wind_speed_10m": 3.0, "wind_speed_80m": 6.0, "wind_speed_120m": 7.0} | (over or {})
    h = {"time": times} | {v + suffix: [vals[v]] * 24 for v in OM_VARS if v != drop}
    h["shortwave_radiation" + suffix][6] = 500.0
    return json.dumps({"hourly": h}).encode()


def test_offsets_pinned():
    assert len(OFFSETS) == 6
    for g in ("radiation", "met", "precip"):
        assert OFFSETS[("nasa", g)] == pd.Timedelta(0)
    for g in ("radiation", "instant", "precip"):
        assert OFFSETS[("openmeteo", g)] == pd.Timedelta(hours=-1)
    assert OFFSETS[("nasa", "met")] == pd.Timedelta(0)


def test_openmeteo_shift(settings):
    df = openmeteo_canon(om_json(), settings)
    assert df.loc["2024-03-01 05:00", "ghi"] == 500.0
    assert df.index[0] == pd.Timestamp("2024-02-29 23:00", tz="UTC")
    assert df["temp"].iloc[0] == 10.0 and df["precip"].iloc[0] == 10.0


def test_openmeteo_lead_and_missing(settings):
    df = openmeteo_canon(om_json(suffix="_previous_day2"), settings, lead=2)
    assert df.loc["2024-03-01 05:00", "ghi"] == 500.0
    with pytest.raises(KeyError):
        openmeteo_canon(om_json(suffix="_previous_day2"), settings, lead=1)
    with pytest.raises(KeyError):
        openmeteo_canon(om_json(drop="surface_pressure"), settings)


def test_nasa_canon(settings):
    df = nasa_canon(nasa_json(), settings)
    assert df.loc["2024-03-01 06:00", "ghi"] == 500.0
    assert (df["pressure"] == 945.0).all()
    assert df["cloud"].isna().all()
    exp = hub_wind(pd.Series([3.0]), 10, pd.Series([5.0]), 50, settings.wind.hub_height_m).iloc[0]
    assert df["ws_hub"].iloc[0] == pytest.approx(exp)


def test_openmeteo_hub_identity_and_nearest(settings):
    h = settings.wind.hub_height_m
    z = min((80, 120), key=lambda z: abs(z - h))
    df = openmeteo_canon(om_json(), settings)
    if h == z:
        assert df["ws_hub"].iloc[0] == {80: 6.0, 120: 7.0}[z]


def test_live_fixture(settings, fixtures_dir):
    df = openmeteo_canon((fixtures_dir / "om_live_gfs_seamless.json").read_bytes(), settings)
    validate_canon(df)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.with_suffix(".meta.json").write_text(json.dumps({"sha256": hashlib.sha256(data).hexdigest()}))


def test_load_source(settings, tmp_path):
    a = settings.data.openmeteo.era5_years[0]
    d = tmp_path / "openmeteo/archive" / settings.data.openmeteo.era5_model
    for y, date in ((a, f"{a}-12-31"), (a + 1, f"{a + 1}-01-01")):
        _write(d / f"{y}.json", om_json(date))
    # only first two years written; shrink config via model_copy is overkill, so patch the file list
    import swf.align.adapters as ad

    orig = ad._year_files
    ad._year_files = lambda *x: [d / f"{a}.json", d / f"{a + 1}.json"]
    try:
        df = load_source("era5", settings, tmp_path)
        assert df.index.is_unique and len(df) == 48
        (d / f"{a}.json").write_bytes(b"{}")
        with pytest.raises(ValueError):
            load_source("era5", settings, tmp_path)
    finally:
        ad._year_files = orig
    with pytest.raises(ValueError):
        load_source("nope", settings, tmp_path)


def test_previous_runs_layouts(settings, tmp_path):
    y = settings.data.openmeteo.previous_runs_years[0]
    d = tmp_path / "openmeteo/previous_runs" / settings.data.openmeteo.nwp_model
    from swf.align.adapters import _year_files

    assert _year_files("gfs_pr_d3", settings, tmp_path)[0].name == f"{y}_day3.json"
    _write(d / f"{y}.json", b"{}")
    assert _year_files("gfs_pr_d3", settings, tmp_path)[0].name == f"{y}.json"


@pytest.mark.realdata
@pytest.mark.parametrize("src", SOURCES)
def test_real_sources(src, settings, raw_root):
    try:
        df = load_source(src, settings, raw_root)
    except ValueError as e:
        if src == "gfs_live" and "no live forecast" in str(e):
            pytest.skip("no live file cached")
        raise
    validate_canon(df)
    if src in ("nasa", "era5"):
        assert len(df) >= 219_000
