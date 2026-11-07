import math
import sqlite3
from contextlib import closing

import pandas as pd
import pytest

from swf.api import db
from swf.features.spec import TARGETS

RUN1 = "2026-11-02T15:00:00Z"
RUN2 = "2026-11-02T16:00:00Z"


def _rows(run, base=0.0, n=72, targets=TARGETS):
    t0 = pd.Timestamp(run)
    return [
        (
            run,
            db.iso(t0 + pd.Timedelta(hours=h)),
            t,
            "baseline3",
            base - 1,
            base,
            base + 1,
        )
        for t in targets
        for h in range(1, n + 1)
    ]


def _hist(n=200):
    t0 = pd.Timestamp(RUN1) - pd.Timedelta(hours=n - 1)
    return [(db.iso(t0 + pd.Timedelta(hours=i)), t, float(i)) for t in TARGETS for i in range(n)]


def test_connect_wal_and_empty(tmp_path):
    p = tmp_path / "sub" / "app.db"
    with closing(db.connect(p)) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert db.read_forecast(p, 72) == (None, [])
    assert db.read_meta(p) == {}


def test_roundtrip_replace_and_limits(tmp_path):
    p = tmp_path / "app.db"
    rows = _rows(RUN1)
    rows[0] = (*rows[0][:4], math.nan, math.nan, math.nan)
    db.write_run(p, RUN1, rows, _hist(), "ok1")
    run, got = db.read_forecast(p, 72)
    assert run == RUN1 and len(got) == 360
    assert [g["target"] for g in got] == sorted(g["target"] for g in got)
    first = [g for g in got if g["target"] == rows[0][2]][0]
    assert first["p50"] is None and first["target_time"].endswith("Z")
    assert len(db.read_forecast(p, 6)[1]) == 6 * len(TARGETS)
    hist = db.read_history(p, 2)
    assert all(len(v) == 48 for v in hist.values()) and set(hist) == set(TARGETS)

    db.write_run(p, RUN2, _rows(RUN2, 5.0), _hist(), "ok2")
    run, got = db.read_forecast(p, 72)
    assert run == RUN2 and len(got) == 360 and all(g["p50"] == 5.0 for g in got)
    assert db.read_meta(p) == {"last_success": "ok2", "run_time": RUN2}


def test_rollback_keeps_previous_run(tmp_path):
    p = tmp_path / "app.db"
    db.write_run(p, RUN1, _rows(RUN1), _hist(), "ok1")
    bad = _rows(RUN2) + [(RUN2, "x", "y", "m", 0, 0, 0, 0)]  # 8 values -> sqlite binding error after the DELETE
    with pytest.raises(sqlite3.Error):
        db.write_run(p, RUN2, bad, _hist(), "ok2")
    run, got = db.read_forecast(p, 72)
    assert run == RUN1 and len(got) == 360
    assert db.read_meta(p)["last_success"] == "ok1"


def test_injection_string_is_data(tmp_path):
    p = tmp_path / "app.db"
    evil = "x'); DROP TABLE forecast;--"
    db.write_run(
        p,
        RUN1,
        [(RUN1, RUN1, evil, "baseline3", 0.0, 1.0, 2.0)],
        [(RUN1, evil, 1.0)],
        "ok",
    )
    assert db.read_forecast(p, 72)[1][0]["target"] == evil
    assert db.read_history(p, 1)[evil] == [(RUN1, 1.0)]


def test_iso_rejects_naive():
    with pytest.raises(ValueError):
        db.iso(pd.Timestamp("2026-11-02"))
