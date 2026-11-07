"""P10/P90 bands from per-horizon-bucket residual quantiles (D-08, D-09, MODEL-04). Shared by training and serving."""

import numpy as np
import pandas as pd

from swf.physics.constraints import enforce


def bucket_label(h: int, buckets) -> str:
    for lo, hi in buckets:
        if lo <= h <= hi:
            return f"{lo}-{hi}"
    raise ValueError(f"horizon {h} is outside every bucket {list(buckets)}")


def residual_offsets(y, p50, horizons, mask, buckets, q=(0.1, 0.9)) -> dict[str, list[float]]:
    """[q10, q90] of y - p50 per bucket; the caller's mask picks scored rows (daytime for t1_kw/ghi)."""
    r = np.asarray(y, float) - np.asarray(p50, float)
    h = np.asarray(horizons)
    ok = np.asarray(mask, bool) & np.isfinite(r)
    out = {}
    for lo, hi in buckets:
        v = r[ok & (h >= lo) & (h <= hi)]
        out[f"{lo}-{hi}"] = [round(float(x), 6) for x in np.quantile(v, q)] if len(v) else [0.0, 0.0]
    return out


def band_frame(p50: pd.Series, q10, q90, target: str, s) -> pd.DataFrame:
    """p10 <= p50 <= p90 with p50 untouched; every column clipped to physical bounds (monotone, so order survives)."""
    base = p50.to_numpy()
    cols = {"p10": np.minimum(base + q10, base), "p50": base, "p90": np.maximum(base + q90, base)}
    return pd.DataFrame(
        {k: enforce(pd.DataFrame({target: v}, index=p50.index), s)[target] for k, v in cols.items()}, index=p50.index
    )
