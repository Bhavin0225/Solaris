"""Two-axis causal feature builder (FEAT-01/02): origin-axis history, target-axis calendar/geometry/covariates, joined by integer gather."""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from swf.align.adapters import openmeteo_canon
from swf.align.clean import RADIATION, clean
from swf.align.consistency import apply_correction
from swf.core.settings import load_features_cfg
from swf.features.history import history_frame
from swf.features.spec import (
    CALENDAR_COLS,
    COVARIATE_COLS,
    GEOMETRY_COLS,
    TARGETS,
    feature_columns,
    history_cols,
    lead_k,
)
from swf.physics.common import clearsky, is_night, solar_position

F32 = np.float32
_COV_SCALARS = ("ghi", "dni", "dhi", "temp", "rh", "pressure", "ws10", "ws_hub", "precip", "cloud")


def check_hourly(idx) -> None:
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None or str(idx.tz) != "UTC":
        raise ValueError("index must be a tz-aware UTC DatetimeIndex")
    if not idx.is_unique:
        raise ValueError("index has duplicate labels")
    if not idx.is_monotonic_increasing:
        raise ValueError("index is not sorted")
    if len(idx) > 1 and not ((idx[1:] - idx[:-1]) == pd.Timedelta(hours=1)).all():
        raise ValueError("index is not strictly hourly (gap or irregular step)")


def _trailing(x: np.ndarray, w: int):
    """Trailing mean/std(ddof=1), each window computed independently; NaN-padded, NaN in window -> NaN."""
    n = len(x)
    mean = np.full(n, np.nan)
    std = np.full(n, np.nan)
    if n >= w:
        win = sliding_window_view(x, w)
        mean[w - 1 :] = win.mean(axis=1)
        std[w - 1 :] = win.std(axis=1, ddof=1)
    return mean, std


def _csi(ghi, idx, s, cfg):
    cs = clearsky(idx, s)["ghi"].to_numpy()
    day = solar_position(idx, s)["zenith"].to_numpy() < cfg.eval.daytime_zenith_deg
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(day, np.asarray(ghi) / cs, 0.0)


def origin_table(hist: pd.DataFrame, cfg, s) -> pd.DataFrame:
    check_hourly(hist.index)
    out: dict[str, np.ndarray] = {}
    for c in TARGETS:
        x = hist[c]
        for k in cfg.lags:
            out[f"{c}_lag{k}"] = x.shift(k).to_numpy()
        for w in cfg.windows:
            out[f"{c}_roll{w}_mean"], out[f"{c}_roll{w}_std"] = _trailing(x.to_numpy(float), w)
    out["csi_hist"] = _csi(hist["ghi"].to_numpy(), hist.index, s, cfg)
    return pd.DataFrame(out, index=hist.index)[history_cols(cfg)].astype(F32)


def target_table(index, cfg, s) -> pd.DataFrame:
    check_hourly(index)
    h = 2 * np.pi * index.hour.to_numpy() / 24
    d = 2 * np.pi * index.dayofyear.to_numpy() / 365.25
    sp = solar_position(index, s)
    az = np.radians(sp["azimuth"].to_numpy())
    cols = {
        "hour_sin": np.sin(h), "hour_cos": np.cos(h), "doy_sin": np.sin(d), "doy_cos": np.cos(d),
        "monsoon": index.month.isin(cfg.monsoon_months).astype(float),
        "zenith": sp["zenith"].to_numpy(), "azimuth_sin": np.sin(az), "azimuth_cos": np.cos(az),
        "clearsky_ghi": clearsky(index, s)["ghi"].to_numpy(),
    }  # fmt: skip
    return pd.DataFrame(cols, index=index)[CALENDAR_COLS + GEOMETRY_COLS].astype(F32)


