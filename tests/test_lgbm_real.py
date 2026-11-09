"""Realdata checks on the Phase 5 LightGBM run (val predictions, registry, artifacts, leaderboard)."""

import csv
import json

import pandas as pd
import pytest

from swf.core.paths import MODELS_DIR, PROCESSED_DIR, REPORTS_DIR
from swf.core.settings import load_features_cfg, load_settings
from swf.evaluate.baselines import truth_frame
from swf.evaluate.longfmt import TARGETS, read_long, validate_long
from swf.evaluate.metrics import daytime_mask
from swf.features.spec import assert_spec
from swf.features.splits import origins_for
from swf.physics.common import is_night
from swf.predict.registry import artifact_path, load_registry

VAL = PROCESSED_DIR / "predictions" / "val" / "lightgbm.parquet"
HAVE = VAL.exists() and (MODELS_DIR / "registry.json").exists()
pytestmark = [
    pytest.mark.realdata,
    pytest.mark.skipif(not HAVE, reason="train-lgbm outputs absent"),
]


def test_val_predictions():
    df = read_long("val", "lightgbm")
    validate_long(df, truth=truth_frame(), origins=origins_for("val"))
    for t, g in df.groupby("target", observed=True):
        assert set(g["horizon"].unique()) == set(range(1, 73)), t
    f = df.dropna(subset=["p10", "p50", "p90"])
    assert (f["p10"] <= f["p50"]).all() and (f["p50"] <= f["p90"]).all()
    assert (df.loc[df["target"] == "rh", "p90"].dropna() <= 100).all()
    s = load_settings()
    for t in ("t1_kw", "ghi"):
        g = df[df["target"] == t]
        night = is_night(pd.DatetimeIndex(g["target_time"]), s).to_numpy()
        assert (g.loc[night, ["p10", "p50", "p90"]].fillna(0) == 0).all().all(), t


def test_registry_and_artifacts():
    reg = load_registry()
    for t in TARGETS:
        e = reg["targets"][t]
        assert e["selected"] == e["runtime"] == "baseline3"
        assert set(e["artifacts"]) == {"1-6", "7-24", "25-72"}
        for rel in e["artifacts"].values():
            p = artifact_path(rel)
            side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
            assert p.exists()
            assert_spec(side)
            assert side["n_es_rows"] > 0
        for m in ("baseline3", "lightgbm"):
            assert all(q10 <= q90 for q10, q90 in e["bands"][m].values())
        assert set(e["val_rmse"]) == {"baseline3", "lightgbm"}


def test_leaderboard_and_no_test_file():
    with open(
        REPORTS_DIR / "evaluation" / "leaderboard.csv", newline="", encoding="utf-8"
    ) as f:
        rows = list(csv.DictReader(f))
    for t in TARGETS:
        got = {r["model"] for r in rows if r["split"] == "val" and r["target"] == t}
        assert {"lightgbm", "baseline3"} <= got, t
    assert not (PROCESSED_DIR / "predictions" / "test" / "lightgbm.parquet").exists()


def test_daytime_coverage():
    s, cfg = load_settings(), load_features_cfg()
    df = read_long("val", "lightgbm")
    for t, g in df.groupby("target", observed=True):
        ok = g["y_true"].notna() & g["p10"].notna()
        if t in ("t1_kw", "ghi"):
            ok &= daytime_mask(
                pd.DatetimeIndex(g["target_time"]), s, cfg.eval.daytime_zenith_deg
            )
        g = g[ok.to_numpy()]
        cov = float(((g["y_true"] >= g["p10"]) & (g["y_true"] <= g["p90"])).mean())
        assert 0.70 <= cov <= 0.90, (t, cov)


def test_predict_split_val_parity(tmp_path):
    from swf.models.lgbm import predict_split

    out = tmp_path / "pred"
    for m in ("baseline3_corrected", "baseline3_raw"):  # predict_split reads baseline 3 from out_root
        (out / "val").mkdir(parents=True, exist_ok=True)
        (out / "val" / f"{m}.parquet").write_bytes((PROCESSED_DIR / "predictions" / "val" / f"{m}.parquet").read_bytes())
    predict_split("val", out_root=out)  # writes only under tmp_path
    got, want = read_long("val", "lightgbm", out), read_long("val", "lightgbm")
    for c in ("p50", "p10", "p90"):
        pd.testing.assert_series_equal(got[c], want[c], check_exact=False, atol=1e-3, rtol=0)
