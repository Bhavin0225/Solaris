import numpy as np
import pandas as pd
import pytest
from synth import canon_frame, clearsky_hourly

from swf.align.canon import CANON_COLS, PHYS_RANGES, UNITS, validate_canon


def test_freeze():
    assert CANON_COLS == ("ghi", "dni", "dhi", "temp", "rh", "pressure", "ws10", "ws_hub", "wd10", "wd_hub", "precip", "cloud")  # fmt: skip
    assert set(UNITS) == set(PHYS_RANGES) == set(CANON_COLS)
    assert UNITS["pressure"] == "hPa"


def test_valid(settings):
    df = canon_frame("2024-03-21", 2, settings)
    assert validate_canon(df) is df


def _cases(d):
    yield d.drop(columns="rh")
    yield d[["dni", "ghi", *CANON_COLS[2:]]]
    yield d.assign(rh=1)
    yield d.set_axis(d.index.tz_localize(None))
    yield d.set_axis(d.index.tz_convert("Asia/Kolkata"))
    yield d.iloc[[0, 0, *range(1, 5)]]
    yield d.iloc[::-1]
    yield d.set_axis(d.index + pd.Timedelta(minutes=30))
    yield d.assign(temp=np.where(np.arange(len(d)) == 3, -999.0, d["temp"]))


def test_rejects(settings):
    for bad in _cases(canon_frame("2024-03-21", 2, settings)):
        with pytest.raises(ValueError):
            validate_canon(bad)


def test_clearsky_start_label(settings):
    g = clearsky_hourly("2024-03-21", 1, settings)["ghi"]
    assert g.iloc[0] < 0.5 and g.iloc[1] > 10


def test_end_convention(settings):
    a = clearsky_hourly("2024-03-21", 1, settings)
    b = clearsky_hourly("2024-03-21", 1, settings, convention="end")
    assert (b.index == a.index + pd.Timedelta(hours=1)).all()
    assert np.allclose(a.values, b.values)
