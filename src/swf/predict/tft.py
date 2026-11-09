"""TFT runtime (MODEL-03, D-19, D-20, D-26): native P10/P50/P90 from a darts TFTModel; darts imported lazily.

Artifacts are darts pickles: load only trusted, locally trained files under models/ (artifact_path blocks escapes).
"""

import functools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from swf.features.spec import assert_spec
from swf.predict.registry import artifact_path

QS = ("0.100", "0.500", "0.900")  # darts 0.48.1 component suffixes (assumption A1 checked: 3 decimals)


def COV_COLS(meta) -> list[str]:  # noqa: N802
    return list(meta["dec_feature_cols"]) + [f"b3_{t}" for t in meta["targets"]]


def _ts(values, times, columns):
    from darts import TimeSeries

    # darts wants naive times; every value here is UTC by construction.
    return TimeSeries.from_times_and_values(times, np.asarray(values, "float32"), columns=columns)


def origin_inputs(meta, enc_y, past_cov, fut_cov, origins, y_fut=None):
    """Per-origin darts series. Target spans origin-(L-1)h..origin (+72 h of labels when y_fut is given, training/ES only);
    covariates always span origin-(L-1)h..origin+72h. NaN cells become the training mean (0 after standardising)."""
    n = meta["norm"]
    ym, ys = np.asarray(n["y_mean"], "float32"), np.asarray(n["y_std"], "float32")
    cm, cs = np.asarray(n["cov_mean"], "float32"), np.asarray(n["cov_std"], "float32")
    enc_y = np.asarray(enc_y, "float32")
    cov = (np.concatenate([past_cov, fut_cov], 1).astype("float32") - cm) / cs
    y = enc_y if y_fut is None else np.concatenate([enc_y, np.asarray(y_fut, "float32")], 1)
    y, cov = np.nan_to_num((y - ym) / ys), np.nan_to_num(cov)
    L = enc_y.shape[1]
    tcols, ccols = list(meta["targets"]), COV_COLS(meta)
    series, covs = [], []
    for i, o in enumerate(pd.DatetimeIndex(origins)):
        o = o.tz_convert("UTC").tz_localize(None) if o.tzinfo is not None else o
        t0 = o - pd.Timedelta(hours=L - 1)
        series.append(_ts(y[i], pd.date_range(t0, periods=y.shape[1], freq="h"), tcols))
        covs.append(_ts(cov[i], pd.date_range(t0, periods=cov.shape[1], freq="h"), ccols))
    return series, covs


def quantiles(model, meta, series, covs, batch) -> np.ndarray:
    """[N,72,5,3] un-normalised, sorted across q."""
    preds = model.predict(
        n=72, series=series, future_covariates=covs, predict_likelihood_parameters=True, batch_size=batch
    )
    if not isinstance(preds, list):
        preds = [preds]
    ym, ys = np.asarray(meta["norm"]["y_mean"]), np.asarray(meta["norm"]["y_std"])
    out = np.empty((len(preds), 72, len(meta["targets"]), len(QS)), np.float64)
    for i, p in enumerate(preds):
        comps = list(p.components)
        for j, t in enumerate(meta["targets"]):
            for k, q in enumerate(QS):
                name = f"{t}_q{q}"
                if name not in comps:
                    raise ValueError(f"expected component {name!r}; darts returned {comps}")
                out[i, :, j, k] = p.values()[:, comps.index(name)] * ys[j] + ym[j]
    return np.sort(out, axis=-1)


@functools.lru_cache(maxsize=4)
def _load(path_str: str, mtime_ns: int):
    from darts.models import TFTModel

    meta = json.loads(Path(path_str).with_suffix(".json").read_text(encoding="utf-8"))
    assert_spec(meta)
    return TFTModel.load(path_str, map_location="cpu"), meta


def predict_quantiles(entry: dict, X: pd.DataFrame, target: str, models_root):
    seq = X.attrs.get("seq")
    if seq is None:
        raise ValueError("tft runtime needs X.attrs['seq'] (encoder window and live baseline 3)")
    rel = entry["artifacts"]["model"]
    key = "q:" + rel
    if key not in seq:
        p = artifact_path(rel, models_root)
        model, meta = _load(str(p), p.stat().st_mtime_ns)
        origin = X.index.get_level_values("issue_time")[0]
        T = origin + pd.to_timedelta(X["horizon"].to_numpy().astype(int), unit="h")
        L, dec_cols, tg = meta["encoder_hours"], meta["dec_feature_cols"], meta["targets"]
        enc = seq["enc"]
        if len(enc) != L:
            raise ValueError(f"encoder window has {len(enc)} rows, expected {L}")
        t_enc = origin - pd.to_timedelta(np.arange(L - 1, -1, -1), unit="h")
        b3 = seq["b3"][tg]
        past = np.concatenate([enc[dec_cols].to_numpy("float32"), b3.reindex(t_enc).to_numpy("float32")], 1)
        fut = np.concatenate([X[dec_cols].to_numpy("float32"), b3.reindex(T).to_numpy("float32")], 1)
        s, c = origin_inputs(meta, enc[tg].to_numpy("float32")[None], past[None], fut[None], [origin])
        seq[key] = (quantiles(model, meta, s, c, 1)[0], list(tg))
    arr, tg = seq[key]
    j = tg.index(target)
    return arr[:, j, 0], arr[:, j, 1], arr[:, j, 2]


def predict_p50(entry: dict, X: pd.DataFrame, b3, target: str, models_root) -> np.ndarray:
    return predict_quantiles(entry, X, target, models_root)[1]
