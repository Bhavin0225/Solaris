"""evaluate --final: selection, once-guard, deployed registry, end-to-end on synthetic tmp data only."""

import json
from argparse import Namespace

import numpy as np
import pandas as pd
import pytest
from synth import make_registry, write_tiny_lgbm, write_tiny_lstm
from test_evaluate_report import ORIGINS, write_interim, write_preds

from swf.core.settings import load_features_cfg
from swf.evaluate import final as F
from swf.evaluate import report as r
from swf.evaluate.longfmt import TARGETS, make_long, pred_path, write_long
from swf.predict.registry import RUNTIMES, artifact_path, load_registry, save_registry

BUCKETS = [(1, 6), (7, 24), (25, 72)]
MSF = 0.5


def lbv(rows, split="val"):
    """rows: {model: (rmse, rmse_own, shared_frac)} for one target 'rh'."""
    return pd.DataFrame([{"split": split, "target": "rh", "model": m, "rmse": a, "rmse_own": b, "shared_frac": c} for m, (a, b, c) in rows.items()])


def full(rows):
    """Same rows for every target."""
    return pd.concat([lbv(rows).assign(target=t) for t in TARGETS], ignore_index=True)


def test_select():
    s = F.select(full({"baseline3": (10, 10, 1), "lightgbm": (8, 8, 1), "lstm": (7, 7, 1), "tft": (11, 11, 1)}), MSF)
    assert s["rh"]["selected"] == "lstm" and s["rh"]["val_rmse"]["baseline3"] == 10
    s = F.select(full({"baseline3": (10, 10, 1), "lightgbm": (12, 12, 1)}), MSF)
    assert s["rh"]["selected"] == "baseline3" and s["rh"]["reason"].startswith(F.NO_WIN)
    s = F.select(full({"baseline3": (10, 10, 1), "lstm": (8, 8, 1), "lightgbm": (8, 8, 1)}), MSF)
    assert s["rh"]["selected"] == "lightgbm"  # tie: CANDIDATES order
    test_rows = full({"baseline3": (10, 10, 1), "lstm": (1, 1, 1)}).assign(split="test")
    s = F.select(pd.concat([full({"baseline3": (10, 10, 1), "lightgbm": (9, 9, 1)}), test_rows]), MSF)
    assert s["rh"]["selected"] == "lightgbm"  # test rows ignored
    # rmse (shared) decides, not rmse_own
    s = F.select(full({"baseline3": (10, 10, 1), "lightgbm": (9, 2, 1), "lstm": (8, 9, 1)}), MSF)
    assert s["rh"]["selected"] == "lstm"
    # lowest rmse but shared_frac too small: cannot win
    s = F.select(full({"baseline3": (10, 10, 1), "lightgbm": (9, 9, 1), "lstm": (5, 5, 0.3)}), MSF)
    assert s["rh"]["selected"] == "lightgbm" and s["rh"]["val_rmse"]["lstm"] == 5
    with pytest.raises(ValueError):
        F.select(lbv({"lightgbm": (1, 1, 1)}), MSF)


def test_select_reads_no_test(tmp_path, monkeypatch):
    import swf.evaluate.longfmt as lf

    def boom(split, *a, **k):
        if split == "test":
            raise AssertionError("test opened")
        raise AssertionError("no parquet read expected")

    monkeypatch.setattr(lf, "read_long", boom)
    monkeypatch.setattr(r, "read_long", boom)
    pd.concat([full({"baseline3": (10, 10, 1), "lstm": (7, 7, 1)}), full({"baseline3": (1, 1, 1)}).assign(split="test")]).to_csv(
        tmp_path / "leaderboard.csv", index=False
    )
    assert F.select_from_reports(tmp_path, MSF)["rh"]["selected"] == "lstm"


@pytest.mark.parametrize("name", F.MARKERS)
def test_once_guard_message(tmp_path, name):
    assert F.guard(tmp_path) is None
    (tmp_path / name).write_text("{}")
    assert name in F.guard(tmp_path) and "no override" in F.guard(tmp_path)


