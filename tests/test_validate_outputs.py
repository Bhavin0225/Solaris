import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("matplotlib")

from swf.validate.run import OPENER, gate, render_validation, write_outputs


def _plant(gating):
    return {
        "gating": gating, "n_rows": 100, "ts_partial_dropped": 3, "dc_kwp": 1.23456, "ac_cap_kw": 3.14159,
        "loss_pct_tuned": 9, "loss_edge": False, "tune_nrmse_pct": 3.0, "heldout_nrmse_pct": 3.4,
        "full_nrmse_pct": 3.1, "heldout_nrmse_at_config_loss_pct": 4.0, "full_nrmse_at_config_loss_pct": 4.3,
        "hourly_nrmse_pct": 2.0, "mbe_pct": 0.1, "full_nrmse_faiman_pct": 3.5,
        "zero_ac_daytime_pct_worst_inverter": 5.0, "zero_ac_daytime_pct_median_inverter": 1.0,
        "loss_curve": {"8": 3.2, "9": 3.0}, "pass": True, "pass_at_config_loss": True,
    }  # fmt: skip


def _slice():
    return {"n": 10, "sim_nrmse_pct": 12.3, "reference_nrmse_pct": 13.1}


METRICS = {
    "solar": {"plant_1": _plant(True), "plant_2": _plant(False)},
    "wind": {
        "target_pct": 14.0, "prd_reference_nrmse_pct": 13.0, "availability_config_pct": 3.5,
        "availability_measured_pct": 3.54, "energy_ratio": 0.877, "pass": True,
        "slices": {k: _slice() for k in ("full_year", "ref_slice", "jan_to_ref")},
    },
    "settings": {
        "day_irradiation_kw_m2": 0.02, "heldout_start_local": "2020-06-01", "solar_target_pct": 10.0,
        "config_loss_pct": 14.0, "local_timezone": "Asia/Kolkata",
    },
}  # fmt: skip


def _series():
    x = np.linspace(0, 100, 50)
    return {k: pd.DataFrame({"sim": x, "act": x}) for k in ("solar_plant_1", "solar_plant_2", "wind")}


def _write(tmp_path):
    caps = {k: 100.0 for k in _series()}
    write_outputs(METRICS, _series(), tmp_path / "o", tmp_path / "notes.md", caps)


def test_write_outputs_idempotent_and_rounded(tmp_path):
    (tmp_path / "notes.md").write_text("hand written\n", encoding="utf-8")
    _write(tmp_path)
    mj, notes = (tmp_path / "o" / "metrics.json").read_bytes(), (tmp_path / "notes.md").read_bytes()
    m = json.loads(mj)
    assert set(m["solar"]) == {"plant_1", "plant_2"} and "wind" in m
    assert m["solar"]["plant_1"]["dc_kwp"] == 1.235 and mj.endswith(b"\n") and b"\r" not in mj
    for k in _series():
        assert (tmp_path / "o" / f"{k}_scatter.png").read_bytes().startswith(b"\x89PNG")
    assert b"hand written" in notes
    _write(tmp_path)
    assert (tmp_path / "o" / "metrics.json").read_bytes() == mj
    assert (tmp_path / "notes.md").read_bytes() == notes


def test_render_and_gate():
    out = render_validation(METRICS)
    assert out.startswith(OPENER) and "| plant_1 | yes |" in out and "| plant_2 | no |" in out
    assert "### Loss curve" in out and "PRD pre-project reference: 13.0%" in out
    for k in ("full_year", "ref_slice", "jan_to_ref"):
        assert f"| {k} |" in out
    assert gate(METRICS)
    bad = {**METRICS, "solar": {**METRICS["solar"], "plant_2": {**_plant(False), "pass": False}}}
    assert gate(bad)  # D-L2: non-gating plant never matters
    bad["solar"]["plant_1"] = {**_plant(True), "pass_at_config_loss": False}
    assert not gate(bad)
