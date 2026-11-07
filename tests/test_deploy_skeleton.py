from datetime import UTC, datetime

from fastapi.testclient import TestClient

from swf.api.main import create_app
from swf.api.refresh import refresh

MARKER = "skeleton-page-marker"


def test_skeleton_end_to_end(api_env, live_client, no_sleep, tmp_path):
    ok = refresh(
        api_env.db, client=live_client, sleep=no_sleep, now=datetime(2026, 11, 2, 16, 20, tzinfo=UTC),
        raw_root=api_env.raw, models_root=api_env.models, registry_path=api_env.registry,
    )  # fmt: skip
    assert ok is True
    assert any((api_env.raw / "openmeteo" / "forecast").iterdir())

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(f"<html>{MARKER}</html>")
    client = TestClient(create_app(api_env.db, start_scheduler=False, static_dir=dist))

    r = client.get("/api/forecast")
    assert r.status_code == 200
    d = r.json()
    assert d["stale"] is False
    assert len(d["targets"]) == 5
    for tf in d["targets"].values():
        assert tf["model"] == "baseline3"
        assert len(tf["points"]) == 72
        for p in tf["points"]:
            assert p["time"].endswith("Z")
            if None not in (p["p10"], p["p50"], p["p90"]):
                assert p["p10"] <= p["p50"] <= p["p90"]

    page = client.get("/")
    assert page.status_code == 200 and MARKER in page.text
    assert client.get("/api/health").json()["status"] == "ok"
