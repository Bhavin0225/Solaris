"""Selection on validation and the once-only final test evaluation (MODEL-05..07, EVAL-08..10; D-21..D-24, D-28)."""

import functools
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from swf.core.paths import CONFIG_DIR, DOCS_DIR, INTERIM_DIR, MODELS_DIR, PROCESSED_DIR, REPO_ROOT, REPORTS_DIR
from swf.core.settings import load_features_cfg, load_settings
from swf.coverage.report import _table, write_auto_block
from swf.evaluate.longfmt import TARGETS, pred_path, read_long
from swf.predict.bands import band_frame, bucket_label

CANDIDATES = ("lightgbm", "lstm", "gru", "tft")
NO_WIN = "no ML model beat baseline 3 on validation"
MARKERS = ("test_started.json", "registry.json")
_BAND = "val_residual_quantiles_by_bucket"


def select(lb: pd.DataFrame, min_shared_frac: float) -> dict:
    """D-21: lowest shared-sample val `rmse` among candidates that beat baseline 3 (validation rows only)."""
    v = lb[lb["split"] == "val"]
    out = {}
    for t in TARGETS:
        g = v[v["target"] == t].assign(model=lambda d: d["model"].astype(str)).set_index("model")
        if "baseline3" not in g.index:
            raise ValueError(f"no baseline3 validation row for {t}")
        ref = float(g.loc["baseline3", "rmse"])
        cand = {m: float(g.loc[m, "rmse"]) for m in CANDIDATES if m in g.index and np.isfinite(g.loc[m, "rmse"])}
        ok = {m: x for m, x in cand.items() if g.loc[m, "shared_frac"] >= min_shared_frac}
        wins = {m: x for m, x in ok.items() if x < ref}
        best = min(wins, key=lambda m: wins[m]) if wins else None  # min is stable: ties follow CANDIDATES order
        if best:
            sel, why = best, f"lowest val RMSE {wins[best]:.4g} among candidates beating baseline 3 ({ref:.4g})"
        else:
            b = min(ok, key=lambda m: ok[m]) if ok else None
            sel, why = "baseline3", f"{NO_WIN} (baseline 3 {ref:.4g}; best candidate {f'{b} {ok[b]:.4g}' if b else 'none'})"
        out[t] = {"selected": sel, "reason": why, "val_rmse": {"baseline3": ref, **cand}}
    return out


def select_from_reports(out_dir, min_shared_frac: float) -> dict:
    return select(pd.read_csv(Path(out_dir) / "leaderboard.csv"), min_shared_frac)


def guard(deployed_dir) -> str | None:
    for name in MARKERS:
        if (Path(deployed_dir) / name).exists():
            return (
                f"{Path(deployed_dir) / name} exists: the test split was already opened by evaluate --final (D-22). "
                "Recovery is a deliberate manual delete by the owner; there is no override flag."
            )
    return None


def git_sha(repo_root=REPO_ROOT) -> str:
    def git(*a):
        return subprocess.run(["git", *a], cwd=repo_root, capture_output=True, text=True, check=False)

    try:
        r = git("rev-parse", "HEAD")
        if r.returncode:
            return "unknown"
        return r.stdout.strip() + ("+dirty" if git("status", "--porcelain", "--untracked-files=no").stdout.strip() else "")
    except OSError:
        return "unknown"


def artifacts_for(model, t, phase5_reg) -> dict:
    if model == "baseline3":
        return {}
    if model == "lightgbm":
        return phase5_reg["targets"][t]["artifacts"]
    return {"model": f"{model}/{model}.pt"}


def bands_for(model, t, phase5_reg, sidecars) -> dict:
    out = {"baseline3": phase5_reg["targets"][t]["bands"]["baseline3"]}
    if model == "lightgbm":
        out["lightgbm"] = phase5_reg["targets"][t]["bands"]["lightgbm"]
    elif model in ("lstm", "gru"):
        out[model] = sidecars[model]["band_offsets"][t]
    elif model == "tft":
        out["tft"] = {"method": "native_quantiles"}
    return out


def _num(x):
    return float(x) if x is not None and np.isfinite(x) else None


def split_dates(cfg) -> dict:
    return {k: [t.isoformat() for t in getattr(cfg.splits, k)] for k in ("train_covariate", "val", "test")}


