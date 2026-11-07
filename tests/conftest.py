from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from swf.core.paths import RAW_DIR
from swf.core.settings import load_settings


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def no_sleep():
    def sleep(delay):
        sleep.calls.append(delay)

    sleep.calls = []
    return sleep


@pytest.fixture
def mock_client():
    def make(handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    return make


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def live_raw(fixtures_dir):
    return (fixtures_dir / "om_live_gfs_seamless.json").read_bytes()


@pytest.fixture
def live_client(mock_client, live_raw):
    def handler(req):
        handler.seen.append(req)
        return httpx.Response(200, content=live_raw)

    handler.seen = []
    c = mock_client(handler)
    c.seen = handler.seen
    return c


@pytest.fixture
def api_env(tmp_path):
    from synth import make_registry

    env = SimpleNamespace(
        db=tmp_path / "app.db", raw=tmp_path / "raw", models=tmp_path / "models",
        registry=tmp_path / "models" / "registry.json",
    )  # fmt: skip
    make_registry(env.registry)
    return env


@pytest.fixture
def raw_root():
    if not (RAW_DIR / "nasa").exists():
        pytest.skip("data/raw not present")
    return RAW_DIR


@pytest.fixture
def seed(tmp_path):
    """seed(last_success_age=timedelta(0)) -> db path with a 360-row forecast and 168 h history per target."""
    from datetime import UTC, datetime, timedelta

    from swf.api import db
    from swf.features.spec import TARGETS

    def make(age=timedelta(0)):
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        run = db.iso(now)
        rows = [
            (run, db.iso(now + timedelta(hours=h - 1)), t, "baseline3", 1.0, 2.0 + h % 3, 5.0)
            for t in TARGETS for h in range(1, 73)
        ]  # fmt: skip
        hist = [(db.iso(now - timedelta(hours=h)), t, 1.0) for t in TARGETS for h in range(168)]
        path = tmp_path / "seed.db"
        db.write_run(path, run, rows, hist, db.iso(datetime.now(UTC) - age))
        return path

    return make
