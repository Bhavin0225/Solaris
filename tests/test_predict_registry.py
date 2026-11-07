import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from synth import make_registry, write_tiny_lgbm

from swf.features.spec import feature_columns
from swf.predict import lgbm as rt
from swf.predict.registry import artifact_path, load_registry, runtime_module, save_registry

B = [(1, 6), (7, 24), (25, 72)]


def test_roundtrip(tmp_path):
    p = tmp_path / "registry.json"
    reg = make_registry(p)
    reg["targets"]["rh"]["val_rmse"]["lightgbm"] = 1.23456789
    save_registry(reg, p)
    text = p.read_text(encoding="utf-8")
    assert text.endswith("\n") and "1.234568" in text and "1.2345678" not in text
    assert load_registry(p)["targets"]["rh"]["val_rmse"]["lightgbm"] == 1.234568


def test_load_errors(tmp_path):
    with pytest.raises(FileNotFoundError, match="train-lgbm"):
        load_registry(tmp_path / "none.json")
    p = tmp_path / "r.json"
    make_registry(p)
    p.write_text(p.read_text().replace('"feature_spec_hash": "', '"feature_spec_hash": "x'), encoding="utf-8")
    with pytest.raises(ValueError, match="train-lgbm"):
        load_registry(p)


def test_artifact_path(tmp_path):
    assert artifact_path("lightgbm/a.txt", tmp_path).is_relative_to(tmp_path.resolve())
    for bad in ("../x.txt", str((tmp_path.parent / "x.txt").resolve())):
        with pytest.raises(ValueError):
            artifact_path(bad, tmp_path)


def test_runtime_module():
    assert runtime_module("baseline3").__name__ == "swf.predict.baseline"
    assert runtime_module("lightgbm").__name__ == "swf.predict.lgbm"
    with pytest.raises(ValueError):
        runtime_module("os")


def test_import_hygiene():
    code = (
        "import sys, swf.predict.registry, swf.predict.baseline, swf.predict.bands, swf.predict.lgbm\n"
        "from swf.predict.registry import runtime_module\n"
        "runtime_module('baseline3')\n"
        "bad = [k for k in sys.modules if k.split('.')[0] in ('lightgbm', 'torch', 'darts', 'matplotlib')"
        " or k.startswith(('swf.evaluate', 'swf.validate', 'swf.models'))]\n"
        "assert not bad, bad\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr


def test_lgbm_predict(tmp_path):
    import lightgbm as lgb

    arts = write_tiny_lgbm(tmp_path, "rh", B)
    cols = feature_columns("covariate")
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.normal(size=(72, len(cols))), columns=cols)
    X["horizon"] = np.arange(1, 73)
    b3 = rng.normal(size=72)
    got = rt.predict_p50({"artifacts": arts}, X, b3, "rh", tmp_path)
    want = b3.copy()
    for lo, hi in B:
        m = ((X.horizon >= lo) & (X.horizon <= hi)).to_numpy()
        bst = lgb.Booster(model_file=str(tmp_path / arts[f"{lo}-{hi}"]))
        want[m] += bst.predict(X.loc[m, cols])
    np.testing.assert_allclose(got, want)
    meta_p = (tmp_path / arts["1-6"]).with_suffix(".json")
    meta_p.write_text(meta_p.read_text().replace('"feature_spec_hash": "', '"feature_spec_hash": "x'), encoding="utf-8")
    rt._load.cache_clear()
    with pytest.raises(ValueError):
        rt.predict_p50({"artifacts": arts}, X, b3, "rh", tmp_path)
