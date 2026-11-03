import numpy as np
import pandas as pd
import pytest

from swf.align.consistency import (
    LOG_ONLY,
    VARS,
    apply_correction,
    decide,
    fit_correction,
    load_coefs,
    monthly_table,
    save_coefs,
)
from swf.physics.common import clearsky, is_night

IDX = pd.date_range("2023-01-01", "2024-12-31 23:00", freq="h", tz="UTC", name="time")


@pytest.fixture
def nasa(settings):
    df = pd.DataFrame(
        {"ghi": clearsky(IDX, settings)["ghi"], "rh": 60.0, "ws10": 4.0,
         "ws_hub": 6.5, "temp": 25.0, "pressure": 950.0},
        index=IDX,
    )  # fmt: skip
    df["ws10"] += np.sin(np.arange(len(IDX)) / 7.0)
    return df


def _row(t, var, m):
    return t[(t.variable == var) & (t.month == m)].iloc[0]


def _cfg(settings, **kw):
    return settings.model_copy(update={"align": settings.align.model_copy(update=kw)})


def test_table_bias_and_columns(nasa, settings):
    ref = nasa.copy()
    ref["ws10"] = nasa["ws10"] - 0.6
    t = monthly_table(nasa, ref, settings)
    assert set(t.variable) == set(VARS + LOG_ONLY)
    for m in range(13):
        r = _row(t, "ws10", m)
        assert r.bias == pytest.approx(-0.6)
        assert r.rmse == pytest.approx(0.6)
        assert r["corr"] == pytest.approx(1.0)


def test_ghi_night_excluded(nasa, settings):
    ref = nasa.copy()
    night = is_night(IDX, settings)
    ref.loc[night, "ghi"] += 999
    r = _row(monthly_table(nasa, ref, settings), "ghi", 0)
    assert r.bias == pytest.approx(0)
    assert r.n == int((~night).sum())


def test_years_and_nan(nasa, settings):
    t = monthly_table(nasa, nasa, settings, years=(2024, 2024))
    assert _row(t, "rh", 0).n == 8784
    ref = nasa.copy()
    ref.iloc[:100, ref.columns.get_loc("rh")] = np.nan
    assert _row(monthly_table(nasa, ref, settings), "rh", 0).n == len(IDX) - 100


def _tbl(var, biases, mean=4.0):
    return pd.DataFrame(
        [{"variable": var, "month": m, "n": 1, "nasa_mean": mean, "bias": b, "rmse": 0, "corr": 1}
         for m, b in enumerate(biases, 1)]
    )  # fmt: skip


def test_decide(settings):
    ok = [0.0] * 12
    t = pd.concat([_tbl("ws10", [-0.6, *ok[1:]]), _tbl("rh", [4.9] * 12), _tbl("ghi", ok),
                   _tbl("ws_hub", [-0.45] * 12)])  # fmt: skip
    d = decide(t, settings)
    assert set(d) == set(VARS)
    assert d["ws10"]["correct"] and d["ws10"]["months_exceeding"] == [1]
    assert not d["rh"]["correct"] and not d["ghi"]["correct"]
    assert d["ws_hub"]["correct"]  # 0.45 > 10% of 4.0
    g = _tbl("ghi", [*ok[:6], -25, *ok[7:]])
    assert decide(g, settings)["ghi"]["months_exceeding"] == [7]
    skipped = settings.model_copy(update={"align": settings.align.model_copy(update={"skip": {"ghi": "no skill"}})})
    dg = decide(g, skipped)["ghi"]
    assert not dg["correct"] and dg["months_exceeding"] == [7] and "no skill" in dg["threshold"]


def test_fit_recovers_and_fit_years(nasa, settings):
    ref = nasa.copy()
    ref["ws10"] = (nasa["ws10"] + 0.375) / 1.25
    c = fit_correction(nasa, ref, settings, ["ws10"])
    for m in range(1, 13):
        e = c["variables"]["ws10"][str(m)]
        assert e["a"] == pytest.approx(1.25, abs=1e-3)
        assert e["b"] == pytest.approx(-0.375, abs=1e-3)
    assert c["variables"]["ws10"]["1"]["n"] == 31 * 24
    ref.loc[ref.index.year == 2024, "ws10"] *= 7
    c2 = fit_correction(nasa, ref, _cfg(settings, fit_years=(2023, 2023)), ["ws10"])
    assert c2["fit_years"] == [2023, 2023]
    assert c2["variables"]["ws10"]["5"]["a"] == pytest.approx(1.25, abs=1e-3)


def test_ghi_fit_daytime_only(nasa, settings):
    e = fit_correction(nasa, nasa, settings, ["ghi"])["variables"]["ghi"]["6"]
    assert e["a"] == pytest.approx(1.0, abs=1e-6)
    assert e["n"] < 30 * 24 * 2


def test_json_roundtrip_and_apply(nasa, settings, tmp_path):
    ref = nasa.copy()
    ref["ws10"] = (nasa["ws10"] + 0.375) / 1.25
    c = fit_correction(nasa, ref, settings, ["ws10", "ghi"])
    p = tmp_path / "c.json"
    save_coefs(c, p)
    loaded = load_coefs(p)
    assert loaded == c
    assert set(c["variables"]["ws10"]) == {str(m) for m in range(1, 13)}
    orig = ref.copy()
    out = apply_correction(ref, c, settings)
    pd.testing.assert_frame_equal(ref, orig)
    assert out["ws10"].to_numpy() == pytest.approx(nasa["ws10"].to_numpy(), abs=1e-2)
    pd.testing.assert_series_equal(out["rh"], ref["rh"])
    pd.testing.assert_frame_equal(out, apply_correction(ref, loaded, settings))


def _lin(b, vs):
    return {"variables": {v: {str(m): {"a": 1.0, "b": b, "n": 1} for m in range(1, 13)} for v in vs}}


def test_apply_clips_nan_night(nasa, settings):
    df = nasa.iloc[:48].copy()
    df.iloc[3, df.columns.get_loc("rh")] = np.nan
    night = is_night(df.index, settings)
    out = apply_correction(df, _lin(50.0, ("ghi", "rh", "ws10")), settings)
    assert out["rh"].max() == 100
    assert np.isnan(out["rh"].iloc[3])
    assert (out.loc[night, "ghi"] == 0).all()
    o2 = apply_correction(df, _lin(-500.0, ("ghi", "ws10")), settings)
    assert (o2["ws10"] == 0).all()
    assert (o2["ghi"] >= 0).all()


def test_load_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="build-weather"):
        load_coefs(tmp_path / "nope.json")


def test_ghi_fit_through_origin_keeps_zero(nasa, settings):
    ref = nasa.copy()
    ref["ghi"] = nasa["ghi"] * 0.8 + 60.0  # offset that an affine fit would absorb into b
    c = fit_correction(nasa, ref, settings, ["ghi"])
    assert all(e["b"] == 0.0 for e in c["variables"]["ghi"].values())
    zero = nasa.iloc[:48].copy()
    zero["ghi"] = 0.0
    assert (apply_correction(zero, c, settings)["ghi"] == 0).all()
