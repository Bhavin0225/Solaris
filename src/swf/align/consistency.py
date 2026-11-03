"""NASA-vs-reference (ERA5) consistency table and monthly linear correction (D-01..D-04, D-17).

numpy/pandas only: the serving image has no sklearn.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from swf.align.canon import PHYS_RANGES
from swf.core.paths import CONFIG_DIR
from swf.core.settings import Settings
from swf.physics.common import is_night

VARS = ("ghi", "rh", "ws10", "ws_hub")
LOG_ONLY = ("temp", "pressure")
_COLS = ["variable", "month", "n", "nasa_mean", "bias", "rmse", "corr"]


def _pairs(nasa, ref, var, s, years=None):
    """Pairwise-clean (n=NASA, r=ref) for var; GHI daytime only."""
    idx = nasa.index.intersection(ref.index)
    if years is not None:
        idx = idx[(idx.year >= years[0]) & (idx.year <= years[1])]
    d = pd.DataFrame({"n": nasa.loc[idx, var], "r": ref.loc[idx, var]}).dropna()
    if var == "ghi" and len(d):
        d = d[~is_night(d.index, s)]
    return d


def monthly_table(nasa, ref, s: Settings, years=None) -> pd.DataFrame:
    """bias = ref - nasa (D-01); month 0 is the all-months row."""
    rows = []
    for var in VARS + LOG_ONLY:
        d = _pairs(nasa, ref, var, s, years)
        for m, g in [*d.groupby(d.index.month), (0, d)]:
            if g.empty:
                continue
            err = g["r"] - g["n"]
            rows.append(
                {
                    "variable": var,
                    "month": int(m),
                    "n": len(g),
                    "nasa_mean": float(g["n"].mean()),
                    "bias": float(err.mean()),
                    "rmse": float(np.sqrt((err**2).mean())),
                    "corr": float(g["r"].corr(g["n"])) if len(g) > 1 else np.nan,
                }
            )
    return pd.DataFrame(rows, columns=_COLS)


def decide(table: pd.DataFrame, s: Settings) -> dict[str, dict]:
    """A variable is corrected when any month 1-12 exceeds its threshold (D-17)."""
    out = {}
    rel = s.align.wind_rel_threshold
    for var in VARS:
        thr = s.align.thresholds[var]
        wind = var in ("ws10", "ws_hub")
        t = table[(table["variable"] == var) & (table["month"] > 0)]
        lim = np.minimum(thr, rel * t["nasa_mean"]) if wind else thr
        months = [int(m) for m in t.loc[t["bias"].abs() > lim, "month"]]
        desc = f"abs bias > {thr:g}" + (f" or > {rel:.0%} of NASA mean" if wind else "")
        out[var] = {"correct": bool(months), "months_exceeding": months, "threshold": desc}
    return out


def fit_correction(nasa, ref, s: Settings, variables) -> dict:
    """y_NASA = a * x_ref + b per variable per UTC month, fit on s.align.fit_years only (D-04)."""
    res = {}
    for var in variables:
        d = _pairs(nasa, ref, var, s, s.align.fit_years)
        res[var] = {}
        for m, g in d.groupby(d.index.month):
            a, b = np.polyfit(g["r"].to_numpy(), g["n"].to_numpy(), 1)
            res[var][str(int(m))] = {"a": float(a), "b": float(b), "n": len(g)}
    return {"source": "era5", "fit_years": list(s.align.fit_years), "variables": res}


def save_coefs(coefs: dict, path: Path) -> None:
    text = json.dumps(coefs, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def load_coefs(path: Path | None = None) -> dict:
    path = Path(path) if path else CONFIG_DIR / "bias_correction.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `python -m swf build-weather` to create it")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_correction(df: pd.DataFrame, coefs: dict, s: Settings) -> pd.DataFrame:
    """Map reference (ERA5) columns into NASA space.

    The one function used by both training (Phase 4) and serving (Phase 5).
    """
    out = df.copy()
    month = pd.Series(out.index.month, index=out.index)
    night = is_night(out.index, s) if "ghi" in coefs["variables"] else None
    for var, per_month in coefs["variables"].items():
        if var not in out.columns:
            continue
        a = month.map({int(k): v["a"] for k, v in per_month.items()})
        b = month.map({int(k): v["b"] for k, v in per_month.items()})
        x = out[var]
        y = (a * x + b).where(a.notna(), x)  # month without coefficients: unchanged
        if var == "ghi":
            y = y.mask(night & x.notna(), 0.0)
        lo, hi = PHYS_RANGES[var]
        out[var] = y.clip(lo, hi)
    return out