def build_registry(selection, phase5_reg, sidecars, lb_test, prob_test, cfg, git) -> dict:
    lb = lb_test.assign(model=lb_test["model"].astype(str)).set_index(["target", "model"])
    pr = prob_test.assign(model=prob_test["model"].astype(str)).set_index(["target", "model"])
    targets = {}
    for t, sel in selection.items():
        m = sel["selected"]
        r, p = lb.loc[(t, m)], pr.loc[(t, m)]
        tm = {k: _num(r[k]) for k in ("rmse", "mae", "nrmse_pct", "skill_vs_baseline3")}
        tm |= {k: _num(p[k]) for k in ("coverage", "width", "pinball")}
        targets[t] = {
            "selected": m, "runtime": m, "reason": sel["reason"], "artifacts": artifacts_for(m, t, phase5_reg),
            "bands": bands_for(m, t, phase5_reg, sidecars), "val_rmse": sel["val_rmse"], "test_metrics": tm,
            "baseline3_test_rmse": _num(lb.loc[(t, "baseline3"), "rmse"]),
            "band_method": "native_quantiles" if m == "tft" else _BAND,
        }  # fmt: skip
    return {
        "baseline3_choice": phase5_reg["baseline3_choice"], "buckets": phase5_reg["buckets"],
        "selection_split": "val", "final_split": "test", "split_dates": split_dates(cfg), "git_sha": git,
        "targets": targets,
    }  # fmt: skip


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _banded_b3(split, t, root, choice, phase5_reg, s) -> pd.DataFrame:
    """Baseline 3 with validation-offset bands, in memory only (the baseline3_* parquets are never rewritten)."""
    df = read_long(split, f"baseline3_{choice['choice'][t]}", root, target=t)
    buckets = [tuple(b) for b in phase5_reg["buckets"]]
    off = phase5_reg["targets"][t]["bands"]["baseline3"]
    df = df.copy()
    df["model"] = pd.Categorical(["baseline3"] * len(df))
    for c in ("p10", "p90"):
        df[c] = df[c].astype("float64")
    for h, idx in df.groupby(df["horizon"].astype(int)).groups.items():
        g = df.loc[idx]
        q10, q90 = off[bucket_label(h, buckets)]
        bf = band_frame(pd.Series(g["p50"].to_numpy("float64"), index=pd.DatetimeIndex(g["target_time"])), q10, q90, t, s)
        df.loc[idx, "p10"], df.loc[idx, "p90"] = bf["p10"].to_numpy(), bf["p90"].to_numpy()
    return df


def _f(x, d=4):
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{d}g}"


def write_reports(selection, phase5_reg, sidecars, lb, bd, root, out_dir, notes_path, s, cfg, choice, models_root):
    """EVAL-08..10, MODEL-07 outputs plus the AUTO:final notes block; returns the test probabilistic rows."""
    from swf.evaluate import figures as fg
    from swf.evaluate.prob import prob_rows

    csv = {"index": False, "float_format": "%.6g", "lineterminator": "\n"}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cands = [m for m in CANDIDATES if pred_path("test", m, root).exists()]
    deployed = {t: selection[t]["selected"] for t in TARGETS}
    rows = []
    for sp in ("val", "test"):
        for t in TARGETS:
            frames = {"baseline3": _banded_b3(sp, t, root, choice, phase5_reg, s)}
            for m in cands:
                d = read_long(sp, m, root, target=t)
                if d["p10"].notna().any() and d["p90"].notna().any():
                    frames[m] = d
            rows.append(prob_rows(frames, t, s, cfg).assign(split=sp))
    prob = pd.concat(rows, ignore_index=True)
    prob = prob[["split", *[c for c in prob.columns if c != "split"]]]
    prob.to_csv(out_dir / "prob_metrics.csv", **csv)
    for sp in ("val", "test"):
        fg.plot_reliability(prob[prob["split"] == sp], sp, out_dir / f"reliability_{sp}.png", deployed=deployed)

    best_cand = {t: min((m for m in selection[t]["val_rmse"] if m != "baseline3"), key=selection[t]["val_rmse"].get, default="lightgbm") for t in TARGETS}
    by_target = {t: deployed[t] if deployed[t] != "baseline3" else best_cand[t] for t in TARGETS}
    table = fg.heatmap_table(bd, "test", cands)
    table.to_csv(out_dir / "skill_heatmap_test.csv", **csv)
    fg.plot_heatmap(table, by_target, out_dir / "skill_heatmap_test.png", deployed=deployed)

    wf = {"baseline3": read_long("test", f"baseline3_{choice['choice']['t5_kw']}", root, target="t5_kw")}
    wf |= {m: read_long("test", m, root, target="t5_kw") for m in cands}
    wcf = fg.wind_cf_table(wf, s, cfg)
    wcf.to_csv(out_dir / "wind_cf.csv", **csv)
    fg.plot_wind_cf(wcf, out_dir / "wind_cf.png", deployed=deployed)

    gain = fg.gain_importance({t: phase5_reg["targets"][t]["artifacts"] for t in TARGETS}, models_root)
    gain.to_csv(out_dir / "lgbm_gain_importance.csv", **csv)
    fg.plot_gain(gain, out_dir / "lgbm_gain_importance.png", deployed=deployed)

    write_auto_block(notes_path, _notes(selection, sidecars, lb, prob[prob["split"] == "test"], cfg), name="final")
    return prob[prob["split"] == "test"].reset_index(drop=True)


