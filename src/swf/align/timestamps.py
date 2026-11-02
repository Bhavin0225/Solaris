"""Timestamp-convention verifier (ALIGN-02, D-13). Canonical frames are start-labelled, so "start" is tested."""

import numpy as np
import pandas as pd

from swf.physics.common import clearsky, is_night, location

ONSET_MIN = 0.90
CENTROID_TOL_H = 0.15
FULL_YEAR_MIN_VALID = 0.90


def onset_rates(ghi: pd.Series, s, convention: str = "start") -> dict:
    g = ghi.where(~is_night(ghi.index, s), 0.0)
    # complete UTC days only (all 24 values present)
    full = g.groupby(g.index.normalize()).filter(lambda x: len(x) == 24 and x.notna().all())
    if full.empty:
        return {"exact": float("nan"), "tol": float("nan"), "n_days": 0}
    days = pd.DatetimeIndex(full.index.normalize().unique())
    pos = full.groupby(full.index.normalize()).apply(lambda x: int(np.argmax(x.to_numpy() > 0)) if (x > 0).any() else -1)
    sunrise = location(s).get_sun_rise_set_transit(days, method="spa")["sunrise"]
    # shortcut: assumes local daylight does not cross 00:00 UTC (true at this longitude), use circular hour maths if the site moves far west
    exp = sunrise.dt.floor("h").dt.hour.to_numpy() + (1 if convention == "end" else 0)
    diff = pos.reindex(days).to_numpy() - exp
    ok = pos.reindex(days).to_numpy() >= 0
    return {
        "exact": float(((diff == 0) & ok).mean()),
        "tol": float((np.isin(diff, (0, 1)) & ok).mean()),
        "n_days": len(days),
    }


def _centroid(obs: pd.Series, cs: pd.Series) -> float:
    h = obs.index.hour
    mo = obs.groupby(h).mean()
    mc = cs.groupby(h).mean()
    c = lambda m: float((m.index.to_numpy() * m.to_numpy()).sum() / m.sum()) if m.sum() > 0 else float("nan")
    return c(mo) - c(mc)


def centroid_diff(ghi: pd.Series, s) -> dict:
    g = ghi.where(~is_night(ghi.index, s), 0.0)
    per_year, full_years, rows = {}, [], []
    for y, grp in g.groupby(g.index.year):
        valid = grp.dropna()
        if valid.empty:
            continue
        per_year[int(y)] = _centroid(valid, clearsky(valid.index, s)["ghi"])
        spans = valid.index.month.min() == 1 and valid.index.month.max() == 12
        if spans and len(valid) / len(grp) >= FULL_YEAR_MIN_VALID:
            full_years.append(int(y))
            rows.append(valid)
    pooled = float("nan")
    if rows:
        v = pd.concat(rows)
        pooled = _centroid(v, clearsky(v.index, s)["ghi"])
    return {"per_year": per_year, "full_years": full_years, "pooled": pooled}


def verify(ghi: pd.Series, s) -> dict:
    on = onset_rates(ghi, s, "start")
    opp = onset_rates(ghi, s, "end")
    cd = centroid_diff(ghi, s)
    passed = bool(
        on["tol"] >= ONSET_MIN and opp["tol"] < ONSET_MIN and abs(cd["pooled"]) <= CENTROID_TOL_H
    )  # NaN pooled -> comparison False -> not passed
    return {
        "onset_exact": on["exact"],
        "onset_tol": on["tol"],
        "onset_tol_opposite": opp["tol"],
        "n_days": on["n_days"],
        "per_year": cd["per_year"],
        "full_years": cd["full_years"],
        "pooled": cd["pooled"],
        "passed": passed,
    }


def met_lag(nasa: pd.DataFrame, ref: pd.DataFrame, s, cols=("temp", "pressure"), lags=range(-2, 3), years=None) -> dict:
    if years is not None:
        nasa = nasa[nasa.index.year.isin(list(years))]
    out = {}
    for c in cols:
        corr = {}
        for k in lags:
            r = ref[c].shift(freq=pd.Timedelta(hours=-k))  # r(t) = ref(t + k)
            corr[k] = float(pd.concat([nasa[c], r], axis=1, sort=False).dropna().corr().iloc[0, 1])
        out[c] = {"best_lag_h": max(corr, key=corr.get), "corr": corr}
    return out
