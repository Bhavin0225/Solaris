"""darts TFT trainer (MODEL-03, MODEL-07; D-14, D-19, D-26, D-27).

Offline only: never imported by swf.api or swf.predict. darts/torch are imported lazily inside functions.
Never scores the final split: predict_split is only called for val here (T-06-12).
"""

import json
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from swf.core.paths import DOCS_DIR, INTERIM_DIR, MODELS_DIR, REPORTS_DIR
from swf.core.settings import load_deep_cfg, load_features_cfg
from swf.coverage.report import write_auto_block
from swf.evaluate.longfmt import TARGETS
from swf.features.build import DEC_COLS, SEQ_COLS, decoder_windows, encoder_windows
from swf.predict import tft as rt

NT = len(TARGETS)
LEVERS = {
    "fit_hours": ["train_stride", "tft.max_epochs"],
    "predict_hours": ["tft.predict_batch_size", "tft.chunk_origins"],
}


def _stack(frame, origins, offs) -> np.ndarray:
    """frame values at origin+offs hours -> [N, len(offs), n_cols] (NaN where absent)."""
    o = pd.DatetimeIndex(origins)
    idx = o.repeat(len(offs)) + pd.to_timedelta(np.tile(offs, len(o)), unit="h")
    return frame.reindex(idx).to_numpy("float32").reshape(len(o), len(offs), -1)


def _raw(tab, B, truth, origins, enc_len, hmax, fut_dec, b3_fut=None) -> dict:
    """Raw per-origin arrays. D-26: encoder history = tab (ERA5-chain hist), labels = truth; B = stitched baseline 3."""
    enc = encoder_windows(tab, origins, enc_len)
    cols = [SEQ_COLS.index(c) for c in DEC_COLS]
    past = np.concatenate([enc[..., cols], _stack(B, origins, np.arange(-(enc_len - 1), 1))], -1)
    steps = np.arange(1, hmax + 1)
    b3_fut = _stack(B, origins, steps) if b3_fut is None else b3_fut
    return {
        "enc_y": enc[..., :NT], "past": past, "fut": np.concatenate([fut_dec, b3_fut], -1),
        "y_fut": _stack(truth[list(TARGETS)], origins, steps), "origins": pd.DatetimeIndex(origins),
    }  # fmt: skip


def train_raw(tab, B, truth, fut_dec, origins, enc_len, hmax) -> dict:
    """Training/ES arrays; origins with a NaN label or future covariate are dropped and counted (past NaN -> mean)."""
    r = _raw(tab, B, truth, origins, enc_len, hmax, fut_dec)
    keep = np.isfinite(r["y_fut"]).all((1, 2)) & np.isfinite(r["fut"]).all((1, 2))
    out = {k: (v[keep] if len(v) == len(keep) else v) for k, v in r.items()}
    out["n_dropped"] = int((~keep).sum())
    return out


def train_series(raw, meta):
    """One darts (target, covariate) pair per origin; the target series carries encoder history then truth labels."""
    return rt.origin_inputs(meta, raw["enc_y"], raw["past"], raw["fut"], raw["origins"], y_fut=raw["y_fut"])


def fit_norm(raw) -> dict:
    def ms(a):
        a = a.reshape(-1, a.shape[-1])
        return [float(x) for x in np.nanmean(a, 0, dtype=np.float64)], [
            float(x) for x in np.maximum(np.nanstd(a, 0, dtype=np.float64), 1e-6)
        ]

    ym, ys = ms(np.concatenate([raw["enc_y"], raw["y_fut"]], 1))
    cm, cs = ms(np.concatenate([raw["past"], raw["fut"]], 1))
    return {"y_mean": ym, "y_std": ys, "cov_mean": cm, "cov_std": cs}


def _hard_stop_cls():
    """Callback class, built on first use (pytorch_lightning is lazy) and published at module level so darts can pickle it."""
    if "HardStop" in globals():
        return globals()["HardStop"]
    import pytorch_lightning as pl

    class HardStop(pl.Callback):
        reason = None

        def __init__(self, hard_stop, every, clock):
            self.hard_stop, self.every, self.clock = hard_stop, every, clock

        def __getstate__(self):  # the clock is a lambda; checkpoints and model.save() only need the data
            return {"hard_stop": None, "every": self.every, "reason": self.reason}  # plain types only (safe loading)

        def _check(self, trainer):
            if self.reason is None and self.hard_stop is not None and self.clock() >= self.hard_stop:
                self.reason = f"hard stop {self.hard_stop.isoformat()} reached during fit at epoch {trainer.current_epoch}"
                trainer.should_stop = True

        def on_train_epoch_end(self, trainer, pl_module):
            self._check(trainer)

        def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx):
            if (batch_idx + 1) % self.every == 0:
                self._check(trainer)

    HardStop.__module__, HardStop.__qualname__ = __name__, "HardStop"
    globals()["HardStop"] = HardStop
    return HardStop


