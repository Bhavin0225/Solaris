"""LSTM/GRU seq2seq residual-on-baseline-3 trainer (MODEL-02; D-01 amended, D-14, D-16, D-17, D-25).

Offline only: never imported by swf.api or swf.predict. Writes val predictions; never writes the registry
and never scores the held-out final split (bands are fit on val and stored in the sidecar, D-17).
"""

import copy
import json
import logging
import os
import random
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from swf.align.adapters import load_source
from swf.align.consistency import load_coefs
from swf.core.paths import INTERIM_DIR, MODELS_DIR
from swf.core.settings import load_deep_cfg, load_features_cfg, load_lgbm_cfg, load_settings
from swf.evaluate.baselines import _NEED, b3_table, load_choice, truth_frame
from swf.evaluate.longfmt import TARGETS, grid, make_long, pred_path, read_long, validate_long, write_long
from swf.evaluate.metrics import align_models, daytime_mask, metrics, scored_mask
from swf.features.build import (
    DEC_COLS,
    SEQ_COLS,
    covariate_table,
    decoder_windows,
    encoder_windows,
    history_input,
    origin_table,
    sequence_table,
    target_table,
)
from swf.features.history import history_frame
from swf.features.spec import artifact_meta
from swf.features.splits import origins_for
from swf.physics.constraints import enforce
from swf.physics.wind import load_power_curve
from swf.models.lgbm import split_fit_es
from swf.predict import lstm as rt
from swf.predict.bands import band_frame, bucket_label, residual_offsets

log = logging.getLogger("swf.models")
NT = len(TARGETS)


def _tables(interim: Path) -> dict:
    s, cfg, lcfg, dcfg, coefs = (
        load_settings(), load_features_cfg(), load_lgbm_cfg(), load_deep_cfg(), load_coefs(),
    )  # fmt: skip
    curve = load_power_curve(s)
    raw = load_source("era5", s)
    hist = history_frame(history_input(raw, s, source="era5"), s, curve, coefs)
    ttab = target_table(hist.index, cfg, s)
    hf = pd.read_parquet(interim / "weather_gfs_hf.parquet")
    cov_tc = covariate_table(hf, s, coefs, cfg)
    cov_pr = {
        k: covariate_table(pd.read_parquet(interim / f"weather_gfs_pr_d{k}.parquet"), s, coefs, cfg)
        for k in (1, 2, 3)
    }
    return {
        "s": s, "cfg": cfg, "lcfg": lcfg, "dcfg": dcfg, "choice": load_choice()["choice"],
        "hist": hist, "otab": origin_table(hist, cfg, s), "ttab": ttab, "cov_tc": cov_tc, "cov_pr": cov_pr,
        "tab": sequence_table(hist, cov_tc, ttab), "truth": truth_frame(interim),
        "b3_st": {"corrected": b3_table(hf, s, curve, coefs), "raw": b3_table(hf, s, curve, None)},
    }  # fmt: skip


def windows(tab, otab, ttab, origins, cov, b3, truth, cfg, enc_len) -> dict:
    """enc [N,L,29], dec [N,72,24], b3 [N,72,5], y [N,72,5]. b3: ndarray, or (b3_st, choice) for stitched training b3."""
    hmax = cfg.horizon_max
    _, _, tt = grid(origins, range(1, hmax + 1))
    n = len(origins)
    if isinstance(b3, tuple):
        b3_st, choice = b3
        b3 = np.stack(
            [b3_st[choice[t]][t].reindex(tt).to_numpy().reshape(n, hmax) for t in TARGETS], -1
        )
    return {
        "enc": encoder_windows(tab, origins, enc_len),
        "dec": decoder_windows(otab, ttab, origins, hmax, cov, cfg),
        "b3": np.asarray(b3, np.float32).reshape(n, hmax, NT),
        "y": np.array(truth[list(TARGETS)].reindex(tt), np.float32).reshape(n, hmax, NT),
    }


