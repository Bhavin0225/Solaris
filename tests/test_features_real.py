"""Realdata smoke: sampled train_covariate and val origins assembled from cached ERA5 and GFS interim parquets."""

import logging

import numpy as np
import pandas as pd
import pytest

from swf.align.adapters import load_source
from swf.align.clean import clean
from swf.align.consistency import load_coefs
from swf.core.paths import INTERIM_DIR, RAW_DIR
from swf.core.settings import load_features_cfg, load_settings
from swf.features.build import (
    assemble,
    covariate_table,
    history_input,
    origin_table,
    target_table,
)
from swf.features.history import history_frame
from swf.features.spec import feature_columns, lead_k
from swf.features.splits import origins_for
from swf.physics.wind import load_power_curve

log = logging.getLogger("swf.features")
GFS = ["weather_gfs_hf", "weather_gfs_pr_d1", "weather_gfs_pr_d2", "weather_gfs_pr_d3"]
HAVE = (RAW_DIR / "openmeteo").exists() and all(
    (INTERIM_DIR / f"{n}.parquet").exists() for n in GFS
)
LOOKAHEAD_MAX = 0.005


def _targets(origins, h=72):
    off = pd.to_timedelta(np.arange(1, h + 1), unit="h")
    return pd.DatetimeIndex(
        (
            origins.tz_convert(None).to_numpy()[:, None] + off.to_numpy()[None, :]
        ).ravel(),
        tz="UTC",
    )


def _filled_share(src, s, origins, only_k=None):
    """Share of sampled (origin, h) rows reading a gap-filled covariate cell (any column; upper bound)."""
    raw = load_source(src, s)
    filled = (
        history_input(raw, s, source=src).isna() & clean(raw, s, source=src)[0].notna()
    ).any(axis=1)
    T = _targets(origins)
    if only_k is not None:
        T = T[lead_k(np.tile(np.arange(1, 73), len(origins))) == only_k]
    n = int(filled.reindex(T).fillna(False).sum())
    log.info(
        "gap-filled covariate cells %s: %d cells, %d/%d sampled rows (%.4f%%)",
        src,
        int(filled.sum()),
        n,
        len(T),
        100 * n / len(T),
    )
    return n / len(T)


@pytest.mark.realdata
@pytest.mark.skipif(not HAVE, reason="cached ERA5 raw / GFS interim parquets absent")
def test_sampled_assembly_from_real_data():
    s, cfg, coefs = load_settings(), load_features_cfg(), load_coefs()
    raw = load_source("era5", s)
    hist = history_frame(
        history_input(raw, s, source="era5"), s, load_power_curve(s), coefs
    )
    otab, ttab = origin_table(hist, cfg, s), target_table(hist.index, cfg, s)
    tc = origins_for("train_covariate", cfg)[::500]
    val = origins_for("val", cfg)[::200]
    cov_tc = covariate_table(
        pd.read_parquet(INTERIM_DIR / "weather_gfs_hf.parquet"), s, coefs, cfg
    )
    cov_val = {
        k: covariate_table(
            pd.read_parquet(INTERIM_DIR / f"weather_gfs_pr_d{k}.parquet"), s, coefs, cfg
        )
        for k in (1, 2, 3)
    }
    for name, origins, cov in (("train_covariate", tc, cov_tc), ("val", val, cov_val)):
        X = assemble(
            otab, ttab, origins, range(1, cfg.horizon_max + 1), cov=cov, cfg=cfg
        )  # a gather miss raises
        assert list(X.columns) == feature_columns("covariate", cfg)
        assert all(dt == np.float32 for dt in X.dtypes)
        assert len(X) == len(origins) * 72
        nan = X.isna().mean()
        log.info("%s NaN rate per column: %s", name, nan[nan > 0].round(4).to_dict())
        if name == "train_covariate":
            hc = [c for c in X.columns if not c.startswith("cov_")]
            assert nan[hc].max() == 0, nan[hc][nan[hc] > 0]
    shares = {"gfs_hf": _filled_share("gfs_hf", s, tc)}
    shares.update(
        {f"gfs_pr_d{k}": _filled_share(f"gfs_pr_d{k}", s, val, k) for k in (1, 2, 3)}
    )
    log.info("gap-fill share per file: %s", shares)
    assert max(shares.values()) <= LOOKAHEAD_MAX, shares
