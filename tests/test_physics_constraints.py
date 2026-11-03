import numpy as np
import pandas as pd

from swf.physics.constraints import enforce

IDX = pd.DatetimeIndex(["2024-03-21 00:00", "2024-03-21 06:00"], tz="UTC")  # night, day


def frame(**cols):
    return pd.DataFrame({k: [v[0], v[1]] for k, v in cols.items()}, index=IDX)


def test_bounds(settings):
    df = frame(
        t1_kw=(100, 900), t5_kw=(-1, 4000), rh=(-3, 104),
        ghi=(50, -2), ws10=(-0.1, 3), ws_hub=(3, -0.2),
    )  # fmt: skip
    out = enforce(df, settings)
    assert out["t1_kw"].tolist() == [0, 800.0]
    assert out["t5_kw"].tolist() == [0, 3600]
    assert out["rh"].tolist() == [0, 100]
    assert out["ghi"].tolist() == [0, 0]
    assert out["ws10"].tolist() == [0, 3]
    assert out["ws_hub"].tolist() == [3, 0]


def test_nan_idempotent_nomutate(settings):
    df = frame(t1_kw=(np.nan, -5), ghi=(np.nan, 10))
    orig = df.copy()
    out = enforce(df, settings)
    assert np.isnan(out["t1_kw"].iloc[0]) and np.isnan(out["ghi"].iloc[0])
    pd.testing.assert_frame_equal(df, orig)
    pd.testing.assert_frame_equal(enforce(out, settings), out)


def test_partial_frame(settings):
    assert enforce(frame(rh=(-1, 101)), settings)["rh"].tolist() == [0, 100]
