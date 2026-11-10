import types

import numpy as np
import pandas as pd
import pytest

from swf.evaluate.figures import (
    D23,
    gain_importance,
    heatmap_table,
    plot_gain,
    plot_heatmap,
    plot_reliability,
    plot_wind_cf,
    wind_cf_table,
)
from swf.evaluate.longfmt import TARGETS, grid, make_long

CFG = types.SimpleNamespace(
    monsoon_months=[6, 7, 8, 9],
    eval=types.SimpleNamespace(horizons=[1, 6, 24, 48, 72], daytime_zenith_deg=85.0),
)
HS = [1, 6, 24, 48, 72]


def _bd():
    rows = []
    for t in TARGETS:
        for se in ("all", "monsoon", "dry"):
            for h in [*HS, "all"]:
                rows.append({"split": "val", "target": t, "model": "lightgbm", "season": se,
                             "horizon": str(h), "skill_vs_baseline3": 0.1 if h == "all" else 0.01 * len(se) + (0 if h == "all" else int(h) / 1000)})  # fmt: skip
    return pd.DataFrame(rows)


def test_heatmap_table():
    bd = _bd()
    t = heatmap_table(bd, "val", ["lightgbm"])
    assert sorted(t["horizon"].unique()) == HS and len(t) == 5 * 3 * 5
    r = t[(t["target"] == "rh") & (t["season"] == "dry") & (t["horizon"] == 24)]["skill_vs_baseline3"].iloc[0]
    assert r == pytest.approx(0.03 + 0.024)


def test_wind_cf(settings):
    o = pd.date_range("2024-05-20", "2024-06-30", freq="12h", tz="UTC")
    i, h, _ = grid(o, [1, 2])
    y = np.where(np.arange(len(h)) % 2 == 0, 400.0, 600.0)
    f = {"m": make_long(i, h, "t5_kw", "m", y, y + 50)}
    t = wind_cf_table(f, settings, CFG).set_index("season")
    R = settings.wind.rated_kw
    assert t.loc["all", "observed_cf"] == pytest.approx(500 / R)
    assert t.loc["all", "rmse_cf"] == pytest.approx(50 / R)
    assert t.loc["all", "predicted_cf"] == pytest.approx(550 / R)
    assert set(t.index) == {"all", "monsoon", "dry"}


def test_gain(tmp_path):
    from synth import write_tiny_lgbm

    arts = {t: write_tiny_lgbm(tmp_path, t, [(1, 6), (7, 24), (25, 72)], seed=k) for k, t in enumerate(["t1_kw", "rh"])}
    df = gain_importance(arts, tmp_path)
    for t in arts:
        assert df[df["target"] == t]["gain_pct"].sum() == pytest.approx(100.0, abs=1e-6)
    from swf.features.spec import feature_columns

    assert set(df[df["target"] == "rh"]["feature"]) == set(feature_columns("covariate"))


def test_plots_titles_and_determinism(tmp_path):
    pytest.importorskip("matplotlib")
    dep = {t: "lightgbm" for t in TARGETS} | {"t5_kw": "baseline3"}
    mbt = {t: "lightgbm" for t in TARGETS}
    tbl = heatmap_table(_bd(), "val", ["lightgbm"])
    titles = plot_heatmap(tbl, mbt, tmp_path / "a.png", dep)
    assert all("lightgbm" in x for x in titles)
    assert [D23 in x for x in titles] == [t == "t5_kw" for t in TARGETS]
    plot_heatmap(tbl, mbt, tmp_path / "b.png", dep)
    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes() != b""

    gain = pd.DataFrame({"target": list(TARGETS) * 2, "feature": ["f1"] * 5 + ["f2"] * 5,
                         "gain": 1.0, "gain_pct": 50.0})  # fmt: skip
    g = plot_gain(gain, tmp_path / "g1.png", deployed=dep)
    assert all("lightgbm" in x for x in g)
    plot_gain(gain, tmp_path / "g2.png", deployed=dep)
    assert (tmp_path / "g1.png").read_bytes() == (tmp_path / "g2.png").read_bytes()

    prob = pd.DataFrame({"target": list(TARGETS), "model": "lightgbm", "rel_q10": 0.1, "rel_q50": 0.5, "rel_q90": 0.9})
    plot_reliability(prob, "val", tmp_path / "r1.png")
    plot_reliability(prob, "val", tmp_path / "r2.png")
    assert (tmp_path / "r1.png").read_bytes() == (tmp_path / "r2.png").read_bytes()

    wt = pd.DataFrame({"season": ["all", "monsoon", "dry"], "model": "m", "n": 1,
                       "observed_cf": 0.3, "predicted_cf": 0.2, "rmse_cf": 0.1})  # fmt: skip
    plot_wind_cf(wt, tmp_path / "w1.png")
    plot_wind_cf(wt, tmp_path / "w2.png")
    assert (tmp_path / "w1.png").read_bytes() == (tmp_path / "w2.png").read_bytes()
