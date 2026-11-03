"""Kaggle T1 wind validation (VAL-03): re-binned manufacturer curve x availability vs LV ActivePower. Pure functions, no matplotlib."""

from pathlib import Path

import pandas as pd

from swf.physics.wind import simulate_wind
from swf.validate.metrics import error_stats

_COLS = ["Date/Time", "LV ActivePower (kW)", "Wind Speed (m/s)", "Theoretical_Power_Curve (KWh)"]


def load_t1(path: Path, wc) -> pd.DataFrame:
    # usecols skips the degree-sign direction column (mojibake-prone); gaps are left as-is.
    df = pd.read_csv(path, encoding="utf-8-sig", usecols=[0, 1, 2, 3])
    if list(df.columns) != _COLS:
        raise ValueError(f"unexpected T1 header: {list(df.columns)}")
    df.columns = ["ts", "lv_kw", "ws", "theo_kw"]
    # SCADA clock stays naive: T1 is never joined with other data and its zone is unknown.
    df["ts"] = pd.to_datetime(df["ts"], format=wc.date_format)
    df = df.set_index("ts")
    if df.index.has_duplicates:
        raise ValueError("duplicate T1 timestamps")
    if (df.index.year != wc.year).any():
        raise ValueError(f"T1 rows outside year {wc.year}")
    return df


def simulate_t1(t1, s, wc, curve=None) -> pd.Series:
    # Standard air: density correction is neutral; curve is not re-fitted (D-L3).
    df = pd.DataFrame({"ws_hub": t1["ws"], "pressure": wc.pressure_hpa, "temp": wc.temp_c}, index=t1.index)
    return simulate_wind(df, s, curve)


def wind_metrics(t1, sim, s, wc) -> dict:
    norm = s.wind.rated_kw
    lo, hi = (pd.Timestamp(d) for d in wc.reference_slice)
    day = t1.index.normalize()
    masks = {
        "full_year": day.notna(),
        "ref_slice": (day >= lo) & (day <= hi),
        "jan_to_ref": day < lo,
    }
    slices = {}
    for name, m in masks.items():
        lv = t1["lv_kw"][m]
        a = error_stats(sim[m], lv, norm)
        r = error_stats(t1["theo_kw"][m], lv, norm)
        slices[name] = {
            "n": a["n"],
            "sim_nrmse_pct": a["nrmse_pct"],
            "reference_nrmse_pct": r["nrmse_pct"],
            "sim_rmse_kw": a["rmse_kw"],
            "reference_rmse_kw": r["rmse_kw"],
            "sim_mbe_pct": a["mbe_pct"],
            "reference_mbe_pct": r["mbe_pct"],
        }
    avail = s.wind.availability_loss
    # availability is not re-fitted (W4: a Jan-Aug fitted factor gave no Sep-Dec gain)
    ok = all(
        slices[k]["sim_nrmse_pct"]
        <= min(wc.target_nrmse_pct, slices[k]["reference_nrmse_pct"], wc.prd_reference_nrmse_pct)
        for k in ("full_year", "ref_slice")
    )
    return {
        "normalisation_kw": norm,
        "target_pct": wc.target_nrmse_pct,
        "prd_reference_nrmse_pct": wc.prd_reference_nrmse_pct,
        "availability_config_pct": avail * 100,
        "availability_measured_pct": float(((t1["ws"] > wc.availability_ws_ms) & (t1["lv_kw"] <= 0)).mean() * 100),
        "energy_ratio": float(t1["lv_kw"].sum() / (sim / (1 - avail)).sum()),
        "slices": slices,
        "pass": bool(ok),
    }
