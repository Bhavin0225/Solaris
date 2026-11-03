import pandas as pd
import pytest
from synth import canon_frame

from swf.align.adapters import openmeteo_canon
from swf.align.clean import clean
from swf.align.consistency import apply_correction, load_coefs
from swf.features.history import TARGETS, history_frame
from swf.physics.simulate import simulate
from swf.physics.wind import load_power_curve


@pytest.fixture
def ctx(settings):
    return (
        settings,
        load_power_curve(settings),
        load_coefs(),
        canon_frame("2024-06-01", 3, settings),
    )


def test_corrected_chain(ctx):
    s, curve, coefs, canon = ctx
    out = history_frame(canon, s, curve, coefs)
    assert tuple(out.columns) == TARGETS and out.index.equals(canon.index)
    w = apply_correction(canon, coefs, s)
    e = simulate(w, s, curve)
    pd.testing.assert_series_equal(out["t1_kw"], e["t1_kw"])
    pd.testing.assert_series_equal(out["t5_kw"], e["t5_kw"])
    pd.testing.assert_series_equal(out["rh"], w["rh"].clip(0, 100))
    pd.testing.assert_series_equal(out["ws10"], w["ws10"].clip(lower=0))
    assert (out["ghi"][canon["ghi"] == 0] == 0).all()


def test_raw(ctx):
    s, curve, _, canon = ctx
    out = history_frame(canon, s, curve)
    pd.testing.assert_series_equal(out["rh"], canon["rh"])
    pd.testing.assert_series_equal(out["ws10"], canon["ws10"])
    pd.testing.assert_series_equal(out["t1_kw"], simulate(canon, s, curve)["t1_kw"])


def test_pointwise_and_nan(ctx):
    s, curve, coefs, canon = ctx
    full = history_frame(canon, s, curve, coefs)
    pd.testing.assert_frame_equal(
        history_frame(canon.iloc[:30], s, curve, coefs), full.iloc[:30]
    )
    bad = canon.copy()
    bad.iloc[12, :] = float("nan")  # local noon-ish, and a night row below
    bad.iloc[2, :] = float("nan")
    out = history_frame(bad, s, curve, coefs)
    assert out.iloc[[2, 12]].isna().all().all()


def test_serving_path(ctx, fixtures_dir):
    s, curve, coefs, _ = ctx
    raw = (fixtures_dir / "om_live_gfs_seamless.json").read_bytes()
    canon, _ = clean(openmeteo_canon(raw, s), s, source="live")
    out = history_frame(canon, s, curve, coefs)
    assert len(out) == 264 and not out.isna().any().any()