def _notes(selection, sidecars, lb, prob_test, cfg) -> str:
    L = ["Generated by `python -m swf evaluate --final`. Do not edit inside this block.", "",
         "## Final evaluation (evaluate --final, test evaluated once)", ""]  # fmt: skip
    sd = split_dates(cfg)
    L += [f"Split dates (UTC): train_covariate {sd['train_covariate'][0]} to {sd['train_covariate'][1]}; val {sd['val'][0]} to {sd['val'][1]}; test {sd['test'][0]} to {sd['test'][1]}.", "",
          f"git sha: {git_sha()}", ""]  # fmt: skip
    ml = lb.assign(model=lb["model"].astype(str)).set_index(["split", "target", "model"])
    pr = prob_test.assign(model=prob_test["model"].astype(str)).set_index(["target", "model"])
    rows = []
    for t in TARGETS:
        m = selection[t]["selected"]
        rows.append([t, m, _f(ml.loc[("val", t, m), "rmse"]), _f(ml.loc[("val", t, "baseline3"), "rmse"]),
                     _f(ml.loc[("test", t, m), "rmse"]), _f(ml.loc[("test", t, "baseline3"), "rmse"]),
                     _f(ml.loc[("test", t, m), "skill_vs_baseline3"]), _f(pr.loc[(t, m), "coverage"])])  # fmt: skip
    L += _table(["target", "selected", "val RMSE selected", "val RMSE baseline3", "test RMSE selected",
                 "test RMSE baseline3", "test skill vs baseline3", "test P10-P90 coverage"], rows)  # fmt: skip
    L += [f"- {t}: {selection[t]['reason']}" for t in TARGETS]
    L += [""] + [f"{t}: {NO_WIN}, so baseline 3 is deployed (D-23)" + "." for t in TARGETS if selection[t]["selected"] == "baseline3"]
    L += ["", "Deep model training (sidecars):", ""]
    for m in ("lstm", "gru"):
        if m in sidecars:
            sc = sidecars[m]
            es = [x for x in sc.get("history", {}).get("es_loss", []) if x is not None and np.isfinite(x)]
            extra = f"; minimal version reported (D-18): {sc['reason']}" if sc.get("status") == "minimal" else ""
            L.append(f"- {m}: best_epoch {sc.get('best_epoch')}, epochs_run {sc.get('epochs_run')}, best early-stopping loss {_f(min(es) if es else None)}{extra}")
    L += ["- tft: see AUTO:tft.", "", "Caveats:", ""]
    L += [
        "- Reliability has 3 quantile points only (P10, P50, P90), so it is a coarse calibration check.",
        "- Validation bands are in-sample on val (offsets are fitted there); test coverage is the honest check.",
        "- Stitched-vs-lead covariate skew (Phase 4 W1): training covariates are stitched short-lead analyses, while validation, test and serving use lead-matched forecasts.",
        "- Encoder source skew (D-26): deep-model encoders read the ERA5 archive history in training/val/test but Open-Meteo past_days at serving; same code path, different source; accepted and not measured.",
        f"- Breakdowns use exact horizons {'/'.join(str(h) for h in cfg.eval.horizons)} (D-24).",
        "",
    ]  # fmt: skip
    return "\n".join(L)


