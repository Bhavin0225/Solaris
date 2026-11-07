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
