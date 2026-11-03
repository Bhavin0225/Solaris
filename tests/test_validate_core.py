import math

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from swf.core import paths
from swf.core.settings import Settings, load_settings, load_validation_cfg
from swf.validate.metrics import error_stats


def _bad(tmp_path, mutate):
    d = yaml.safe_load((paths.CONFIG_DIR / "validation.yaml").read_text(encoding="utf-8"))
    mutate(d)
    (tmp_path / "validation.yaml").write_text(yaml.safe_dump(d), encoding="utf-8")
    return tmp_path


def test_loads_committed_config():
    vc = load_validation_cfg()
    assert vc.solar.loss_grid_pct == (8, 20)
    assert vc.solar.irradiation_max_range_kw_m2 == (0.5, 1.6)
    assert vc.solar.plants["plant_1"].gating is True
    assert vc.solar.plants["plant_2"].gating is False
    assert vc.wind.pressure_hpa == 1013.25 and vc.wind.temp_c == 15.0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["solar"].update(loss_grid_pct=[20, 8]),
        lambda d: d["solar"]["plants"]["plant_1"].update(generation_csv="../x.csv"),
        lambda d: d.update(extra=1),
        lambda d: d["solar"]["plants"]["plant_1"].update(gating=False),
    ],
)
def test_bad_config_fails(tmp_path, mutate):
    with pytest.raises(ValidationError):
        load_validation_cfg(_bad(tmp_path, mutate))


def test_error_stats():
    r = error_stats(np.array([1, 2, 3]), np.array([1, 2, 5]), norm=10)
    assert r["rmse_kw"] == pytest.approx(math.sqrt(4 / 3))
    assert r["nrmse_pct"] == pytest.approx(math.sqrt(4 / 3) / 10 * 100)
    assert r["mae_kw"] == pytest.approx(2 / 3)
    assert r["mbe_pct"] == pytest.approx(-2 / 3 / (8 / 3) * 100)
    assert r["n"] == 3
    assert error_stats([1, np.nan, 3], [1, 2, 5], 10)["n"] == 2


def test_settings_untouched():
    assert load_settings() and "validation" not in Settings.model_fields
