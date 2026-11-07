import numpy as np
import pandas as pd
import pytest

from swf.physics.solar import ac_cap_kw
from swf.predict.bands import band_frame, bucket_label, residual_offsets

B = [(1, 6), (7, 24), (25, 72)]


def test_bucket_label():
    assert bucket_label(5, B) == "1-6"
    assert bucket_label(24, B) == "7-24"
    with pytest.raises(ValueError):
        bucket_label(73, B)


def test_residual_offsets():
    rng = np.random.default_rng(0)
    n = 60000
    h = rng.integers(1, 73, n)
    p = rng.normal(size=n)
    y = p + rng.normal(size=n)
    off = residual_offsets(y, p, h, np.ones(n, bool), B)
    for lab in ("1-6", "7-24", "25-72"):
        assert off[lab][0] == pytest.approx(-1.2816, abs=0.1)
        assert off[lab][1] == pytest.approx(1.2816, abs=0.1)
    y[:5] = np.nan
    mask = np.ones(n, bool)
    mask[h <= 6] = False
    assert residual_offsets(y, p, h, mask, B)["1-6"] == [0.0, 0.0]


def test_band_ordering_and_bounds(settings):
    idx = pd.DatetimeIndex(["2024-06-01T06:00Z", "2024-06-01T18:00Z"])
    f = band_frame(pd.Series([100.0, 50.0], index=idx), 5.0, 8.0, "t1_kw", settings)
    assert (f.p10 <= f.p50).all() and (f.p50 <= f.p90).all()
    assert f.p50.iloc[0] == 100.0
    assert (f.iloc[1] == 0).all()  # night
    f = band_frame(pd.Series([1e9], index=idx[:1]), -1.0, 1.0, "t1_kw", settings)
    assert f.p90.iloc[0] <= ac_cap_kw(settings)
    g = band_frame(pd.Series([95.0], index=idx[:1]), -10.0, 10.0, "rh", settings)
    assert g.p90.iloc[0] == 100.0 and g.p10.iloc[0] == 85.0
    g = band_frame(pd.Series([40.0], index=idx[:1]), 3.0, 5.0, "ghi", settings)
    assert g.p10.iloc[0] == 40.0
