import hashlib
import json
import logging
import os
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from synth import canon_frame

from swf.core.paths import INTERIM_DIR, PROCESSED_DIR
from swf.evaluate import report as r
from swf.evaluate.baselines import MODELS
from swf.evaluate.longfmt import TARGETS, make_long, pred_path, read_long, write_long
from swf.features.spec import spec_hash

ORIGINS = {
    "val": ["2024-02-10", "2024-07-10", "2024-10-10"],
    "test": ["2025-02-10", "2025-07-10", "2025-10-10"],
}
RAW_BETTER = ("ws10", "t5_kw")


def bias_for(split, model, target):
    if model == "persistence":
        return 3.0
    if model == "climatology":
        return 4.0
    if model.startswith("baseline3_stitched"):
        return 2.5
    if model not in ("baseline3_raw", "baseline3_corrected"):
        return 5.0
    raw_wins = (target in RAW_BETTER) == (split == "val")
    good = "baseline3_raw" if raw_wins else "baseline3_corrected"
    return 1.0 if model == good else 2.0


def write_preds(root, extra=()):
    for split, os_ in ORIGINS.items():
        issue = np.repeat(pd.DatetimeIndex(os_, tz="UTC"), 72)
        hor = np.tile(np.arange(1, 73), len(os_))
        tt = issue + pd.to_timedelta(hor, unit="h")
        for m in (*MODELS, *extra):
            parts = []
            for i, t in enumerate(TARGETS):
                y = 100 + 10 * i + (tt.hour.to_numpy() % 7) + (tt.dayofyear.to_numpy() % 5)
                parts.append(make_long(issue, hor, t, m, y, y + bias_for(split, m, t)))
            write_long(pd.concat(parts, ignore_index=True), split, m, root)


def write_interim(d, s):
    d.mkdir(parents=True, exist_ok=True)
    nasa = canon_frame("2024-03-01", 4, s)
    nasa.to_parquet(d / "weather_nasa.parquet")
    for n in ("weather_gfs_hf", "weather_gfs_pr_d1", "weather_gfs_pr_d2", "weather_gfs_pr_d3"):
        g = nasa.copy()
        g["ws10"] += 0.5
        g.to_parquet(d / f"{n}.parquet")


@pytest.fixture
def env(tmp_path, settings):
    write_preds(tmp_path / "pred")
    write_interim(tmp_path / "interim", settings)
    return {
        "out_dir": tmp_path / "out",
        "notes_path": tmp_path / "notes.md",
        "pred_root": tmp_path / "pred",
        "choice_path": tmp_path / "choice.json",
        "interim_dir": tmp_path / "interim",
    }


def go(env, split="all"):
    return r.run(Namespace(split=split), **env)


def test_ordering_and_shape(env):
    assert go(env) == 0
    ch = json.loads(env["choice_path"].read_text())
    assert ch["choice"] == {
        "rh": "corrected", "ghi": "corrected", "t1_kw": "corrected", "ws10": "raw", "t5_kw": "raw",
    }  # fmt: skip
    lb = pd.read_csv(env["out_dir"] / "leaderboard.csv")
    assert len(lb) == 70
    assert (lb["feature_spec_hash"] == spec_hash()).all()
    for sp in ("val", "test"):
        a = lb[(lb.split == sp) & (lb.target == "ws10")].set_index("model")
        assert a.loc["baseline3", "rmse"] == pytest.approx(a.loc["baseline3_raw", "rmse"])
        assert a.loc["baseline3", "skill_vs_baseline3"] == 0
    bd = pd.read_csv(env["out_dir"] / "breakdown.csv", dtype={"horizon": str})
    assert set(bd.horizon) == {"1", "6", "24", "48", "72", "all"}
    assert set(bd.season) == {"all", "monsoon", "dry"}
    assert (bd["feature_spec_hash"] == spec_hash()).all()
    bias = pd.read_csv(env["out_dir"] / "gfs_bias_val.csv")
    assert (bias["feature_spec_hash"] == spec_hash()).all()
    raw = bias[(bias.variant == "raw") & (bias.variable == "ws10")]
    assert np.allclose(raw["bias"], 0.5)
    g = bias[bias.variable == "ghi"].pivot(index="lead", columns="variant", values="bias")
    assert np.allclose(g["raw"], g["corrected"])
    for f in ("rmse_by_horizon_val.png", "skill_val.png", "gfs_bias_val.png"):
        assert (env["out_dir"] / f).exists()
    txt = env["notes_path"].read_text()
    for k in ("BEGIN AUTO:evaluation", "D-06", "D-05", "lead-age", "same hour", "train/serve skew",
              "zenith < 85", "monsoon", f"feature_spec_hash: {spec_hash()}", "D-03a"):  # fmt: skip
        assert k in txt


