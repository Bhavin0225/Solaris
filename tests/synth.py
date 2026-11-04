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


def hist_frame(start, days, s, seed=0):
    import numpy as np

    from swf.features.history import history_frame
    from swf.physics.wind import load_power_curve

    h = history_frame(canon_frame(start, days, s), s, load_power_curve(s), None)
    rng = np.random.default_rng(seed)
    h["rh"] = (h["rh"] + rng.normal(0, 3, len(h))).clip(0, 100)
    h["ws10"] = (h["ws10"] + rng.normal(0, 0.5, len(h))).clip(0)
    return h


def pr_trio(start, days, s):
    out = {}
    for k in (1, 2, 3):
        d = canon_frame(start, days, s)
        d["ws10"] += 0.1 * k
        out[k] = d
    return out
