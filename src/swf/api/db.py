"""SQLite WAL forecast cache (API-03). One short-lived connection per call; only the latest run is kept."""

import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast(
    run_time TEXT NOT NULL, target_time TEXT NOT NULL, target TEXT NOT NULL, model TEXT NOT NULL, p10 REAL, p50 REAL, p90 REAL,
    PRIMARY KEY (run_time, target, target_time));
CREATE TABLE IF NOT EXISTS history(
    time TEXT NOT NULL, target TEXT NOT NULL, value REAL, PRIMARY KEY (target, time));
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn


def iso(ts) -> str:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _nan_to_none(row: tuple) -> tuple:
    return tuple(None if isinstance(v, float) and math.isnan(v) else v for v in row)


def write_run(path, run_time: str, rows: list[tuple], history: list[tuple], last_success: str) -> None:
    with (
        closing(connect(path)) as conn,
        conn,
    ):  # one transaction: commit on success, rollback on error
        conn.execute("DELETE FROM forecast")
        conn.executemany(
            "INSERT INTO forecast VALUES (?,?,?,?,?,?,?)",
            [_nan_to_none(r) for r in rows],
        )
        conn.execute("DELETE FROM history")
        conn.executemany("INSERT INTO history VALUES (?,?,?)", [_nan_to_none(r) for r in history])
        conn.executemany(
            "INSERT OR REPLACE INTO meta VALUES (?,?)",
            [("last_success", last_success), ("run_time", run_time)],
        )


def read_meta(path) -> dict[str, str]:
    with closing(connect(path)) as conn:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def read_forecast(path, hours: int) -> tuple[str | None, list[dict]]:
    run_time = read_meta(path).get("run_time")
    if run_time is None:
        return None, []
    with closing(connect(path)) as conn:
        cur = conn.execute(
            "SELECT target, target_time, model, p10, p50, p90 FROM forecast WHERE run_time = ? ORDER BY target, target_time",
            (run_time,),
        )
        cols = [c[0] for c in cur.description]
        seen: dict[str, int] = defaultdict(int)
        out = []
        for r in cur:
            seen[r[0]] += 1
            if seen[r[0]] <= hours:
                out.append(dict(zip(cols, r)))
    return run_time, out


def read_history(path, days: int) -> dict[str, list[tuple[str, float | None]]]:
    with closing(connect(path)) as conn:
        rows = conn.execute("SELECT target, time, value FROM history ORDER BY target, time").fetchall()
    by: dict[str, list] = defaultdict(list)
    for t, ts, v in rows:
        by[t].append((ts, v))
    return {t: v[-days * 24 :] for t, v in by.items()}
