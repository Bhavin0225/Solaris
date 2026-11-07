import json
import threading
from datetime import timedelta

from fastapi.testclient import TestClient

from swf.api.main import create_app
from swf.core.paths import REPO_ROOT


def test_job_registered_and_fires_at_startup(tmp_path):
    ev, got = threading.Event(), {}

    def recorder(db_path):
        got["db_path"] = db_path
        ev.set()

    app = create_app(tmp_path / "s.db", refresh_fn=recorder, static_dir=None)
    with TestClient(app):
        job = app.state.scheduler.get_job("refresh")
        assert job.max_instances == 1 and job.coalesce is True
        assert job.trigger.interval == timedelta(hours=1)
        assert ev.wait(5)
    assert got["db_path"] == tmp_path / "s.db"


def test_cache_served_during_refresh(seed):
    started, release = threading.Event(), threading.Event()

    def blocker(db_path):
        started.set()
        release.wait(10)

    app = create_app(seed(), refresh_fn=blocker, static_dir=None)
    try:
        with TestClient(app) as c:
            assert started.wait(5)
            r = c.get("/api/forecast")
            assert r.status_code == 200
            assert all(len(t["points"]) == 72 for t in r.json()["targets"].values())
            release.set()
    finally:
        release.set()


def test_openapi_published():
    """Regenerate: .venv/Scripts/python -c "import json; from swf.api.main import create_app;
    open('docs/openapi.json','w',newline='\\n').write(json.dumps(create_app(start_scheduler=False,
    static_dir=None).openapi(), indent=2, sort_keys=True)+'\\n')"
    """
    live = create_app(start_scheduler=False, static_dir=None).openapi()
    pub = json.loads((REPO_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    assert pub == live
    for p in ("health", "forecast", "forecast/summary", "history", "metrics", "site"):
        assert f"/api/{p}" in pub["paths"]