def test_registry_fields(tmp_path):
    cfg = load_features_cfg()
    arts = {t: write_tiny_lgbm(tmp_path, t, BUCKETS, seed=i) for i, t in enumerate(TARGETS)}
    p5 = make_registry(tmp_path / "registry.json", lightgbm_artifacts=arts)
    write_tiny_lstm(tmp_path)
    sidecars = {"lstm": json.loads((tmp_path / "lstm" / "lstm.json").read_text())}
    sel_models = {"ghi": "lstm", "rh": "tft", "ws10": "baseline3", "t1_kw": "lightgbm", "t5_kw": "lightgbm"}
    selection = {t: {"selected": m, "reason": "why", "val_rmse": {"baseline3": 2.0, m: 1.0}} for t, m in sel_models.items()}
    lb = pd.DataFrame([{"split": "test", "target": t, "model": m, "rmse": 1.5, "mae": 1.0, "nrmse_pct": 3.0, "skill_vs_baseline3": 0.1} for t, mm in sel_models.items() for m in {mm, "baseline3"}])
    pr = pd.DataFrame([{"target": t, "model": m, "coverage": 0.8, "width": 4.0, "pinball": np.nan} for t, m in sel_models.items()])
    reg = F.build_registry(selection, p5, sidecars, lb, pr, cfg, "abc")
    out = tmp_path / "deployed" / "registry.json"
    save_registry(reg, out)
    d = load_registry(out)
    assert d["split_dates"].keys() == {"train_covariate", "val", "test"} and d["git_sha"] == "abc"
    assert d["final_split"] == "test" and d["selection_split"] == "val" and d["buckets"] and d["baseline3_choice"]
    for t, m in sel_models.items():
        e = d["targets"][t]
        assert e["selected"] == e["runtime"] == m and e["runtime"] in RUNTIMES
        for k in ("reason", "artifacts", "bands", "val_rmse", "test_metrics", "baseline3_test_rmse", "band_method"):
            assert k in e
        assert set(e["test_metrics"]) == {"rmse", "mae", "nrmse_pct", "skill_vs_baseline3", "coverage", "width", "pinball"}
        assert e["test_metrics"]["pinball"] is None and e["baseline3_test_rmse"] == 1.5
        assert e["band_method"] == ("native_quantiles" if m == "tft" else "val_residual_quantiles_by_bucket")
        assert "baseline3" in e["bands"]
        for rel in e["artifacts"].values():
            assert artifact_path(rel, tmp_path).is_relative_to(tmp_path.resolve())
            assert m == "tft" or artifact_path(rel, tmp_path).exists()
    assert d["targets"]["ghi"]["bands"]["lstm"] == sidecars["lstm"]["band_offsets"]["ghi"]
    assert d["targets"]["rh"]["bands"]["tft"] == {"method": "native_quantiles"}
    assert d["targets"]["ws10"]["artifacts"] == {}


# ---- synthetic end-to-end ----

BIAS = {  # val/test bias per model per target; baseline 3 is 1.0 (official choice)
    "lightgbm": {"rh": 6.0, "ghi": 0.5, "t1_kw": 0.5, "ws10": 0.5, "t5_kw": 0.5},
    "lstm": {"rh": 6.0, "ghi": 3.0, "t1_kw": 3.0, "ws10": 3.0, "t5_kw": 0.2},
}


def write_cand(root, split, model):
    issue = np.repeat(pd.DatetimeIndex(ORIGINS[split], tz="UTC"), 72)
    hor = np.tile(np.arange(1, 73), len(ORIGINS[split]))
    tt = issue + pd.to_timedelta(hor, unit="h")
    parts = []
    for i, t in enumerate(TARGETS):
        y = 100 + 10 * i + (tt.hour.to_numpy() % 7) + (tt.dayofyear.to_numpy() % 5)
        p = y + BIAS[model][t]
        parts.append(make_long(issue, hor, t, model, y, p, p - 1.5, p + 1.5))
    return write_long(pd.concat(parts, ignore_index=True), split, model, root)


@pytest.fixture
def fenv(tmp_path, settings):
    root, models = tmp_path / "pred", tmp_path / "models"
    write_preds(root)
    write_interim(tmp_path / "interim", settings)
    for m in BIAS:
        write_cand(root, "val", m)
    arts = {t: write_tiny_lgbm(models, t, BUCKETS, seed=i) for i, t in enumerate(TARGETS)}
    make_registry(models / "registry.json", lightgbm_artifacts=arts)
    write_tiny_lstm(models)
    e = {
        "out_dir": tmp_path / "out", "notes_path": tmp_path / "notes.md", "pred_root": root,
        "choice_path": tmp_path / "choice.json", "interim_dir": tmp_path / "interim",
    }  # fmt: skip
    assert r.run(Namespace(split="val", final=False), **e) == 0
    return {**e, "models_root": models}


def good_predictors(fenv, calls=None):
    def mk(m):
        def f(split, interim_dir=None, out_root=None, models_root=None):
            dep = fenv["models_root"] / "deployed"
            assert (dep / "selection_val.json").exists()
            marker = json.loads((dep / "test_started.json").read_text())
            assert set(marker) == {"git_sha", "split_dates"}
            assert not (dep / "registry.json").exists()
            if calls is not None:
                calls.append(m)
            write_cand(out_root, split, m)

        return f

    return {m: mk(m) for m in BIAS}


