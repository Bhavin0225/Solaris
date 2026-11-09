"""Probabilistic metrics (EVAL-08): coverage, width, pinball, reliability."""

import numpy as np
import pandas as pd

from swf.evaluate.metrics import DAYTIME_TARGETS, daytime_mask

QUANTILES = (0.1, 0.5, 0.9)


def pinball(y, pred, q) -> float:
    e = np.asarray(y, dtype="float64") - np.asarray(pred, dtype="float64")
    return float(np.mean(np.maximum(q * e, (q - 1) * e)))


def prob_metrics(y, p10, p50, p90) -> dict:
    y, p10, p50, p90 = (np.asarray(a, dtype="float64") for a in (y, p10, p50, p90))
    n = len(y)
    if n == 0:
        return {"n": 0, "coverage": np.nan, "width": np.nan, "pinball": np.nan}
    return {
        "n": n,
        "coverage": float(np.mean((p10 <= y) & (y <= p90))),
        "width": float(np.mean(p90 - p10)),
        "pinball": float(np.mean([pinball(y, p, q) for q, p in zip(QUANTILES, (p10, p50, p90), strict=True)])),
    }


def reliability(y, p10, p50, p90) -> list[tuple[float, float]]:
    y = np.asarray(y, dtype="float64")
    return [(q, float(np.mean(y <= np.asarray(p, dtype="float64")))) for q, p in zip(QUANTILES, (p10, p50, p90), strict=True)]


def prob_rows(frames: dict, target, s, cfg) -> pd.DataFrame:
    parts = {}
    for name, df in frames.items():
        d = df[df["target"].astype(str) == target].set_index(["issue_time", "horizon"])
        for c in ("p10", "p90"):
            if d[c].isna().all():
                raise ValueError(f"model {name} has no {c} band for {target}; pass only band-producing models")
        parts[name] = d
    names = list(parts)
    idx = parts[names[0]].index
    for d in parts.values():
        idx = idx.intersection(d.index)
    ref = parts[names[0]].loc[idx]
    mask = np.isfinite(ref["y_true"].to_numpy(dtype="float64"))
    for name, d in parts.items():
        d = d.loc[idx]
        if not np.array_equal(d["y_true"].to_numpy(), ref["y_true"].to_numpy(), equal_nan=True):
            raise ValueError(f"y_true differs between models for target {target} (model {name})")
        for c in ("p10", "p50", "p90"):
            mask &= np.isfinite(d[c].to_numpy(dtype="float64"))
    if target in DAYTIME_TARGETS:
        mask &= daytime_mask(ref["target_time"], s, cfg.eval.daytime_zenith_deg)
    y = ref["y_true"].to_numpy(dtype="float64")[mask]
    rows = []
    for name, d in parts.items():
        d = d.loc[idx]
        p = [d[c].to_numpy(dtype="float64")[mask] for c in ("p10", "p50", "p90")]
        rel = reliability(y, *p)
        rows.append(
            {"target": target, "model": name, **prob_metrics(y, *p)}
            | {f"rel_q{int(q * 100)}": v for q, v in rel}
        )
    return pd.DataFrame(rows)
