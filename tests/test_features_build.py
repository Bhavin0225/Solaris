import numpy as np
import pandas as pd
import pytest
from synth import canon_frame, hist_frame, pr_trio

from swf.align.adapters import openmeteo_canon
from swf.align.clean import clean
from swf.align.consistency import apply_correction, load_coefs
from swf.core.settings import load_features_cfg
from swf.features.build import (
    assemble,
    check_hourly,
    covariate_table,
    history_input,
    iter_features,
    origin_table,
    serve_features,
    target_table,
)
from swf.features.spec import COVARIATE_COLS, feature_columns, history_cols
from swf.physics.wind import load_power_curve

CFG = load_features_cfg()
START = "2024-06-01"


@pytest.fixture(scope="module")
def tabs():
    from swf.core.settings import load_settings

    s = load_settings()
    hist = hist_frame(START, 20, s)
    return s, hist, origin_table(hist, CFG, s), target_table(pd.date_range(START, periods=24 * 24, freq="h", tz="UTC"), CFG, s)


def test_check_hourly():
    good = pd.date_range(START, periods=5, freq="h", tz="UTC")
    check_hourly(good)
    for bad in (
        good.tz_localize(None),
        good.tz_convert("Asia/Kolkata"),
        good[::-1],
        good.append(good[:1]),
        good.delete(2),
    ):
        with pytest.raises(ValueError):
            check_hourly(bad)


