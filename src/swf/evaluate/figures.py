"""Evaluation figures and tables for Phase 6 (EVAL-08..10, MODEL-07)."""

import json

import numpy as np
import pandas as pd

from swf.evaluate.longfmt import TARGETS
from swf.evaluate.metrics import SEASONS, _season, align_models, scored_mask
from swf.predict.registry import artifact_path

D23 = "baseline 3 deployed (D-23)"
_SAVE = {"dpi": 120, "metadata": {"Software": None}}


def _title(target, model=None, deployed=None) -> str:
    t = f"{target}: {model}" if model else target
    if deployed and deployed.get(target) == "baseline3":
        t += f" | {D23}"
    return t


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def heatmap_table(bd, split, models) -> pd.DataFrame:
    d = bd[(bd["split"] == split) & bd["model"].astype(str).isin(models) & (bd["horizon"].astype(str) != "all")].copy()
    d["horizon"] = d["horizon"].astype(int)
    d["model"] = d["model"].astype(str)
    return d[["target", "model", "season", "horizon", "skill_vs_baseline3"]].reset_index(drop=True)


def plot_heatmap(table, model_by_target, path, deployed=None) -> list[str]:
    plt = _plt()
    fig, axes = plt.subplots(1, len(TARGETS), figsize=(22, 3.6))
    titles = []
    for ax, t in zip(axes, TARGETS, strict=True):
        m = model_by_target[t]
        g = table[(table["target"] == t) & (table["model"] == m)]
        piv = g.pivot_table(index="season", columns="horizon", values="skill_vs_baseline3").reindex(list(SEASONS))
        v = float(np.nanmax(np.abs(piv.to_numpy()))) if piv.notna().any().any() else 1.0
        v = v or 1.0
        ax.imshow(piv.to_numpy(dtype="float64"), cmap="RdBu", vmin=-v, vmax=v, aspect="auto")
        ax.set_xticks(range(piv.shape[1]), [str(c) for c in piv.columns])
        ax.set_yticks(range(piv.shape[0]), list(piv.index))
        for (i, j), val in np.ndenumerate(piv.to_numpy(dtype="float64")):
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7)
        titles.append(_title(t, m, deployed))
        ax.set_title(titles[-1], fontsize=7)
        ax.set_xlabel("horizon (h)")
    fig.suptitle("skill vs baseline 3; exact horizons 1/6/24/48/72 h (D-24)")
    fig.tight_layout()
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return titles


def wind_cf_table(frames, s, cfg) -> pd.DataFrame:
    wide = align_models(frames, "t5_kw")
    models = list(frames)
    m = scored_mask(wide, models, "t5_kw", s, cfg.eval.daytime_zenith_deg)
    rated = float(s.wind.rated_kw)
    season = _season(wide, cfg)
    y = wide["y_true"].to_numpy(dtype="float64")
    rows = []
    for se in SEASONS:
        sel = m & (np.ones(len(wide), bool) if se == "all" else season == se)
        for k in models:
            p = wide[k].to_numpy(dtype="float64")
            n = int(sel.sum())
            rows.append({
                "season": se, "model": k, "n": n,
                "observed_cf": y[sel].mean() / rated if n else np.nan,
                "predicted_cf": p[sel].mean() / rated if n else np.nan,
                "rmse_cf": float(np.sqrt(np.mean((p[sel] - y[sel]) ** 2))) / rated if n else np.nan,
            })  # fmt: skip
    return pd.DataFrame(rows)


def plot_wind_cf(table, path, deployed=None) -> list[str]:
    plt = _plt()
    models = list(dict.fromkeys(table["model"].astype(str)))
    fig, ax = plt.subplots(figsize=(8, 4))
    w = 0.8 / (len(models) + 1)
    x = np.arange(len(SEASONS))
    obs = table[table["model"].astype(str) == models[0]].set_index("season").reindex(list(SEASONS))
    ax.bar(x, obs["observed_cf"], w, label="observed")
    for i, k in enumerate(models, 1):
        g = table[table["model"].astype(str) == k].set_index("season").reindex(list(SEASONS))
        ax.bar(x + i * w, g["predicted_cf"], w, label=k)
    ax.set_xticks(x + w * len(models) / 2, list(SEASONS))
    ax.set_ylabel("capacity factor")
    title = _title("t5_kw", None, deployed) + " (simulated energy, rated kW from config/plant.yaml)"
    ax.set_title(title, fontsize=8)
    ax.legend(fontsize=6, title="model")
    fig.tight_layout()
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return [title]


def gain_importance(artifacts, models_root) -> pd.DataFrame:
    import lightgbm as lgb

    rows = []
    for t in TARGETS:
        if t not in artifacts:
            continue
        total, names = None, None
        for rel in artifacts[t].values():
            p = artifact_path(rel, models_root)
            b = lgb.Booster(model_file=str(p))
            cols = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))["feature_columns"]
            if b.feature_name() != cols:
                raise ValueError(f"{p}: booster feature names differ from sidecar feature_columns")
            g = np.asarray(b.feature_importance("gain"), dtype="float64")
            total = g if total is None else total + g
            names = cols
        s = total.sum()
        d = pd.DataFrame({"target": t, "feature": names, "gain": total, "gain_pct": 100 * total / s if s else 0.0})
        rows.append(d.sort_values("gain_pct", ascending=False, kind="stable"))
    return pd.concat(rows, ignore_index=True)


def plot_gain(df, path, top=15, deployed=None) -> list[str]:
    plt = _plt()
    fig, axes = plt.subplots(1, len(TARGETS), figsize=(22, 5))
    titles = []
    for ax, t in zip(axes, TARGETS, strict=True):
        g = df[df["target"] == t].head(top).iloc[::-1]
        ax.barh(g["feature"], g["gain_pct"])
        ax.tick_params(labelsize=6)
        ax.set_xlabel("gain (%)")
        titles.append(_title(t, "lightgbm", deployed))
        ax.set_title(titles[-1], fontsize=7)
    fig.tight_layout()
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return titles


def plot_reliability(prob_df, split, path, deployed=None) -> list[str]:
    plt = _plt()
    fig, axes = plt.subplots(1, len(TARGETS), figsize=(20, 4))
    titles = []
    for ax, t in zip(axes, TARGETS, strict=True):
        ax.plot([0, 1], [0, 1], "k--", lw=0.8)
        for k, g in prob_df[prob_df["target"] == t].groupby(prob_df["model"].astype(str)):
            ax.plot([0.1, 0.5, 0.9], g[["rel_q10", "rel_q50", "rel_q90"]].iloc[0], marker="o", label=k)
        titles.append(_title(t, None, deployed))
        ax.set_title(titles[-1], fontsize=7)
        ax.set_xlabel("nominal quantile")
        ax.legend(fontsize=6)
    fig.suptitle(f"{split}: 3 quantile points (P10, P50, P90) per model; EVAL-08")
    fig.tight_layout()
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return titles
