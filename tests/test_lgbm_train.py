"""Synthetic tests for swf.models.lgbm pure pieces (no data/ access)."""

import json

import numpy as np
import pandas as pd

from swf.core.settings import load_features_cfg, load_lgbm_cfg
from swf.features.spec import assert_spec, feature_columns
from swf.features.splits import origins_for
from swf.models.lgbm import fit_bucket, save_bucket, split_fit_es, to_grid
from swf.predict.lgbm import predict_p50

_L = load_lgbm_cfg()
LCFG = _L.model_copy(update={
    "num_boost_round": 20, "early_stopping_rounds": 5,
    "params": {**_L.params, "num_threads": 1, "min_data_in_leaf": 20},
})  # fmt: skip


def _xy(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    cols = feature_columns("covariate")
    X = pd.DataFrame(rng.normal(size=(n, len(cols))).astype("float32"), columns=cols)
    return X, (X.iloc[:, 0] * 2 + rng.normal(size=n) * 0.1).to_numpy("float32")


def test_split_fit_es_purged():
    cfg = load_features_cfg()
    tc = origins_for("train_covariate", cfg)
    fit, es = split_fit_es(tc, LCFG.es_tail_start, 72)
    h72 = pd.Timedelta(hours=72)
    assert fit.max() + h72 < LCFG.es_tail_start
    assert es.min() == LCFG.es_tail_start
    assert es.max() + h72 <= pd.Timestamp(cfg.splits.train_covariate[1])
    assert not ((fit.year == 2024).any() or (es.year == 2024).any())


def test_to_grid_roundtrip():
    n, b = 3, [(1, 6), (7, 24), (25, 72)]
    preds = {f"{lo}-{hi}": np.arange(n * (hi - lo + 1), dtype=float) + 1000 * lo for lo, hi in b}
    g = to_grid(preds, n, b).reshape(n, 72)
    assert np.array_equal(g[:, 6:24].ravel(), preds["7-24"])
    assert np.array_equal(g[:, :6].ravel(), preds["1-6"])
    assert np.isfinite(g).all()


def test_fit_deterministic_save_predict(tmp_path):
    X, y = _xy()
    Xv, yv = _xy(500, 1)
    b1, b2 = fit_bucket(X, y, Xv, yv, LCFG), fit_bucket(X, y, Xv, yv, LCFG)
    assert np.array_equal(b1.predict(Xv), b2.predict(Xv))
    assert b1.best_iteration <= 20
    rel = save_bucket(b1, tmp_path, "t1_kw", 1, 6, {"n_es_rows": 500})
    assert rel == "lightgbm/t1_kw_1-6.txt"
    meta = json.loads((tmp_path / rel).with_suffix(".json").read_text(encoding="utf-8"))
    assert_spec(meta)
    assert meta["bucket"] == "1-6" and meta["target"] == "t1_kw" and meta["seed"] == LCFG.seed
    assert meta["best_iteration"] == b1.best_iteration
    Xp = Xv.assign(horizon=3.0)
    b3 = np.linspace(0, 1, len(Xp))
    out = predict_p50({"artifacts": {"1-6": rel}}, Xp, b3, "t1_kw", tmp_path)
    assert np.allclose(out, b3 + b1.predict(Xp[meta["feature_columns"]], num_iteration=b1.best_iteration))
    y_true = np.array([5.0, 7.0])
    assert np.array_equal((y_true - b3[:2]) + b3[:2], y_true) or np.allclose((y_true - b3[:2]) + b3[:2], y_true)
