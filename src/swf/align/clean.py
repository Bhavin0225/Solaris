"""Cleaning (ALIGN-03/04): complete hourly index, physical clipping, night-zeroing, <= max_gap_h fill (D-11)."""

import logging

import numpy as np
import pandas as pd

from swf.align.canon import CANON_COLS, PHYS_RANGES, validate_canon
from swf.physics.common import clearsky, is_night

log = logging.getLogger("swf.align")

REPORT_COLS = ("source", "variable", "year", "pct_missing_before", "pct_missing_after", "clipped_low", "clipped_high", "night_zeroed")  # fmt: skip
RADIATION = ("ghi", "dni", "dhi")
KT_MAX = 1.5
DIRECTION = ("wd10", "wd_hub")
MET = ("temp", "rh", "pressure", "ws10", "ws_hub", "precip", "cloud")


def short_gap_mask(x: pd.Series, max_len: int) -> pd.Series:
    """True on NaN rows inside interior NaN runs of length <= max_len."""
    na = x.isna()
    run = (~na).cumsum()
    length = na.groupby(run).transform("sum")
    has_before = run > 0
    has_after = (~na)[::-1].cumsum()[::-1] > 0
    return na & (length <= max_len) & has_before & has_after


def _interp(x: pd.Series) -> pd.Series:
    return x.interpolate(method="time", limit_area="inside")


def _fill_gaps(df: pd.DataFrame, s) -> pd.DataFrame:
    n = s.align.max_gap_h
    out = df.copy()
    night = is_night(df.index, s)
    cs_all = clearsky(df.index, s)
    for c in MET:  # mask instead of limit= so long gaps are not partially filled
        m = short_gap_mask(df[c], n)
        out[c] = df[c].where(~m, _interp(df[c]))
    for c in DIRECTION:  # interpolate sin/cos so 350 -> 10 passes through 0
        m = short_gap_mask(df[c], n)
        rad = np.deg2rad(df[c])
        ang = np.rad2deg(np.arctan2(_interp(np.sin(rad)), _interp(np.cos(rad)))) % 360
        out[c] = df[c].where(~m, ang)
    for c in RADIATION:
        x = df[c]
        gap = short_gap_mask(x, n)
        allnight = (night | x.notna()).groupby(x.notna().cumsum()).transform("all")
        cs = cs_all[c]
        # kt is NaN at night/twilight, so a gap touching sunrise/sunset merges with the night run and stays NaN
        kt = (x / cs).where(cs > 5).clip(upper=KT_MAX)  # cap: kt blows up near the horizon
        ok = gap & ~allnight & short_gap_mask(kt, n)
        filled = (_interp(kt) * cs).clip(0, PHYS_RANGES[c][1])
        out[c] = x.where(~ok, filled).where(~(gap & allnight), 0.0)
    return out


def _pct_missing(df: pd.DataFrame) -> pd.DataFrame:
    return df.isna().groupby(df.index.year).mean() * 100


def clean(df, s, *, source, start=None, end=None):
    idx = pd.date_range(
        start if start is not None else df.index.min(),
        end if end is not None else df.index.max(),
        freq="h", tz="UTC", name="time",
    )  # fmt: skip
    d = df.reindex(idx)
    before = _pct_missing(d)
    miss_before = d.isna().to_numpy().mean()

    lo = pd.Series({c: PHYS_RANGES[c][0] for c in CANON_COLS})
    hi = pd.Series({c: PHYS_RANGES[c][1] for c in CANON_COLS})
    low, high = d.lt(lo, axis=1), d.gt(hi, axis=1)
    d = d.clip(lower=lo, upper=hi, axis=1)

    night = is_night(d.index, s)
    nz = pd.DataFrame(False, index=d.index, columns=list(CANON_COLS))
    for c in RADIATION:
        nz[c] = night & (d[c] > 0)
        d.loc[night & d[c].notna(), c] = 0.0

    d = _fill_gaps(d, s)
    d.loc[night, list(RADIATION)] = 0.0  # radiation at night is physically 0, whatever the gap length
    after = _pct_missing(d)
    validate_canon(d)
    if not (d.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("cleaned index is not evenly hourly")

    yr = d.index.year
    rows = [
        (source, c, int(y), before.loc[y, c], after.loc[y, c],
         int(low[c][yr == y].sum()), int(high[c][yr == y].sum()), int(nz[c][yr == y].sum()))
        for c in CANON_COLS for y in before.index
    ]  # fmt: skip
    rep = pd.DataFrame(rows, columns=list(REPORT_COLS))
    log.info(
        "clean source=%s rows=%d missing_before=%.3f missing_after=%.3f clipped=%d night_zeroed=%d",
        source, len(d), miss_before, d.isna().to_numpy().mean(),
        int(low.sum().sum() + high.sum().sum()), int(nz.sum().sum()),
    )  # fmt: skip
    return d, rep
