"""LightGBM direct multi-horizon residual models on baseline 3 (MODEL-01, MODEL-04; D-01, D-07..D-09, D-13, D-14)."""

import json
import logging
import os
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from swf.align.adapters import load_source
from swf.align.consistency import load_coefs
from swf.core.paths import INTERIM_DIR, MODELS_DIR
from swf.core.settings import load_features_cfg, load_lgbm_cfg, load_settings
from swf.evaluate.baselines import _NEED, b3_table, load_choice, truth_frame
from swf.evaluate.longfmt import (
    TARGETS,
    grid,
    make_long,
    pred_path,
    read_long,
    validate_long,
    write_long,
)
from swf.evaluate.metrics import align_models, daytime_mask, metrics, scored_mask
from swf.features.build import (
    assemble,
    covariate_table,
    history_input,
    origin_table,
    target_table,
)
from swf.features.history import history_frame
from swf.features.spec import artifact_meta
from swf.features.splits import origins_for
from swf.physics.constraints import enforce
from swf.physics.wind import load_power_curve
from swf.predict.bands import band_frame, bucket_label, residual_offsets
from swf.predict.registry import save_registry

log = logging.getLogger("swf.models")
F32 = np.float32


def split_fit_es(origins: pd.DatetimeIndex, tail_start, horizon_max: int):
    """D-14: early-stopping tail = origins from tail_start; fit origins are purged so no fit target reaches the tail."""
    tail_start = pd.Timestamp(tail_start)
    es = origins[origins >= tail_start]
    fit = origins[origins + pd.Timedelta(hours=horizon_max) < tail_start]
    if len(es) == 0 or len(fit) == 0:
        raise ValueError(
            f"empty fit ({len(fit)}) or early-stopping ({len(es)}) origin set for tail {tail_start}"
        )
    return fit, es


def to_grid(preds_t: dict, n_origins: int, buckets) -> np.ndarray:
    """One target's {bucket_label: predictions} -> flat origin-major array over horizons 1..max."""
    hmax = buckets[-1][1]
    full = np.full((n_origins, hmax), np.nan)
    for lo, hi in buckets:
        full[:, lo - 1 : hi] = np.asarray(preds_t[f"{lo}-{hi}"]).reshape(
            n_origins, hi - lo + 1
        )
    return full.ravel()


def fit_bucket(X_tr, y_tr, X_va, y_va, lcfg) -> lgb.Booster:
    params = dict(lcfg.params) | {"seed": lcfg.seed}
    ok_tr, ok_va = np.isfinite(y_tr), np.isfinite(y_va)
    dtr = lgb.Dataset(
        X_tr[ok_tr], np.asarray(y_tr)[ok_tr].astype(F32), free_raw_data=True
    )
    dva = lgb.Dataset(
        X_va[ok_va], np.asarray(y_va)[ok_va].astype(F32), free_raw_data=True
    )
    return lgb.train(
        params, dtr, num_boost_round=lcfg.num_boost_round, valid_sets=[dva],
        callbacks=[lgb.early_stopping(lcfg.early_stopping_rounds, verbose=False)],
    )  # fmt: skip


def save_bucket(booster, models_root, target, lo, hi, extra: dict) -> str:
    rel = f"lightgbm/{target}_{lo}-{hi}.txt"
    path = Path(models_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(path), num_iteration=booster.best_iteration)
    meta = artifact_meta("covariate") | {
        "target": target, "bucket": f"{lo}-{hi}", "best_iteration": int(booster.best_iteration), "seed": int(booster.params.get("seed", -1)),
    } | extra  # fmt: skip
    side = path.with_suffix(".json")
    tmp = Path(str(side) + ".tmp")
    tmp.write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, side)
    return rel