def b3_from_long(split, choice, origins, hmax, out_root=None) -> np.ndarray:
    """Lead-matched baseline-3 p50 [N,72,5] from the shared long-format parquet."""
    out = []
    for t in TARGETS:
        df = read_long(split, f"baseline3_{choice[t]}", out_root, target=t)
        assert len(df) == len(origins) * hmax
        assert (pd.DatetimeIndex(df["issue_time"]).to_numpy()[::hmax] == np.asarray(origins)).all()
        out.append(df["p50"].to_numpy("float64").reshape(len(origins), hmax))
    return np.stack(out, -1).astype(np.float32)


def fit_norm(w, enc_cols, targets) -> dict:
    """Channel stats from the fit windows only (std floor 1e-6)."""

    def ms(a):
        m = np.nanmean(a, axis=(0, 1), dtype=np.float64)
        return m, np.maximum(np.nanstd(a, axis=(0, 1), dtype=np.float64), 1e-6)

    em, es = ms(w["enc"])
    dm, ds = ms(w["dec"])
    bm, bs = ms(w["b3"])
    rs = np.maximum(np.nanstd(w["y"] - w["b3"], axis=(0, 1), dtype=np.float64), 1e-6)
    f = lambda a: [float(x) for x in a]  # noqa: E731
    return {
        "norm": {"enc_mean": f(em), "enc_std": f(es), "dec_mean": f(np.r_[dm, bm]), "dec_std": f(np.r_[ds, bs])},
        "resid_std": f(rs),
    }  # fmt: skip


def _masked_mse(pred, target, mask):
    d = (pred - target) ** 2 * mask
    return d.sum() / mask.sum().clamp(min=1)


def _tensors(w, meta):
    e, d = rt.prep(meta, w["enc"], w["dec"], w["b3"])
    rs = np.asarray(meta["resid_std"], np.float32)
    r = (w["y"] - w["b3"]) / rs
    m = np.isfinite(r)
    return [torch.from_numpy(a) for a in (e, d, np.nan_to_num(r).astype(np.float32), m.astype(np.float32))]