def go_final(fenv, **kw):
    return F.run_final(Namespace(final=True), predictors=kw.pop("predictors", None), **fenv)


@pytest.mark.parametrize("name", F.MARKERS)
def test_once_guard(fenv, name, capsys):
    dep = fenv["models_root"] / "deployed"
    dep.mkdir()
    (dep / name).write_text("{}")
    assert go_final(fenv, predictors={}) == 1
    assert name in capsys.readouterr().out
    assert not (dep / "selection_val.json").exists()


def test_crash_leaves_marker(fenv, capsys):
    def boom(split, **kw):
        raise RuntimeError("gpu died")

    with pytest.raises(RuntimeError):
        go_final(fenv, predictors={**good_predictors(fenv), "lstm": boom})
    dep = fenv["models_root"] / "deployed"
    assert (dep / "test_started.json").exists() and not (dep / "registry.json").exists()
    capsys.readouterr()
    assert go_final(fenv, predictors=good_predictors(fenv)) == 1
    assert "test_started.json" in capsys.readouterr().out


@pytest.fixture
def done(fenv):
    calls = []
    assert go_final(fenv, predictors=good_predictors(fenv, calls)) == 0
    return fenv, calls


def test_run_final_order(done):
    fenv, calls = done
    assert sorted(calls) == ["lightgbm", "lstm"]
    sel = json.loads((fenv["models_root"] / "deployed" / "selection_val.json").read_text())
    assert {t: v["selected"] for t, v in sel.items()} == {
        "rh": "baseline3", "ghi": "lightgbm", "t1_kw": "lightgbm", "ws10": "lightgbm", "t5_kw": "lstm",
    }  # fmt: skip
    lb = pd.read_csv(fenv["out_dir"] / "leaderboard.csv")
    assert {"lightgbm", "lstm"} <= set(lb[lb.split == "test"].model)
    reg = load_registry(fenv["models_root"] / "deployed" / "registry.json")
    assert reg["targets"]["t5_kw"]["runtime"] == "lstm" and reg["targets"]["rh"]["runtime"] == "baseline3"
    assert not pred_path("test", "tft", fenv["pred_root"]).exists()


def test_write_reports(done):
    fenv, _ = done
    out = fenv["out_dir"]
    for f in ("prob_metrics.csv", "reliability_test.png", "reliability_val.png", "skill_heatmap_test.csv", "skill_heatmap_test.png",
              "wind_cf.csv", "wind_cf.png", "lgbm_gain_importance.csv", "lgbm_gain_importance.png"):  # fmt: skip
        assert (out / f).exists(), f
    pm = pd.read_csv(out / "prob_metrics.csv")
    assert {"split", "target", "model", "n", "coverage", "width", "pinball", "rel_q10", "rel_q50", "rel_q90"} <= set(pm)
    assert (pm.model == "baseline3").any() and set(pm.split) == {"val", "test"}
    assert not (pred_path("test", "baseline3", fenv["pred_root"]).exists())  # baseline3 bands stay in memory
    txt = fenv["notes_path"].read_text()
    for k in ("BEGIN AUTO:final", "rh: no ML model beat baseline 3 on validation, so baseline 3 is deployed (D-23)", "3 quantile points",
              "in-sample", "Phase 4 W1", "ERA5 archive", "D-26", "1/6/24/48/72"):  # fmt: skip
        assert k in txt
    assert "t5_kw" in txt and "lstm" in txt


def test_heatmap(done):
    fenv, _ = done
    hm = pd.read_csv(fenv["out_dir"] / "skill_heatmap_test.csv")
    bd = pd.read_csv(fenv["out_dir"] / "breakdown.csv", dtype={"horizon": str})
    bd = bd[bd.split == "test"].set_index(["target", "model", "season", "horizon"])["skill_vs_baseline3"]
    assert set(hm.horizon) <= {1, 6, 24, 48, 72} and len(hm) > 0
    for row in hm.itertuples():
        assert bd.loc[(row.target, row.model, row.season, str(row.horizon))] == pytest.approx(row.skill_vs_baseline3, nan_ok=True)


def test_wind_cf(done):
    fenv, _ = done
    w = pd.read_csv(fenv["out_dir"] / "wind_cf.csv")
    assert {"baseline3", "lightgbm", "lstm"} <= set(w.model) and {"all", "monsoon", "dry"} == set(w.season)
    assert w["observed_cf"].notna().any()


def test_figure_titles():
    from swf.evaluate import figures as fg

    t = fg._title("rh", "lightgbm", {"rh": "baseline3"})
    assert "lightgbm" in t and fg.D23 in t
    assert fg.D23 not in fg._title("ghi", "lstm", {"ghi": "lstm"})
