"""Baselines (EVAL-01..03): persistence, climatology, baseline 3 (GFS -> physics, no ML) in the common long format."""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from swf.align.consistency import load_coefs
from swf.core.paths import CONFIG_DIR, INTERIM_DIR
from swf.core.settings import load_features_cfg, load_settings
from swf.evaluate.longfmt import TARGETS, grid, make_long, validate_long, write_long
from swf.evaluate.metrics import align_models, metrics, scored_mask
from swf.features.history import history_frame
from swf.features.spec import assert_spec, lead_k, spec_hash
from swf.features.splits import origins_for
from swf.physics.wind import load_power_curve

MODELS = (
    "persistence",
    "climatology",
    "baseline3_corrected",
    "baseline3_raw",
    "baseline3_stitched_corrected",
    "baseline3_stitched_raw",
)
SAME_HOUR = (
    "t1_kw",
    "ghi",
)  # diurnal targets: persist the same hour of the latest observed day
_NEED = (
    "weather_nasa.parquet",
    "energy_sim.parquet",
    "weather_gfs_hf.parquet",
    "weather_gfs_pr_d1.parquet",
    "weather_gfs_pr_d2.parquet",
    "weather_gfs_pr_d3.parquet",
)


def truth_frame(interim_dir=INTERIM_DIR) -> pd.DataFrame:
    d = Path(interim_dir)
    nasa, energy = d / "weather_nasa.parquet", d / "energy_sim.parquet"
    if not nasa.exists():
        raise FileNotFoundError(f"{nasa} missing; run `python -m swf build-weather`")
    if not energy.exists():
        raise FileNotFoundError(
            f"{energy} missing; run `python -m swf simulate-energy`"
        )
    w, e = pd.read_parquet(nasa), pd.read_parquet(energy)
    return pd.concat([e["t1_kw"], w[["rh", "ghi", "ws10"]], e["t5_kw"]], axis=1)[
        list(TARGETS)
    ]


def _long(model, origins, horizons, truth, pred_by_target) -> pd.DataFrame:
    issue, hor, tt = grid(origins, horizons)
    parts = [
        make_long(
            issue, hor, t, model,
            truth[t].reindex(tt).to_numpy(), pred_by_target[t],
        )
        for t in TARGETS
    ]  # fmt: skip
    return pd.concat(parts, ignore_index=True)


def persistence(truth, origins, horizons) -> pd.DataFrame:
    issue, hor, tt = grid(origins, horizons)
    preds = {}
    for c in TARGETS:
        if c in SAME_HOUR:  # truth[t + h - 24*ceil(h/24)] <= t
            src = tt - pd.to_timedelta(24 * lead_k(hor.astype("int64")), unit="h")
        else:
            src = pd.DatetimeIndex(issue, tz="UTC")
        preds[c] = truth[c].reindex(src).to_numpy()
    return _long("persistence", origins, horizons, truth, preds)


def climatology_table(truth, cfg) -> pd.DataFrame:
    a, b = cfg.splits.train_weather_only
    tr = truth.loc[a:b]
    return tr.groupby([tr.index.month, tr.index.hour]).mean()


def climatology(truth, table, origins, horizons) -> pd.DataFrame:
    _, _, tt = grid(origins, horizons)
    key = pd.MultiIndex.from_arrays([tt.month, tt.hour])
    preds = {c: table[c].reindex(key).to_numpy() for c in TARGETS}
    return _long("climatology", origins, horizons, truth, preds)


def b3_table(gfs, s, curve, coefs=None) -> pd.DataFrame:
    """Same chain as the feature history; run once per table, never per origin."""
    return history_frame(gfs, s, curve, coefs)


def baseline3(tables, truth, origins, horizons, model) -> pd.DataFrame:
    _, hor, tt = grid(origins, horizons)
    k = lead_k(hor.astype("int64"))
    preds = {}
    for c in TARGETS:
        if isinstance(tables, pd.DataFrame):
            preds[c] = tables[c].reindex(tt).to_numpy()
            continue
        p = np.full(len(tt), np.nan)
        for kk, tab in tables.items():
            m = k == kk
            p[m] = tab[c].reindex(tt[m]).to_numpy()
        preds[c] = p
    return _long(model, origins, horizons, truth, preds)