def hard_stop_callback(hard_stop, every_n_batches, clock):
    return _hard_stop_cls()(hard_stop, every_n_batches, clock)


def _name(log_version) -> str:
    return f"tft_{log_version}"


def make_model(dcfg, models_root, n_epochs, log_version, stop_cb):
    from darts.models import TFTModel
    from darts.utils.likelihood_models import QuantileRegression
    from pytorch_lightning.callbacks import EarlyStopping
    from pytorch_lightning.loggers import CSVLogger

    t, root = dcfg.tft, Path(models_root) / "tft"
    (root / "darts").mkdir(parents=True, exist_ok=True)  # darts mkdirs only the leaf
    return TFTModel(
        input_chunk_length=dcfg.encoder_hours, output_chunk_length=load_features_cfg().horizon_max,
        hidden_size=t.hidden_size, lstm_layers=t.lstm_layers, num_attention_heads=t.attention_heads,
        dropout=t.dropout, batch_size=t.batch_size, n_epochs=n_epochs, add_relative_index=False,
        likelihood=QuantileRegression([0.1, 0.5, 0.9]), random_state=dcfg.seed,
        optimizer_kwargs={"lr": t.lr}, model_name=_name(log_version), work_dir=str(root / "darts"),
        save_checkpoints=True, force_reset=True,
        pl_trainer_kwargs={
            "accelerator": t.accelerator, "devices": 1, "enable_progress_bar": False,
            "log_every_n_steps": 1,  # darts logs train_loss per step; curves() averages it per epoch
            "callbacks": [EarlyStopping(monitor="val_loss", patience=t.patience), stop_cb],
            "logger": CSVLogger(str(root / "logs"), name="", version=log_version),
        },
    )  # fmt: skip


def fit(inputs, dcfg, models_root, n_epochs, log_version, stop_cb, best=False):
    """Every TFT fit (timing included) logs train_loss/val_loss per epoch against the D-14 ES series."""
    shutil.rmtree(Path(models_root) / "tft" / "logs" / log_version, ignore_errors=True)  # no stale rows
    model = make_model(dcfg, models_root, n_epochs, log_version, stop_cb)
    (s, c), (vs, vc) = inputs["fit"], inputs["es"]
    model.fit(
        series=s, future_covariates=c, val_series=vs, val_future_covariates=vc,
        max_samples_per_ts=1, dataloader_kwargs={"num_workers": 0},
    )  # fmt: skip
    if best and stop_cb.reason is None:  # darts keeps last-epoch weights unless the best checkpoint is reloaded
        from darts.models import TFTModel
        # trusted: the checkpoint was written by this process seconds ago (darts does the same internally)
        model = TFTModel.load_from_checkpoint(
            _name(log_version), work_dir=str(Path(models_root) / "tft" / "darts"), best=True, trusted=True, map_location="cpu"
        )
    return model


def scrub(model):
    """Drop fit-only callbacks/logger from the stored hyper-parameters so the served artifact loads under darts safe loading."""
    for pk in (model._model_params.get("pl_trainer_kwargs") or {}, model.trainer_params):
        pk["callbacks"], pk["logger"] = [], False
    return model


def project(epoch_s, per_origin_s, n_epochs, n_origins, now, hard_stop) -> dict:
    fit_h, pred_h = epoch_s * n_epochs / 3600, per_origin_s * n_origins / 3600
    total = fit_h + pred_h
    return {
        "epoch_seconds": epoch_s, "per_origin_seconds": per_origin_s, "n_epochs": n_epochs, "n_origins": n_origins,
        "fit_hours": fit_h, "predict_hours": pred_h, "projected_hours": total,
        "hard_stop_utc": hard_stop.isoformat() if hard_stop else None,
        "fits_before_stop": True if hard_stop is None else now + timedelta(hours=total) <= hard_stop,
        "levers": LEVERS,
    }  # fmt: skip


