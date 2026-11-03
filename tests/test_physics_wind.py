import logging

import numpy as np
import pandas as pd
import pytest

from swf.core.paths import CONFIG_DIR
from swf.physics import wind
from swf.physics.common import RHO0, air_density

HDR = "Date/Time,LV ActivePower (kW),Wind Speed (m/s),Theoretical_Power_Curve (KWh),Wind Direction (Â°)\n"


def _t1(tmp_path, rows, date="02 01 2018 00:10"):
    p = tmp_path / "T1.csv"
    p.write_text(HDR + "".join(f"{date},0,{v},{k},0\n" for v, k in rows), encoding="utf-8-sig")
    return p


def test_build_centre_bins(tmp_path):
    rows = [(1.0, 0), (2.9, 10), (3.1, 20), (7.74, 1000), (8.2, 1700), (13.1, 3600), (20.0, 3600)]
    c = wind.build_power_curve(_t1(tmp_path, rows))
    assert list(c.columns) == ["speed_ms", "kw"]
    assert c["speed_ms"].is_monotonic_increasing
    kw = c.set_index("speed_ms")["kw"]
    assert kw[3.0] == 15 and kw[7.5] == 1000 and kw[8.0] == 1700


def test_build_bad_date(tmp_path):
    with pytest.raises(ValueError):
        wind.build_power_curve(_t1(tmp_path, [(5.0, 100)], date="13 13 2018 00:00"))


def test_parametric(settings):
    c = wind.parametric_curve(settings).set_index("speed_ms")["kw"]
    w = settings.wind
    assert (c[c.index < w.cut_in_ms] == 0).all()
    assert c[w.rated_ms] == w.rated_kw and c[20.0] == w.rated_kw
    assert c.is_monotonic_increasing


def test_fallback_warns(settings, tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="swf.physics"):
        c = wind.load_power_curve(settings, tmp_path)
    assert "parametric" in caplog.text and len(c) > 10


def _df(ws, p=1013.3, t=15.0):
    n = len(ws)
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({"ws_hub": ws, "pressure": [p] * n, "temp": [t] * n}, index=idx)


CURVE = pd.DataFrame({"speed_ms": [0.0, 5.0, 10.0, 25.0], "kw": [0.0, 500.0, 2000.0, 3600.0]})


def test_density_identity_and_knots(settings):
    assert abs(air_density(1.225 * 287.05 * 288.15 / 100, 15) - RHO0) < 1e-9
    loss = 1 - settings.wind.availability_loss
    out = wind.simulate_wind(_df([5.0, 7.5]), settings, CURVE)
    assert out.name == "t5_kw"
    assert abs(out.iloc[0] - 500 * loss) < 1.0  # 1013.3 hPa rounds rho to RHO0 within ~1e-5
    assert abs(out.iloc[1] - 1250 * loss) < 1.0


def test_density_correction(settings):
    v = 8.0 * (air_density(950, 25) / RHO0) ** (1 / 3)
    exp = np.interp(v, CURVE.speed_ms, CURVE.kw) * (1 - settings.wind.availability_loss)
    assert abs(wind.simulate_wind(_df([8.0], 950, 25), settings, CURVE).iloc[0] - exp) < 1e-9


def test_cutout_nan_rated(settings):
    out = wind.simulate_wind(_df([25.0, 26.0, 0.0, np.nan, 24.0]), settings, CURVE)
    assert out.iloc[0] == 0 and out.iloc[1] == 0 and out.iloc[2] == 0
    assert np.isnan(out.iloc[3])
    assert out.max() <= settings.wind.rated_kw


def test_committed_curve(settings):
    c = wind.load_power_curve(settings)
    assert (CONFIG_DIR / settings.wind.power_curve_csv).exists()
    kw = c.set_index("speed_ms")["kw"]
    assert (kw[kw.index < 3.0] == 0).all()
    assert 10 <= kw[3.0] <= 25 and 1450 <= kw[8.0] <= 1600  # research cited 1675, which is the left-edge bin [8.0,8.5)
    assert (kw[(kw.index >= 13.0) & (kw.index <= 25.0)] == 3600).all()
    assert kw[kw.index <= 13.0].is_monotonic_increasing
