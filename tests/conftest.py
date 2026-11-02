from pathlib import Path

import httpx
import pytest

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
