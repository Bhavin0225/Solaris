import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from synth import canon_frame

from swf.align.consistency import load_coefs
from swf.core.paths import INTERIM_DIR
from swf.core.settings import load_features_cfg
from swf.evaluate import baselines as b
from swf.evaluate.longfmt import TARGETS, grid, make_long, validate_long
from swf.features.splits import origins_for
from swf.physics.wind import load_power_curve

CFG = load_features_cfg()
HOURS = range(1, 73)


def hand_truth(start="2024-02-20", days=14):
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC", name="time")
    return pd.DataFrame({c: np.arange(len(idx), dtype=float) + 1000 * i for i, c in enumerate(TARGETS)}, index=idx)


def origin(ts="2024-03-01 10:00"):
    return pd.DatetimeIndex([pd.Timestamp(ts, tz="UTC")], name="issue_time")


def test_truth_frame_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="build-weather"):
        b.truth_frame(tmp_path)
    pd.DataFrame({"rh": [1.0], "ghi": [1.0], "ws10": [1.0]}).to_parquet(tmp_path / "weather_nasa.parquet")
    with pytest.raises(FileNotFoundError, match="simulate-energy"):
        b.truth_frame(tmp_path)


def test_truth_frame_columns(tmp_path):
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC", name="time")
    pd.DataFrame({"rh": 1.0, "ghi": 2.0, "ws10": 3.0}, index=idx).to_parquet(tmp_path / "weather_nasa.parquet")
    pd.DataFrame({"t1_kw": 4.0, "t5_kw": 5.0}, index=idx).to_parquet(tmp_path / "energy_sim.parquet")
    t = b.truth_frame(tmp_path)
    assert tuple(t.columns) == TARGETS and t["t5_kw"].iloc[0] == 5.0 and t["rh"].iloc[0] == 1.0


def test_persistence():
    truth, o = hand_truth(), origin()
    df = b.persistence(truth, o, HOURS)
    validate_long(df, truth=truth, origins=o)
    assert len(df) == 72 * 5 and set(df["model"].astype(str)) == {"persistence"}
    assert df["p10"].isna().all() and df["p90"].isna().all()
    t0 = o[0]
    for c in ("ws10", "rh", "t5_kw"):
        g = df[df["target"] == c]
        assert (g["p50"] == np.float32(truth[c][t0])).all()
    for c in ("t1_kw", "ghi"):
        g = df[df["target"] == c].set_index("horizon")["p50"]
        exp = {1: "2024-02-29 11:00", 24: "2024-03-01 10:00", 25: "2024-02-29 11:00", 72: "2024-03-01 10:00"}
        for h, ts in exp.items():
            assert g[h] == np.float32(truth[c][pd.Timestamp(ts, tz="UTC")])
        assert (df[df["target"] == c]["target_time"] - pd.to_timedelta(24 * b.lead_k(df[df["target"] == c]["horizon"].astype("int64")), unit="h") <= t0).all()


def test_climatology_train_years_only():
    idx = pd.date_range("2020-01-01", "2024-12-31 23:00", freq="h", tz="UTC", name="time")
    truth = pd.DataFrame({c: 1.0 for c in TARGETS}, index=idx)
    truth.loc["2024-03-01":, "ws10"] = 1000.0  # outside train_weather_only (ends 2023)
    table = b.climatology_table(truth, CFG)
    assert table["ws10"].max() == 1.0
    o = origin()
    df = b.climatology(truth, table, o, HOURS)
    validate_long(df, truth=truth, origins=o)
    assert len(df) == 72 * 5 and (df[df["target"] == "ws10"]["p50"] == 1.0).all()
    tt = pd.Timestamp("2024-03-01 11:00", tz="UTC")
    assert table.loc[(tt.month, tt.hour), "rh"] == 1.0


@pytest.fixture
def s(settings):
    return settings


def lead_tables(s):
    curve = load_power_curve(s)
    base = canon_frame("2024-06-01", 6, s)
    tabs = {}
    for k in (1, 2, 3):
        w = base.copy()
        w["ws10"] = 3.0 * k
        tabs[k] = w
    return base, tabs, curve


def test_baseline3_lead_matching(s):
    base, raw, curve = lead_tables(s)
    tabs = {k: b.b3_table(v, s, curve) for k, v in raw.items()}
    truth = tabs[1]
    o = origin("2024-06-02 00:00")
    df = b.baseline3(tabs, truth, o, HOURS, "baseline3_raw")
    validate_long(df, origins=o)
    g = df[df["target"] == "ws10"].set_index("horizon")["p50"]
    assert (g.loc[1:24] == 3.0).all() and (g.loc[25:48] == 6.0).all() and (g.loc[49:72] == 9.0).all()
    st = b.baseline3(tabs[2], truth, o, HOURS, "baseline3_stitched_raw")
    assert (st[st["target"] == "ws10"]["p50"] == 6.0).all()