def run_final(args, out_dir=None, notes_path=None, pred_root=None, choice_path=None, interim_dir=None,
              models_root=None, predictors=None) -> int:  # fmt: skip
    from swf.evaluate.baselines import MODELS, load_choice
    from swf.evaluate.report import _CSV, _merge, score_split
    from swf.predict.registry import load_registry, save_registry

    out_dir = Path(out_dir) if out_dir else REPORTS_DIR / "evaluation"
    notes_path = Path(notes_path) if notes_path else DOCS_DIR / "data_notes.md"
    root = Path(pred_root) if pred_root else PROCESSED_DIR / "predictions"
    choice_path = Path(choice_path) if choice_path else CONFIG_DIR / "baseline3_choice.json"
    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    models_root = Path(models_root) if models_root else MODELS_DIR
    dep = models_root / "deployed"
    msg = guard(dep)
    if msg:
        print(msg)
        return 1
    s, cfg = load_settings(), load_features_cfg()
    if not (models_root / "registry.json").exists():
        print("run `python -m swf train-lgbm` first (models/registry.json)")
        return 1
    if not (out_dir / "leaderboard.csv").exists() or not (pd.read_csv(out_dir / "leaderboard.csv")["split"] == "val").any():
        print("run `python -m swf evaluate --split val` first")
        return 1
    if not pred_path("val", "lightgbm", root).exists() or any(not pred_path("test", m, root).exists() for m in MODELS):
        print("run `python -m swf baselines` and `train-lgbm` first (val lightgbm and test baseline predictions)")
        return 1
    try:
        choice = load_choice(choice_path)
        phase5_reg = load_registry(models_root / "registry.json")
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return 1

    selection = select_from_reports(out_dir, cfg.eval.min_shared_frac)
    _write_json(dep / "selection_val.json", selection)  # before any test file is touched (Pitfall 9)
    print(pd.DataFrame({t: {"selected": v["selected"], "reason": v["reason"]} for t, v in selection.items()}).T.to_string())
    _write_json(dep / "test_started.json", {"git_sha": git_sha(), "split_dates": split_dates(cfg)})
    print("test_started.json marks that test data was opened; delete it only by a deliberate owner decision")

    cands = [m for m in CANDIDATES if pred_path("val", m, root).exists()]
    if predictors is None:
        from swf.models import lgbm, seq, tft

        predictors = {"lightgbm": lgbm.predict_split, "lstm": functools.partial(seq.predict_split, name="lstm"),
                      "gru": functools.partial(seq.predict_split, name="gru"), "tft": tft.predict_split}  # fmt: skip
    for m in cands:
        predictors[m]("test", interim_dir=interim, out_root=root, models_root=models_root)

    lb_t, bd_t = score_split("test", s, cfg, root, choice)
    out_dir.mkdir(parents=True, exist_ok=True)
    lb = _merge(out_dir / "leaderboard.csv", lb_t, ["test"])
    bd = _merge(out_dir / "breakdown.csv", bd_t, ["test"])
    lb.to_csv(out_dir / "leaderboard.csv", **_CSV)
    bd.to_csv(out_dir / "breakdown.csv", **_CSV)

    sidecars = {m: json.loads((models_root / m / f"{m}.json").read_text(encoding="utf-8")) for m in cands if m != "lightgbm"}
    prob_test = write_reports(selection, phase5_reg, sidecars, lb, bd, root, out_dir, notes_path, s, cfg, choice, models_root)
    reg = build_registry(selection, phase5_reg, sidecars, lb[lb["split"] == "test"], prob_test, cfg, git_sha())
    save_registry(reg, dep / "registry.json")  # last write
    print(pd.DataFrame({t: {k: v[k] for k in ("selected", "baseline3_test_rmse")} | v["test_metrics"] for t, v in reg["targets"].items()}).T.to_string())
    return 0
