import types

import numpy as np
import pandas as pd
import pytest

from swf.evaluate.longfmt import make_long
from swf.evaluate.prob import pinball, prob_metrics, prob_rows, reliability

CFG = types.SimpleNamespace(eval=types.SimpleNamespace(daytime_zenith_deg=85.0))


def test_pinball():
    assert pinball([1, 2, 3], [2, 2, 2], 0.1) == pytest.approx(1 / 3)


def test_prob_metrics_and_reliability():
    y, p10, p50, p90 = [0, 1, 2, 3], [-1, 0, 0, 4], [0, 1, 1, 4], [1, 2, 1, 5]
    m = prob_metrics(y, p10, p50, p90)
    assert m["coverage"] == 0.5 and m["width"] == 1.5 and m["n"] == 4
    assert reliability(y, p10, p50, p90) == [(0.1, 0.25), (0.5, 0.75), (0.9, 0.75)]
    assert np.isnan(prob_metrics([], [], [], [])["coverage"])


def _f(model, target, issue, y, p10, p50, p90):
    n = len(y)
    return make_long(pd.DatetimeIndex(issue), [1] * n, target, model, y, p50, p10, p90)


def test_prob_rows_shared_and_daytime(settings):
    # 06:00 UTC is day at Davanagere, 18:00 UTC (23:30 IST) is night
    iss = ["2024-06-01 05:00", "2024-06-01 06:00", "2024-06-01 17:00"]
    a = _f("a", "t1_kw", iss, [1, 2, 3], [0, 1, 2], [1, 2, 3], [2, 3, 4])
    b = _f("b", "t1_kw", iss, [1, 2, 3], [np.nan, 1, 2], [1, 2, 3], [3, 4, 5])
    r = prob_rows({"a": a, "b": b}, "t1_kw", settings, CFG).set_index("model")
    assert r.loc["a", "n"] == 1 and r.loc["b", "n"] == 1  # nan row and night row dropped from both
    assert r.loc["a", "coverage"] == 1.0 and r.loc["b", "width"] == 3.0
    nb = _f("c", "t1_kw", iss, [1, 2, 3], [np.nan] * 3, [1, 2, 3], [np.nan] * 3)
    with pytest.raises(ValueError, match="c"):
        prob_rows({"a": a, "c": nb}, "t1_kw", settings, CFG)
