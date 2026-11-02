import numpy as np
import pandas as pd
import pytest

from swf.physics import common as c


def test_density_sea_level():
    assert c.air_density(1013.25, 15.0) == pytest.approx(1.225, abs=0.002)


def test_density_950():
    assert 1.10 <= c.air_density(950.0, 25.0) <= 1.12


def test_density_kpa_conversion():
    assert c.air_density(95.0 * c.KPA_TO_HPA, 25.0) == pytest.approx(
        c.air_density(950.0, 25.0)
    )


def test_hub_wind_formula():
    a = np.log(1.25) / np.log(5)
    assert c.hub_wind(4.0, 10, 5.0, 50, 80) == pytest.approx(5.0 * 1.6**a)


def test_hub_wind_clip():
    assert c.hub_wind(1.0, 10, 20.0, 50, 80) == pytest.approx(20.0 * 1.6**0.40)
    assert c.hub_wind(5.0, 10, 3.0, 50, 80) == pytest.approx(3.0 * 1.6**0.05)


def test_hub_wind_calm_default():
    assert c.hub_wind(0.3, 10, 2.0, 50, 80) == pytest.approx(2.0 * 1.6**0.143)


def test_hub_wind_identity_nan_series():
    s = pd.Series([3.0, np.nan], index=pd.date_range("2024-01-01", periods=2, freq="h"))
    out = c.hub_wind(s * 0.8, 10, s, 80, 80)
    assert out.iloc[0] == 3.0 and np.isnan(out.iloc[1]) and out.index.equals(s.index)
    arr = c.hub_wind(np.array([4.0, np.nan]), 10, np.array([5.0, 5.0]), 50, 80)
    assert np.isnan(arr[1]) and arr[0] > 5.0


def test_midpoints_and_night(settings):
    idx = pd.DatetimeIndex(["2024-03-21 18:00", "2024-03-21 06:00"], tz="UTC")
    assert (c.midpoints(idx) - idx == pd.Timedelta(minutes=30)).all()
    assert list(c.is_night(idx, settings)) == [True, False]


def test_clearsky(settings):
    idx = pd.date_range("2024-03-21", periods=24, freq="h", tz="UTC")
    cs = c.clearsky(idx, settings)
    assert cs.index.equals(idx)
    assert cs["ghi"].iloc[18] == 0
    assert cs["ghi"].iloc[6:8].max() > 900
