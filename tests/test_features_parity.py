"""FEAT-06: the training path and the serving entry point give identical features on the committed live fixture."""

import shutil

import pandas as pd
from pandas.testing import assert_frame_equal

from swf.align.adapters import load_source, openmeteo_canon
from swf.align.clean import clean
from swf.align.consistency import load_coefs
from swf.core.settings import load_features_cfg
from swf.features.build import (
    assemble,
    covariate_table,
    history_input,
    origin_table,
    serve_features,
    target_table,
)
from swf.features.history import history_frame
from swf.features.spec import feature_columns
from swf.physics.wind import load_power_curve

FIXTURE = "om_live_gfs_seamless"


def test_train_serve_parity(settings, fixtures_dir, tmp_path):
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
    # same adapter in both paths
    assert_frame_equal(canon_train, clean(openmeteo_canon(raw_bytes, s), s, source="live")[0], check_exact=True)

    hist = history_frame(history_input(raw_train, s), s, curve, coefs)
    lo = canon_train.index[0] + pd.Timedelta(hours=max(cfg.lags))
    hi = canon_train.index[-1] - pd.Timedelta(hours=cfg.horizon_max)
    valid = pd.date_range(lo, hi, freq="h")
    assert len(valid) >= 1 and len(valid) == 24  # sanity for this fixture
    batch = assemble(
        origin_table(hist, cfg, s), target_table(canon_train.index, cfg, s), valid, range(1, 73),
        cov=covariate_table(canon_train, s, coefs, cfg), cfg=cfg,
    )  # fmt: skip

    for t in valid:
        served = serve_features(raw_bytes, s, cfg, coefs, curve, origin=t)
        assert list(served.columns) == feature_columns("covariate", cfg)
        assert not served.isna().any().any()
        assert_frame_equal(served, batch.xs(t, level="issue_time", drop_level=False), check_exact=True)
