import json

import numpy as np
from pandas.testing import assert_series_equal

from swf.align.adapters import openmeteo_canon
from swf.align.clean import clean
from swf.align.consistency import load_coefs
from swf.core.paths import CONFIG_DIR
from swf.evaluate.baselines import b3_table
from swf.features.spec import TARGETS
from swf.physics.wind import load_power_curve
from swf.predict.baseline import live_tables, predict_p50


def test_live_equals_phase4_chain(settings, fixtures_dir):
    raw = (fixtures_dir / "om_live_gfs_seamless.json").read_bytes()
    coefs, curve = load_coefs(), load_power_curve(settings)
    choice = json.loads((CONFIG_DIR / "baseline3_choice.json").read_text(encoding="utf-8"))["choice"]
    live = live_tables(raw, settings, coefs, curve, choice)
    canon = clean(openmeteo_canon(raw, settings), settings, source="live")[0]
    for t in TARGETS:
        want = b3_table(canon, settings, curve, coefs if choice[t] == "corrected" else None)[t]
        assert_series_equal(live[t], want, check_names=False)


def test_predict_p50_passthrough():
    b3 = np.array([1.0, 2.0])
    assert (predict_p50({}, None, b3, "rh", None) == b3).all()
