"""LightGBM runtime: p50 = baseline 3 + bucketed residual booster. lightgbm is imported lazily."""

import functools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from swf.features.spec import assert_spec
from swf.predict.registry import artifact_path


@functools.lru_cache(maxsize=32)
def _load(path_str: str, mtime_ns: int):
    # shortcut: boosters cached per (path, mtime); restart the server if models/ is replaced wholesale.
    import lightgbm as lgb

    meta = json.loads(Path(path_str).with_suffix(".json").read_text(encoding="utf-8"))
    assert_spec(meta)
    return lgb.Booster(model_file=path_str), meta  # text model, never pickle


def predict_p50(entry: dict, X: pd.DataFrame, b3: np.ndarray, target: str, models_root) -> np.ndarray:
    out = np.asarray(b3, float).copy()
    h = X["horizon"].to_numpy()
    for label, rel in entry["artifacts"].items():
        lo, hi = (int(v) for v in label.split("-"))
        p = artifact_path(rel, models_root)
        booster, meta = _load(str(p), p.stat().st_mtime_ns)
        m = (h >= lo) & (h <= hi)
        if m.any():
            out[m] += booster.predict(X.loc[m, meta["feature_columns"]])
    return out
