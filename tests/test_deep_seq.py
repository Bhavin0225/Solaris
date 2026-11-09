"""Deep-model sequence windows: shapes, no look-ahead, decoder = assemble, and train/serve parity."""

import shutil

import numpy as np
import pandas as pd
import pytest
from synth import pr_trio, seq_inputs

from swf.align.adapters import load_source
from swf.align.clean import clean
from swf.align.consistency import load_coefs
from swf.core.settings import load_features_cfg
from swf.features.build import (
    DEC_COLS,
    SEQ_COLS,
    assemble,
    covariate_table,
    decoder_windows,
    encoder_windows,
    history_input,
    origin_table,
    sequence_table,
    serve_sequence,
    target_table,
)
from swf.features.history import history_frame
from swf.physics.wind import load_power_curve

FIXTURE = "om_live_gfs_seamless"
START = "2024-03-01"


@pytest.fixture
def tab(settings):
    hist, cov, ttab = seq_inputs(START, 14, settings)
    return sequence_table(hist, cov, ttab)


def test_encoder_shapes(tab):
    o = tab.index[[200, 250]]
    w = encoder_windows(tab, o, 168)
    assert w.shape == (2, 168, len(SEQ_COLS)) and w.dtype == np.float32
    np.testing.assert_array_equal(w[0, -1], tab.loc[o[0]].to_numpy(np.float32))
    np.testing.assert_array_equal(w[0, 0], tab.loc[o[0] - pd.Timedelta(hours=167)].to_numpy(np.float32))


def test_no_lookahead(tab):
    o = tab.index[[200]]
    before = encoder_windows(tab, o, 168)
    t2 = tab.copy()
    t2.iloc[201:] = 999.0
    np.testing.assert_array_equal(before, encoder_windows(t2, o, 168))


def test_gather_miss_raises(tab):
    with pytest.raises(ValueError):
        encoder_windows(tab, [tab.index[100]], 168)  # < 168 h before
    with pytest.raises(ValueError):
        encoder_windows(tab, [tab.index[-1] + pd.Timedelta(hours=5)], 168)  # absent


def test_decoder_matches_assemble(settings):
    cfg = load_features_cfg()
    hist, cov, ttab = seq_inputs(START, 14, settings)
    otab = origin_table(hist, cfg, settings)
    trio = {k: covariate_table(c, settings, load_coefs(), cfg) for k, c in pr_trio(START, 14, settings).items()}
    origins = hist.index[[200, 210]]
    for c in (cov, trio):
        want = assemble(otab, ttab, origins, range(1, 73), cov=c, cfg=cfg)[DEC_COLS].to_numpy(np.float32)
        got = decoder_windows(otab, ttab, origins, 72, c, cfg, chunk=1)
        assert got.shape == (2, 72, len(DEC_COLS))
        np.testing.assert_array_equal(got.reshape(-1, len(DEC_COLS)), want)


def test_serve_parity(settings, fixtures_dir, tmp_path):
    s, cfg, coefs, curve = settings, load_features_cfg(), load_coefs(), load_power_curve(settings)
    dst = tmp_path / "openmeteo/archive" / s.data.openmeteo.era5_model
    dst.mkdir(parents=True)
    shutil.copy(fixtures_dir / f"{FIXTURE}.json", dst / "2026.json")
    shutil.copy(fixtures_dir / f"{FIXTURE}.meta.json", dst / "2026.meta.json")
    om = s.data.openmeteo.model_copy(update={"era5_years": (2026, 2026)})
    s_tmp = s.model_copy(update={"data": s.data.model_copy(update={"openmeteo": om})})

    raw_bytes = (fixtures_dir / f"{FIXTURE}.json").read_bytes()
    raw_train = load_source("era5", s_tmp, raw_root=tmp_path)
    canon_train = clean(raw_train, s, source="era5")[0]
    tab = sequence_table(
        history_frame(history_input(raw_train, s), s, curve, coefs),
        covariate_table(canon_train, s, coefs, cfg),
        target_table(canon_train.index, cfg, s),
    )
    lo = canon_train.index[0] + pd.Timedelta(hours=max(cfg.lags))
    hi = canon_train.index[-1] - pd.Timedelta(hours=cfg.horizon_max)
    valid = pd.date_range(lo, hi, freq="h")
    assert len(valid) == 24
    for t in valid:
        served = serve_sequence(raw_bytes, s, cfg, coefs, curve, t, 168)
        assert list(served.columns) == SEQ_COLS
        np.testing.assert_array_equal(served.to_numpy(), encoder_windows(tab, [t], 168)[0])