def test_deterministic(env):
    go(env)
    names = ("leaderboard.csv", "breakdown.csv", "gfs_bias_val.csv", "rmse_by_horizon_val.png", "skill_val.png", "gfs_bias_val.png")

    def digest():
        return [hashlib.sha256((env["out_dir"] / n).read_bytes()).hexdigest() for n in names]

    a, notes = digest(), env["notes_path"].read_bytes()
    go(env)
    assert digest() == a and env["notes_path"].read_bytes() == notes


def test_test_refused_without_choice(env, capsys):
    assert go(env, "test") == 1
    assert "python -m swf evaluate --split val" in capsys.readouterr().out
    assert not (env["out_dir"] / "leaderboard.csv").exists()


def test_frozen_choice_kept(env, caplog):
    go(env, "val")
    frozen = json.loads(env["choice_path"].read_text())
    frozen["choice"]["rh"] = "raw"
    env["choice_path"].write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    before = env["choice_path"].read_bytes()
    with caplog.at_level(logging.WARNING, logger="swf.evaluate"):
        assert go(env) == 0
    assert env["choice_path"].read_bytes() == before and "differs" in caplog.text


def test_stale_hash_rejected(env):
    p = pred_path("val", "persistence", env["pred_root"])
    t = pq.read_table(p)
    meta = {**(t.schema.metadata or {}), b"swf_meta": json.dumps({"feature_spec_hash": "0" * 16}).encode()}
    pq.write_table(t.replace_schema_metadata(meta), p)
    with pytest.raises(ValueError, match="feature spec mismatch"):
        go(env)


def test_extra_model_joins(env):
    write_preds(env["pred_root"], extra=("lgbm",))
    go(env)
    lb = pd.read_csv(env["out_dir"] / "leaderboard.csv")
    assert len(lb) == 80 and "lgbm" in set(lb.model)
    assert len(read_long("val", "lgbm", env["pred_root"])) > 0


REAL = Path(os.environ.get("SWF_REAL_INTERIM", INTERIM_DIR))
HAVE = (PROCESSED_DIR / "predictions" / "val").exists() and (REAL / "weather_nasa.parquet").exists()


@pytest.mark.realdata
@pytest.mark.skipif(not HAVE, reason="predictions/interim absent; run `python -m swf baselines`")
def test_realdata_end_to_end(tmp_path):
    kw = {"out_dir": tmp_path / "o", "notes_path": tmp_path / "n.md", "choice_path": tmp_path / "c.json", "interim_dir": REAL}
    assert r.run(Namespace(split="all"), **kw) == 0
    lb = pd.read_csv(tmp_path / "o" / "leaderboard.csv")
    assert len(lb) == 70 and lb["rmse"].notna().all() and (lb["shared_frac"] >= 0.5).all()
    assert (lb[lb.model == "baseline3"].groupby("split").size() == 5).all()
    a = (tmp_path / "o" / "leaderboard.csv").read_bytes()
    r.run(Namespace(split="all"), **kw)
    assert (tmp_path / "o" / "leaderboard.csv").read_bytes() == a


def test_single_split_keeps_other_rows(env):
    go(env)
    names = ("leaderboard.csv", "breakdown.csv")
    a = [(env["out_dir"] / n).read_bytes() for n in names]
    notes = env["notes_path"].read_bytes()
    assert go(env, "test") == 0
    assert [(env["out_dir"] / n).read_bytes() for n in names] == a
    assert env["notes_path"].read_bytes() == notes
    assert go(env, "val") == 0
    assert [(env["out_dir"] / n).read_bytes() for n in names] == a


def test_stale_choice_hash_returns_1(env, capsys):
    go(env, "val")
    ch = json.loads(env["choice_path"].read_text())
    ch["feature_spec_hash"] = "0" * 16
    env["choice_path"].write_text(json.dumps(ch))
    assert go(env) == 1
    assert "feature spec mismatch" in capsys.readouterr().out
