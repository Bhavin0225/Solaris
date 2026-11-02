"""Synthetic canonical data with exact interval means (no network)."""

import pandas as pd

from swf.align.canon import CANON_COLS
from swf.physics.common import location

_MET = {
    "temp": 25.0, "rh": 60.0, "pressure": 950.0, "ws10": 4.0, "ws_hub": 6.5,
    "wd10": 180.0, "wd_hub": 180.0, "precip": 0.0, "cloud": 0.0,
}  # fmt: skip


def clearsky_hourly(start, days, s, *, convention="start"):
    minutes = pd.date_range(start, periods=days * 24 * 60, freq="min", tz="UTC")
    cs = location(s).get_clearsky(minutes + pd.Timedelta(seconds=30), model="ineichen")
    cs = cs.set_axis(minutes)[["ghi", "dni", "dhi"]]
    out = cs.resample("1h").mean().astype("float64")
    if convention == "end":
        out.index = out.index + pd.Timedelta(hours=1)
    out.index.name = "time"
    return out


def canon_frame(start, days, s, *, convention="start"):
    df = clearsky_hourly(start, days, s, convention=convention)
    for k, v in _MET.items():
        df[k] = v
    return df[list(CANON_COLS)]
