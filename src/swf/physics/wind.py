"""Wind chain (PRD 4.3): empirical power curve, density-corrected hub speed, cut-out, availability loss."""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from swf.core.paths import CONFIG_DIR
from swf.core.settings import load_settings
from swf.fetch.kaggle import require_kaggle_files
from swf.physics.common import RHO0, air_density

log = logging.getLogger("swf.physics")


def build_power_curve(t1_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(t1_csv, encoding="utf-8-sig")
    df = df[["Date/Time", "Wind Speed (m/s)", "Theoretical_Power_Curve (KWh)"]]
    pd.to_datetime(df["Date/Time"], format="%d %m %Y %H:%M")  # fail loud on a wrong date order
    # centre bins: left-edge bins would shift the curve ~0.25 m/s high
    centre = (df["Wind Speed (m/s)"] * 2).round() / 2
    out = df["Theoretical_Power_Curve (KWh)"].groupby(centre).median().dropna()
    return out.rename_axis("speed_ms").rename("kw").reset_index().sort_values("speed_ms", ignore_index=True)


def parametric_curve(s) -> pd.DataFrame:
    w = s.wind
    v = np.arange(0, w.cut_out_ms + 0.25, 0.5)
    # not the PRD simple cubic: that gives 382 kW at 8 m/s against about 1,527 kW on the real curve (decision W-3)
    p = w.rated_kw * (v**3 - w.cut_in_ms**3) / (w.rated_ms**3 - w.cut_in_ms**3)
    p = np.where(v < w.cut_in_ms, 0.0, np.minimum(p, w.rated_kw))
    return pd.DataFrame({"speed_ms": v, "kw": p})


def load_power_curve(s, config_dir: Path | None = None) -> pd.DataFrame:
    path = Path(config_dir or CONFIG_DIR) / s.wind.power_curve_csv
    if path.exists():
        return pd.read_csv(path)
    log.warning("power curve file missing, using parametric fallback (%s)", path)
    return parametric_curve(s)


def simulate_wind(df: pd.DataFrame, s, curve: pd.DataFrame | None = None) -> pd.Series:
    w = s.wind
    curve = load_power_curve(s) if curve is None else curve
    rho = air_density(df["pressure"], df["temp"])
    v = df["ws_hub"] * (rho / RHO0) ** (1 / 3)  # density applied once, on hub speed
    p = np.interp(v, curve["speed_ms"], curve["kw"], left=0.0, right=curve["kw"].iloc[-1])
    p = np.where(v >= w.cut_out_ms, 0.0, p) * (1 - w.availability_loss)
    p = np.where(np.isnan(v), np.nan, np.clip(p, 0.0, w.rated_kw))
    return pd.Series(p, index=df.index, name="t5_kw")


def run(args: argparse.Namespace) -> int:
    s = load_settings()
    files = require_kaggle_files(s)
    curve = build_power_curve(files["T1.csv"])
    curve.to_csv(CONFIG_DIR / s.wind.power_curve_csv, index=False, float_format="%.4f", lineterminator="\n")
    at = {v: float(np.interp(v, curve["speed_ms"], curve["kw"])) for v in (3.0, 8.0, 13.0)}
    print(f"{len(curve)} bins; kW at 3/8/13 m/s: {at[3.0]:.1f} / {at[8.0]:.1f} / {at[13.0]:.1f}")
    return 0
