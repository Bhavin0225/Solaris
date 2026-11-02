import hashlib
import json

import httpx

from swf.fetch.cache import fetch_to_cache


def test_sidecar_contents(tmp_path, mock_client, no_sleep):
    body = b'{"x":  [1, 2]}'
    c = mock_client(lambda r: httpx.Response(200, content=body))
    dest = tmp_path / "2001.json"
    fetch_to_cache(
        c, "https://example.test/api", {"q": 1}, dest,
        summarize=lambda b: {"rows": 3, "columns": ["a"], "pct_missing": {"a": 0.0}},
        min_interval=1.5, sleep=no_sleep,
    )
    meta = json.loads(dest.with_suffix(".meta.json").read_text())
    assert set(meta) == {
        "url", "params", "retrieved_utc", "http_status", "bytes", "sha256",
        "swf_version", "force", "rows", "columns", "pct_missing",
    }
    assert meta["url"].endswith("?q=1") and meta["http_status"] == 200
    assert meta["bytes"] == len(body)
    assert meta["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert meta["retrieved_utc"].endswith("Z")
    assert no_sleep.calls == [1.5]