def timing(inputs, dcfg, models_root, clock) -> dict:
    tc = dcfg.tft
    cb = hard_stop_callback(tc.hard_stop_utc, tc.stop_check_batches, clock)
    t0 = time.time()
    model = fit(inputs, dcfg, models_root, 1, "timing", cb)
    epoch_s = time.time() - t0
    ps, pc = inputs["pred"]
    t0 = time.time()
    for i in range(0, len(ps), tc.chunk_origins):
        rt.quantiles(model, inputs["meta"], ps[i : i + tc.chunk_origins], pc[i : i + tc.chunk_origins], tc.predict_batch_size)
    per_origin = (time.time() - t0) / max(len(ps), 1)
    out = project(epoch_s, per_origin, tc.max_epochs, inputs["n_origins"], clock(), tc.hard_stop_utc)
    p = Path(models_root) / "tft" / "timing.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"fit_hours {out['fit_hours']:.2f} (epoch {epoch_s:.0f}s x {tc.max_epochs}), predict_hours {out['predict_hours']:.2f} "
          f"({per_origin * 1000:.1f} ms x {inputs['n_origins']}), total {out['projected_hours']:.2f} h, "
          f"fits_before_stop {out['fits_before_stop']}")  # fmt: skip
    print(f"levers: {LEVERS}", flush=True)
    return out


def curves(log_dir, out_dir) -> pd.DataFrame:
    log_dir, out_dir = Path(log_dir), Path(out_dir)
    paths = [log_dir / v / "metrics.csv" for v in ("run", "timing")]
    p = next((x for x in paths if x.exists()), None)
    if p is None:
        raise FileNotFoundError(f"no TFT metrics: {paths[0]} or {paths[1]}")
    df = pd.read_csv(p)
    cols = [c for c in ("train_loss", "val_loss") if c in df]
    if len(cols) < 2:
        raise ValueError(f"{p} lacks train_loss/val_loss (has {list(df.columns)})")
    tbl = df.groupby("epoch")[cols].mean().reset_index()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(tbl["epoch"] + 1, tbl["train_loss"], marker="o", label="train")
    ax.plot(tbl["epoch"] + 1, tbl["val_loss"], marker="o", label="val (2023-H2 tail)")
    ax.set(xlabel="epoch", ylabel="quantile loss (standardised)", title=f"TFT training curves ({p.parent.name})")
    ax.legend()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "tft_training_curves.png", dpi=110, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return tbl


def write_stop(reason, timing_d: dict, curve_table, notes_path) -> None:
    lines = ["## TFT (MODEL-03)", "", "- status: stopped (D-19)", f"- reason: {reason}"]
    if timing_d:
        lines.append(
            f"- timing: fit_hours {timing_d['fit_hours']:.2f}, predict_hours {timing_d['predict_hours']:.2f}, "
            f"projected {timing_d['projected_hours']:.2f} h, hard stop {timing_d['hard_stop_utc'] or 'none'}"
        )
    if curve_table is not None and len(curve_table):
        lines.append(f"- epochs logged: {len(curve_table)}, best val loss {curve_table['val_loss'].min():.4f}")
        lines.append("- curves: reports/evaluation/tft_training_curves.png")
    write_auto_block(Path(notes_path), "\n".join(lines), name="tft")


