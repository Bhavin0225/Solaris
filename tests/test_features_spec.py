import json

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from swf.core import paths
from swf.core.settings import load_features_cfg
from swf.features.spec import (
    COVARIATE_COLS,
    artifact_meta,
    assert_spec,
    feature_columns,
    feature_spec,
    lead_k,
    spec_hash,
)

# update consciously when the spec changes; bump spec_version for logic changes
GOLDEN_HASH = "bd5c6b0683036df5"


def _bad(tmp_path, mutate):
    raw = yaml.safe_load((paths.CONFIG_DIR / "features.yaml").read_text(encoding="utf-8"))
    mutate(raw)
    (tmp_path / "features.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_features_cfg(tmp_path)


def test_committed_config():
    c = load_features_cfg()
    assert c.lags == [0, 1, 2, 3, 4, 5, 6, 12, 24, 48, 168]
    assert c.windows == [6, 24] and c.horizon_max == 72 and c.monsoon_months == [6, 7, 8, 9]
    assert c.eval.horizons == [1, 6, 24, 48, 72]
    assert c.splits.val[0] == pd.Timestamp("2024-01-01", tz="UTC")


def _set(path, value):
    def m(raw):
        d = raw
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = value

    return m


BAD = {
    "extra_key": lambda r: r.update(bogus=1),
    "val_before_train_end": _set(["splits", "val"], ["2023-06-01T00:00:00Z", "2024-12-31T23:00:00Z"]),
    "test_overlaps_val": _set(["splits", "test"], ["2024-06-01T00:00:00Z", "2025-12-31T23:00:00Z"]),
    "cov_outside_weather": _set(["splits", "train_covariate"], ["2000-01-01T00:00:00Z", "2023-12-31T23:00:00Z"]),
    "naive_datetime": _set(["splits", "val"], ["2024-01-01T00:00:00", "2024-12-31T23:00:00"]),
    "horizon_zero": _set(["eval", "horizons"], [0, 6]),
    "horizon_73": _set(["eval", "horizons"], [1, 73]),
    "month_13": _set(["monsoon_months"], [6, 13]),
    "unsorted_lags": _set(["lags"], [0, 2, 1]),
    "duplicate_lags": _set(["lags"], [0, 1, 1]),
}


@pytest.mark.parametrize("name", list(BAD))
def test_bad_config_fails_at_load(tmp_path, name):
    with pytest.raises(ValidationError):
        _bad(tmp_path, BAD[name])


def test_column_sets():
    w, c = feature_columns("weather_only"), feature_columns("covariate")
    assert (len(w), len(c)) == (86, 101)
    assert len(set(w)) == 86 and len(set(c)) == 101
    assert w[-1] == c[-1] == "horizon"
    assert not [x for x in c if x in ("doy", "dayofyear") or x.endswith("_deg")]
    with pytest.raises(ValueError):
        feature_columns("bogus")


def test_golden_hash_and_sensitivity(tmp_path):
    assert spec_hash() == GOLDEN_HASH
    cfg = load_features_cfg()
    cfg2 = cfg.model_copy(update={"lags": [0, 1, 2, 3, 4, 5, 6, 12, 24, 48, 169]})
    assert spec_hash(feature_spec(cfg2)) != GOLDEN_HASH
    alt = tmp_path / "bc.json"
    alt.write_bytes((paths.CONFIG_DIR / "bias_correction.json").read_bytes() + b" ")
    assert spec_hash(feature_spec(coefs_path=alt)) != GOLDEN_HASH


def test_spec_deterministic_and_notes():
    a, b = feature_spec(), feature_spec()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert any("D-05" in n for n in a["notes"]) and any("D-06" in n for n in a["notes"])
    assert not [c for c in COVARIATE_COLS if "gti" in c]


def test_artifact_meta_and_assert_spec():
    m = artifact_meta("covariate")
    assert set(m) == {"feature_spec_hash", "feature_set", "feature_columns"}
    assert assert_spec(m) is None
    with pytest.raises(ValueError, match=spec_hash()):
        assert_spec({**m, "feature_spec_hash": "0" * 16})
    with pytest.raises(ValueError, match="cov_csi"):
        assert_spec({**m, "feature_columns": [c for c in m["feature_columns"] if c != "cov_csi"]})
    h = artifact_meta(None)
    assert h == {"feature_spec_hash": spec_hash()}
    assert assert_spec(h) is None
    with pytest.raises(ValueError):
        assert_spec({})


def test_lead_k():
    assert [lead_k(h) for h in (1, 24, 25, 48, 49, 72)] == [1, 1, 2, 2, 3, 3]
    assert np.bincount(lead_k(np.arange(1, 73)))[1:].tolist() == [24, 24, 24]
