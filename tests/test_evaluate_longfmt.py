import numpy as np
import pandas as pd
import pytest

from swf.evaluate.longfmt import (
    LONG_COLS,
    TARGETS,
    grid,
    make_long,
    pred_path,
    read_long,
    validate_long,
    write_long,
)

ORIG = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")


def sample(target="ws10", model="m"):
    i, h, _ = grid(ORIG, range(1, 73))
    return make_long(
        i, h, target, model, np.arange(len(h), dtype=float), np.arange(len(h)) + 0.5
    )


def test_grid():
    _, h, tt = grid(ORIG, range(1, 73))
    assert len(h) == 144
    assert tt[0] == pd.Timestamp("2024-01-01 01:00", tz="UTC")
    assert tt[-1] == pd.Timestamp("2024-01-04 01:00", tz="UTC")


def test_make_valid():
    df = sample()
    assert tuple(df.columns) == LONG_COLS
    assert df["p10"].isna().all() and df["p90"].isna().all()
    assert str(df["issue_time"].dtype) == "datetime64[ns, UTC]"
    validate_long(df)


def _set(d, col, val):
    d.loc[d.index[0], col] = val
    return d


def _h(v):
    def f(d):
        d["horizon"] = d["horizon"].astype("int64")
        d.loc[0, "horizon"] = v
        d["horizon"] = d["horizon"].astype("int16")
        d["target_time"] = d["issue_time"] + pd.to_timedelta(
            d["horizon"].astype("int64"), unit="h"
        )
        return d

    return f


def _shift(d):
    d["target_time"] = d["target_time"] + pd.Timedelta(hours=1)
    return d


def _naive(d):
    d["issue_time"] = d["issue_time"].dt.tz_localize(None)
    return d


def _target(d):
    d["target"] = d["target"].astype(str)
    return d


def _f64(d):
    d["p50"] = d["p50"].astype("float64")
    return d


CASES = [
    lambda d: d.drop(columns="p90"),
    lambda d: d.assign(x=1),
    _h(0),
    _h(73),
    lambda d: pd.concat([d, d.iloc[:1]], ignore_index=True),
    _shift,
    _naive,
    _target,
    _f64,
]


@pytest.mark.parametrize("f", CASES)
def test_rejects(f):
    with pytest.raises(ValueError):
        validate_long(f(sample()))


def test_truth_and_origins():
    i, h, t = grid(ORIG[:1], range(1, 5))
    truth = pd.DataFrame(
        {k: np.arange(100, 104, dtype=float) for k in TARGETS}, index=t
    )
    truth.iloc[1, :] = np.nan
    ok = make_long(i, h, "ws10", "m", truth["ws10"].to_numpy(), np.zeros(4))
    validate_long(ok, truth=truth, origins=ORIG)
    with pytest.raises(ValueError):
        validate_long(ok.assign(y_true=ok["y_true"] + np.float32(1)), truth=truth)
    with pytest.raises(ValueError):
        validate_long(ok, origins=ORIG[1:])


def test_roundtrip(tmp_path):
    df = pd.concat([sample("ws10"), sample("rh")], ignore_index=True)
    df["target"] = pd.Categorical(df["target"].astype(str), categories=TARGETS)
    write_long(df, "val", "m", root=tmp_path)
    back = read_long("val", "m", root=tmp_path)
    exp = df.sort_values(["target", "issue_time", "horizon"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(back, exp)
    only = read_long("val", "m", root=tmp_path, target="ws10")
    assert set(only["target"].astype(str)) == {"ws10"} and len(only) == 144


@pytest.mark.parametrize("m", ["../x", "Baseline3"])
def test_pred_path_safe(m):
    with pytest.raises(ValueError):
        pred_path("val", m)
