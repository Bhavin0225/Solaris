import json
from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from swf.api.main import create_app
from swf.api.refresh import refresh
from swf.core.paths import MODELS_DIR, REPORTS_DIR, REPO_ROOT
from swf.features.spec import TARGETS
from swf.predict.registry import RUNTIMES, artifact_path, load_registry

DEP = MODELS_DIR / "deployed" / "registry.json"
EV = REPORTS_DIR / "evaluation"
pytestmark = [pytest.mark.realdata, pytest.mark.skipif(not DEP.exists(), reason="evaluate --final not run")]


def test_registry_fields_real():
    reg = load_registry(DEP)
    assert reg["feature_spec_hash"] == "3bd1a73d99093287"
    assert reg["split_dates"] and reg["git_sha"]
    marker = json.loads((DEP.parent / "test_started.json").read_text())
    assert set(marker) == {"git_sha", "split_dates"}
    # the 2026-11-09 run read the SHA again after rewriting tracked reports, so its registry says +dirty (fixed since)
    assert reg["git_sha"].removesuffix("+dirty") == marker["git_sha"] and marker["split_dates"] == reg["split_dates"]
    keys = {"selected", "runtime", "artifacts", "reason", "test_metrics", "baseline3_test_rmse", "band_method", "bands", "val_rmse"}
    metrics = {"rmse", "mae", "nrmse_pct", "skill_vs_baseline3", "coverage", "width", "pinball"}
    for t in TARGETS:
        e = reg["targets"][t]
        assert keys <= set(e), t
        assert metrics <= set(e["test_metrics"]), t
        assert e["runtime"] in RUNTIMES
        for a in e["artifacts"].values():
            assert artifact_path(a, MODELS_DIR).exists(), a


def test_selection_frozen_on_val():
    reg = load_registry(DEP)
    sel = json.loads((DEP.parent / "selection_val.json").read_text())
    for t in TARGETS:
        e, s = reg["targets"][t], sel[t]
        assert e["selected"] == s["selected"]
        if e["selected"] == "baseline3":
            assert "no ML model beat baseline 3 on validation" in e["reason"]
        else:
            assert e["val_rmse"][e["selected"]] < e["val_rmse"]["baseline3"]


def test_test_rows():
    lb = pd.read_csv(EV / "leaderboard.csv")
    test = lb[lb["split"] == "test"]
    val = lb[lb["split"] == "val"]
    for m in ["baseline3", *[m for m in ("lightgbm", "lstm", "gru", "tft") if m in set(val["model"])]]:
        assert set(test[test["model"].str.startswith(m)]["target"]) >= set(TARGETS), m


def test_eval_outputs():
    for f in ["prob_metrics.csv", "reliability_test.png", "skill_heatmap_test.csv", "skill_heatmap_test.png", "wind_cf.csv",
              "wind_cf.png", "lgbm_gain_importance.csv", "lgbm_gain_importance.png"]:  # fmt: skip
        assert (EV / f).exists(), f
    pm = pd.read_csv(EV / "prob_metrics.csv")
    assert {"val", "test"} <= set(pm["split"]) and "coverage" in pm.columns
    hm = pd.read_csv(EV / "skill_heatmap_test.csv")
    hcol = next(c for c in hm.columns if "horizon" in c.lower())
    assert set(hm[hcol]) <= {1, 6, 24, 48, 72}
    assert "BEGIN AUTO:final" in (REPO_ROOT / "docs" / "data_notes.md").read_text(encoding="utf-8")


def test_served_deployed(api_env, live_client, no_sleep):
    reg = load_registry(DEP)
    ok = refresh(api_env.db, client=live_client, sleep=no_sleep, now=datetime(2026, 11, 2, 16, 20, tzinfo=UTC),
                 raw_root=api_env.raw, models_root=MODELS_DIR, registry_path=None)  # fmt: skip
    assert ok is True
    d = TestClient(create_app(api_env.db, start_scheduler=False, static_dir=None)).get("/api/forecast").json()
    for t in TARGETS:
        assert d["targets"][t]["model"] == reg["targets"][t]["runtime"]
