"""Realdata checks on the Phase 6 LSTM run (val predictions, sidecar, checkpoint, leaderboard)."""

import csv
import json

import pandas as pd
import pytest

from swf.core.paths import MODELS_DIR, PROCESSED_DIR, REPORTS_DIR
from swf.core.settings import load_settings
from swf.evaluate.baselines import truth_frame
from swf.evaluate.longfmt import TARGETS, read_long, validate_long
from swf.features.spec import assert_spec
from swf.features.splits import origins_for
from swf.physics.common import is_night

VAL = PROCESSED_DIR / "predictions" / "val" / "lstm.parquet"
SIDE = MODELS_DIR / "lstm" / "lstm.json"
HAVE = VAL.exists() and SIDE.exists()
pytestmark = [pytest.mark.realdata, pytest.mark.skipif(not HAVE, reason="train-lstm outputs absent")]


def test_lstm():
    origins = origins_for("val")
    df = read_long("val", "lstm")
    validate_long(df, truth=truth_frame(), origins=origins)
    for t, g in df.groupby("target", observed=True):
        assert set(g["horizon"].unique()) == set(range(1, 73)), t
        assert len(g) == len(origins) * 72, t
    f = df.dropna(subset=["p10", "p50", "p90"])
    assert (f["p10"] <= f["p50"]).all() and (f["p50"] <= f["p90"]).all()
    assert (df.loc[df["target"] == "rh", "p90"].dropna() <= 100).all()
    s = load_settings()
    for t in ("t1_kw", "ghi"):
        g = df[df["target"] == t]
        night = is_night(pd.DatetimeIndex(g["target_time"]), s).to_numpy()
        assert (g.loc[night, ["p10", "p50", "p90"]].fillna(0) == 0).all().all(), t

    meta = json.loads(SIDE.read_text(encoding="utf-8"))
    assert_spec(meta)
    assert meta["status"] in {"stable", "minimal"}
    if meta["status"] == "minimal":
        assert meta["reason"]
    assert meta["best_epoch"] >= 1
    h = meta["history"]
    assert all(pd.Series(h[k][: meta["best_epoch"]]).map(pd.notna).all() for k in ("train_loss", "es_loss"))
    assert set(meta["band_offsets"]) == set(TARGETS)
    assert all(len(v) == 3 for v in meta["band_offsets"].values())

    import torch

    assert isinstance(torch.load(MODELS_DIR / "lstm" / "lstm.pt", weights_only=True), dict)
    with (REPORTS_DIR / "evaluation" / "leaderboard.csv").open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["model"] == "lstm" and r["split"] == "val"]
    assert {r["target"] for r in rows} >= set(TARGETS)
