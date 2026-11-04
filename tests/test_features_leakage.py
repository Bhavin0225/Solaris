"""FEAT-05: no feature at origin t reads data after t, except the covariate at t + h.

Scope note: the stitched Historical Forecast covariate exemption is a documented train/serve skew
(training sees a short-lead analysis issued near t + h, serving sees a day 1-3 lead), not a causal proof.
These tests only prove the builder reads the covariate row at exactly t + h; Plan 06 quantifies the skew
as the stitched-vs-lead-matched RMSE gap on validation.
"""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal
from synth import canon_frame, hist_frame, pr_trio

from swf.align.clean import clean
from swf.align.consistency import load_coefs
from swf.core.settings import load_features_cfg
from swf.features.build import (
    assemble,
    covariate_table,
    history_input,
    origin_table,
    target_table,
)
from swf.features.history import history_frame
from swf.features.spec import COVARIATE_COLS, history_cols
from swf.physics.wind import load_power_curve

CFG = load_features_cfg()
H = [1, 24, 72]


def _after(df, t, fn):
    """Copy of df with every row strictly after t replaced by fn(shape)."""
    later = np.asarray(df.index > t)[:, None]
    return pd.DataFrame(np.where(later, fn(df.shape), df.to_numpy()), index=df.index, columns=df.columns)


@pytest.fixture(scope="module")
def s():
    from swf.core.settings import load_settings

    return load_settings()


@pytest.fixture(scope="module")
def hist(s):
    return hist_frame("2024-01-01", 40, s)


@pytest.fixture(scope="module")
def full(hist, s):
    return origin_table(hist, CFG, s)


def _origins(hist):
    rng = np.random.default_rng(0)
    pick = rng.choice(np.arange(168, len(hist)), 25, replace=False)
    ts = list(hist.index[pick]) + [hist.index[168], pd.Timestamp("2024-02-01 00:00", tz="UTC"), hist.index[-1]]
    return sorted(set(ts))


def test_truncation_and_perturbation(hist, full, s):
    rng = np.random.default_rng(1)
    for t in _origins(hist):
        trunc = origin_table(hist.loc[:t], CFG, s)
        assert_series_equal(trunc.loc[t], full.loc[t], check_exact=True)
        pert = _after(hist, t, lambda sh: rng.normal(size=sh) * 1e6)
        assert_series_equal(origin_table(pert, CFG, s).loc[t], full.loc[t], check_exact=True)


def test_history_frame_causal(s):
    canon = canon_frame("2024-01-01", 10, s)
    curve = load_power_curve(s)
    t = canon.index[100]
    pert = _after(canon, t, lambda sh: np.random.default_rng(2).uniform(1, 1000, sh))
    a = history_frame(pert, s, curve, None).loc[:t]
    b = history_frame(canon, s, curve, None).loc[:t]
    assert_frame_equal(a, b, check_exact=True)


@pytest.fixture(scope="module")
def cov_setup(hist, s):
    canon = canon_frame("2024-01-01", 40, s)
    cov = covariate_table(canon, s, load_coefs(), CFG)
    return cov, target_table(hist.index, CFG, s)


def test_target_axis_sensitivity(hist, full, cov_setup):
    cov, tt = cov_setup
    t = hist.index[400]
    hc = history_cols(CFG)
    base = assemble(full, tt, [t], H, cov=cov, cfg=CFG)
    for h in H:
        T = t + pd.Timedelta(hours=h)
        other = cov.copy()
        keep = other.index == T
        other.loc[~keep] = other.loc[~keep] + 123.0
        a = assemble(full, tt, [t], H, cov=other, cfg=CFG)
        assert_series_equal(a.loc[(t, h)], base.loc[(t, h)], check_exact=True)
        hit = cov.copy()
        hit.loc[T] = hit.loc[T] + 123.0
        b = assemble(full, tt, [t], H, cov=hit, cfg=CFG)
        assert not (b.loc[(t, h), COVARIATE_COLS] == base.loc[(t, h), COVARIATE_COLS]).all()
        assert_series_equal(b.loc[(t, h), hc], base.loc[(t, h), hc], check_exact=True)


def test_history_columns_ignore_post_origin(hist, full, s, cov_setup):
    cov, tt = cov_setup
    t = hist.index[400]
    hc = history_cols(CFG)
    pert = _after(hist, t, lambda sh: np.random.default_rng(3).normal(size=sh) * 1e6)
    a = assemble(origin_table(pert, CFG, s), tt, [t], range(1, 73), cov=cov, cfg=CFG)
    b = assemble(full, tt, [t], range(1, 73), cov=cov, cfg=CFG)
    assert_frame_equal(a[hc], b[hc], check_exact=True)


def test_lead_matched_ignores_other_leads(hist, full, s):
    tt = target_table(hist.index, CFG, s)
    coefs = load_coefs()
    trio = {k: covariate_table(v, s, coefs, CFG) for k, v in pr_trio("2024-01-01", 40, s).items()}
    t = hist.index[400]
    base = assemble(full, tt, [t], range(1, 73), cov=trio, cfg=CFG)
    hs = base.index.get_level_values("horizon")
    for ks, m in (((2, 3), hs <= 24), ((1,), hs > 24)):
        alt = {k: (v + 50.0 if k in ks else v) for k, v in trio.items()}
        a = assemble(full, tt, [t], range(1, 73), cov=alt, cfg=CFG)
        assert_frame_equal(a[m], base[m], check_exact=True)


def test_gap_straddling_origin_does_not_leak(s):
    raw = canon_frame("2024-03-01", 15, s)
    curve, coefs = load_power_curve(s), load_coefs()
    t = pd.Timestamp("2024-03-09 06:00", tz="UTC")  # 11:30 IST, daytime
    assert (t - raw.index[0]) >= pd.Timedelta(hours=169)
    gap = [t - pd.Timedelta(hours=1), t, t + pd.Timedelta(hours=1)]
    assert len(gap) <= s.align.max_gap_h
    raw = raw.copy()
    raw.loc[gap, ["rh", "ws10"]] = np.nan
    after = raw.index > t + pd.Timedelta(hours=1)
    fac = np.random.default_rng(4).uniform(0.2, 3.0, (after.sum(), raw.shape[1]))
    pert = raw.copy()
    pert.loc[after] = raw.loc[after].to_numpy() * fac

    def build(r, inp):
        return origin_table(history_frame(inp(r), s, curve, coefs), CFG, s).loc[t]

    def hi(r):
        return history_input(r, s)

    def plain(r):
        return clean(r, s, source="history")[0]

    a, b = build(raw, hi), build(pert, hi)
    assert_series_equal(a, b, check_exact=True)
    assert np.isnan(a[["rh_lag0", "rh_lag1", "ws10_lag0", "ws10_lag1"]]).all()
    # sensitivity: plain clean() interpolation fills the gap from post-origin labels
    assert build(raw, plain)["rh_lag1"] != build(pert, plain)["rh_lag1"]
