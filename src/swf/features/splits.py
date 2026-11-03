"""Chronological splits with purge (FEAT-04). Origins are a plain chronological hourly range."""

import logging

import pandas as pd

from swf.core.settings import FeaturesCfg, load_features_cfg

log = logging.getLogger("swf.features")

SPLITS = ("train_weather_only", "train_covariate", "val", "test")


def origins_for(split: str, cfg: FeaturesCfg | None = None) -> pd.DatetimeIndex:
    """Hourly UTC issue times whose horizon_max-h target window lies inside the split (D-06: purge only, no embargo)."""
    cfg = cfg or load_features_cfg()
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {SPLITS}")
    start, end = (pd.Timestamp(t) for t in getattr(cfg.splits, split))
    lo = start
    if split == "train_weather_only":  # history warm-up for the longest lag
        lo = start + pd.Timedelta(hours=max(cfg.lags))
    hi = end - pd.Timedelta(hours=cfg.horizon_max)
    return pd.date_range(lo, hi, freq="h", tz="UTC", name="issue_time")


def split_table(cfg: FeaturesCfg | None = None) -> list[dict]:
    cfg = cfg or load_features_cfg()
    rows = []
    for sp in SPLITS:
        o = origins_for(sp, cfg)
        start, end = getattr(cfg.splits, sp)
        rows.append(
            {
                "split": sp,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "first_origin": o[0].isoformat(),
                "last_origin": o[-1].isoformat(),
                "n_origins": len(o),
                "n_purged": cfg.horizon_max,
                "n_warmup": max(cfg.lags) if sp == "train_weather_only" else 0,
            }
        )
    return rows


def render_splits(cfg: FeaturesCfg | None = None) -> str:
    from swf.coverage.report import _table

    rows = split_table(cfg)
    for r in rows:
        log.info("split %s", r)
    head = ["split", "start", "end", "first origin", "last origin", "origins", "purged (h)", "warm-up (h)"]
    body = [[r["split"], r["start"], r["end"], r["first_origin"], r["last_origin"], r["n_origins"], r["n_purged"], r["n_warmup"]] for r in rows]
    return "\n".join(_table(head, body))
