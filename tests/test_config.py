import shutil

import pytest
import yaml
from pydantic import ValidationError

from swf.core import paths
from swf.core.settings import load_settings


def _mutated(tmp_path, fn, file="site.yaml"):
    for f in ("site.yaml", "plant.yaml"):
        shutil.copy(paths.CONFIG_DIR / f, tmp_path / f)
    p = tmp_path / file
    d = yaml.safe_load(p.read_text())
    fn(d)
    p.write_text(yaml.safe_dump(d))
    return tmp_path


def test_loads(settings):
    assert settings.site.latitude == 14.4644
    assert settings.data.openmeteo.nwp_model == "gfs_seamless"
    assert settings.data.openmeteo.era5_model == "era5"
    assert settings.solar.tilt_deg == 15


def test_typo_key(tmp_path):
    def f(d):
        d["site"]["lattitude"] = d["site"].pop("latitude")

    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, f))


def test_16_nasa_params(tmp_path):
    def f(d):
        d["data"]["nasa"]["parameters"] = [f"P{i}" for i in range(16)]

    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, f))


@pytest.mark.parametrize("bad", ["best_match", "GFS/../x"])
def test_bad_nwp_model(tmp_path, bad):
    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, lambda d: d["data"]["openmeteo"].update(nwp_model=bad)))


@pytest.mark.parametrize("bad", ["best_match", "../x"])
def test_bad_probe_model(tmp_path, bad):
    with pytest.raises(ValidationError):
        load_settings(
            _mutated(tmp_path, lambda d: d["data"]["openmeteo"].update(probe_models=["gfs_seamless", bad]))
        )


def test_bad_era5_model(tmp_path):
    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, lambda d: d["data"]["openmeteo"].update(era5_model="era5_land")))


@pytest.mark.parametrize("bad", ["anikannal", "../evil/x", "a/b c"])
def test_bad_slug(tmp_path, bad):
    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, lambda d: d["kaggle"].update(solar_slug=bad)))


@pytest.mark.parametrize("bad", ["../T1.csv", "sub/T1.csv", "T1.txt"])
def test_bad_expected_rows_key(tmp_path, bad):
    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, lambda d: d["kaggle"]["expected_rows"].update({bad: 1})))


def test_no_coordinate_literals(settings):
    lits = [str(settings.site.latitude), str(settings.site.longitude)]
    for py in (paths.REPO_ROOT / "src").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert not any(s in text for s in lits), py
