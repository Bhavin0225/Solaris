import numpy as np
import pandas as pd
import pytest
from synth import clearsky_hourly

from swf.align.adapters import load_source
from swf.align.timestamps import centroid_diff, met_lag, onset_rates, verify


@pytest.fixture(scope="module")
def year_cs():
    from swf.core.settings import load_settings

    return clearsky_hourly("2024-01-01", 366, load_settings())


def test_verify_correct(year_cs, settings):
    r = verify(year_cs["ghi"], settings)
    assert r["passed"] is True, r
    assert r["onset_tol"] == 1.0 and r["onset_tol_opposite"] < 0.9 and abs(r["pooled"]) < 0.05


def test_verify_wrong_convention(year_cs, settings):
    shifted = year_cs["ghi"].shift(freq=pd.Timedelta(hours=1))
    r = verify(shifted, settings)
    assert abs(r["pooled"]) == pytest.approx(1.0, abs=0.1) and r["passed"] is False


def test_onset_direction(settings):
    ghi = clearsky_hourly("2024-01-01", 60, settings)["ghi"]
    assert onset_rates(ghi, settings, "start")["tol"] == 1.0
    assert onset_rates(ghi, settings, "end")["tol"] < 0.9


def test_night_spike_ignored(settings):
    ghi = clearsky_hourly("2024-01-01", 60, settings)["ghi"]
    base = onset_rates(ghi, settings)
    ghi = ghi.copy()
    ghi.loc["2024-01-10 20:00"] = 5.0  # night label (IST 01:30) is still zero-masked
    assert onset_rates(ghi, settings) == base


def test_nan_day_excluded(settings):
    ghi = clearsky_hourly("2024-01-01", 10, settings)["ghi"].copy()
    ghi.loc["2024-01-03 10:00"] = np.nan
    assert onset_rates(ghi, settings)["n_days"] == 9


def test_partial_year_not_pooled(year_cs, settings):
    g = pd.concat([year_cs["ghi"], clearsky_hourly("2025-01-01", 60, settings)["ghi"]])
    r = centroid_diff(g, settings)
    assert 2025 in r["per_year"] and r["full_years"] == [2024]


def test_met_lag():
    idx = pd.date_range("2024-01-01", periods=24 * 60, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    nasa = pd.DataFrame({c: np.cumsum(rng.normal(size=len(idx))) for c in ("temp", "pressure")}, index=idx)
    ref = nasa.shift(freq=pd.Timedelta(hours=1))
    assert all(v["best_lag_h"] == 1 for v in met_lag(nasa, ref, None).values())
    assert all(v["best_lag_h"] == 0 for v in met_lag(nasa, nasa, None).values())


@pytest.mark.realdata
@pytest.mark.parametrize("src", ["nasa", "era5", "gfs_hf", "gfs_pr_d1", "gfs_pr_d2", "gfs_pr_d3"])
def test_real_convention(src, settings, raw_root):
    r = verify(load_source(src, settings, raw_root)["ghi"], settings)
    assert r["passed"], r
