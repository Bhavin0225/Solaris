import pandas as pd
import pytest

from swf.core.settings import load_features_cfg
from swf.features.splits import SPLITS, origins_for, split_table

EXPECTED = {"train_weather_only": 201360, "train_covariate": 24048, "val": 8712, "test": 8688}


@pytest.mark.parametrize("split", SPLITS)
def test_origin_counts_and_bounds(split):
    cfg = load_features_cfg()
    o = origins_for(split, cfg)
    start, end = (pd.Timestamp(t) for t in getattr(cfg.splits, split))
    lo = start + pd.Timedelta(hours=max(cfg.lags)) if split == "train_weather_only" else start
    hi = end - pd.Timedelta(hours=cfg.horizon_max)
    assert len(o) == len(pd.date_range(lo, hi, freq="h")) == EXPECTED[split]
    assert o[0] >= start and o[-1] + pd.Timedelta(hours=cfg.horizon_max) <= end
    assert o.name == "issue_time" and str(o.tz) == "UTC" and o.freq == "h"


def test_no_leak_between_splits():
    cfg = load_features_cfg()
    train_end = origins_for("train_weather_only", cfg)[-1] + pd.Timedelta(hours=72)
    assert train_end < origins_for("val", cfg)[0]
    assert origins_for("val", cfg)[-1] + pd.Timedelta(hours=72) < origins_for("test", cfg)[0]


def test_split_table_and_unknown():
    rows = split_table()
    assert [r["split"] for r in rows] == list(SPLITS)
    assert all(r["n_purged"] == 72 for r in rows) and rows[0]["n_warmup"] == 168
    with pytest.raises(ValueError):
        origins_for("nope")