def explain(model, bg_series, bg_covs, out_dir, n_bg) -> pd.DataFrame:
    from darts.explainability import TFTExplainer

    L = model.input_chunk_length
    ex = TFTExplainer(model, background_series=[s[:L] for s in bg_series[:n_bg]], background_future_covariates=bg_covs[:n_bg])
    rows = []
    for block, df in ex.explain().get_feature_importances().items():
        if df is not None:
            df = pd.concat(df) if isinstance(df, list) else df  # one frame per target component: average them
            rows += [(block.replace("_importance", ""), f, float(v)) for f, v in df.mean(axis=0).items()]
    tbl = pd.DataFrame(rows, columns=["block", "feature", "importance"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl.to_csv(out_dir / "tft_variable_selection.csv", index=False, lineterminator="\n")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    blocks = list(dict.fromkeys(tbl["block"]))
    fig, axes = plt.subplots(1, len(blocks), figsize=(6 * len(blocks), 7), squeeze=False)
    for ax, b in zip(axes[0], blocks, strict=True):
        d = tbl[tbl["block"] == b].sort_values("importance")
        ax.barh(d["feature"], d["importance"])
        ax.set_title(f"TFT variable selection: {b}")
    fig.savefig(out_dir / "tft_variable_selection.png", dpi=110, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return tbl


def _inputs(interim, dcfg, tables=None) -> dict:
    from swf.core.settings import load_lgbm_cfg
    from swf.features.splits import origins_for
    from swf.features.spec import artifact_meta
    from swf.models import seq
    from swf.models.lgbm import split_fit_es

    T = tables or seq._tables(interim)
    cfg, lcfg, choice, truth = T["cfg"], load_lgbm_cfg(), T["choice"], T["truth"]
    hmax, L = cfg.horizon_max, dcfg.encoder_hours
    B = pd.DataFrame({t: T["b3_st"][choice[t]][t] for t in TARGETS})
    fit_o, es_o = split_fit_es(origins_for("train_covariate", cfg), lcfg.es_tail_start, hmax)
    assert es_o.max() + pd.Timedelta(hours=hmax) < pd.Timestamp(cfg.splits.val[0])
    raws = {}
    for k, o in (("fit", fit_o[:: dcfg.train_stride]), ("es", es_o[:: dcfg.train_stride])):
        dec = decoder_windows(T["otab"], T["ttab"], o, hmax, T["cov_tc"], cfg)
        raws[k] = train_raw(T["tab"], B, truth, dec, o, L, hmax)
    meta = artifact_meta(None) | {
        "targets": list(TARGETS), "dec_feature_cols": DEC_COLS, "encoder_hours": L,
        "norm": fit_norm(raws["fit"]), "hp": dcfg.tft.model_dump(mode="json"), "seed": dcfg.seed,
        "train_stride": dcfg.train_stride, "n_fit": len(raws["fit"]["origins"]), "n_dropped": raws["fit"]["n_dropped"],
    }  # fmt: skip
    val_o = origins_for("val", cfg)
    po = val_o[:: max(len(val_o) // dcfg.tft.timing_origins, 1)][: dcfg.tft.timing_origins]
    dec = decoder_windows(T["otab"], T["ttab"], po, hmax, T["cov_pr"], cfg)
    pr = _raw(T["tab"], B, truth, po, L, hmax, dec)
    return {
        "meta": meta, "fit": train_series(raws["fit"], meta), "es": train_series(raws["es"], meta),
        "pred": rt.origin_inputs(meta, pr["enc_y"], pr["past"], pr["fut"], po),
        "n_origins": len(val_o) + len(origins_for("test", cfg)),  # counts only: no test data is read (T-06-12)
        "T": T,
    }  # fmt: skip


def predict_split(split, interim_dir=None, out_root=None, models_root=None, tables=None) -> Path:
    from swf.core.settings import load_settings
    from swf.evaluate.longfmt import grid, make_long, validate_long, write_long
    from swf.features.splits import origins_for
    from swf.models import seq
    from swf.physics.constraints import enforce

    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    models_root = Path(models_root) if models_root else MODELS_DIR
    T = tables or seq._tables(interim)
    s, cfg, dcfg, choice, truth = (T[k] for k in ("s", "cfg", "dcfg", "choice", "truth"))
    hmax, tc = cfg.horizon_max, dcfg.tft
    pt = models_root / "tft" / "tft.pt"
    model, meta = rt._load(str(pt), pt.stat().st_mtime_ns)
    origins = origins_for(split, cfg)
    n = len(origins)
    B = pd.DataFrame({t: T["b3_st"][choice[t]][t] for t in TARGETS})
    b3 = seq.b3_from_long(split, choice, origins, hmax, out_root)  # lead-matched serving-style b3 (D-02)
    Q = np.empty((n, hmax, NT, 3), np.float64)
    for i in range(0, n, tc.chunk_origins):
        o = origins[i : i + tc.chunk_origins]
        dec = decoder_windows(T["otab"], T["ttab"], o, hmax, T["cov_pr"], cfg)
        r = _raw(T["tab"], B, truth, o, meta["encoder_hours"], hmax, dec, b3[i : i + len(o)])
        ser, cov = rt.origin_inputs(meta, r["enc_y"], r["past"], r["fut"], o)
        Q[i : i + len(o)] = rt.quantiles(model, meta, ser, cov, tc.predict_batch_size)
    issue, hor, tt = grid(origins, range(1, hmax + 1))
    Y = np.array(truth[list(TARGETS)].reindex(tt), np.float64).reshape(n, hmax, NT)
    parts = []
    for j, t in enumerate(TARGETS):
        for k in range(3):  # sorted in quantiles(); clip each per horizon (unique target-time index for enforce)
            for h in range(hmax):
                col = pd.Series(Q[:, h, j, k], index=tt[h::hmax])
                Q[:, h, j, k] = enforce(pd.DataFrame({t: col}), s)[t].to_numpy()
        parts.append(make_long(issue, hor, t, "tft", Y[:, :, j].ravel(), Q[:, :, j, 1].ravel(), Q[:, :, j, 0].ravel(), Q[:, :, j, 2].ravel()))
    df = pd.concat(parts, ignore_index=True)
    validate_long(df, truth=truth, origins=origins)
    return write_long(df, split, "tft", out_root)


def _rmse_report(T, out_root) -> None:
    from swf.evaluate.longfmt import read_long
    from swf.evaluate.metrics import align_models, metrics, scored_mask

    cfg, choice, s = T["cfg"], T["choice"], T["s"]
    frames = {"tft": read_long("val", "tft", out_root)}
    for t in TARGETS:
        frames["baseline3"] = read_long("val", f"baseline3_{choice[t]}", out_root)
        wide = align_models(frames, t)
        m = scored_mask(wide, ["tft", "baseline3"], t, s, cfg.eval.daytime_zenith_deg)
        y = wide["y_true"].to_numpy("float64")[m]
        r = {n: float(metrics(y, wide[n].to_numpy("float64")[m], 1.0, "")["rmse"]) for n in ("tft", "baseline3")}
        print(f"{t}: val RMSE tft {r['tft']:.4g} baseline3 {r['baseline3']:.4g}", flush=True)


def run(args, interim_dir=None, out_root=None, models_root=None, notes_path=None, out_dir=None, clock=None,
        dcfg=None, inputs=None) -> int:  # fmt: skip
    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    models_root = Path(models_root) if models_root else MODELS_DIR
    notes_path = Path(notes_path) if notes_path else DOCS_DIR / "data_notes.md"
    out_dir = Path(out_dir) if out_dir else REPORTS_DIR / "evaluation"
    dcfg = dcfg or load_deep_cfg()
    tc, clock = dcfg.tft, clock or (lambda: datetime.now(UTC))
    hs, tj, logs = tc.hard_stop_utc, models_root / "tft" / "timing.json", models_root / "tft" / "logs"
    tim = json.loads(tj.read_text(encoding="utf-8")) if tj.exists() else {}
    if args.stop:
        has_logs = any((logs / v / "metrics.csv").exists() for v in ("run", "timing"))
        write_stop("stop requested by the owner (D-19)", tim, curves(logs, out_dir) if has_logs else None, notes_path)
        return 0
    if args.timing_only:
        timing(inputs or _inputs(interim, dcfg), dcfg, models_root, clock)
        return 0
    if hs is not None and clock() >= hs:
        print("past the D-19 hard stop; run `python -m swf train-tft --stop`")
        return 3
    if not tim:
        print("run `python -m swf train-tft --timing-only` first")
        return 1
    if not tim["fits_before_stop"]:
        print(f"projection breaks the hard stop: fit_hours {tim['fit_hours']:.2f} + predict_hours {tim['predict_hours']:.2f}")
        print("fit term levers: train_stride, tft.max_epochs; predict term levers: tft.predict_batch_size, "
              "tft.chunk_origins; re-time after any change, or run `python -m swf train-tft --stop`")  # fmt: skip
        return 3
    inputs = inputs or _inputs(interim, dcfg)
    meta = inputs["meta"]
    cb = hard_stop_callback(hs, tc.stop_check_batches, clock)
    model = fit(inputs, dcfg, models_root, tc.max_epochs, "run", cb, best=True)
    tbl = curves(logs, out_dir)
    if cb.reason:
        write_stop(cb.reason, tim, tbl, notes_path)
        print(cb.reason)
        return 3
    from swf.models.seq import _write_side

    pt = models_root / "tft" / "tft.pt"
    scrub(model).save(str(pt))
    _write_side(pt, meta | {
        "best_epoch": int(tbl["val_loss"].idxmin()) + 1, "epochs_run": len(tbl), "timing": tim,
    })  # fmt: skip
    T = inputs["T"]
    print(f"wrote {predict_split('val', interim, out_root, models_root, tables=T)}", flush=True)
    explain(model, inputs["fit"][0], inputs["fit"][1], out_dir, tc.explain_background)
    write_auto_block(
        notes_path,
        f"## TFT (MODEL-03)\n\n- status: ran\n- epochs: {len(tbl)}, best val loss {tbl['val_loss'].min():.4f}\n"
        "- curves: reports/evaluation/tft_training_curves.png",
        name="tft",
    )
    _rmse_report(T, out_root)
    return 0
