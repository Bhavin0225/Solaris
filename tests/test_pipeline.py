import json

import numpy as np
import pandas as pd
import pytest
from synth import canon_frame

from swf.align.build import render_cleaning, render_consistency, render_timestamps
from swf.align.canon import validate_canon
from swf.align.clean import REPORT_COLS
from swf.core.paths import CONFIG_DIR, INTERIM_DIR
from swf.core.settings import load_settings
from swf.physics.common import is_night
from swf.physics.simulate import render_physics, simulate
from swf.physics.solar import ac_cap_kw

S = load_settings()


def _res(passed=True):
    return {"onset_exact": 0.95, "onset_tol": 0.99, "onset_tol_opposite": 0.1, "n_days": 10,
            "per_year": {2001: 0.01, 2002: 0.5}, "full_years": [2001], "pooled": 0.01, "passed": passed}  # fmt: skip


def test_render_timestamps():
    met = {"pressure": {"best_lag_h": 0, "corr": {k: 0.9 for k in range(-2, 3)}}}
    out = render_timestamps({"nasa": _res(), "gfs_hf": _res(False)}, met)
    assert (
        "shift h" in out
        and "partial (not gating)" in out
        and "PASS" in out
        and "FAIL" in out
    )
    assert "not gating" in out and out == render_timestamps(
        {"nasa": _res(), "gfs_hf": _res(False)}, met
    )


def test_render_cleaning():
    rows = [
        ("nasa", "ghi", 2001, 1.0, 0.0, 0, 0, 5),
        ("nasa", "rh", 2001, 0.0, 0.0, 0, 0, 0),
    ]
    out = render_cleaning(pd.DataFrame(rows, columns=list(REPORT_COLS)))
    assert (
        out.startswith("Generated")
        and "Only rows with a non-zero value are listed" in out
    )
    assert (
        "| nasa | ghi | 2001" in out
        and "| nasa | rh |" not in out
        and "- nasa: every other" in out
    )


def test_render_consistency():
    t = pd.DataFrame([("ghi", 0, 10, 500.0, 1.0, 2.0, 0.9), ("ghi", 3, 5, 500.0, 1.0, 2.0, 0.9)],
                     columns=["variable", "month", "n", "nasa_mean", "bias", "rmse", "corr"])  # fmt: skip
    d = {
        "ghi": {"correct": True, "months_exceeding": [3], "threshold": "abs bias > 20"}
    }
    out = render_consistency(t, d, t, t)
    assert "| ghi | all |" in out and "yes" in out and "diagnostic only" in out


def test_simulate_bounds_and_physics_block():
    w = canon_frame("2024-03-21", 2, S)
    e = simulate(w, S)
    assert list(e.columns) == ["t1_kw", "t5_kw"] and e.index.equals(w.index)
    assert e["t1_kw"].max() <= ac_cap_kw(S) and e["t5_kw"].max() <= S.wind.rated_kw
    assert (e["t1_kw"][is_night(e.index, S)] == 0).all()
    out = render_physics(e, S)
    assert "833.3" in out and "800.0" in out and out == render_physics(e, S)


def _have(p):
    return pytest.mark.skipif(not p.exists(), reason=f"{p} absent")


@pytest.mark.realdata
@_have(INTERIM_DIR / "weather_nasa.parquet")
@pytest.mark.parametrize(
    "src", ["nasa", "era5", "gfs_hf", "gfs_pr_d1", "gfs_pr_d2", "gfs_pr_d3"]
)
def test_real_weather_tables(src):
    df = pd.read_parquet(INTERIM_DIR / f"weather_{src}.parquet")
    validate_canon(df)
    assert (df.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all()


@pytest.mark.realdata
@_have(INTERIM_DIR / "energy_sim.parquet")
def test_real_energy_sim():
    e = pd.read_parquet(INTERIM_DIR / "energy_sim.parquet")
    assert (
        e["t1_kw"].max() <= ac_cap_kw(S) + 1e-9 and e["t5_kw"].max() <= S.wind.rated_kw
    )
    assert (e["t1_kw"][is_night(e.index, S)] == 0).all()


@pytest.mark.realdata
@_have(CONFIG_DIR / "bias_correction.json")
def test_real_bias_json():
    d = json.loads((CONFIG_DIR / "bias_correction.json").read_text())
    assert (
        d["fit_years"] == [2001, 2023]
        and not np.setdiff1d(["ghi", "rh", "ws10", "ws_hub"], list(d["variables"])).size
    )
