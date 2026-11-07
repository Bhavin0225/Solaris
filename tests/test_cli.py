import subprocess
import sys


def _swf(*args):
    return subprocess.run([sys.executable, "-m", "swf", *args], capture_output=True, text=True, check=False)


def test_help_lists_commands():
    r = _swf("--help")
    assert r.returncode == 0
    for cmd in ["check-gpu", "fetch", "kaggle", "probe", "coverage", "data", "curve", "build-weather", "simulate-energy", "validate", "features", "baselines", "evaluate", "train-lgbm", "serve"]:
        assert cmd in r.stdout


def test_evaluate_split_choices():
    r = _swf("evaluate", "--help")
    assert r.returncode == 0
    assert "{val,test,all}" in r.stdout


def test_openmeteo_apis():
    r = _swf("fetch", "openmeteo", "--help")
    assert r.returncode == 0
    for api in ["era5", "historical", "previous", "live", "all"]:
        assert api in r.stdout


def test_serve_args():
    r = _swf("serve", "--help")
    assert r.returncode == 0
    assert "--host" in r.stdout and "--port" in r.stdout