def build_split(split, s, cfg, interim_dir=INTERIM_DIR) -> dict:
    d = Path(interim_dir)
    origins = origins_for(split, cfg)
    horizons = range(1, cfg.horizon_max + 1)
    truth = truth_frame(d)
    hf = pd.read_parquet(d / "weather_gfs_hf.parquet")
    pr = {k: pd.read_parquet(d / f"weather_gfs_pr_d{k}.parquet") for k in (1, 2, 3)}
    coefs, curve = (
        load_coefs(),
        load_power_curve(s),
    )  # D-04: committed ERA5->NASA coefs, no GFS refit
    tab = {}
    for c in (True, False):
        cf = coefs if c else None
        tab[("pr", c)] = {k: b3_table(v, s, curve, cf) for k, v in pr.items()}
        tab[("hf", c)] = b3_table(hf, s, curve, cf)
    table = climatology_table(truth, cfg)
    return {
        "persistence": persistence(truth, origins, horizons),
        "climatology": climatology(truth, table, origins, horizons),
        "baseline3_corrected": baseline3(tab[("pr", True)], truth, origins, horizons, "baseline3_corrected"),
        "baseline3_raw": baseline3(tab[("pr", False)], truth, origins, horizons, "baseline3_raw"),
        "baseline3_stitched_corrected": baseline3(tab[("hf", True)], truth, origins, horizons, "baseline3_stitched_corrected"),
        "baseline3_stitched_raw": baseline3(tab[("hf", False)], truth, origins, horizons, "baseline3_stitched_raw"),
    }  # fmt: skip


def select_baseline3(val_frames, s, cfg) -> dict:
    """D-03a: per target, lower validation RMSE of corrected vs raw lead-matched GFS."""
    a, b = (pd.Timestamp(t) for t in cfg.splits.val)
    frames = {k: val_frames[k] for k in ("baseline3_corrected", "baseline3_raw")}
    for k, df in frames.items():
        it = df["issue_time"]
        if (it < a).any() or (it > b).any():
            raise ValueError(
                f"{k}: issue_time outside validation split; selection may only see validation data"
            )
    choice, rmses = {}, {}
    for t in TARGETS:
        wide = align_models(frames, t)
        mask = scored_mask(wide, list(frames), t, s, cfg.eval.daytime_zenith_deg)
        y = wide["y_true"].to_numpy(dtype="float64")[mask]
        r = {
            n: metrics(y, wide[m].to_numpy(dtype="float64")[mask], 1.0, "")["rmse"]
            for n, m in (("corrected", "baseline3_corrected"), ("raw", "baseline3_raw"))
        }
        choice[t] = "raw" if r["raw"] < r["corrected"] else "corrected"
        rmses[t] = {n: round(v, 6) for n, v in r.items()}
    return {
        "rule": "official baseline 3 = lower validation (2024) RMSE of corrected vs raw lead-matched GFS, per target, frozen before test scoring (D-03a)",
        "split": "val",
        "choice": choice,
        "val_rmse": rmses,
    }


def _choice_path(path):
    return Path(path) if path else CONFIG_DIR / "baseline3_choice.json"


def save_choice(choice, path=None) -> None:
    path = _choice_path(path)
    text = (
        json.dumps(
            {**choice, "feature_spec_hash": spec_hash()}, indent=2, sort_keys=True
        )
        + "\n"
    )
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_choice(path=None) -> dict:
    path = _choice_path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing; run `python -m swf evaluate --split val` to freeze the baseline-3 choice"
        )
    d = json.loads(path.read_text(encoding="utf-8"))
    try:
        assert_spec({"feature_spec_hash": d.get("feature_spec_hash")})
    except ValueError as e:
        raise ValueError(
            f"{e}; delete config/baseline3_choice.json and rerun `python -m swf evaluate --split val`"
        ) from e
    return d


def run(args, out_root=None, interim_dir=None) -> int:
    interim = Path(interim_dir) if interim_dir else INTERIM_DIR
    if any(not (interim / n).exists() for n in _NEED):
        print(
            "run `python -m swf build-weather` and `python -m swf simulate-energy` first"
        )
        return 1
    s, cfg = load_settings(), load_features_cfg()
    truth = truth_frame(interim)
    for split in ("val", "test"):
        origins = origins_for(split, cfg)
        for model, df in build_split(split, s, cfg, interim).items():
            validate_long(df, truth=truth, origins=origins)
            write_long(df, split, model, out_root)
            nan = df.groupby("target", observed=True)["p50"].apply(
                lambda x: int(x.isna().sum())
            )
            print(
                f"{split} {model}: {len(df)} rows; NaN p50 per target {nan.to_dict()}"
            )
    return 0
