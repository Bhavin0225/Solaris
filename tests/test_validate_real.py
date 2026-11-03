import argparse
import hashlib
import json

import pytest

pytest.importorskip("matplotlib")

from swf.core.paths import CONFIG_DIR, INTERIM_DIR, RAW_DIR
from swf.validate.run import run


@pytest.mark.realdata
@pytest.mark.skipif(not (RAW_DIR / "kaggle" / "T1.csv").exists(), reason="Kaggle files absent")
def test_real_validation(tmp_path):
    plant = CONFIG_DIR / "plant.yaml"
    h = hashlib.sha256(plant.read_bytes()).hexdigest()
    sim = INTERIM_DIR / "energy_sim.parquet"
    mt = sim.stat().st_mtime_ns if sim.exists() else None
    assert run(argparse.Namespace(), out_dir=tmp_path / "v", notes_path=tmp_path / "notes.md") == 0
    m = json.loads((tmp_path / "v" / "metrics.json").read_text(encoding="utf-8"))
    p1 = m["solar"]["plant_1"]
    assert p1["heldout_nrmse_pct"] < 10 and p1["heldout_nrmse_at_config_loss_pct"] < 10
    assert 8 <= p1["loss_pct_tuned"] <= 20 and p1["ts_partial_dropped"] > 0
    assert m["solar"]["plant_2"]["gating"] is False
    sl = m["wind"]["slices"]
    for k in ("full_year", "ref_slice"):
        assert sl[k]["sim_nrmse_pct"] <= min(14, sl[k]["reference_nrmse_pct"], 13.0)
    assert sl["ref_slice"]["n"] == 10098
    assert hashlib.sha256(plant.read_bytes()).hexdigest() == h
    assert (sim.stat().st_mtime_ns if sim.exists() else None) == mt