def run(args, interim_dir=None, out_root=None, models_root=None) -> int:
    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    models_root = Path(models_root) if models_root else MODELS_DIR
    need_val = [
        pred_path("val", m, out_root) for m in ("baseline3_corrected", "baseline3_raw")
    ]
    if any(not (interim / n).exists() for n in _NEED) or any(
        not p.exists() for p in need_val
    ):
        print(
            "run `python -m swf build-weather`, `simulate-energy`, `baselines` and `evaluate --split val` first"
        )
        return 1
    choice = load_choice()["choice"]
    s, cfg, lcfg, coefs = (
        load_settings(),
        load_features_cfg(),
        load_lgbm_cfg(),
        load_coefs(),
    )
    curve = load_power_curve(s)
    hmax = cfg.horizon_max
    assert lcfg.buckets[-1][1] == hmax
    buckets = [tuple(b) for b in lcfg.buckets]
    tc_start, tc_end = (pd.Timestamp(t) for t in cfg.splits.train_covariate)
    assert tc_start < lcfg.es_tail_start < tc_end
    assert lcfg.origin_stride == 1, "D-01: hourly training origins"
    log.info("hourly training origins (origin_stride=%d)", lcfg.origin_stride)

    raw = load_source("era5", s)
    hist = history_frame(history_input(raw, s, source="era5"), s, curve, coefs)
    otab, ttab = origin_table(hist, cfg, s), target_table(hist.index, cfg, s)
    hf = pd.read_parquet(interim / "weather_gfs_hf.parquet")
    cov_tc = covariate_table(hf, s, coefs, cfg)
    cov_val = {
        k: covariate_table(
            pd.read_parquet(interim / f"weather_gfs_pr_d{k}.parquet"), s, coefs, cfg
        )
        for k in (1, 2, 3)
    }
    truth = truth_frame(interim)
    fit_origins, es_origins = split_fit_es(
        origins_for("train_covariate", cfg), lcfg.es_tail_start, hmax
    )
    assert es_origins.max() + pd.Timedelta(hours=hmax) < pd.Timestamp(cfg.splits.val[0])
    va_origins = origins_for("val", cfg)
    n_val = len(va_origins)
    b3_st = {
        "corrected": b3_table(hf, s, curve, coefs),
        "raw": b3_table(hf, s, curve, None),
    }
    issue, hor, tt = grid(va_origins, range(1, hmax + 1))
    day_mask_cache = None

    def tgt_y(origins, lo, hi, t):
        _, _, ttt = grid(origins, range(lo, hi + 1))
        return (
            truth[t].reindex(ttt).to_numpy()
            - b3_st[choice[t]][t].reindex(ttt).to_numpy()
        ).astype(F32)

    parts, reg_targets, table = [], {}, []
    for t in TARGETS:
        b3v = read_long("val", f"baseline3_{choice[t]}", out_root, target=t)
        assert len(b3v) == n_val * hmax
        assert (pd.DatetimeIndex(b3v["issue_time"]) == pd.DatetimeIndex(issue)).all()
        B3 = b3v["p50"].to_numpy("float64").reshape(n_val, hmax)
        Y = truth[t].reindex(tt).to_numpy().reshape(n_val, hmax)
        preds_t, arts, iters = {}, {}, {}
        for lo, hi in buckets:
            label = f"{lo}-{hi}"
            hs = range(lo, hi + 1)
            X_fit = assemble(otab, ttab, fit_origins, hs, cov=cov_tc, cfg=cfg)
            X_es = assemble(otab, ttab, es_origins, hs, cov=cov_tc, cfg=cfg)
            y_fit, y_es = tgt_y(fit_origins, lo, hi, t), tgt_y(es_origins, lo, hi, t)
            booster = fit_bucket(
                X_fit, y_fit, X_es, y_es, lcfg
            )  # D-14: no 2024 row here
            arts[label] = save_bucket(
                booster, models_root, t, lo, hi,
                {"n_train_rows": int(np.isfinite(y_fit).sum()), "n_es_rows": int(np.isfinite(y_es).sum())},
            )  # fmt: skip
            iters[label] = int(booster.best_iteration)
            del X_fit, X_es, y_fit, y_es
            X_va = assemble(
                otab, ttab, va_origins, hs, cov=cov_val, cfg=cfg
            )  # lead-matched (D-02)
            preds_t[label] = booster.predict(X_va)
            del X_va
        p50 = B3 + to_grid(preds_t, n_val, buckets).reshape(n_val, hmax)
        for h in range(hmax):  # clip per horizon: unique target-time index for enforce
            col = pd.Series(p50[:, h], index=tt[h::hmax])
            p50[:, h] = enforce(pd.DataFrame({t: col}), s)[t].to_numpy()
        if t in ("t1_kw", "ghi"):
            if day_mask_cache is None:
                day_mask_cache = daytime_mask(tt, s, cfg.eval.daytime_zenith_deg)
            mask = day_mask_cache
        else:
            mask = np.ones(len(tt), bool)
        hv = hor.astype(int)
        off_lgb = residual_offsets(
            Y.ravel(), p50.ravel(), hv, mask, buckets, lcfg.band_quantiles
        )
        off_b3 = residual_offsets(
            Y.ravel(), B3.ravel(), hv, mask, buckets, lcfg.band_quantiles
        )
        p10, p90 = np.full_like(p50, np.nan), np.full_like(p50, np.nan)
        for h in range(hmax):
            q10, q90 = off_lgb[bucket_label(h + 1, buckets)]
            bf = band_frame(pd.Series(p50[:, h], index=tt[h::hmax]), q10, q90, t, s)
            p10[:, h], p90[:, h] = bf["p10"].to_numpy(), bf["p90"].to_numpy()
        yr, p10r, p90r = Y.ravel(), p10.ravel(), p90.ravel()
        ok = mask & np.isfinite(yr) & np.isfinite(p10r)
        cov = float(((yr >= p10r) & (yr <= p90r))[ok].mean())
        parts.append(make_long(issue, hor, t, "lightgbm", yr, p50.ravel(), p10r, p90r))
        reg_targets[t] = {"arts": arts, "off_lgb": off_lgb, "off_b3": off_b3}
        table.append((t, cov, iters))
        log.info("%s coverage(daytime) %.3f best_iter %s", t, cov, iters)
        print(
            f"{t}: daytime [p10,p90] coverage {cov:.3f}; best_iteration {iters}",
            flush=True,
        )

    df = pd.concat(parts, ignore_index=True)
    validate_long(df, truth=truth, origins=va_origins)
    write_long(df, "val", "lightgbm", out_root)

    frames = {"lightgbm": df}
    targets_reg = {}
    for t in TARGETS:
        frames["baseline3"] = read_long("val", f"baseline3_{choice[t]}", out_root)
        wide = align_models(frames, t)
        m = scored_mask(
            wide, ["lightgbm", "baseline3"], t, s, cfg.eval.daytime_zenith_deg
        )
        y = wide["y_true"].to_numpy("float64")[m]
        r = {
            n: float(metrics(y, wide[n].to_numpy("float64")[m], 1.0, "")["rmse"])
            for n in ("lightgbm", "baseline3")
        }
        rt = reg_targets[t]
        targets_reg[t] = {
            "selected": "baseline3", "runtime": "baseline3",
            "reason": f"D-13: Phase 5 serves baseline3; lightgbm candidate val RMSE {r['lightgbm']:.4g} vs baseline3 {r['baseline3']:.4g}; selection in Phase 6 (MODEL-05)",
            "artifacts": rt["arts"], "bands": {"baseline3": rt["off_b3"], "lightgbm": rt["off_lgb"]}, "val_rmse": r,
        }  # fmt: skip
        print(
            f"{t}: val RMSE lightgbm {r['lightgbm']:.4g} baseline3 {r['baseline3']:.4g}",
            flush=True,
        )
    save_registry(
        {
            "baseline3_choice": choice,
            "buckets": [list(b) for b in buckets],
            "selection_split": "val",
            "targets": targets_reg,
        },
        models_root / "registry.json",
    )
    return 0
