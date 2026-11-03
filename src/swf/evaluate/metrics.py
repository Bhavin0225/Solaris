"""Metrics on the shared scored sample (EVAL-05/06): numpy/pandas only, no sklearn (serving image may import it)."""

import numpy as np
import pandas as pd

from swf.physics.common import solar_position
from swf.physics.solar import ac_cap_kw

DAYTIME_TARGETS = ("t1_kw", "ghi")
SEASONS = ("all", "monsoon", "dry")
NAN_METRICS = {"mae": np.nan, "rmse": np.nan, "mbe": np.nan, "nrmse_pct": np.nan}


def metrics(y, p, norm, norm_kind) -> dict:
    y = np.asarray(y, dtype="float64")
    p = np.asarray(p, dtype="float64")
    ok = np.isfinite(y) & np.isfinite(p)
    n = int(ok.sum())
    out = {"n": n, **NAN_METRICS, "norm": norm, "norm_kind": norm_kind}
    if n:
        e = p[ok] - y[ok]
        rmse = float(np.sqrt(np.mean(e**2)))
        out.update(
            mae=float(np.mean(np.abs(e))),
            rmse=rmse,
            mbe=float(np.mean(e)),
            nrmse_pct=rmse / norm * 100,
        )
    return out


def norm_for(target, y_shared, s) -> tuple[float, str]:
    if target == "t1_kw":
        return float(ac_cap_kw(s)), "solar_ac_capacity_kw"
    if target == "t5_kw":
        return float(s.wind.rated_kw), "wind_rated_kw"
    return float(
        np.mean(np.asarray(y_shared, dtype="float64"))
    ), "mean_actual_shared_sample"


def skill(rmse, rmse_ref) -> float:
    if (
        rmse_ref is None
        or not np.isfinite(rmse_ref)
        or rmse_ref == 0
        or not np.isfinite(rmse)
    ):
        return float("nan")
    return float(1 - rmse / rmse_ref)


def daytime_mask(target_time, s, zenith_deg) -> np.ndarray:
    return (
        solar_position(pd.DatetimeIndex(target_time), s)["zenith"].to_numpy()
        < zenith_deg
    )


def align_models(frames: dict, target) -> pd.DataFrame:
    """Wide frame indexed (issue_time, horizon): target_time, y_true, one p50 column per model."""
    wide = None
    for name, df in frames.items():
        d = df[df["target"].astype(str) == target].set_index(["issue_time", "horizon"])
        d = d[["target_time", "y_true", "p50"]].rename(columns={"p50": name})
        if wide is None:
            wide = d
            continue
        both = wide[["y_true"]].join(d[["y_true"]], how="inner", rsuffix="_new")
        if not np.array_equal(
            both["y_true"].to_numpy(), both["y_true_new"].to_numpy(), equal_nan=True
        ):
            raise ValueError(
                f"y_true differs between models for target {target} (model {name})"
            )
        wide = wide.join(d, how="outer", rsuffix="_new")
        for c in ("target_time", "y_true"):
            wide[c] = wide[c].fillna(wide.pop(c + "_new"))
    return wide


def scored_mask(wide, models, target, s, zenith_deg) -> np.ndarray:
    m = np.isfinite(wide["y_true"].to_numpy(dtype="float64"))
    for k in models:
        m &= np.isfinite(wide[k].to_numpy(dtype="float64"))
    if target in DAYTIME_TARGETS:
        m &= daytime_mask(wide["target_time"], s, zenith_deg)
    return m


def _season(wide, cfg) -> np.ndarray:
    month = pd.DatetimeIndex(wide["target_time"]).month
    return np.where(np.isin(month, list(cfg.monsoon_months)), "monsoon", "dry")


def breakdown(
    wide, models, target, s, cfg, refs=("baseline3", "persistence")
) -> pd.DataFrame:
    mask = scored_mask(wide, models, target, s, cfg.eval.daytime_zenith_deg)
    y = wide["y_true"].to_numpy(dtype="float64")
    norm, kind = norm_for(target, y[mask], s)
    hor = wide.index.get_level_values("horizon").to_numpy()
    season = _season(wide, cfg)
    present = [r for r in refs if r in models]
    rows = []
    for h in [*cfg.eval.horizons, "all"]:
        hm = np.ones(len(wide), bool) if h == "all" else hor == h
        for se in SEASONS:
            sm = np.ones(len(wide), bool) if se == "all" else season == se
            sel = mask & hm & sm
            res = {
                k: metrics(y[sel], wide[k].to_numpy(dtype="float64")[sel], norm, kind)
                for k in models
            }
            for k in models:
                row = {
                    "target": target,
                    "model": k,
                    "horizon": str(h),
                    "season": se,
                    **res[k],
                }
                for r in refs:
                    row[f"skill_vs_{r}"] = (
                        skill(res[k]["rmse"], res[r]["rmse"])
                        if r in present
                        else np.nan
                    )
                rows.append(row)
    return pd.DataFrame(rows)


def leaderboard_rows(
    wide, models, target, s, cfg, refs=("baseline3", "persistence")
) -> pd.DataFrame:
    z = cfg.eval.daytime_zenith_deg
    mask = scored_mask(wide, models, target, s, z)
    day = (
        daytime_mask(wide["target_time"], s, z)
        if target in DAYTIME_TARGETS
        else np.ones(len(wide), bool)
    )
    y = wide["y_true"].to_numpy(dtype="float64")
    n_possible = int((np.isfinite(y) & day).sum())
    n_shared = int(mask.sum())
    frac = n_shared / n_possible if n_possible else 0.0
    if frac < cfg.eval.min_shared_frac:
        raise ValueError(
            f"{target}: shared sample is {frac:.2%} of {n_possible} possible rows "
            f"(< min_shared_frac {cfg.eval.min_shared_frac})"
        )
    bd = breakdown(wide, models, target, s, cfg, refs)
    bd = bd[(bd["horizon"] == "all") & (bd["season"] == "all")].drop(
        columns=["horizon", "season"]
    )
    own = []
    for k in models:
        p = wide[k].to_numpy(dtype="float64")
        ok = np.isfinite(y) & np.isfinite(p) & day
        own.append(
            {
                "model": k,
                "n_own": int(ok.sum()),
                "rmse_own": metrics(y[ok], p[ok], 1.0, "")["rmse"],
            }
        )
    out = bd.merge(pd.DataFrame(own), on="model").rename(columns={"n": "n_shared"})
    out["shared_frac"] = frac
    cols = ["target", "model", "n_own", "rmse_own", "n_shared", "shared_frac", "mae", "rmse", "mbe",
            "nrmse_pct", "norm", "norm_kind", "skill_vs_baseline3", "skill_vs_persistence"]  # fmt: skip
    return out[cols].reset_index(drop=True)
