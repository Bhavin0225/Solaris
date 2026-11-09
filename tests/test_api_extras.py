import json
import shutil
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from swf.api import db
from swf.api.main import create_app
from swf.core.settings import load_settings
from swf.features.spec import TARGETS

RUN = datetime(2026, 10, 28, 6, tzinfo=UTC)  # inside the live fixture span (2026-10-26 .. 2026-11-05)


def _app(db_path, tmp_path, **kw):
    kw.setdefault("static_dir", None)
    return TestClient(
        create_app(
            db_path, start_scheduler=False, leaderboard_path=tmp_path / "none.csv", reports_dir=tmp_path / "reports",
            interim_dir=tmp_path / "interim", raw_root=tmp_path / "raw", registry_path=tmp_path / "registry.json", **kw,
        )
    )  # fmt: skip


def _db_at(path, run):
    rows = [(db.iso(run), db.iso(run + timedelta(hours=h - 1)), t, "baseline3", 1.0, 2.0, 3.0) for t in TARGETS for h in range(1, 73)]
    db.write_run(path, db.iso(run), rows, [], db.iso(run))
    return path


# ---- weather -----------------------------------------------------------------------------------


def _put_live(tmp_path, fixtures_dir, run):
    s = load_settings()
    d = tmp_path / "raw" / "openmeteo" / "forecast" / s.data.openmeteo.nwp_model
    d.mkdir(parents=True)
    shutil.copy(fixtures_dir / "om_live_gfs_seamless.json", d / f"{run + timedelta(hours=1):%Y%m%dT%H}.json")


def test_weather_points(tmp_path, fixtures_dir):
    _put_live(tmp_path, fixtures_dir, RUN)
    c = _app(_db_at(tmp_path / "w.db", RUN), tmp_path)
    r = c.get("/api/weather")
    assert r.status_code == 200, r.text
    d = r.json()
    pts = d["points"]
    assert pts and all(set(p) == {"time", "temp", "cloud", "precip", "is_day"} for p in pts)
    assert all(p["time"].endswith("Z") for p in pts)
    assert {p["is_day"] for p in pts} == {True, False}
    # IST date of run+1h is 2026-10-28 -> IST midnight = 2026-10-27T18:30Z
    assert datetime.fromisoformat(pts[0]["time"]) <= datetime(2026, 10, 27, 18, 30, tzinfo=UTC)
    assert datetime.fromisoformat(pts[-1]["time"]) <= RUN + timedelta(hours=72)
    assert d["run_time"].endswith("Z")


def test_weather_missing_file_and_empty_db(tmp_path):
    assert _app(_db_at(tmp_path / "w.db", RUN), tmp_path).get("/api/weather").status_code == 503
    assert _app(tmp_path / "empty.db", tmp_path).get("/api/weather").status_code == 503


# ---- correlation -------------------------------------------------------------------------------


def _parquets(tmp_path, n=200):
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC", name="time")
    rng = np.random.default_rng(0)
    ghi = rng.uniform(0, 1000, n)
    (tmp_path / "interim").mkdir(exist_ok=True)
    pd.DataFrame({"t1_kw": ghi * 0.8 + rng.normal(0, 5, n), "t5_kw": rng.uniform(0, 2000, n)}, index=idx).to_parquet(
        tmp_path / "interim" / "energy_sim.parquet"
    )
    pd.DataFrame({"ghi": ghi, "rh": rng.uniform(20, 90, n), "ws10": rng.uniform(0, 10, n)}, index=idx).to_parquet(
        tmp_path / "interim" / "weather_nasa.parquet"
    )


def test_correlation_matrix(seed, tmp_path):
    _parquets(tmp_path)
    d = _app(seed(), tmp_path).get("/api/correlation").json()
    assert d["targets"] == ["t1_kw", "t5_kw", "ghi", "rh", "ws10"]
    m = np.array(d["matrix"])
    assert m.shape == (5, 5) and np.allclose(m, m.T) and np.allclose(np.diag(m), 1.0)
    assert d["n"] == 200 and d["period_start"].endswith("Z") and d["period_end"].endswith("Z")
    assert m[0, 2] > 0.9


def test_correlation_missing(seed, tmp_path):
    assert _app(seed(), tmp_path).get("/api/correlation").status_code == 503


# ---- performance -------------------------------------------------------------------------------


