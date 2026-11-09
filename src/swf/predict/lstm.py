"""LSTM/GRU seq2seq runtime (MODEL-02, D-16, D-25): p50 = baseline 3 + residual network. torch is imported lazily."""

import functools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from swf.features.spec import assert_spec
from swf.predict.registry import artifact_path


def build_net(hp: dict, n_enc: int, n_dec: int, n_out: int):
    import torch

    rnn = {"lstm": torch.nn.LSTM, "gru": torch.nn.GRU}[hp["rnn"]]
    drop = hp["dropout"] if hp["layers"] > 1 else 0.0

    class Seq2Seq(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = rnn(n_enc, hp["hidden"], hp["layers"], dropout=drop, batch_first=True)
            self.dec = rnn(n_dec, hp["hidden"], hp["layers"], dropout=drop, batch_first=True)
            self.head = torch.nn.Linear(hp["hidden"], n_out)

        def forward(self, enc, dec):
            _, state = self.enc(enc)
            out, _ = self.dec(dec, state)
            return self.head(out)

    return Seq2Seq()


def n_enc_channels(meta) -> int:
    return len(meta["enc_cols"]) + len(meta["targets"])  # + NaN-mask per target history column


def n_dec_channels(meta) -> int:
    return len(meta["dec_feature_cols"]) + len(meta["targets"])  # + b3 per target


def prep(meta, enc, dec, b3):
    """Standardise; NaN-mask channels for the target history; NaN -> 0. float32 in, float32 out."""
    n, nt = meta["norm"], len(meta["targets"])
    enc = np.asarray(enc, np.float32)
    mask = np.isnan(enc[..., :nt]).astype(np.float32)
    e = (enc - np.asarray(n["enc_mean"], np.float32)) / np.asarray(n["enc_std"], np.float32)
    e = np.nan_to_num(np.concatenate([e, mask], -1)).astype(np.float32)
    d = np.concatenate([np.asarray(dec, np.float32), np.asarray(b3, np.float32)], -1)
    d = (d - np.asarray(n["dec_mean"], np.float32)) / np.asarray(n["dec_std"], np.float32)
    return e, np.nan_to_num(d).astype(np.float32)


def forecast(net, meta, enc, dec, b3, device="cpu", batch=1024) -> np.ndarray:
    import torch

    e, d = prep(meta, enc, dec, b3)
    net.eval().to(device)
    outs = []
    with torch.no_grad():
        for i in range(0, len(e), batch):
            eb = torch.from_numpy(e[i : i + batch]).to(device)
            db = torch.from_numpy(d[i : i + batch]).to(device)
            outs.append(net(eb, db).cpu().numpy())
    out = np.concatenate(outs) if outs else np.empty((0, d.shape[1], len(meta["targets"])), np.float32)
    return np.asarray(b3, np.float64) + out.astype(np.float64) * np.asarray(meta["resid_std"], np.float64)


@functools.lru_cache(maxsize=8)
def _load(path_str: str, mtime_ns: int):
    # shortcut: nets cached per (path, mtime); restart the server if models/ is replaced wholesale.
    import torch

    meta = json.loads(Path(path_str).with_suffix(".json").read_text(encoding="utf-8"))
    assert_spec(meta)
    net = build_net(meta["hp"], n_enc_channels(meta), n_dec_channels(meta), len(meta["targets"]))
    net.load_state_dict(torch.load(path_str, map_location="cpu", weights_only=True))
    return net.eval(), meta


def predict_p50(entry: dict, X: pd.DataFrame, b3, target: str, models_root) -> np.ndarray:
    seq = X.attrs.get("seq")
    if seq is None:
        raise ValueError("lstm runtime needs X.attrs['seq'] (encoder window and live baseline 3)")
    rel = entry["artifacts"]["model"]
    key = "out:" + rel
    if key not in seq:
        p = artifact_path(rel, models_root)
        net, meta = _load(str(p), p.stat().st_mtime_ns)
        origin = X.index.get_level_values("issue_time")[0]
        T = origin + pd.to_timedelta(X["horizon"].to_numpy().astype(int), unit="h")
        if len(seq["enc"]) != meta["encoder_hours"]:
            raise ValueError(f"encoder window has {len(seq['enc'])} rows, expected {meta['encoder_hours']}")
        enc = seq["enc"][meta["enc_cols"]].to_numpy("float32")[None]
        dec = X[meta["dec_feature_cols"]].to_numpy("float32")[None]
        b3all = seq["b3"].reindex(T)[meta["targets"]].to_numpy("float32")[None]
        seq[key] = (forecast(net, meta, enc, dec, b3all)[0], list(meta["targets"]))
    arr, targets = seq[key]
    return arr[:, targets.index(target)].astype(float)