def train(w_fit, w_es, meta, lc, seed, device, deadline=None, clock=None):
    """(best state_dict on CPU, history, best_epoch 1-based). Non-finite loss / deadline -> best so far (D-18)."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if device == "cuda" and not torch.cuda.is_available():
        log.warning("cuda requested but unavailable; falling back to cpu")
        device = "cpu"
    clock = clock or (lambda: datetime.now(UTC))
    net = rt.build_net(meta["hp"], rt.n_enc_channels(meta), rt.n_dec_channels(meta), NT).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=lc.lr, weight_decay=lc.weight_decay)
    fit_t, es_t = _tensors(w_fit, meta), _tensors(w_es, meta)
    gen = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(*fit_t), batch_size=lc.batch_size, shuffle=True, generator=gen, num_workers=0
    )  # fmt: skip
    hist = {"train_loss": [], "es_loss": [], "stop_reason": None}
    best, best_ep, best_state = np.inf, 0, None
    for ep in range(1, lc.max_epochs + 1):
        net.train()
        tot, cnt, bad = 0.0, 0.0, False
        for e, d, r, m in loader:
            e, d, r, m = (x.to(device) for x in (e, d, r, m))
            loss = _masked_mse(net(e, d), r, m)
            if not torch.isfinite(loss):
                bad = True
                break
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), lc.grad_clip)
            opt.step()
            tot, cnt = tot + loss.item() * float(m.sum()), cnt + float(m.sum())
        if not bad:
            net.eval()
            es_tot, es_cnt = 0.0, 0.0
            with torch.no_grad():
                for i in range(0, len(es_t[0]), 1024):
                    e, d, r, m = (x[i : i + 1024].to(device) for x in es_t)
                    l = _masked_mse(net(e, d), r, m)
                    if not torch.isfinite(l):
                        bad = True
                        break
                    es_tot, es_cnt = es_tot + float(l) * float(m.sum()), es_cnt + float(m.sum())
        if bad:
            if best_state is None:
                raise RuntimeError(f"non-finite loss at epoch {ep} with no finite epoch before it")
            hist["stop_reason"] = f"non-finite loss at epoch {ep}"
            break
        tl, el = tot / max(cnt, 1.0), es_tot / max(es_cnt, 1.0)
        hist["train_loss"].append(tl)
        hist["es_loss"].append(el)
        print(f"epoch {ep:3d} train {tl:.5f} es {el:.5f}", flush=True)
        if el < best:
            best, best_ep = el, ep
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
        if deadline is not None and clock() >= deadline:
            hist["stop_reason"] = f"D-18 stabilise deadline reached at epoch {ep}"
            break
        if ep - best_ep >= lc.patience:
            break
    return copy.deepcopy(best_state), hist, best_ep


def save(models_root, name, state, meta) -> str:
    rel = f"{name}/{name}.pt"
    p = Path(models_root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, p)
    _write_side(p, meta)
    return rel


def _write_side(pt: Path, meta: dict) -> None:
    side = pt.with_suffix(".json")
    tmp = Path(str(side) + ".tmp")
    tmp.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, side)


def predict_split(split, name="lstm", interim_dir=None, out_root=None, models_root=None, tables=None) -> Path:
    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    models_root = Path(models_root) if models_root else MODELS_DIR
    T = tables or _tables(interim)
    s, cfg, lcfg, dcfg, choice, truth = (T[k] for k in ("s", "cfg", "lcfg", "dcfg", "choice", "truth"))
    hmax = cfg.horizon_max
    buckets = [tuple(b) for b in lcfg.buckets]
    pt = models_root / name / f"{name}.pt"
    net, meta = rt._load(str(pt), pt.stat().st_mtime_ns)
    origins = origins_for(split, cfg)
    n = len(origins)
    b3 = b3_from_long(split, choice, origins, hmax, out_root)
    w = windows(T["tab"], T["otab"], T["ttab"], origins, T["cov_pr"], b3, truth, cfg, meta["encoder_hours"])
    dev = "cuda" if dcfg.lstm.device == "cuda" and torch.cuda.is_available() else "cpu"
    p50 = rt.forecast(net, meta, w["enc"], w["dec"], w["b3"], device=dev)  # [n,72,5], serving forward path
    issue, hor, tt = grid(origins, range(1, hmax + 1))
    hv = hor.astype(int)
    meta = json.loads(pt.with_suffix(".json").read_text(encoding="utf-8"))
    offsets = {} if split == "val" else meta.get("band_offsets")
    if split != "val" and not offsets:
        raise ValueError("band_offsets absent from the sidecar; run train-lstm (D-17: no refit outside val)")
    parts, day = [], None
    for j, t in enumerate(TARGETS):
        P = p50[:, :, j]
        for h in range(hmax):  # clip per horizon: unique target-time index for enforce
            col = pd.Series(P[:, h], index=tt[h::hmax])
            P[:, h] = enforce(pd.DataFrame({t: col}), s)[t].to_numpy()
        Y = w["y"][:, :, j].ravel()
        if split == "val":
            if t in ("t1_kw", "ghi"):
                day = daytime_mask(tt, s, cfg.eval.daytime_zenith_deg) if day is None else day
                mask = day
            else:
                mask = np.ones(len(tt), bool)
            offsets[t] = residual_offsets(Y, P.ravel(), hv, mask, buckets, lcfg.band_quantiles)
        p10, p90 = np.full_like(P, np.nan), np.full_like(P, np.nan)
        for h in range(hmax):
            q10, q90 = offsets[t][bucket_label(h + 1, buckets)]
            bf = band_frame(pd.Series(P[:, h], index=tt[h::hmax]), q10, q90, t, s)
            p10[:, h], p90[:, h] = bf["p10"].to_numpy(), bf["p90"].to_numpy()
        parts.append(make_long(issue, hor, t, name, Y, P.ravel(), p10.ravel(), p90.ravel()))
    if split == "val":
        meta["band_offsets"] = offsets
        _write_side(pt, meta)
    df = pd.concat(parts, ignore_index=True)
    validate_long(df, truth=truth, origins=origins)
    return write_long(df, split, name, out_root)


def run(args, interim_dir=None, out_root=None, models_root=None) -> int:
    t0 = time.time()
    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    models_root = Path(models_root) if models_root else MODELS_DIR
    need_val = [pred_path("val", m, out_root) for m in ("baseline3_corrected", "baseline3_raw")]
    if any(not (interim / n).exists() for n in _NEED) or any(not p.exists() for p in need_val):
        print("run `python -m swf build-weather`, `simulate-energy`, `baselines` and `evaluate --split val` first")
        return 1
    T = _tables(interim)
    cfg, lcfg, dcfg, choice, truth, s = (T[k] for k in ("cfg", "lcfg", "dcfg", "choice", "truth", "s"))
    lc, hmax, enc_len = dcfg.lstm, cfg.horizon_max, dcfg.encoder_hours
    name = lc.rnn
    fit, es = split_fit_es(origins_for("train_covariate", cfg), lcfg.es_tail_start, hmax)
    assert es.max() + pd.Timedelta(hours=hmax) < pd.Timestamp(cfg.splits.val[0])
    fit, es = fit[:: dcfg.train_stride], es[:: dcfg.train_stride]
    b3 = (T["b3_st"], choice)
    w_fit = windows(T["tab"], T["otab"], T["ttab"], fit, T["cov_tc"], b3, truth, cfg, enc_len)
    w_es = windows(T["tab"], T["otab"], T["ttab"], es, T["cov_tc"], b3, truth, cfg, enc_len)
    meta = artifact_meta(None) | {
        "model": name, "enc_cols": SEQ_COLS, "dec_feature_cols": DEC_COLS, "targets": list(TARGETS),
        "encoder_hours": enc_len, "hp": lc.model_dump(mode="json"), "seed": dcfg.seed,
        "train_stride": dcfg.train_stride, "baseline3_choice": choice, "n_fit": len(fit), "n_es": len(es),
    } | fit_norm(w_fit, SEQ_COLS, TARGETS)  # fmt: skip
    print(f"fit origins {len(fit)}, es origins {len(es)}, device {lc.device}", flush=True)
    state, history, best_ep = train(w_fit, w_es, meta, lc, dcfg.seed, lc.device, deadline=lc.stable_by_utc)
    reason = history["stop_reason"] or ("" if best_ep >= 1 else "no early-stopping improvement")
    meta |= {
        "best_epoch": best_ep, "epochs_run": len(history["es_loss"]), "history": history,
        "status": "minimal" if reason else "stable", "reason": reason,
        "wall_seconds": round(time.time() - t0, 1),
    }  # fmt: skip
    save(models_root, name, state, meta)
    del w_fit, w_es
    pt = predict_split("val", name, interim_dir, out_root, models_root, tables=T)
    print(f"wrote {pt}; status {meta['status']} {reason}", flush=True)
    frames = {name: read_long("val", name, out_root)}
    for t in TARGETS:
        frames["baseline3"] = read_long("val", f"baseline3_{choice[t]}", out_root)
        wide = align_models(frames, t)
        m = scored_mask(wide, [name, "baseline3"], t, s, cfg.eval.daytime_zenith_deg)
        y = wide["y_true"].to_numpy("float64")[m]
        r = {n: float(metrics(y, wide[n].to_numpy("float64")[m], 1.0, "")["rmse"]) for n in (name, "baseline3")}
        print(f"{t}: val RMSE {name} {r[name]:.4g} baseline3 {r['baseline3']:.4g}", flush=True)
    return 0
