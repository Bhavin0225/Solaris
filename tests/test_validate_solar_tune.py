import numpy as np
import pandas as pd
import pytest

from swf.core.settings import load_settings, load_validation_cfg
from swf.physics.solar import ac_cap_kw
from swf.validate.kaggle_solar import (
    daytime,
    is_heldout,
    plant_settings,
    simulate_plant,
    tune_loss,
    validate_plant,
)

START = pd.Timestamp("2020-06-01 00:00", tz="UTC")
P = 1000.0
KEYS = [
    "gating",
    "loss_pct_tuned",
    "loss_edge",
    "loss_curve",
    "tune_nrmse_pct",
    "heldout_nrmse_pct",
    "full_nrmse_pct",
    "hourly_nrmse_pct",
    "rmse_kw",
    "mae_kw",
    "mbe_pct",
    "n_rows",
    "config_loss_pct",
    "heldout_nrmse_at_config_loss_pct",
    "full_nrmse_at_config_loss_pct",
    "full_nrmse_faiman_pct",
    "target_pct",
    "pass",
    "pass_at_config_loss",
    "heldout_nrmse_at_ref_loss_pct",
    "full_nrmse_at_ref_loss_pct",
    "dc_kwp",
    "ac_cap_kw",
]


@pytest.fixture
def s():
    return load_settings()


@pytest.fixture
def vs():
    return load_validation_cfg().solar


def _frame(s, loss):
    idx = pd.date_range("2020-05-30 06:00", periods=96, freq="1h", tz="UTC")
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "irr_kw_m2": rng.uniform(0.1, 1.0, len(idx)),
            "t_module": rng.uniform(25, 55, len(idx)),
            "t_ambient": rng.uniform(20, 35, len(idx)),
        },
        index=idx,
    )
    df["ac_kw"] = simulate_plant(df, plant_settings(s, P, loss))
    return df


def test_plant_settings_anchor(s):
    p = plant_settings(s, 1000, 9)
    assert ac_cap_kw(p) == pytest.approx(1000, abs=1e-9)
    assert s.solar.loss_pct == 14


def test_simulate_modes(s):
    df = pd.DataFrame({"irr_kw_m2": [0.5], "t_module": [40.0], "t_ambient": [30.0]})
    p = plant_settings(s, P, 10)
    assert simulate_plant(df, p).iloc[0] != simulate_plant(df, p, "faiman").iloc[0]


def test_tune_recovers_loss(s, vs):
    r = tune_loss(_frame(s, 12), s, vs, peak_ac_kw=P, start_utc=START)
    assert r["loss_pct_tuned"] == 12 and not r["loss_edge"]
    assert list(r["loss_curve"]) == [str(k) for k in range(8, 21)]


def test_tune_edge(s, vs):
    r = tune_loss(_frame(s, 25), s, vs, peak_ac_kw=P, start_utc=START)
    assert r["loss_pct_tuned"] == 20 and r["loss_edge"]


def test_split_boundary_and_daytime(s, vs):
    i = pd.DatetimeIndex([START - pd.Timedelta("1min"), START])
    assert list(is_heldout(pd.DataFrame(index=i), START)) == [False, True]
    assert daytime(_frame(s, 12), vs).all()


def test_validate_plant_keys(s, vs):
    vs = vs.model_copy(update={"heldout_start_local": START.date()})
    out = validate_plant(
        _frame(s, 12), {"peak_ac_kw": P}, s, vs, gating=True, ref_loss_pct=9
    )
    assert all(k in out for k in KEYS)
    assert out["loss_pct_tuned"] == 12 and out["pass"] is True
    assert out["full_nrmse_pct"] == pytest.approx(0, abs=1e-6)