def test_origin_table(tabs):
    s, hist, o, _ = tabs
    assert list(o.columns) == history_cols(CFG) and (o.dtypes == np.float32).all()
    t = hist.index[300]
    assert o.loc[t, "ws10_lag24"] == np.float32(hist.ws10[t - pd.Timedelta(hours=24)])
    assert o.loc[t, "ws10_lag0"] == np.float32(hist.ws10[t])
    w = hist.rh.iloc[300 - 23 : 301]
    assert o.loc[t, "rh_roll24_mean"] == pytest.approx(w.mean(), rel=1e-6)
    assert o.loc[t, "rh_roll24_std"] == pytest.approx(w.std(ddof=1), rel=1e-5)
    assert o["rh_roll24_mean"].iloc[:23].isna().all() and o["rh_roll24_mean"].iloc[23:].notna().all()
    assert o["ws10_lag168"].iloc[:168].isna().all()
    h2 = hist.copy()
    h2.iloc[290, h2.columns.get_loc("rh")] = np.nan
    assert np.isnan(origin_table(h2, CFG, s).loc[t, "rh_roll24_mean"])
    noon = hist.index[300 // 24 * 24 + 6]  # 06 UTC = midday IST
    assert o.loc[noon, "csi_hist"] > 0.5
    assert o.loc[hist.index[0], "csi_hist"] == 0.0


def test_target_table(tabs):
    _, _, _, tt = tabs
    np.testing.assert_allclose(tt.hour_sin**2 + tt.hour_cos**2, 1, atol=1e-6)
    np.testing.assert_allclose(tt.doy_sin**2 + tt.doy_cos**2, 1, atol=1e-6)
    assert (tt.monsoon == tt.index.month.isin([6, 7, 8, 9]).astype(float)).all()
    assert not {"doy", "dayofyear", "azimuth", "wd10", "wd_hub"} & set(tt.columns)


def test_covariate_table(settings):
    c = canon_frame(START, 3, settings)
    c["wd10"] = 90.0
    coefs = load_coefs()
    ct = covariate_table(c, settings, coefs, CFG)
    assert list(ct.columns) == COVARIATE_COLS
    ac = apply_correction(c, coefs, settings)
    np.testing.assert_allclose(ct.cov_rh, ac.rh, rtol=1e-6)
    np.testing.assert_allclose(ct.cov_ws10, ac.ws10, rtol=1e-6)
    np.testing.assert_allclose(ct.cov_ws_hub, ac.ws_hub, rtol=1e-6)
    np.testing.assert_allclose(ct.cov_ghi, c.ghi, rtol=1e-6)
    np.testing.assert_allclose(ct.cov_wd10_sin, np.sin(np.radians(90)), atol=1e-6)
    assert ct.cov_csi.iloc[0] == 0.0


def test_assemble(tabs, settings):
    s, hist, o, tt = tabs
    origins = hist.index[200:204]
    a = assemble(o, tt, origins, cfg=CFG)
    assert list(a.columns) == feature_columns("weather_only") and (a.dtypes == np.float32).all()
    assert len(a) == 4 * 72 and a.index.names == ["issue_time", "horizon"]
    t, h = origins[1], 30
    row = a.loc[(t, h)]
    assert row["rh_lag24"] == o.loc[t, "rh_lag24"] and row["zenith"] == tt.loc[t + pd.Timedelta(hours=h), "zenith"]
    assert row["horizon"] == h
    trio = pr_trio(START, 20, s)
    coefs = load_coefs()
    cd = {k: covariate_table(v, s, coefs, CFG) for k, v in trio.items()}
    b = assemble(o, tt, origins, cov=cd, cfg=CFG)
    assert list(b.columns) == feature_columns("covariate")
    for h, k in ((1, 1), (24, 1), (25, 2), (48, 2), (49, 3), (72, 3)):
        T = origins[0] + pd.Timedelta(hours=h)
        assert b.loc[(origins[0], h), "cov_ws10"] == cd[k].loc[T, "cov_ws10"]
    st = assemble(o, tt, origins, cov=cd[2], cfg=CFG)
    assert st.loc[(origins[0], 1), "cov_ws10"] == cd[2].loc[origins[0] + pd.Timedelta(hours=1), "cov_ws10"]


def test_assemble_raises(tabs):
    s, hist, o, tt = tabs
    with pytest.raises(ValueError):
        assemble(o, tt, [pd.Timestamp("2020-01-01", tz="UTC")], cfg=CFG)
    with pytest.raises(ValueError):
        assemble(o, tt, [tt.index[-10]], cfg=CFG)
    coefs = load_coefs()
    cd = {k: covariate_table(v, s, coefs, CFG) for k, v in pr_trio(START, 20, s).items()}
    del cd[3]
    with pytest.raises(ValueError):
        assemble(o, tt, hist.index[200:201], cov=cd, cfg=CFG)


def test_iter_equals_assemble(tabs):
    _, hist, o, tt = tabs
    origins = hist.index[200:220]
    pd.testing.assert_frame_equal(pd.concat(list(iter_features(o, tt, origins, cfg=CFG, chunk=7))), assemble(o, tt, origins, cfg=CFG))


def test_history_input(settings):
    raw = canon_frame(START, 3, settings)
    noon = raw.index[5:8]  # 05-07 UTC, daytime
    raw.loc[noon, "ws10"] = np.nan
    raw.loc[raw.index[16], "ghi"] = np.nan  # night: cleaner zeroes it
    raw = raw.drop(raw.index[40])
    cleaned = clean(raw, settings, source="history")[0]
    assert not cleaned.loc[noon, "ws10"].isna().any()  # clean alone interpolates
    out = history_input(raw, settings)
    assert out.loc[noon, "ws10"].isna().all()
    assert out.iloc[16]["ghi"] == 0.0
    assert out.iloc[40].drop(["ghi", "dni", "dhi"]).isna().all()  # night radiation stays 0
    keep = out.index.difference(noon).difference(out.index[[40]])
    pd.testing.assert_frame_equal(out.loc[keep], cleaned.loc[keep])


def test_serve_features(settings, fixtures_dir):
    raw = (fixtures_dir / "om_live_gfs_seamless.json").read_bytes()
    canon = clean(openmeteo_canon(raw, settings), settings, source="live")[0]
    coefs, curve = load_coefs(), load_power_curve(settings)
    lo = canon.index[0] + pd.Timedelta(hours=max(CFG.lags))
    hi = canon.index[-1] - pd.Timedelta(hours=CFG.horizon_max)
    for T in (lo, hi):
        f = serve_features(raw, settings, CFG, coefs, curve, T)
        assert len(f) == 72 and list(f.columns) == feature_columns("covariate")
    with pytest.raises(ValueError, match="history"):
        serve_features(raw, settings, CFG, coefs, curve, canon.index[0] + pd.Timedelta(hours=100))
    with pytest.raises(ValueError, match="72 h"):
        serve_features(raw, settings, CFG, coefs, curve, canon.index[-1] - pd.Timedelta(hours=10))
