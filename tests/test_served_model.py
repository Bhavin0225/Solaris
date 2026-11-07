from datetime import UTC, datetime

from fastapi.testclient import TestClient

from swf.api.main import create_app
from swf.api.refresh import refresh
from swf.core.paths import MODELS_DIR
from swf.features.spec import TARGETS
from swf.predict.registry import load_registry


def test_committed_registry_serves_baseline3(api_env, live_client, no_sleep):
    reg = load_registry()
    assert all(reg["targets"][t]["runtime"] == "baseline3" for t in TARGETS)
    ok = refresh(api_env.db, client=live_client, sleep=no_sleep, now=datetime(2026, 11, 2, 16, 20, tzinfo=UTC),
                 raw_root=api_env.raw, models_root=MODELS_DIR, registry_path=MODELS_DIR / "registry.json")  # fmt: skip
    assert ok is True
    d = TestClient(create_app(api_env.db, start_scheduler=False, static_dir=None)).get("/api/forecast").json()
    assert set(d["targets"]) == set(TARGETS)
    for t, tf in d["targets"].items():
        assert tf["model"] == "baseline3" and len(tf["points"]) == 72