def _tiny_inputs(n=3):
    from swf.evaluate.longfmt import TARGETS

    rng = np.random.default_rng(0)
    enc = rng.normal(size=(n, 168, len(SEQ_COLS))).astype("float32")
    dec = rng.normal(size=(n, 72, len(DEC_COLS))).astype("float32")
    b3 = rng.normal(size=(n, 72, len(TARGETS))).astype("float32")
    return enc, dec, b3


def test_net_shapes():
    pytest.importorskip("torch")
    import torch
    from synth import tiny_lstm_hp

    from swf.predict.lstm import build_net

    for rnn in ("lstm", "gru"):
        net = build_net(tiny_lstm_hp(rnn), 34, 29, 5)
        out = net(torch.zeros(2, 168, 34), torch.zeros(2, 72, 29))
        assert tuple(out.shape) == (2, 72, 5)


def test_residual_identity(tmp_path):
    pytest.importorskip("torch")
    from synth import write_tiny_lstm

    from swf.predict.lstm import _load, forecast

    rel = write_tiny_lstm(tmp_path)["model"]
    net, meta = _load(str(tmp_path / rel), 0)
    net.head.weight.data.zero_()
    net.head.bias.data.zero_()
    enc, dec, b3 = _tiny_inputs()
    np.testing.assert_allclose(forecast(net, meta, enc, dec, b3), b3.astype("float64"))


def test_checkpoint_roundtrip_weights_only(tmp_path):
    pytest.importorskip("torch")
    import torch
    from synth import write_tiny_lstm

    from swf.predict.lstm import _load, forecast

    rel = write_tiny_lstm(tmp_path)["model"]
    p = tmp_path / rel
    sd = torch.load(p, weights_only=True)
    assert isinstance(sd, dict)
    net, meta = _load(str(p), p.stat().st_mtime_ns)
    enc, dec, b3 = _tiny_inputs()
    a = forecast(net, meta, enc, dec, b3)
    net2, _ = _load(str(p), p.stat().st_mtime_ns + 1)
    np.testing.assert_array_equal(a, forecast(net2, meta, enc, dec, b3))


def _serve_X(n_origin=1):
    from swf.evaluate.longfmt import TARGETS

    enc, dec, b3 = _tiny_inputs(1)
    origin = pd.Timestamp("2025-06-01", tz="UTC")
    T = origin + pd.to_timedelta(np.arange(1, 73), unit="h")
    idx = pd.MultiIndex.from_arrays([[origin] * 72, np.arange(1, 73)], names=["issue_time", "horizon"])
    X = pd.DataFrame(dec[0], columns=DEC_COLS, index=idx)
    X["horizon"] = np.arange(1, 73)
    full = pd.date_range(origin - pd.Timedelta(hours=200), origin + pd.Timedelta(hours=80), freq="h")
    X.attrs["seq"] = {
        "enc": pd.DataFrame(enc[0], columns=SEQ_COLS),
        "b3": pd.DataFrame(1.0, index=full, columns=list(TARGETS)),
    }
    return X


def test_predict_p50_cached(tmp_path, monkeypatch):
    from swf.evaluate.longfmt import TARGETS

    pytest.importorskip("torch")
    from synth import write_tiny_lstm

    import swf.predict.lstm as m

    entry = {"artifacts": write_tiny_lstm(tmp_path)}
    calls = []
    real = m.forecast
    monkeypatch.setattr(m, "forecast", lambda *a, **k: calls.append(1) or real(*a, **k))
    X = _serve_X()
    for t in TARGETS:
        assert m.predict_p50(entry, X, None, t, tmp_path).shape == (72,)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        m.predict_p50(entry, pd.DataFrame(X.to_numpy(), columns=X.columns, index=X.index), None, "rh", tmp_path)  # no attrs


def test_lstm_spec_mismatch(tmp_path):
    pytest.importorskip("torch")
    import json

    from synth import write_tiny_lstm

    from swf.predict.lstm import _load

    rel = write_tiny_lstm(tmp_path)["model"]
    side = (tmp_path / rel).with_suffix(".json")
    meta = json.loads(side.read_text())
    meta["feature_spec_hash"] = "bad"
    side.write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        _load(str(tmp_path / rel), 1)


