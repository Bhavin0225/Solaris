import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from swf.api import db, main
from swf.api.main import create_app


@pytest.fixture
def client(seed, tmp_path):
    return TestClient(create_app(seed(), start_scheduler=False, static_dir=None, leaderboard_path=tmp_path / "none.csv"))


def test_forecast_shape_and_z(client):
    r = client.get("/api/forecast")
    assert r.status_code == 200
    d = r.json()
    assert d["stale"] is False and len(d["targets"]) == 5
    for tf in d["targets"].values():
        assert len(tf["points"]) == 72
        assert all(p["time"].endswith("Z") for p in tf["points"])
    assert d["run_time"].endswith("Z")
    assert all(len(t["points"]) == 6 for t in client.get("/api/forecast?hours=6").json()["targets"].values())
    assert client.get("/api/forecast?hours=0").status_code == 422
    assert client.get("/api/forecast?hours=73").status_code == 422


def test_history_bounds(client):
    d = client.get("/api/history?days=7").json()
    assert all(len(v) == 168 for v in d["targets"].values())
    assert client.get("/api/history?days=8").status_code == 422


def test_summary_window(client):
    from datetime import datetime

    d = client.get("/api/forecast/summary").json()
    assert d["n_hours"] == 24
    span = datetime.fromisoformat(d["window_end"]) - datetime.fromisoformat(d["window_start"])
    assert span.total_seconds() == 24 * 3600


def test_health_and_empty(client, tmp_path):
    assert client.get("/api/health").json()["status"] == "ok"
    empty = TestClient(create_app(tmp_path / "e.db", start_scheduler=False, static_dir=None))
    assert empty.get("/api/health").json()["status"] == "empty"
    r = empty.get("/api/forecast")
    assert r.status_code == 503 and "pending" in r.json()["detail"]


def test_metrics(seed, tmp_path):
    csv = tmp_path / "lb.csv"
    csv.write_text(
        "split,target,model,n_own,rmse_own,n_shared,shared_frac,mae,rmse,mbe,nrmse_pct,norm,norm_kind,skill_vs_baseline3,skill_vs_persistence,feature_spec_hash\n"
        "val,rh,baseline3,10,1.5,10,1.0,1,1.5,0.1,2,100,x,,-0.4,abc\n"
    )
    c = TestClient(create_app(seed(), start_scheduler=False, static_dir=None, leaderboard_path=csv))
    row = c.get("/api/metrics").json()["rows"][0]
    assert row["skill_vs_baseline3"] is None and row["n_own"] == 10 and row["rmse"] == 1.5


def test_missing_metrics(client):
    assert client.get("/api/metrics").json() == {"rows": []}


def test_site(client):
    d = client.get("/api/site").json()
    assert d["site"]["display_timezone"] == "Asia/Kolkata" and d["solar"]["dc_kwp"] > 0


def test_static_mount_after_routes(seed, tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<html>hi</html>")
    c = TestClient(create_app(seed(), start_scheduler=False, static_dir=tmp_path / "web"))
    assert c.get("/").text == "<html>hi</html>"
    assert c.get("/api/health").json()["status"] == "ok"


def test_create_app_touches_no_disk(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("db.connect called at create_app")

    monkeypatch.setattr(db, "connect", boom)
    create_app(tmp_path / "x.db", start_scheduler=False, static_dir=None)
    assert not (tmp_path / "x.db").exists()
    assert main.app is not None


def test_import_hygiene(tmp_path):
    code = (
        "import sys, swf.api.main\n"
        "bad=[m for m in sys.modules if m.split('.')[0] in ('torch','darts','matplotlib','lightgbm')"
        " or m.startswith(('swf.evaluate','swf.validate','swf.models'))]\n"
        "assert not bad, bad"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
