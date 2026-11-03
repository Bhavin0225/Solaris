import logging

import numpy as np
import pandas as pd
from synth import canon_frame

from swf.align.canon import CANON_COLS, PHYS_RANGES
from swf.align.clean import REPORT_COLS, clean, short_gap_mask
from swf.physics.common import is_night


def _nan(n, runs):
    x = pd.Series(1.0, index=pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC"))
    for a, b in runs:
        x.iloc[a:b] = np.nan
    return x


def test_short_gap_mask():
    m = short_gap_mask(_nan(30, [(0, 2), (5, 8), (12, 16), (28, 30)]), 3)
    assert m.iloc[5:8].all() and m.sum() == 3


def test_reindex_no_mutation(settings):
    d = canon_frame("2024-03-20", 3, settings)
    orig = d.copy()
    out, rep = clean(d.drop(d.index[[10, 11]]), settings, source="t")
    assert (out.index == d.index).all() and out.index.name == "time"
    assert tuple(rep.columns) == REPORT_COLS
    assert set(rep["variable"]) == set(CANON_COLS)
    out2, rep2 = clean(d, settings, source="t", start=d.index[0] - pd.Timedelta(hours=5))
    assert out2["temp"].iloc[:5].isna().all()  # leading never filled
    assert rep2["pct_missing_after"].max() > 0
    pd.testing.assert_frame_equal(d, orig)


def test_clip_nightzero_log(settings, caplog):
    d = canon_frame("2024-03-20", 3, settings)
    nt = is_night(d.index, settings).to_numpy()
    night = int(np.flatnonzero(nt)[0])
    day = int(np.flatnonzero(~nt & (d["ghi"] > 100).to_numpy())[0])
    d.iloc[night, [0, 1, 2]] = [12.0, 30.0, 8.0]
    d.iloc[40, d.columns.get_loc("rh")] = 105
    d.iloc[41, d.columns.get_loc("ws10")] = -1
    g = d["ghi"].iloc[day]
    _, base = clean(canon_frame("2024-03-20", 3, settings), settings, source="t")
    with caplog.at_level(logging.INFO, logger="swf.align"):
        out, rep = clean(d, settings, source="t")
    assert out["rh"].iloc[40] == 100 and out["ws10"].iloc[41] == 0
    r = rep.set_index("variable")
    assert r.loc["rh", "clipped_high"].sum() == 1 and r.loc["ws10", "clipped_low"].sum() == 1
    b = base.set_index("variable")
    assert [r.loc[c, "night_zeroed"].sum() - b.loc[c, "night_zeroed"].sum() for c in ("ghi", "dni", "dhi")] == [1, 1, 1]
    assert out.iloc[night][["ghi", "dni", "dhi"]].eq(0).all() and out["ghi"].iloc[day] == g
    assert len([m for m in caplog.messages if m.startswith("clean source=")]) == 1


def _gap(settings, col, a, n, ramp=False):
    d = canon_frame("2024-03-20", 3, settings)
    if ramp:
        d[col] = np.arange(len(d), dtype=float)
    ref = d.copy()
    d.iloc[a : a + n, d.columns.get_loc(col)] = np.nan
    return ref, d


def test_midday_refill(settings):
    ref, d = _gap(settings, "ghi", 29, 2)
    d.iloc[29:31, [1, 2]] = np.nan
    out, _ = clean(d, settings, source="t")
    for c in ("ghi", "dni", "dhi"):
        assert np.allclose(out[c].iloc[29:31], ref[c].iloc[29:31], rtol=0.02)


def test_sunrise_sunset_stay_nan(settings):
    ref = canon_frame("2024-03-20", 3, settings)
    day = np.flatnonzero(~is_night(ref.index, settings).to_numpy()[24:48]) + 24
    for a in (day[0] - 1, day[-1] - 1):
        _, d = _gap(settings, "ghi", int(a), 3)
        out, _ = clean(d, settings, source="t")
        seg, nt = out["ghi"].iloc[a : a + 3], is_night(out.index, settings)[a : a + 3]
        assert seg[~nt].isna().all() and (seg[nt] == 0).all()  # night hours are 0, daylight stays NaN


def test_night_gap_zero(settings):
    _, d = _gap(settings, "ghi", 14, 2)
    d.iloc[14:16, [1, 2]] = np.nan
    out, _ = clean(d, settings, source="t")
    assert (out[["ghi", "dni", "dhi"]].iloc[14:16] == 0).all().all()


def test_temp_linear_and_long(settings):
    _, d = _gap(settings, "temp", 10, 2, ramp=True)
    out, rep = clean(d, settings, source="t")
    assert np.allclose(out["temp"].iloc[10:12], [10, 11])
    t = rep[rep.variable == "temp"]
    assert t["pct_missing_before"].iloc[0] > 0 and t["pct_missing_after"].iloc[0] == 0
    _, d4 = _gap(settings, "temp", 10, 4, ramp=True)
    out4, _ = clean(d4, settings, source="t")
    assert out4["temp"].iloc[10:14].isna().all()


def test_wind_direction_wraps(settings):
    d = canon_frame("2024-03-20", 3, settings)
    d["wd10"] = np.where(np.arange(len(d)) < 10, 350.0, 10.0)
    d.iloc[10:12, d.columns.get_loc("wd10")] = np.nan
    d.iloc[9, d.columns.get_loc("wd10")] = 350.0
    out, _ = clean(d, settings, source="t")
    assert np.allclose(out["wd10"].iloc[10:12], [356.7, 3.3], atol=0.1)


def test_leading_block_stays_nan(settings):
    d = canon_frame("2024-03-20", 3, settings)
    d.iloc[:5] = np.nan
    out, _ = clean(d, settings, source="t")
    assert out["temp"].iloc[:5].isna().all()


def test_long_midday_gap_stays_nan(settings):
    _, d = _gap(settings, "ghi", 28, 4)
    out, _ = clean(d, settings, source="t")
    assert out["ghi"].iloc[28:32].isna().all()


def test_trailing_gap_stays_nan(settings):
    d = canon_frame("2024-03-20", 3, settings)
    d.iloc[-2:, d.columns.get_loc("temp")] = np.nan
    out, _ = clean(d, settings, source="t")
    assert out["temp"].iloc[-2:].isna().all()


def test_filled_values_clipped(settings):
    _, d = _gap(settings, "rh", 10, 2)
    out, _ = clean(d, settings, source="t")
    assert out["rh"].iloc[10:12].eq(60.0).all()


def test_long_night_gap_zero_and_fill_capped(settings):
    _, d = _gap(settings, "ghi", 0, 8)  # starts at night, longer than max_gap_h
    out, _ = clean(d, settings, source="t")
    assert (out["ghi"].iloc[:8][is_night(out.index, settings)[:8]] == 0).all()
    assert (out["ghi"].dropna() <= PHYS_RANGES["ghi"][1]).all()