def test_lstm_import_light():
    import subprocess
    import sys

    code = "import sys, swf.predict.lstm, swf.predict.registry; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def _tiny_windows(settings, n_fit=24, n_es=8):
    from swf.evaluate.longfmt import TARGETS
    from swf.models import seq

    cfg = load_features_cfg()
    hist, cov, ttab = seq_inputs(START, 14, settings)
    otab = origin_table(hist, cfg, settings)
    tab = sequence_table(hist, cov, ttab)
    rng = np.random.default_rng(1)
    truth = pd.DataFrame(rng.normal(size=(len(hist), len(TARGETS))), index=hist.index, columns=list(TARGETS))
    b3 = pd.DataFrame(rng.normal(size=(len(hist), len(TARGETS))), index=hist.index, columns=list(TARGETS))
    choice = dict.fromkeys(TARGETS, "corrected")
    o = hist.index[200 : 200 + n_fit + n_es]
    mk = lambda og: seq.windows(tab, otab, ttab, og, cov, ({"corrected": b3}, choice), truth, cfg, 168)  # noqa: E731
    return mk(o[:n_fit]), mk(o[n_fit:])


def _tiny_meta(w):
    from synth import tiny_lstm_hp

    from swf.evaluate.longfmt import TARGETS
    from swf.models import seq

    return {"enc_cols": SEQ_COLS, "dec_feature_cols": DEC_COLS, "targets": list(TARGETS), "hp": tiny_lstm_hp("lstm", 8)} | seq.fit_norm(w, SEQ_COLS, TARGETS)


def _lc(**kw):
    from swf.core.settings import load_deep_cfg

    return load_deep_cfg().lstm.model_copy(update={"hidden": 8, "layers": 2, "dropout": 0.0, "batch_size": 64, "lr": 0.01, "device": "cpu"} | kw)


def test_windows_shapes(settings):
    pytest.importorskip("torch")
    wf, we = _tiny_windows(settings)
    assert wf["enc"].shape == (24, 168, len(SEQ_COLS)) and wf["dec"].shape == (24, 72, len(DEC_COLS))
    assert wf["b3"].shape == wf["y"].shape == (24, 72, 5)


def test_train_lowers_loss(settings):
    pytest.importorskip("torch")
    from swf.models import seq

    wf, we = _tiny_windows(settings)
    wf["y"][0, 0, 0] = np.nan  # NaN target is masked, never reaches the loss
    meta = _tiny_meta(wf)
    state, hist, best = seq.train(wf, we, meta, _lc(max_epochs=3, patience=3), 0, "cpu")
    assert len(hist["train_loss"]) == len(hist["es_loss"]) == 3 and best >= 1
    assert np.isfinite(hist["train_loss"]).all() and hist["train_loss"][-1] < hist["train_loss"][0]
    assert hist["stop_reason"] is None and isinstance(state, dict)


def test_es_origins_before_val():
    from swf.features.splits import origins_for
    from swf.models.lgbm import split_fit_es

    cfg = load_features_cfg()
    from swf.core.settings import load_lgbm_cfg

    fit, es = split_fit_es(origins_for("train_covariate", cfg), load_lgbm_cfg().es_tail_start, 72)
    fit, es = fit[::3], es[::3]
    lim = pd.Timestamp(cfg.splits.val[0])
    assert fit.max() + pd.Timedelta(hours=72) < lim and es.max() + pd.Timedelta(hours=72) < lim
    assert fit.max() + pd.Timedelta(hours=72) < es.min() + pd.Timedelta(hours=72)


def test_deadline_minimal(settings, monkeypatch):
    pytest.importorskip("torch")
    from datetime import UTC, datetime

    from swf.models import seq

    wf, we = _tiny_windows(settings)
    meta = _tiny_meta(wf)
    past = datetime(2000, 1, 1, tzinfo=UTC)
    state, hist, best = seq.train(wf, we, meta, _lc(max_epochs=5, patience=5), 0, "cpu", deadline=past)
    assert best == 1 and "D-18" in hist["stop_reason"] and len(hist["es_loss"]) == 1

    real, n = seq._masked_mse, {"c": 0}

    def poisoned(p, t, m):  # 1 train + 1 es call per epoch: calls 9+ are epoch 5 on
        n["c"] += 1
        out = real(p, t, m)
        return out * float("nan") if n["c"] > 8 else out

    monkeypatch.setattr(seq, "_masked_mse", poisoned)
    state, hist, best = seq.train(wf, we, meta, _lc(max_epochs=20, patience=20), 0, "cpu")
    assert "non-finite" in hist["stop_reason"] and best >= 1 and len(hist["es_loss"]) == 4
