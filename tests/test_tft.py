"""TFT rung: per-origin series, quantile runtime, D-27 projection, D-19 stop (tiny CPU models)."""

import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("darts")
from synth import tiny_tft_inputs, write_tiny_tft  # noqa: E402

from swf.evaluate.longfmt import TARGETS  # noqa: E402
from swf.features.build import DEC_COLS  # noqa: E402


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    root = tmp_path_factory.mktemp("tft")
    return root, {"artifacts": write_tiny_tft(root)}


def _meta():
    from synth import tiny_tft_norm

    return {"targets": list(TARGETS), "dec_feature_cols": DEC_COLS, "norm": tiny_tft_norm(), "encoder_hours": 168}


def test_origin_inputs_spans():
    from swf.predict.tft import origin_inputs

    nc = len(DEC_COLS) + 5
    o = pd.date_range("2025-03-01", periods=2, freq="D", tz="UTC")
    s, c = origin_inputs(_meta(), np.zeros((2, 168, 5)), np.zeros((2, 168, nc)), np.zeros((2, 72, nc)), o)
    assert s[0].end_time() == o[0].tz_localize(None) and len(s[0]) == 168
    assert c[0].end_time() == o[0].tz_localize(None) + pd.Timedelta(hours=72) and c[0].n_components == 29
    assert c[0].start_time() == s[0].start_time()


def test_quantiles_shape_sorted(tiny):
    from swf.predict.tft import _load, quantiles

    root, entry = tiny
    p = root / "tft" / "tft.pt"
    model, meta = _load(str(p), p.stat().st_mtime_ns)
    s, c = tiny_tft_inputs(n=3)
    q = quantiles(model, meta, [x[:168] for x in s], c, 2)
    assert q.shape == (3, 72, 5, 3) and np.isfinite(q).all()
    assert (np.diff(q, axis=-1) >= 0).all()


def test_component_names(tiny):
    root, _ = tiny
    from swf.predict.tft import _load

    p = root / "tft" / "tft.pt"
    model, meta = _load(str(p), p.stat().st_mtime_ns)
    s, c = tiny_tft_inputs(n=1)
    pr = model.predict(n=72, series=[s[0][:168]], future_covariates=c, predict_likelihood_parameters=True)
    comps = list(pr[0].components if isinstance(pr, list) else pr.components)
    print("DARTS_COMPONENTS", comps)
    assert comps == [f"{t}_q{q}" for t in TARGETS for q in ("0.100", "0.500", "0.900")]


def test_predict_quantiles_cached(tiny, monkeypatch):
    import swf.predict.tft as m

    root, entry = tiny
    p = root / "tft" / "tft.pt"
    model, _ = m._load(str(p), p.stat().st_mtime_ns)
    calls = []
    real = model.predict
    monkeypatch.setattr(model, "predict", lambda *a, **k: calls.append(1) or real(*a, **k), raising=False)
    origin = pd.Timestamp("2025-06-01", tz="UTC")
    idx = pd.MultiIndex.from_arrays([[origin] * 72, np.arange(1, 73)], names=["issue_time", "horizon"])
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(72, len(DEC_COLS))), columns=DEC_COLS, index=idx)
    X["horizon"] = np.arange(1, 73)
    full = pd.date_range(origin - pd.Timedelta(hours=200), origin + pd.Timedelta(hours=80), freq="h")
    X.attrs["seq"] = {
        "enc": pd.DataFrame(rng.normal(size=(168, len(DEC_COLS) + 5)), columns=list(TARGETS) + DEC_COLS[: len(DEC_COLS)]),
        "b3": pd.DataFrame(1.0, index=full, columns=list(TARGETS)),
    }
    for t in TARGETS:
        p10, p50, p90 = m.predict_quantiles(entry, X, t, root)
        assert p50.shape == (72,) and (p10 <= p50).all() and (p50 <= p90).all()
    assert len(calls) == 1
    with pytest.raises(ValueError):
        m.predict_quantiles(entry, pd.DataFrame(X.to_numpy(), columns=X.columns, index=X.index), "rh", root)


def test_tft_import_light():
    code = "import sys, swf.predict.tft, swf.predict.registry; assert 'darts' not in sys.modules and 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