def covariate_table(gfs_canon, s, coefs, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_features_cfg()
    c = apply_correction(gfs_canon, coefs, s)
    out = {f"cov_{x}": c[x].to_numpy() for x in _COV_SCALARS}
    for x in ("wd10", "wd_hub"):
        r = np.radians(c[x].to_numpy())
        out[f"cov_{x}_sin"], out[f"cov_{x}_cos"] = np.sin(r), np.cos(r)
    out["cov_csi"] = _csi(c["ghi"].to_numpy(), c.index, s, cfg)
    return pd.DataFrame(out, index=c.index)[COVARIATE_COLS].astype(F32)


def _gather(tab: pd.DataFrame, idx: pd.DatetimeIndex, what: str) -> np.ndarray:
    pos = tab.index.get_indexer(idx)
    if (pos == -1).any():
        raise ValueError(f"{what}: {(pos == -1).sum()} requested times missing, first {idx[pos == -1][0]}")
    return tab.to_numpy(F32)[pos]


def assemble(origin_tab, target_tab, origins, horizons=range(1, 73), cov=None, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_features_cfg()
    check_hourly(origin_tab.index)
    check_hourly(target_tab.index)
    origins = pd.DatetimeIndex(origins)
    h = np.asarray(list(horizons), dtype=int)
    nh = len(h)
    hist = _gather(origin_tab, origins, "origin_table")
    T = pd.DatetimeIndex((origins.tz_convert(None).to_numpy()[:, None] + pd.to_timedelta(h, unit="h").to_numpy()[None, :]).ravel(), tz="UTC")
    blocks = [np.repeat(hist, nh, axis=0), _gather(target_tab, T, "target_table")]
    if isinstance(cov, dict):
        if not {1, 2, 3} <= set(cov):
            raise ValueError("lead-matched covariates need keys 1, 2, 3")
        k = lead_k(np.tile(h, len(origins)))
        c = np.empty((len(T), len(COVARIATE_COLS)), F32)
        for kk in (1, 2, 3):
            m = k == kk
            if m.any():
                c[m] = _gather(cov[kk], T[m], f"cov[{kk}]")
        blocks.append(c)
    elif cov is not None:
        blocks.append(_gather(cov, T, "cov"))
    blocks.append(np.tile(h, len(origins)).astype(F32)[:, None])
    cols = feature_columns("weather_only" if cov is None else "covariate", cfg)
    idx = pd.MultiIndex.from_arrays([np.repeat(origins, nh), np.tile(h, len(origins))], names=["issue_time", "horizon"])
    return pd.DataFrame(np.concatenate(blocks, axis=1), index=idx, columns=cols)


def iter_features(origin_tab, target_tab, origins, horizons=range(1, 73), cov=None, cfg=None, chunk=2000):
    origins = pd.DatetimeIndex(origins)
    for i in range(0, len(origins), chunk):
        yield assemble(origin_tab, target_tab, origins[i : i + chunk], horizons, cov, cfg)


def history_input(raw_canon: pd.DataFrame, s, source="history") -> pd.DataFrame:
    """Cleaned frame with every interpolated cell back to NaN, so no history value is filled from later labels."""
    c = clean(raw_canon, s, source=source)[0]
    filled = raw_canon.reindex(c.index).isna()
    night = is_night(c.index, s).to_numpy()
    for r in RADIATION:
        filled[r] &= ~night  # night zero is a function of time, not data
    return c.mask(filled)


def serve_features(raw: bytes, s, cfg, coefs, curve, origin) -> pd.DataFrame:
    origin = pd.Timestamp(origin)
    raw_canon = openmeteo_canon(raw, s)
    canon = clean(raw_canon, s, source="live")[0]
    need_h = max(max(cfg.lags), max(cfg.windows) - 1)
    if origin - pd.Timedelta(hours=need_h) < canon.index[0]:
        raise ValueError(f"serving needs >= {need_h + 1} h of history before origin {origin}")
    if origin + pd.Timedelta(hours=cfg.horizon_max) > canon.index[-1]:
        raise ValueError(f"serving needs {cfg.horizon_max} h of forecast after origin {origin}")
    hi = history_input(raw_canon, s, source="live").loc[origin - pd.Timedelta(hours=need_h) : origin]
    hist = history_frame(hi, s, curve, coefs)
    return assemble(
        origin_table(hist, cfg, s), target_table(canon.index, cfg, s), pd.DatetimeIndex([origin]),
        range(1, cfg.horizon_max + 1), cov=covariate_table(canon, s, coefs, cfg), cfg=cfg,
    )  # fmt: skip
