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