def _csvs(tmp_path):
    ev = tmp_path / "reports" / "evaluation"
    ev.mkdir(parents=True)
    (ev / "prob_metrics.csv").write_text(
        "split,target,model,n,coverage,width,pinball,rel_q10,rel_q50,rel_q90\n"
        "val,t1_kw,baseline3,10,0.7,1,1,0.1,0.5,0.9\n"
        "test,t1_kw,baseline3,10,0.8,2,3,0.1,0.5,0.9\n"
    )
    (ev / "breakdown.csv").write_text(
        "split,target,model,horizon,season,n,mae,rmse,mbe,nrmse_pct,norm,norm_kind,skill_vs_baseline3,skill_vs_persistence,feature_spec_hash\n"
        "val,t1_kw,baseline3,1,all,5,1,2,0,3,800,k,0,0,h\n"
        "test,t1_kw,baseline3,1,all,5,1,2,0,3,800,k,0,0,h\n"
        "test,t1_kw,tft,24,all,5,1,2,0,3,800,k,,0,h\n"
        "test,t1_kw,tft,all,all,5,1,2,0,3,800,k,0.2,0,h\n"
        "test,t1_kw,tft,24,monsoon,5,1,2,0,3,800,k,0.2,0,h\n"
    )
    (ev / "skill_heatmap_test.csv").write_text("target,model,season,horizon,skill_vs_baseline3\nt1_kw,lightgbm,all,1,0.5\n")
    (ev / "wind_cf.csv").write_text("season,model,n,observed_cf,predicted_cf,rmse_cf\nall,baseline3,9,0.3,0.29,0.19\n")


def test_performance_rows(seed, tmp_path):
    _csvs(tmp_path)
    d = _app(seed(), tmp_path).get("/api/performance").json()
    assert [r["coverage"] for r in d["coverage"]] == [0.8]
    assert [(r["model"], r["horizon"]) for r in d["horizon"]] == [("baseline3", 1), ("tft", 24)]
    assert d["horizon"][1]["skill_vs_baseline3"] is None
    assert d["heatmap"] == [{"target": "t1_kw", "model": "lightgbm", "season": "all", "horizon": 1, "skill_vs_baseline3": 0.5}]
    assert d["wind_cf"][0]["n"] == 9


def test_performance_missing(seed, tmp_path):
    assert _app(seed(), tmp_path).get("/api/performance").json() == {"coverage": [], "horizon": [], "heatmap": [], "wind_cf": []}


# ---- figures -----------------------------------------------------------------------------------


def test_figures_allowlist(seed, tmp_path):
    v = tmp_path / "reports" / "validation"
    v.mkdir(parents=True)
    (v / "wind_scatter.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "reports" / "evaluation").mkdir()
    (tmp_path / "reports" / "evaluation" / "leaderboard.csv").write_text("secret")
    c = _app(seed(), tmp_path)
    r = c.get("/api/figures/wind_scatter")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == b"\x89PNG fake"
    assert c.get("/api/figures/leaderboard").status_code == 404
    assert c.get("/api/figures/..%2Fevaluation%2Fleaderboard.csv").status_code == 404
    assert c.get("/api/figures/wind_cf").status_code == 404  # allowlisted but file missing


# ---- build -------------------------------------------------------------------------------------


def test_build_info(seed, tmp_path, monkeypatch):
    (tmp_path / "registry.json").write_text(
        json.dumps({"schema_version": 2, "git_sha": "abc123", "final_split": "test",
                    "targets": {"t1_kw": {"runtime": "tft"}, "rh": {"runtime": "lightgbm"}}})
    )  # fmt: skip

    from swf.api import extras

    def boom(*a, **k):
        raise OSError("no git")

    monkeypatch.setattr(extras.subprocess, "run", boom)
    extras.git_short_sha.cache_clear()
    c = _app(seed(), tmp_path)
    try:
        d = c.get("/api/build").json()
    finally:
        extras.git_short_sha.cache_clear()
    assert d["git_sha"] is None and d["registry_git_sha"] == "abc123"
    assert d["schema_version"] == 2 and d["final_split"] == "test"
    assert d["models"] == {"t1_kw": "tft", "rh": "lightgbm"}
    s = load_settings()
    assert d["kaggle"] == {"solar_slug": s.kaggle.solar_slug, "wind_slug": s.kaggle.wind_slug}
    run = datetime.fromisoformat(c.get("/api/health").json()["run_time"])
    assert datetime.fromisoformat(d["data_through"]) == run + timedelta(hours=1)


def test_build_missing_registry(seed, tmp_path):
    r = _app(seed(), tmp_path).get("/api/build")
    assert r.status_code == 200
    assert r.json()["models"] == {} and r.json()["schema_version"] is None


# ---- SPA fallback ------------------------------------------------------------------------------


def test_spa_fallback(seed, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA-MARKER</html>")
    c = _app(seed(), tmp_path, static_dir=dist)
    r = c.get("/performance")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "SPA-MARKER" in r.text
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert c.get("/api/health").json()["status"] == "ok"
