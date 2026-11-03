"""Kaggle solar plant validation (VAL-01/02): sensor POA + module temperature -> ac_from_poa. Pure functions, no matplotlib."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from pvlib import temperature

from swf.physics.solar import ac_cap_kw, ac_from_poa
from swf.validate.metrics import error_stats

log = logging.getLogger("swf.validate")


def heldout_start_utc(vs) -> pd.Timestamp:
    """Configured plant-local held-out date -> UTC, the single conversion of the boundary."""
    return (
        pd.Timestamp(vs.heldout_start_local)
        .tz_localize(vs.local_timezone)
        .tz_convert("UTC")
    )


def load_plant(gen_csv: Path, wx_csv: Path, pc, vs) -> tuple[pd.DataFrame, dict]:
    """Parse one plant: UTC-indexed frame (ac_kw, irr_kw_m2, t_module, t_ambient) plus stats."""
    gen_csv, wx_csv = Path(gen_csv), Path(wx_csv)
    gen = pd.read_csv(
        gen_csv,
        usecols=["DATE_TIME", "SOURCE_KEY", "AC_POWER"],
        encoding="utf-8-sig",
    )  # DC_POWER is mis-scaled, never read
    gen["DATE_TIME"] = pd.to_datetime(
        gen["DATE_TIME"], format=pc.generation_date_format
    )
    if gen.duplicated(["DATE_TIME", "SOURCE_KEY"]).any():
        raise ValueError(f"{gen_csv}: duplicate (DATE_TIME, SOURCE_KEY) rows")
    wx = pd.read_csv(
        wx_csv,
        encoding="utf-8-sig",
        usecols=[
            "DATE_TIME",
            "AMBIENT_TEMPERATURE",
            "MODULE_TEMPERATURE",
            "IRRADIATION",
        ],
    )
    wx["DATE_TIME"] = pd.to_datetime(wx["DATE_TIME"], format=vs.weather_date_format)
    if wx["DATE_TIME"].duplicated().any():
        raise ValueError(f"{wx_csv}: duplicate weather timestamps")
    lo, hi = vs.irradiation_max_range_kw_m2
    irr_max = float(wx["IRRADIATION"].max())
    if not lo < irr_max < hi:
        raise ValueError(
            f"{wx_csv}: IRRADIATION max {irr_max} kW/m2 outside {lo}..{hi}: check units"
        )

    # per-inverter dropouts: zero AC while the sensor says it is bright
    j = gen.merge(wx[["DATE_TIME", "IRRADIATION"]], on="DATE_TIME")
    bright = j[j["IRRADIATION"] > vs.dropout_irradiation_kw_m2]
    zero_pct = (bright["AC_POWER"] == 0).groupby(bright["SOURCE_KEY"]).mean() * 100

    agg = gen.groupby("DATE_TIME").agg(
        ac_kw=("AC_POWER", "sum"), n_inv=("AC_POWER", "count")
    )
    # count skips NaN AC_POWER, so a missing reading drops the timestamp
    full = agg[agg["n_inv"] == vs.n_inverters].drop(columns="n_inv")
    wx = wx.set_index("DATE_TIME").rename(
        columns={
            "IRRADIATION": "irr_kw_m2",
            "MODULE_TEMPERATURE": "t_module",
            "AMBIENT_TEMPERATURE": "t_ambient",
        }
    )
    df = full.join(wx, how="inner")  # by timestamp, never row order
    if df.empty:
        raise ValueError(
            f"{gen_csv}: no timestamps with all {vs.n_inverters} inverters and weather"
        )
    first, last = df.index.min().date(), df.index.max().date()
    if (first, last) != tuple(vs.span_local):
        raise ValueError(
            f"{gen_csv}: span {first}..{last} != configured {vs.span_local}"
        )
    tune_rows = df[df.index.tz_localize(vs.local_timezone).tz_convert("UTC") < heldout_start_utc(vs)]
    if tune_rows.empty:
        raise ValueError(f"{gen_csv}: no rows before the held-out start")
    stats = {
        "ts_total": len(agg),
        "ts_partial_dropped": int((agg["n_inv"] != vs.n_inverters).sum()),
        "ts_no_weather": int((~full.index.isin(wx.index)).sum()),
        "rows_out": len(df),
        # tune-window peak only: the dc_kwp anchor / AC cap / nRMSE denominator must not see held-out data
        "peak_ac_kw": float(tune_rows["ac_kw"].max()),
        "peak_ac_kw_all_rows": float(df["ac_kw"].max()),
        "irr_max_kw_m2": irr_max,
        "zero_ac_daytime_pct_worst_inverter": float(zero_pct.max()),
        "zero_ac_daytime_pct_median_inverter": float(zero_pct.median()),
    }
    log.info(
        "%s: dropped %d partial, %d without weather",
        gen_csv.name, stats["ts_partial_dropped"], stats["ts_no_weather"],
    )  # fmt: skip
    df.index = df.index.tz_localize(vs.local_timezone).tz_convert(
        "UTC"
    )  # the only local->UTC of data
    return df, stats


def plant_settings(s, peak_ac_kw: float, loss_pct: float):
    """Settings copy whose AC cap equals the observed peak (same dc_ac_ratio/eta convention as plant.yaml)."""
    return s.model_copy(
        update={
            "solar": s.solar.model_copy(
                update={
                    "dc_kwp": s.solar.dc_ac_ratio * peak_ac_kw / s.solar.eta_inv_nom,
                    "loss_pct": loss_pct,
                }
            )
        }
    )


def daytime(df: pd.DataFrame, vs) -> pd.Series:
    return df["irr_kw_m2"] > vs.day_irradiation_kw_m2


def is_heldout(df: pd.DataFrame, start_utc: pd.Timestamp) -> np.ndarray:
    return np.asarray(df.index >= start_utc)


def simulate_plant(df: pd.DataFrame, s_plant, temp: str = "module") -> pd.Series:
    poa = df["irr_kw_m2"] * 1000  # kW/m2 POA -> W/m2
    tc = (
        temperature.faiman(poa, df["t_ambient"]) if temp == "faiman" else df["t_module"]
    )
    return ac_from_poa(poa, tc, s_plant)


def _nrmse(df, s_plant, mask, temp="module") -> float:
    sim = simulate_plant(df[mask], s_plant, temp)
    return error_stats(sim, df.loc[mask, "ac_kw"], ac_cap_kw(s_plant))["nrmse_pct"]


def tune_loss(df, s, vs, peak_ac_kw: float, start_utc: pd.Timestamp) -> dict:
    tune = (daytime(df, vs) & ~is_heldout(df, start_utc)).to_numpy()
    lo, hi = vs.loss_grid_pct
    curve = {
        str(k): _nrmse(df, plant_settings(s, peak_ac_kw, k), tune)
        for k in range(lo, hi + 1)
    }
    best = min(curve, key=curve.get)  # first on ties
    return {
        "loss_pct_tuned": int(best),
        "loss_curve": curve,
        "loss_edge": int(best) in (lo, hi),
    }


def validate_plant(
    df, stats, s, vs, gating: bool, ref_loss_pct: float | None = None
) -> dict:
    peak, start = stats["peak_ac_kw"], heldout_start_utc(vs)
    tuned = tune_loss(df, s, vs, peak, start)
    day = daytime(df, vs).to_numpy()
    held = is_heldout(df, start)
    masks = {"tune": day & ~held, "heldout": day & held, "full": day}
    sp = plant_settings(s, peak, tuned["loss_pct_tuned"])
    cfg = plant_settings(s, peak, s.solar.loss_pct)
    norm = ac_cap_kw(sp)
    sim = simulate_plant(df, sp)
    full = error_stats(sim[day], df["ac_kw"][day], norm)
    hourly = (
        pd.DataFrame({"sim": sim[day], "act": df["ac_kw"][day]})
        .resample("1h")
        .mean()
        .dropna()
    )
    out = {
        "gating": gating,
        "dc_kwp": float(sp.solar.dc_kwp),
        "ac_cap_kw": float(norm),
        **tuned,
        "tune_nrmse_pct": _nrmse(df, sp, masks["tune"]),
        "heldout_nrmse_pct": _nrmse(df, sp, masks["heldout"]),
        "full_nrmse_pct": full["nrmse_pct"],
        "hourly_nrmse_pct": error_stats(hourly["sim"], hourly["act"], norm)[
            "nrmse_pct"
        ],
        "rmse_kw": full["rmse_kw"],
        "mae_kw": full["mae_kw"],
        "mbe_pct": full["mbe_pct"],
        "n_rows": full["n"],
        "config_loss_pct": float(s.solar.loss_pct),
        "heldout_nrmse_at_config_loss_pct": _nrmse(df, cfg, masks["heldout"]),
        "full_nrmse_at_config_loss_pct": _nrmse(df, cfg, masks["full"]),
        "full_nrmse_faiman_pct": _nrmse(df, sp, masks["full"], "faiman"),
        "target_pct": float(vs.target_nrmse_pct),
    }
    if ref_loss_pct is not None:
        ref = plant_settings(s, peak, ref_loss_pct)
        out["heldout_nrmse_at_ref_loss_pct"] = _nrmse(df, ref, masks["heldout"])
        out["full_nrmse_at_ref_loss_pct"] = _nrmse(df, ref, masks["full"])
    out["pass"] = bool(out["heldout_nrmse_pct"] <= vs.target_nrmse_pct)
    out["pass_at_config_loss"] = bool(
        out["heldout_nrmse_at_config_loss_pct"] <= vs.target_nrmse_pct
    )
    return {**stats, **out}
