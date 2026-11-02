"""Single cached-fetch primitive: verbatim bytes + sidecar meta, atomic, throttled, retried (D-10..D-12)."""

import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from swf import __version__

logger = logging.getLogger("swf.fetch")

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def make_client(timeout: float = 120.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": f"swf/{__version__} (student project)"})


def safe_part(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError(f"unsafe path part {name!r}")
    return name


def _meta_path(dest: Path) -> Path:
    return dest.with_suffix(".meta.json")


def is_cached(dest: Path) -> bool:
    """Sidecar is the commit marker: a hit needs a sidecar whose sha256 matches the data bytes."""
    meta = _meta_path(dest)
    if not (dest.exists() and meta.exists()):
        return False
    try:
        want = json.loads(meta.read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError):
        return False
    return want == hashlib.sha256(dest.read_bytes()).hexdigest()


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 429 and "daily" in exc.response.text.lower():
            return False  # daily quota will not reset within a retry window
        return exc.response.status_code in RETRY_STATUS
    return isinstance(exc, httpx.TransportError)


_backoff = wait_exponential(multiplier=2, max=60)


def _wait(retry_state) -> float:
    """Exponential backoff, but honour a numeric Retry-After header (capped at 5 min)."""
    delay = _backoff(retry_state)
    exc = retry_state.outcome.exception()
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return min(max(delay, float(exc.response.headers["Retry-After"])), 300.0)
        except (KeyError, ValueError):
            pass
    return delay


def fetch_to_cache(
    client: httpx.Client,
    url: str,
    params: dict,
    dest: Path,
    *,
    summarize: Callable[[bytes], dict],
    force: bool = False,
    min_interval: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    if is_cached(dest) and not force:
        logger.info("cache hit %s", dest)
        return "hit"

    @retry(
        retry=retry_if_exception(_retryable),
        wait=_wait,
        stop=stop_after_attempt(6),
        sleep=sleep,
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _get() -> httpx.Response:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp

    resp = _get()
    content = resp.content  # verbatim bytes, never re-serialised
    summary = summarize(content)
    meta = {
        "url": str(resp.request.url),
        "params": params,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": resp.status_code,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "swf_version": __version__,
        "force": force,
        **summary,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta_dest = _meta_path(dest)
    meta_dest.unlink(missing_ok=True)  # un-commit first: a crash before the new sidecar means "not cached"
    tmp, meta_tmp = dest.with_suffix(".json.tmp"), meta_dest.with_suffix(".json.tmp")
    tmp.write_bytes(content)
    meta_tmp.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, dest)
    os.replace(meta_tmp, meta_dest)  # sidecar last = commit marker
    logger.info(
        "fetch %s",
        json.dumps(
            {
                "url": meta["url"],
                "status": resp.status_code,
                "rows": summary.get("rows"),
                "pct_missing": summary.get("pct_missing"),
            }
        ),
    )
    sleep(min_interval)
    return "fetched"
