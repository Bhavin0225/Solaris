"""TFT rung: per-origin series, quantile runtime, D-27 projection, D-19 stop (tiny CPU models)."""

import json
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


# ---- trainer (models/tft.py) ----
from argparse import Namespace  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

HS = datetime(2026, 11, 11, 18, 30, tzinfo=UTC)


def _dcfg(**kw):
    from swf.core.settings import load_deep_cfg

    d = load_deep_cfg()
    t = d.tft.model_copy(update={"accelerator": "cpu", "hidden_size": 4, "lstm_layers": 1, "attention_heads": 1,
                                 "batch_size": 4, "max_epochs": 5, "hard_stop_utc": HS, "timing_origins": 2,
                                 "chunk_origins": 2, "predict_batch_size": 2, "explain_background": 2} | kw)  # fmt: skip
    return d.model_copy(update={"tft": t})


def _tiny_inputs():
    s, c = tiny_tft_inputs(n=4)
    ps = [x[:168] for x in s[:2]]
    return {"meta": _meta(), "fit": (s, c), "es": (s[:2], c[:2]), "pred": (ps, c[:2]), "n_origins": 100,
            "T": None}  # fmt: skip


def test_train_series_d26():
    from swf.features.build import SEQ_COLS
    from swf.models import tft

    idx = pd.date_range("2025-01-01", periods=600, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    tab = pd.DataFrame(rng.normal(size=(600, len(SEQ_COLS))), index=idx, columns=SEQ_COLS).astype("float32")
    truth = tab[list(TARGETS)] + 5.0
    B = pd.DataFrame(1.0, index=idx, columns=list(TARGETS))
    o = idx[200:203]
    truth.loc[o[2] + pd.Timedelta(hours=72), "rh"] = np.nan
    raw = tft.train_raw(tab, B, truth, np.zeros((3, 72, len(DEC_COLS)), "float32"), o, 168, 72)
    assert raw["n_dropped"] == 1 and len(raw["origins"]) == 2
    s, c = tft.train_series(raw, _meta())
    v = s[0].values()
    np.testing.assert_allclose(v[:168], tab[list(TARGETS)].loc[o[0] - pd.Timedelta(hours=167) : o[0]].to_numpy(), atol=1e-5)
    np.testing.assert_allclose(v[168:], truth.loc[o[0] + pd.Timedelta(hours=1) : o[0] + pd.Timedelta(hours=72)].to_numpy(), atol=1e-5)
    assert len(c[0]) == 240


def test_project():
    from swf.models.tft import project

    now = HS - timedelta(hours=100)
    p = project(60, 0.01, 30, 17520, now, HS)
    assert p["fit_hours"] == pytest.approx(0.5) and p["predict_hours"] == pytest.approx(0.01 * 17520 / 3600)
    assert p["projected_hours"] == pytest.approx(p["fit_hours"] + p["predict_hours"]) and p["fits_before_stop"]
    assert not project(3600, 0.01, 200, 17520, now, HS)["fits_before_stop"]


def test_run_refuses_past_hard_stop(tmp_path):
    from swf.models import tft

    rc = tft.run(Namespace(stop=False, timing_only=False), models_root=tmp_path, dcfg=_dcfg(),
                 clock=lambda: HS + timedelta(seconds=1))  # fmt: skip
    assert rc == 3 and not (tmp_path / "tft" / "tft.pt").exists()


def test_project_without_hard_stop():
    from swf.models.tft import project

    p = project(60, 0.01, 30, 100, HS, None)
    assert p["fits_before_stop"] is True and p["hard_stop_utc"] is None


def test_hard_stop_callback_none_never_stops():
    from swf.models import tft

    cb = tft.hard_stop_callback(None, 50, lambda: HS + timedelta(days=999))
    cb.on_train_batch_end(type("T", (), {"current_epoch": 0})(), None, None, None, 49)
    assert cb.reason is None


def test_run_no_hard_stop_gate(tmp_path):
    from swf.models import tft

    # no timing.json: with the deadline off the clock gate is skipped and run reaches the timing gate (rc 1), not 3
    rc = tft.run(Namespace(stop=False, timing_only=False), models_root=tmp_path, dcfg=_dcfg(hard_stop_utc=None),
                 clock=lambda: HS + timedelta(days=999))  # fmt: skip
    assert rc == 1


def test_run_refuses_bad_projection(tmp_path):
    from swf.models import tft

    (tmp_path / "tft").mkdir()
    (tmp_path / "tft" / "timing.json").write_text(json.dumps(tft.project(3600, 1, 100, 17520, HS - timedelta(hours=1), HS)))
    rc = tft.run(Namespace(stop=False, timing_only=False), models_root=tmp_path, dcfg=_dcfg(), clock=lambda: HS - timedelta(hours=1))
    assert rc == 3 and not (tmp_path / "tft" / "tft.pt").exists()


def test_write_stop(tmp_path):
    from swf.models import tft

    n = tmp_path / "notes.md"
    tft.write_stop("hard stop X reached", tft.project(1, 1, 1, 1, HS - timedelta(hours=2), HS), None, n)
    t = n.read_text()
    assert "stopped" in t and "hard stop X reached" in t and "fit_hours" in t


def test_fit_tiny_cpu(tmp_path):
    from swf.models import tft

    cb = tft.hard_stop_callback(HS, 50, lambda: HS - timedelta(days=1))
    model = tft.fit(_tiny_inputs(), _dcfg(), tmp_path, 2, "run", cb, best=True)
    assert model is not None and cb.reason is None
    tft.scrub(model).save(str(tmp_path / "tft" / "tft.pt"))  # served artifact must load without our callback class
    from swf.predict.tft import quantiles
    from darts.models import TFTModel

    m2 = TFTModel.load(str(tmp_path / "tft" / "tft.pt"), map_location="cpu")
    s, c = _tiny_inputs()["fit"]
    assert quantiles(m2, _meta(), [x[:168] for x in s[:1]], c[:1], 1).shape == (1, 72, 5, 3)
    tbl = tft.curves(tmp_path / "tft" / "logs", tmp_path)
    assert {"train_loss", "val_loss"} <= set(tbl.columns) and len(tbl) == 2 and np.isfinite(tbl["val_loss"]).all()
    from swf.core.settings import load_lgbm_cfg
    from swf.features.splits import origins_for
    from swf.models.lgbm import split_fit_es

    fit_o, es_o = split_fit_es(origins_for("train_covariate"), load_lgbm_cfg().es_tail_start, 72)
    tail = pd.Timestamp(load_lgbm_cfg().es_tail_start)
    assert (es_o >= tail).all() and (fit_o + pd.Timedelta(hours=72) < tail).all()


def test_explain_tiny(tmp_path):
    from swf.models import tft

    cb = tft.hard_stop_callback(HS, 50, lambda: HS - timedelta(days=1))
    inp = _tiny_inputs()
    model = tft.fit(inp, _dcfg(), tmp_path, 1, "run", cb)
    tbl = tft.explain(model, inp["fit"][0], inp["fit"][1], tmp_path, 2)
    assert {"block", "feature", "importance"} == set(tbl.columns) and len(tbl) > 0
    assert (tmp_path / "tft_variable_selection.png").exists() and (tmp_path / "tft_variable_selection.csv").exists()


def test_hard_stop_callback_halts(tmp_path):
    from swf.models import tft

    calls = []

    def clock():
        calls.append(1)
        return HS - timedelta(seconds=1) if len(calls) == 1 else HS + timedelta(seconds=1)

    tj = tmp_path / "tft" / "timing.json"
    tj.parent.mkdir(parents=True)
    tj.write_text(json.dumps(tft.project(1, 0.001, 5, 10, HS - timedelta(hours=5), HS)))
    notes = tmp_path / "notes.md"
    rc = tft.run(Namespace(stop=False, timing_only=False), models_root=tmp_path, notes_path=notes, out_dir=tmp_path,
                 clock=clock, dcfg=_dcfg(), inputs=_tiny_inputs())  # fmt: skip
    assert rc == 3 and not (tmp_path / "tft" / "tft.pt").exists()
    t = notes.read_text()
    assert "stopped (D-19)" in t and "reached during fit at epoch 0" in t
    assert len(tft.curves(tmp_path / "tft" / "logs", tmp_path)) == 1  # halted after the first epoch of five


def test_timing_then_stop(tmp_path):
    from swf.models import tft

    out = tft.timing(_tiny_inputs(), _dcfg(), tmp_path, lambda: HS - timedelta(days=1))
    assert (tmp_path / "tft" / "timing.json").exists() and out["fits_before_stop"]
    notes = tmp_path / "notes.md"
    rc = tft.run(Namespace(stop=True, timing_only=False), models_root=tmp_path, notes_path=notes, out_dir=tmp_path, dcfg=_dcfg())
    assert rc == 0 and (tmp_path / "tft_training_curves.png").exists() and "stopped" in notes.read_text()
    tbl = tft.curves(tmp_path / "tft" / "logs", tmp_path)
    assert "val_loss" in tbl and np.isfinite(tbl["val_loss"].iloc[0])
