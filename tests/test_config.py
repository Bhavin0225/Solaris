import shutil

import pytest
import yaml
from pydantic import ValidationError

from swf.core import paths
from swf.core.settings import LgbmCfg, Settings, load_features_cfg, load_lgbm_cfg, load_settings


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


def test_align_keys(settings):
    assert settings.align.max_gap_h == 3
    assert settings.align.fit_years == (2001, 2023)
    assert settings.solar.albedo == 0.25
    assert settings.wind.power_curve_csv == "power_curve.csv"


def _bad_cases():
    return [
        ("site.yaml", lambda d: d["align"].update(max_gap_h=0)),
        ("site.yaml", lambda d: d["align"].update(fit_years=[2023, 2001])),
        ("site.yaml", lambda d: d["align"]["thresholds"].pop("ws_hub")),
        ("site.yaml", lambda d: d["align"].update(bogus=1)),
        ("plant.yaml", lambda d: d["solar"].update(albedo=1.5)),
        ("plant.yaml", lambda d: d["wind"].update(power_curve_csv="../x.csv")),
    ]


@pytest.mark.parametrize("file,fn", _bad_cases())
def test_bad_align_config(tmp_path, file, fn):
    with pytest.raises(ValidationError):
        load_settings(_mutated(tmp_path, fn, file))


@pytest.mark.parametrize(
    "path, value",
    [
        (("solar", "dc_ac_ratio"), 0),
        (("solar", "eta_inv_nom"), 1.5),
        (("wind", "availability_loss"), 1.0),
        (("wind", "cut_in_ms"), 20.0),
        (("align", "fit_years"), (2001, 2030)),
    ],
)
def test_bad_values_rejected(settings, path, value):
    d = settings.model_dump()
    d[path[0]][path[1]] = value
    with pytest.raises(ValueError):
        Settings(**d)


def test_lgbm_cfg_loads():
    c = load_lgbm_cfg()
    f = load_features_cfg()
    assert c.origin_stride == 1
    assert c.buckets == [(1, 6), (7, 24), (25, 72)]
    assert c.buckets[-1][1] == f.horizon_max
    assert f.splits.train_covariate[0] < c.es_tail_start < f.splits.train_covariate[1]


def test_lgbm_cfg_rejects():
    base = yaml.safe_load((paths.CONFIG_DIR / "lgbm.yaml").read_text())
    for bad in ({"extra": 1}, {"buckets": [[1, 6], [8, 24]]}, {"band_quantiles": [0.9, 0.1]}, {"es_tail_start": "2023-07-01T00:00:00"}):
        with pytest.raises(ValidationError):
            LgbmCfg(**{**base, **bad})


def test_deep_cfg_loads():
    from datetime import timedelta

    from swf.core.settings import load_deep_cfg
    from swf.features.spec import spec_hash

    c = load_deep_cfg()
    assert c.train_stride == 3 and c.encoder_hours == 168
    assert c.lstm.hidden == 128 and c.tft.hidden_size == 64
    assert c.lstm.stable_by_utc is None and c.tft.hard_stop_utc is None  # D-62
    assert spec_hash() == "3bd1a73d99093287"


def test_deep_cfg_explicit_deadlines_utc():
    from swf.core.settings import DeepCfg, load_deep_cfg

    d = load_deep_cfg().model_dump(mode="json")
    d["lstm"]["stable_by_utc"], d["tft"]["hard_stop_utc"] = "2026-11-10T18:29:59Z", "2026-11-11T18:29:59Z"
    c = DeepCfg(**d)
    assert c.lstm.stable_by_utc.utcoffset().total_seconds() == 0 and c.lstm.stable_by_utc < c.tft.hard_stop_utc


def _deep_edits():
    return [
        lambda d: d.update(extra=1),
        lambda d: d["lstm"].update(extra=1),
        lambda d: d.update(train_stride=0),
        lambda d: d["lstm"].update(rnn="transformer"),
        lambda d: d["tft"].update(hard_stop_utc="2026-11-11T18:29:59"),
        lambda d: d["lstm"].update(stable_by_utc="2026-11-10T18:29:59"),
    ]


@pytest.mark.parametrize("edit", _deep_edits())
def test_deep_cfg_rejects(edit):
    from swf.core.settings import DeepCfg

    d = yaml.safe_load((paths.CONFIG_DIR / "deep.yaml").read_text())
    edit(d)
    with pytest.raises(ValidationError):
        DeepCfg(**d)
