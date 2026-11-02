import logging

import httpx
import pytest

from swf.fetch.cache import fetch_to_cache, is_cached, safe_part

URL = "https://example.test/api"
BODY = b'{"a": 1,  "b": [1.0, 2]}'


def summ(b):
    return {"rows": 1, "columns": ["a"], "pct_missing": {"a": 0.0}}


class Handler:
    def __init__(self, statuses=(200,)):
        self.statuses = list(statuses)
        self.n = 0

    def __call__(self, request):
        i = min(self.n, len(self.statuses) - 1)
        self.n += 1
        return httpx.Response(self.statuses[i], content=BODY)


def go(client, dest, sleep, **kw):
    return fetch_to_cache(client, URL, {"q": 1}, dest, summarize=summ, sleep=sleep, **kw)


def test_fetch_then_hit(tmp_path, mock_client, no_sleep):
    h = Handler()
    c = mock_client(h)
    dest = tmp_path / "x" / "2001.json"
    assert go(c, dest, no_sleep) == "fetched"
    assert dest.read_bytes() == BODY
    assert is_cached(dest)
    slept = len(no_sleep.calls)
    assert go(c, dest, no_sleep) == "hit"
    assert h.n == 1 and len(no_sleep.calls) == slept


def test_force_refetches(tmp_path, mock_client, no_sleep):
    h = Handler()
    c = mock_client(h)
    dest = tmp_path / "2001.json"
    go(c, dest, no_sleep)
    go(c, dest, no_sleep, force=True)
    assert h.n == 2


def test_missing_sidecar_not_hit(tmp_path, mock_client, no_sleep):
    dest = tmp_path / "2001.json"
    dest.write_bytes(b"partial")
    assert not is_cached(dest)
    h = Handler()
    assert go(mock_client(h), dest, no_sleep) == "fetched"
    assert dest.read_bytes() == BODY


def test_leftover_tmp_not_hit(tmp_path):
    (tmp_path / "2001.json.tmp").write_bytes(b"x")
    assert not is_cached(tmp_path / "2001.json")


def test_429_then_200_backs_off(tmp_path, mock_client, no_sleep):
    h = Handler([429, 200])
    assert go(mock_client(h), tmp_path / "a.json", no_sleep) == "fetched"
    assert h.n == 2
    assert len(no_sleep.calls) == 2 and no_sleep.calls[0] > 0  # backoff, then throttle


def test_503_exhausts(tmp_path, mock_client, no_sleep):
    h = Handler([503])
    dest = tmp_path / "a.json"
    with pytest.raises(httpx.HTTPStatusError):
        go(mock_client(h), dest, no_sleep)
    assert h.n == 6
    assert not dest.exists() and not dest.with_suffix(".meta.json").exists()


def test_422_fails_immediately(tmp_path, mock_client, no_sleep):
    h = Handler([422])
    dest = tmp_path / "a.json"
    with pytest.raises(httpx.HTTPStatusError):
        go(mock_client(h), dest, no_sleep)
    assert h.n == 1
    assert not dest.exists() and not dest.with_suffix(".meta.json").exists()


def test_connect_error_retried(tmp_path, mock_client, no_sleep):
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, content=BODY)

    assert go(mock_client(handler), tmp_path / "a.json", no_sleep) == "fetched"
    assert len(calls) == 2


def test_safe_part():
    assert safe_part("gfs_seamless") == "gfs_seamless"
    for bad in ("../x", "Best Match"):
        with pytest.raises(ValueError):
            safe_part(bad)


def test_log_lines(tmp_path, mock_client, no_sleep, caplog):
    caplog.set_level(logging.INFO, logger="swf.fetch")
    c = mock_client(Handler())
    dest = tmp_path / "a.json"
    go(c, dest, no_sleep)
    go(c, dest, no_sleep)
    msgs = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("fetch ") and "pct_missing" in m and '"url"' in m for m in msgs)
    assert any(m.startswith("cache hit") for m in msgs)