def test_baseline3_corrected_vs_raw_and_nan(s):
    base, raw, curve = lead_tables(s)
    coefs = load_coefs()
    cor = {k: b.b3_table(v, s, curve, coefs) for k, v in raw.items()}
    unc = {k: b.b3_table(v, s, curve) for k, v in raw.items()}
    o = origin("2024-06-02 00:00")
    a = b.baseline3(cor, unc[1], o, HOURS, "baseline3_corrected")
    r = b.baseline3(unc, unc[1], o, HOURS, "baseline3_raw")
    p = lambda d, t: d[d["target"] == t]["p50"].to_numpy()  # noqa: E731
    assert not np.array_equal(p(a, "ws10"), p(r, "ws10"))
    assert not np.array_equal(p(a, "rh"), p(r, "rh"))
    assert np.array_equal(p(a, "ghi"), p(r, "ghi"))
    nan = {k: v.copy() for k, v in raw.items()}
    nan[1].loc[pd.Timestamp("2024-06-02 05:00", tz="UTC"), "ws10"] = np.nan
    tabs = {k: b.b3_table(v, s, curve) for k, v in nan.items()}
    d = b.baseline3(tabs, unc[1], o, HOURS, "baseline3_raw")
    g = d[d["target"] == "ws10"].set_index("horizon")["p50"]
    assert np.isnan(g[5]) and g[4] == 3.0


def _val_frames():
    o = pd.date_range("2024-03-01 04:00", periods=6, freq="h", tz="UTC")
    i, h, _ = grid(o, range(1, 5))
    n = len(h)
    y = np.linspace(100, 500, n)
    good = {"corrected": ("rh", "t1_kw", "ghi"), "raw": ("ws10", "t5_kw")}
    out = {}
    for var in ("corrected", "raw"):
        parts = []
        for t in TARGETS:
            err = 1.0 if t in good[var] else 5.0
            parts.append(make_long(i, h, t, f"baseline3_{var}", y, y + err))
        out[f"baseline3_{var}"] = pd.concat(parts, ignore_index=True)
    return out


def test_select_baseline3(s):
    ch = b.select_baseline3(_val_frames(), s, CFG)
    assert ch["choice"] == {"t1_kw": "corrected", "rh": "corrected", "ghi": "corrected", "ws10": "raw", "t5_kw": "raw"}
    assert ch["split"] == "val" and set(ch["val_rmse"]) == set(TARGETS)
    tie = _val_frames()
    tie["baseline3_raw"] = tie["baseline3_corrected"].assign(model="baseline3_raw")
    assert set(b.select_baseline3(tie, s, CFG)["choice"].values()) == {"corrected"}


def test_select_rejects_non_val(s):
    fr = _val_frames()
    o = pd.date_range("2025-03-01 04:00", periods=2, freq="h", tz="UTC")
    i, h, _ = grid(o, range(1, 3))
    fr["baseline3_raw"] = make_long(i, h, "rh", "baseline3_raw", np.ones(len(h)), np.ones(len(h)))
    with pytest.raises(ValueError, match="validation"):
        b.select_baseline3(fr, s, CFG)


def test_choice_roundtrip(s, tmp_path):
    p = tmp_path / "c.json"
    ch = b.select_baseline3(_val_frames(), s, CFG)
    b.save_choice(ch, p)
    first = p.read_bytes()
    b.save_choice(ch, p)
    assert p.read_bytes() == first
    got = b.load_choice(p)
    assert got["choice"] == ch["choice"] and got["feature_spec_hash"] == b.spec_hash()
    with pytest.raises(FileNotFoundError, match="python -m swf evaluate --split val"):
        b.load_choice(tmp_path / "missing.json")


def test_choice_spec_mismatch(tmp_path):
    p = tmp_path / "c.json"
    for d in ({"choice": {}}, {"choice": {}, "feature_spec_hash": "0" * 16}):
        p.write_text(json.dumps(d), encoding="utf-8")
        with pytest.raises(ValueError, match="feature spec mismatch") as e:
            b.load_choice(p)
        assert "delete config/baseline3_choice.json and rerun `python -m swf evaluate --split val`" in str(e.value)


def test_run_missing_inputs(tmp_path, capsys):
    assert b.run(None, out_root=tmp_path, interim_dir=tmp_path) == 1
    assert "build-weather" in capsys.readouterr().out


REAL = Path(os.environ.get("SWF_REAL_INTERIM", INTERIM_DIR))
HAVE = all((REAL / n).exists() for n in b._NEED)


@pytest.mark.realdata
@pytest.mark.skipif(not HAVE, reason="interim parquets absent")
def test_chain_identity_on_nasa(settings):
    src = REAL / "weather_nasa.parquet"
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    nasa = pd.read_parquet(src)
    out = b.b3_table(nasa, settings, load_power_curve(settings))
    sim = pd.read_parquet(REAL / "energy_sim.parquet")
    for c in ("t1_kw", "t5_kw"):
        pd.testing.assert_series_equal(out[c], sim[c])
    assert hashlib.sha256(src.read_bytes()).hexdigest() == h


@pytest.mark.realdata
@pytest.mark.skipif(not HAVE, reason="interim parquets absent")
def test_build_split_val(settings):
    frames = b.build_split("val", settings, CFG, REAL)
    o, truth = origins_for("val", CFG), b.truth_frame(REAL)
    assert set(frames) == set(b.MODELS)
    for df in frames.values():
        validate_long(df, truth=truth, origins=o)
        assert len(df) == 8712 * 72 * 5
