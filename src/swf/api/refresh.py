"""Refresh job: Open-Meteo live payload -> features -> baseline 3 / registry models -> bands -> SQLite (API-02..05)."""

import logging
import time
from datetime import UTC, datetime

import httpx
import numpy as np
import pandas as pd

from swf.align.consistency import load_coefs
from swf.api.db import iso, write_run
from swf.core.paths import DB_PATH, MODELS_DIR, RAW_DIR
from swf.core.settings import load_features_cfg, load_settings
from swf.features.build import serve_features
from swf.features.spec import TARGETS
from swf.fetch.cache import make_client
from swf.fetch.openmeteo import fetch_live
from swf.physics.constraints import enforce
from swf.physics.wind import load_power_curve
from swf.predict.bands import band_frame, bucket_label
from swf.predict.baseline import live_tables
from swf.predict.registry import load_registry, runtime_module

logger = logging.getLogger("swf.api")

HISTORY_HOURS = 168  # 7 days, the most /api/history serves


def origin_for(now: datetime) -> pd.Timestamp:
    """Last fully observed interval-start label: the hour before the current one."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware UTC")
    return pd.Timestamp(now).tz_convert("UTC").floor("h") - pd.Timedelta(hours=1)


def build_run(raw: bytes, origin, s, cfg, coefs, curve, reg: dict, models_root) -> tuple[list[tuple], list[tuple]]:
    X = serve_features(raw, s, cfg, coefs, curve, origin)
    tab = live_tables(raw, s, coefs, curve, reg["baseline3_choice"])
    h = X["horizon"].to_numpy().astype(int)
    T = pd.DatetimeIndex(origin + pd.to_timedelta(h, unit="h"))
    labels = [bucket_label(int(k), reg["buckets"]) for k in h]
    run = iso(origin)
    rows = []
    for t in TARGETS:
        entry = reg["targets"][t]
        mod = runtime_module(entry["runtime"])
        p50 = mod.predict_p50(entry, X, tab[t].reindex(T).to_numpy(), t, models_root)
        p50 = enforce(pd.DataFrame({t: p50}, index=T), s)[t]
        bands = entry["bands"][entry["runtime"]]
        q10 = np.array([bands[lab][0] for lab in labels])
        q90 = np.array([bands[lab][1] for lab in labels])
        bf = band_frame(p50, q10, q90, t, s)
        rows += [(run, iso(ts), t, entry["runtime"], r.p10, r.p50, r.p90) for ts, r in zip(bf.index, bf.itertuples())]
    hist_tab = tab.loc[origin - pd.Timedelta(hours=HISTORY_HOURS - 1) : origin]
    hist = [(iso(ts), t, v) for t in TARGETS for ts, v in hist_tab[t].items()]
    return rows, hist


def refresh(
    db_path=None, *, client=None, sleep=time.sleep, now=None, raw_root=None, models_root=None, registry_path=None
) -> bool:
    db_path = db_path or DB_PATH
    raw_root = raw_root or RAW_DIR
    models_root = models_root or MODELS_DIR
    registry_path = registry_path or models_root / "registry.json"
    now = now or datetime.now(UTC)
    own = client is None
    client = client or make_client()
    try:
        origin = origin_for(now)  # first: a bad `now` fails before any cache file is written
        s = load_settings()
        path = fetch_live(client, s, root=raw_root, now=now, sleep=sleep)
        reg = load_registry(registry_path)
        rows, hist = build_run(
            path.read_bytes(), origin, s, load_features_cfg(), load_coefs(), load_power_curve(s), reg, models_root
        )
        write_run(db_path, iso(origin), rows, hist, iso(datetime.now(UTC)))  # wall clock: stale age stays real (D-11)
        logger.info("refresh ok: %d forecast rows, origin %s", len(rows), origin)
        return True
    except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
        logger.error("refresh failed, serving cached forecast: %s", e)
        return False
    finally:
        if own:
            client.close()
