"""Synthetic canonical data with exact interval means (no network)."""

import pandas as pd

from swf.align.canon import CANON_COLS
from swf.physics.common import location

_MET = {
    "temp": 25.0, "rh": 60.0, "pressure": 950.0, "ws10": 4.0, "ws_hub": 6.5,
    "wd10": 180.0, "wd_hub": 180.0, "precip": 0.0, "cloud": 0.0,
}  # fmt: skip


def clearsky_hourly(start, days, s, *, convention="start"):
    minutes = pd.date_range(start, periods=days * 24 * 60, freq="min", tz="UTC")
    cs = location(s).get_clearsky(minutes + pd.Timedelta(seconds=30), model="ineichen")
    cs = cs.set_axis(minutes)[["ghi", "dni", "dhi"]]
    out = cs.resample("1h").mean().astype("float64")
    if convention == "end":
        out.index = out.index + pd.Timedelta(hours=1)
    out.index.name = "time"
    return out


def canon_frame(start, days, s, *, convention="start"):
    df = clearsky_hourly(start, days, s, convention=convention)
    for k, v in _MET.items():
        df[k] = v
    return df[list(CANON_COLS)]


def hist_frame(start, days, s, seed=0):
    import numpy as np

    from swf.features.history import history_frame
    from swf.physics.wind import load_power_curve

    h = history_frame(canon_frame(start, days, s), s, load_power_curve(s), None)
    rng = np.random.default_rng(seed)
    h["rh"] = (h["rh"] + rng.normal(0, 3, len(h))).clip(0, 100)
    h["ws10"] = (h["ws10"] + rng.normal(0, 0.5, len(h))).clip(0)
    return h


def pr_trio(start, days, s):
    out = {}
    for k in (1, 2, 3):
        d = canon_frame(start, days, s)
        d["ws10"] += 0.1 * k
        out[k] = d
    return out


def write_tiny_lgbm(models_root, target, buckets, seed=0):
    import json

    import lightgbm as lgb
    import numpy as np

    from swf.features.spec import artifact_meta, feature_columns

    cols = feature_columns("covariate")
    rng = np.random.default_rng(seed)
    out = {}
    for lo, hi in buckets:
        label = f"{lo}-{hi}"
        X = pd.DataFrame(rng.normal(size=(200, len(cols))), columns=cols)
        params = {"objective": "regression", "verbosity": -1, "seed": seed, "deterministic": True,
                  "force_row_wise": True, "num_threads": 1, "min_data_in_leaf": 5}  # fmt: skip
        b = lgb.train(params, lgb.Dataset(X, rng.normal(size=200)), num_boost_round=5)
        rel = f"lightgbm/{target}_{label}.txt"
        p = models_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        b.save_model(str(p))
        meta = artifact_meta("covariate") | {"target": target, "bucket": label}
        p.with_suffix(".json").write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        out[label] = rel
    return out


def make_registry(path, buckets=((1, 6), (7, 24), (25, 72)), lightgbm_artifacts=None):
    import json

    from swf.core.paths import CONFIG_DIR
    from swf.features.spec import TARGETS
    from swf.predict.registry import save_registry

    choice = json.loads((CONFIG_DIR / "baseline3_choice.json").read_text(encoding="utf-8"))["choice"]
    labels = [f"{lo}-{hi}" for lo, hi in buckets]
    arts = lightgbm_artifacts or {}
    targets = {}
    for t in TARGETS:
        sel = "lightgbm" if t in arts else "baseline3"
        targets[t] = {
            "selected": sel, "runtime": sel, "reason": "synthetic", "artifacts": arts.get(t, {}),
            "bands": {m: {lab: [-1.0, 1.0] for lab in labels} for m in ("baseline3", "lightgbm")},
            "val_rmse": {"baseline3": 1.0, "lightgbm": 1.0},
        }  # fmt: skip
    reg = {"baseline3_choice": choice, "buckets": [list(b) for b in buckets], "selection_split": "val", "targets": targets}
    save_registry(reg, path)
    return reg


def seq_inputs(start, days, s, seed=0):
    from swf.core.settings import load_features_cfg
    from swf.align.consistency import load_coefs
    from swf.features.build import covariate_table, target_table

    hist = hist_frame(start, days, s, seed)
    cov = covariate_table(canon_frame(start, days, s), s, load_coefs())
    return hist, cov, target_table(hist.index, load_features_cfg(), s)


def tiny_lstm_hp(rnn="lstm", hidden=4):
    return {"rnn": rnn, "hidden": hidden, "layers": 2, "dropout": 0.0}


def write_tiny_lstm(models_root, name="lstm", rnn="lstm", hidden=4, seed=0):
    import json

    import numpy as np
    import torch

    from swf.evaluate.longfmt import TARGETS
    from swf.features.build import DEC_COLS, SEQ_COLS
    from swf.features.spec import artifact_meta
    from swf.predict.lstm import build_net

    hp = tiny_lstm_hp(rnn, hidden)
    nt = len(TARGETS)
    torch.manual_seed(seed)
    net = build_net(hp, len(SEQ_COLS) + nt, len(DEC_COLS) + nt, nt)
    p = models_root / name / f"{name}.pt"
    p.parent.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), p)
    off = {t: {"1-6": [-1.0, 1.0], "7-24": [-1.0, 1.0], "25-72": [-1.0, 1.0]} for t in TARGETS}
    meta = artifact_meta(None) | {
        "model": name, "enc_cols": SEQ_COLS, "dec_feature_cols": DEC_COLS, "targets": list(TARGETS),
        "encoder_hours": 168, "hp": hp, "band_offsets": off, "resid_std": [1.0] * nt,
        "norm": {"enc_mean": [0.0] * len(SEQ_COLS), "enc_std": [1.0] * len(SEQ_COLS),
                 "dec_mean": [0.0] * (len(DEC_COLS) + nt), "dec_std": [1.0] * (len(DEC_COLS) + nt)},
    }  # fmt: skip
    p.with_suffix(".json").write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
    return {"model": f"{name}/{name}.pt"}
