from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from swf.api.main import create_app
from swf.api.refresh import refresh


def _down(req):
    raise httpx.ConnectError("down")


@pytest.mark.parametrize("handler", [_down, lambda req: httpx.Response(503)])
def test_outage_serves_cache_flagged_stale(seed, api_env, mock_client, no_sleep, handler):
    db = seed(timedelta(hours=3))
    ok = refresh(db, client=mock_client(handler), sleep=no_sleep, raw_root=api_env.raw,
                 models_root=api_env.models, registry_path=api_env.registry)  # fmt: skip
    assert ok is False and no_sleep.calls
    c = TestClient(create_app(db, start_scheduler=False, static_dir=None))
    d = c.get("/api/forecast").json()
    assert d["stale"] is True and d["age_minutes"] >= 180
    assert all(len(t["points"]) == 72 for t in d["targets"].values())
    assert c.get("/api/health").json()["status"] == "stale"


def test_fresh_not_stale(seed):
    c = TestClient(create_app(seed(timedelta(minutes=30)), start_scheduler=False, static_dir=None))
    assert c.get("/api/forecast").json()["stale"] is False
