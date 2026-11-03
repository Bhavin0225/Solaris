import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from swf.core import paths
from swf.core.settings import load_features_cfg


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
