import json
from datetime import UTC, datetime

import httpx
import numpy as np
import pandas as pd
import pytest
from synth import make_registry, write_tiny_lgbm

from swf.align.consistency import load_coefs
from swf.api import db
from swf.api.refresh import origin_for, refresh
from swf.core.settings import load_features_cfg
from swf.features.build import serve_features
from swf.features.spec import TARGETS
from swf.fetch import openmeteo as om
from swf.physics.constraints import enforce
from swf.physics.wind import load_power_curve
from swf.predict.baseline import live_tables

NOW = datetime(2026, 11, 2, 16, 20, tzinfo=UTC)
ORIGIN = pd.Timestamp("2026-11-02T15:00Z")


def _run(env, client, sleep, now=NOW):
    return refresh(
        env.db,
        client=client,
        sleep=sleep,
        now=now,
        raw_root=env.raw,
        models_root=env.models,
        registry_path=env.registry,
    )


def _extend(raw: bytes, hours=24) -> bytes:
    d = json.loads(raw)
    h = d["hourly"]
    first = pd.Timestamp(h["time"][0])
    pre = [(first - pd.Timedelta(hours=hours - i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    for k, col in h.items():
        h[k] = (pre if k == "time" else col[:hours]) + col
    return json.dumps(d).encode()


def _client(mock_client, body):
    return mock_client(lambda req: httpx.Response(200, content=body))


def test_origin_for():
    assert origin_for(NOW) == ORIGIN
    assert origin_for(datetime(2026, 11, 2, 0, 30, tzinfo=UTC)) == pd.Timestamp("2026-11-01T23:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        origin_for(datetime(2026, 11, 2, 0, 30))


def test_live_params_past_days(settings):
    assert om.live_params(settings)["past_days"] == 8


def test_naive_now_writes_nothing(api_env, live_client, no_sleep):
    assert _run(api_env, live_client, no_sleep, now=datetime(2026, 11, 2, 16, 20)) is False
    assert not api_env.db.exists() and not api_env.raw.exists() and not live_client.seen


def test_refresh_baseline3(api_env, live_client, live_raw, no_sleep, settings):
    assert _run(api_env, live_client, no_sleep) is True
    run, rows = db.read_forecast(api_env.db, 72)
    assert run == "2026-11-02T15:00:00Z" and len(rows) == 5 * 72
    assert {r["model"] for r in rows} == {"baseline3"}
    assert all(r["p10"] <= r["p50"] <= r["p90"] for r in rows)
    for t in TARGETS:
        tr = [r for r in rows if r["target"] == t]
        assert tr[0]["target_time"] == "2026-11-02T16:00:00Z" and tr[-1]["target_time"] == "2026-11-05T15:00:00Z"
    assert any(r["p50"] == 0.0 for r in rows if r["target"] in ("t1_kw", "ghi"))
    hist = db.read_history(api_env.db, 7)
    assert all(len(hist[t]) == 168 and hist[t][-1][0] == "2026-11-02T15:00:00Z" for t in TARGETS)
    assert "last_success" in db.read_meta(api_env.db)

    # parity with Plan 01 live baseline 3, after enforce
    reg = json.loads(api_env.registry.read_text())
    tab = live_tables(live_raw, settings, load_coefs(), load_power_curve(settings), reg["baseline3_choice"])
    T = ORIGIN + pd.to_timedelta(np.arange(1, 73), unit="h")
    for t in TARGETS:
        exp = enforce(pd.DataFrame({t: tab[t].reindex(T).to_numpy()}, index=T), settings)[t].to_numpy()
        got = np.array([r["p50"] for r in rows if r["target"] == t])
        np.testing.assert_allclose(got, exp, atol=1e-9)


def test_refresh_lightgbm_rh(api_env, live_client, live_raw, no_sleep, settings):
    arts = {"rh": write_tiny_lgbm(api_env.models, "rh", [(1, 6), (7, 24), (25, 72)])}
    reg = make_registry(api_env.registry, lightgbm_artifacts=arts)
    assert _run(api_env, live_client, no_sleep) is True
    _, rows = db.read_forecast(api_env.db, 72)
    assert {r["model"] for r in rows if r["target"] == "rh"} == {"lightgbm"}
    assert {r["model"] for r in rows if r["target"] != "rh"} == {"baseline3"}

    from swf.predict import lgbm

    cfg, coefs, curve = load_features_cfg(), load_coefs(), load_power_curve(settings)
    X = serve_features(live_raw, settings, cfg, coefs, curve, ORIGIN)
    tab = live_tables(live_raw, settings, coefs, curve, reg["baseline3_choice"])
    T = ORIGIN + pd.to_timedelta(X["horizon"].to_numpy().astype(int), unit="h")
    p = lgbm.predict_p50(reg["targets"]["rh"], X, tab["rh"].reindex(T).to_numpy(), "rh", api_env.models)
    exp = enforce(pd.DataFrame({"rh": p}, index=T), settings)["rh"].to_numpy()
    got = np.array([r["p50"] for r in rows if r["target"] == "rh"])
    np.testing.assert_allclose(got, exp, atol=1e-9)


def test_refresh_at_00_utc_needs_past_days_8(api_env, live_raw, mock_client, no_sleep, settings):
    now = datetime(2026, 11, 2, 0, 30, tzinfo=UTC)
    # the 7-day payload covers origin 23:00 with zero spare hours (canon labels shift back 1 h); one hour earlier fails
    args = (settings, load_features_cfg(), load_coefs(), load_power_curve(settings))
    serve_features(live_raw, *args, pd.Timestamp("2026-11-01T23:00Z"))
    with pytest.raises(ValueError, match="history"):
        serve_features(live_raw, *args, pd.Timestamp("2026-11-01T22:00Z"))
    assert _run(api_env, _client(mock_client, _extend(live_raw)), no_sleep, now=now) is True
    assert db.read_forecast(api_env.db, 72)[0] == "2026-11-01T23:00:00Z"


@pytest.mark.parametrize("kind", ["connect", "503"])
def test_outage_keeps_cache(api_env, live_client, mock_client, no_sleep, kind):
    assert _run(api_env, live_client, no_sleep) is True
    before = (db.read_forecast(api_env.db, 72), db.read_meta(api_env.db))

    def handler(req):
        if kind == "connect":
            raise httpx.ConnectError("down", request=req)
        return httpx.Response(503)

    no_sleep.calls.clear()
    later = datetime(2026, 11, 2, 17, 20, tzinfo=UTC)
    assert _run(api_env, mock_client(handler), no_sleep, now=later) is False
    assert no_sleep.calls  # retried, without really sleeping
    assert (db.read_forecast(api_env.db, 72), db.read_meta(api_env.db)) == before


def _lstm_runtimes(arts):
    off = {lab: [-1.0, 1.0] for lab in ("1-6", "7-24", "25-72")}
    return {t: ("lstm", arts, off) for t in TARGETS}


def test_default_registry_path(tmp_path):
    from swf.api.refresh import default_registry_path

    (tmp_path / "registry.json").write_text("{}")
    assert default_registry_path(tmp_path) == tmp_path / "registry.json"
    (tmp_path / "deployed").mkdir()
    (tmp_path / "deployed" / "registry.json").write_text("{}")
    assert default_registry_path(tmp_path) == tmp_path / "deployed" / "registry.json"


def test_refresh_prefers_deployed(api_env, live_client, no_sleep):
    arts = {"rh": write_tiny_lgbm(api_env.models, "rh", [(1, 6), (7, 24), (25, 72)])}
    make_registry(api_env.models / "deployed" / "registry.json", lightgbm_artifacts=arts)
    assert refresh(api_env.db, client=live_client, sleep=no_sleep, now=NOW, raw_root=api_env.raw, models_root=api_env.models)
    _, rows = db.read_forecast(api_env.db, 72)
    assert {r["model"] for r in rows if r["target"] == "rh"} == {"lightgbm"}


def test_refresh_lstm(api_env, live_client, no_sleep):
    pytest.importorskip("torch")
    from synth import write_tiny_lstm

    make_registry(api_env.registry, runtimes=_lstm_runtimes(write_tiny_lstm(api_env.models)))
    assert _run(api_env, live_client, no_sleep) is True
    _, rows = db.read_forecast(api_env.db, 72)
    assert len(rows) == 360 and {r["model"] for r in rows} == {"lstm"}
    assert all(r["p10"] <= r["p50"] <= r["p90"] for r in rows)
    assert any(r["p50"] == 0.0 for r in rows if r["target"] in ("t1_kw", "ghi"))


def test_refresh_tft(api_env, live_client, no_sleep):
    pytest.importorskip("darts")
    from synth import write_tiny_tft

    arts = write_tiny_tft(api_env.models)
    nq = {"method": "native_quantiles"}
    make_registry(api_env.registry, runtimes={t: ("tft", arts, nq) for t in ("rh", "ws10")})
    assert _run(api_env, live_client, no_sleep) is True
    _, rows = db.read_forecast(api_env.db, 72)
    for t in ("rh", "ws10"):
        tr = [r for r in rows if r["target"] == t]
        assert len(tr) == 72 and {r["model"] for r in tr} == {"tft"}
        assert all(r["p10"] <= r["p50"] <= r["p90"] for r in tr)
    assert all(r["p90"] <= 100 for r in rows if r["target"] == "rh")
    assert {r["model"] for r in rows if r["target"] == "ghi"} == {"baseline3"}


def test_no_seq_for_tabular(api_env, live_client, no_sleep, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("serve_sequence called")

    monkeypatch.setattr("swf.api.refresh.serve_sequence", boom)
    assert _run(api_env, live_client, no_sleep) is True
