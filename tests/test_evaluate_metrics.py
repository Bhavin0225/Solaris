import types
import warnings

import numpy as np
import pandas as pd
import pytest

from swf.evaluate.longfmt import grid, make_long
from swf.evaluate.metrics import (
    align_models,
    breakdown,
    daytime_mask,
    leaderboard_rows,
    metrics,
    norm_for,
    scored_mask,
    skill,
)
from swf.physics.solar import ac_cap_kw

CFG = types.SimpleNamespace(
    monsoon_months=[6, 7, 8, 9],
    eval=types.SimpleNamespace(
        horizons=[1, 6, 24, 48, 72], daytime_zenith_deg=85.0, min_shared_frac=0.5, csi_min_clearsky_wm2=1.0
    ),
)


def test_metrics():
    m = metrics([1, 2, 3, np.nan], [2, 2, 5, 1], norm=4, norm_kind="x")
    assert m["n"] == 3 and m["mae"] == 1.0 and m["mbe"] == 1.0
    assert m["rmse"] == pytest.approx(np.sqrt(5 / 3))
    assert m["nrmse_pct"] == pytest.approx(np.sqrt(5 / 3) / 4 * 100)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        e = metrics([np.nan], [1.0], 1.0, "x")
    assert e["n"] == 0 and np.isnan(e["rmse"]) and np.isnan(e["nrmse_pct"])


def test_norm_for(settings):
    assert norm_for("t1_kw", [1], settings) == (
        ac_cap_kw(settings),
        "solar_ac_capacity_kw",
    )
    assert norm_for("t5_kw", [1], settings) == (settings.wind.rated_kw, "wind_rated_kw")
    assert norm_for("ws10", [2, 4], settings) == (3.0, "mean_actual_shared_sample")


def test_skill():
    assert skill(0.5, 1.0) == 0.5
    assert np.isnan(skill(1.0, 0.0)) and np.isnan(skill(1.0, np.nan))


def test_daytime(settings):
    t = pd.DatetimeIndex(["2024-06-01 06:00", "2024-06-01 20:00"], tz="UTC")
    assert daytime_mask(t, settings, 85.0).tolist() == [True, False]


def _frame(model, target, y, p, origins, horizons):
    i, h, _ = grid(origins, horizons)
    return make_long(i, h, target, model, y, p)


def test_align_and_mask(settings):
    o = pd.DatetimeIndex(["2024-06-01 06:00"], tz="UTC")
    a = _frame("a", "ws10", [1.0, 2.0, 3.0], [1.0, np.nan, 3.0], o, [1, 2, 3])
    b = _frame("b", "ws10", [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], o, [1, 2, 3])
    w = align_models({"a": a, "b": b}, "ws10")
    assert list(w.columns) == ["target_time", "y_true", "a", "b"]
    assert scored_mask(w, ["a", "b"], "ws10", settings, 85.0).tolist() == [
        True,
        False,
        True,
    ]
    bad = _frame("c", "ws10", [1.0, 9.0, 3.0], [0.0] * 3, o, [1, 2, 3])
    with pytest.raises(ValueError):
        align_models({"a": a, "c": bad}, "ws10")


def test_scored_mask_night(settings):
    o = pd.DatetimeIndex(
        ["2024-06-01 17:00"], tz="UTC"
    )  # targets 18:00, 19:00 UTC: night; 06:00 is day
    for tgt, expect in (("ghi", [False, False]), ("rh", [True, True])):
        f = _frame("a", tgt, [1.0, 1.0], [1.0, 1.0], o, [1, 2])
        w = align_models({"a": f}, tgt)
        assert scored_mask(w, ["a"], tgt, settings, 85.0).tolist() == expect


def _three(settings, target="rh"):
    o = pd.date_range("2024-05-20 00:00", "2024-06-30 00:00", freq="12h", tz="UTC")
    i, h, _ = grid(o, range(1, 73))
    rng = np.random.default_rng(0)
    y = rng.uniform(40, 80, len(h))
    errs = {"baseline3": 4.0, "persistence": 8.0, "climatology": 2.0}
    frames = {k: make_long(i, h, target, k, y, y + e) for k, e in errs.items()}
    return align_models(frames, target), list(errs), y


def test_breakdown(settings):
    w, models, y = _three(settings)
    bd = breakdown(w, models, "rh", settings, CFG)
    assert len(bd) == 6 * 3 * 3
    assert set(bd["horizon"]) == {"1", "6", "24", "48", "72", "all"}
    assert set(bd["season"]) == {"monsoon", "dry", "all"}
    assert np.allclose(
        bd["norm"], y.mean(), rtol=1e-5
    )  # mean over full shared sample, every slice
    sl = bd[(bd["horizon"] == "all") & (bd["season"] == "all")].set_index("model")
    assert sl.loc["baseline3", "skill_vs_baseline3"] == 0.0
    assert sl.loc["climatology", "skill_vs_baseline3"] == pytest.approx(0.5)
    assert sl.loc["baseline3", "skill_vs_persistence"] == pytest.approx(0.5)
    assert sl.loc["baseline3", "rmse"] == pytest.approx(4.0, rel=1e-5)
    assert (bd["n"] > 0).all()


def test_breakdown_missing_ref(settings):
    w, _models, _ = _three(settings)
    bd = breakdown(w, ["climatology"], "rh", settings, CFG)
    assert bd["skill_vs_baseline3"].isna().all()


def test_leaderboard(settings):
    w, models, _ = _three(settings)
    lb = leaderboard_rows(w, models, "rh", settings, CFG)
    assert (
        len(lb) == 3
        and (lb["n_own"] == lb["n_shared"]).all()
        and (lb["shared_frac"] == 1.0).all()
    )
    w2 = w.copy()
    w2.loc[w2.index[: len(w2) * 6 // 10], "climatology"] = np.nan
    with pytest.raises(ValueError, match="rh"):
        leaderboard_rows(w2, models, "rh", settings, CFG)
    w3 = w.copy()
    w3.loc[w3.index[: len(w3) // 4], "climatology"] = np.nan
    lb3 = leaderboard_rows(w3, models, "rh", settings, CFG).set_index("model")
    assert (
        lb3.loc["baseline3", "n_own"]
        > lb3.loc["climatology", "n_own"]
        == lb3.loc["climatology", "n_shared"]
    )
