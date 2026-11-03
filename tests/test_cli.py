import subprocess
import sys


def _swf(*args):
    return subprocess.run([sys.executable, "-m", "swf", *args], capture_output=True, text=True, check=False)


def test_help_lists_commands():
    r = _swf("--help")
    assert r.returncode == 0
    for cmd in ["check-gpu", "fetch", "kaggle", "probe", "coverage", "data", "curve", "build-weather", "simulate-energy"]:
        assert cmd in r.stdout


def test_openmeteo_apis():
    r = _swf("fetch", "openmeteo", "--help")
    assert r.returncode == 0
    for api in ["era5", "historical", "previous", "live", "all"]:
        assert api in r.stdout
