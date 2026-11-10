import argparse
import subprocess
import sys

import swf.cli as cli


def _swf(*args):
    return subprocess.run([sys.executable, "-m", "swf", *args], capture_output=True, text=True, check=False)


def test_help_lists_commands():
    r = _swf("--help")
    assert r.returncode == 0
    for cmd in ["check-gpu", "fetch", "kaggle", "probe", "coverage", "data", "curve", "build-weather", "simulate-energy", "validate", "features", "baselines", "evaluate", "train", "train-lgbm", "train-lstm", "train-tft", "serve"]:
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


def test_train_tft_flags():
    r = _swf("train-tft", "--help")
    assert r.returncode == 0 and "--timing-only" in r.stdout and "--stop" in r.stdout


def test_evaluate_final_flag():
    r = _swf("evaluate", "--help")
    assert "--final" in r.stdout and "--force" not in r.stdout


def _record(monkeypatch, fail=None):
    calls = []

    def fake(m, a):
        calls.append((m, a))
        return 1 if m == fail else 0

    monkeypatch.setattr(cli, "_run", fake)
    return calls


def test_data_chain_order(monkeypatch):
    calls = _record(monkeypatch)
    assert cli.main(["data"]) == 0
    assert [m for m, _ in calls] == [
        "swf.fetch.nasa", "swf.fetch.openmeteo", "swf.fetch.kaggle", "swf.physics.wind", "swf.align.build",
        "swf.physics.simulate", "swf.validate.run", "swf.features.run", "swf.evaluate.baselines",
    ]  # fmt: skip


def test_data_fail_fast(monkeypatch):
    calls = _record(monkeypatch, fail="swf.fetch.kaggle")
    assert cli.main(["data"]) == 1
    assert [m for m, _ in calls][-1] == "swf.fetch.kaggle"


def _marker(monkeypatch, tmp_path, exists):
    p = tmp_path / "test_started.json"
    if exists:
        p.write_text("{}")
    monkeypatch.setattr(cli, "_stale_marker", lambda: p)


def test_train_lgbm_only(monkeypatch, tmp_path):
    _marker(monkeypatch, tmp_path, False)
    calls = _record(monkeypatch)
    assert cli.main(["train", "--lgbm-only"]) == 0
    assert [m for m, _ in calls] == ["swf.models.lgbm"]


def test_train_refuses_stale(monkeypatch, tmp_path, capsys):
    _marker(monkeypatch, tmp_path, True)
    calls = _record(monkeypatch)
    assert cli.main(["train", "--lgbm-only"]) == 1
    assert "--accept-stale-results" in capsys.readouterr().out and not calls
    assert cli.main(["train", "--lgbm-only", "--accept-stale-results"]) == 0
    out = capsys.readouterr().out
    assert out.count("WARNING") == 1 and [m for m, _ in calls] == ["swf.models.lgbm"]


def test_train_full_order(monkeypatch, tmp_path):
    _marker(monkeypatch, tmp_path, False)
    calls = _record(monkeypatch)
    assert cli.main(["train"]) == 0
    assert [m for m, _ in calls] == ["swf.models.lgbm", "swf.models.seq", "swf.models.tft", "swf.models.tft"]
    assert calls[2][1].timing_only is True and calls[3][1].timing_only is False and calls[3][1].stop is False


def test_serve_missing_frontend(monkeypatch, tmp_path, capsys):
    import uvicorn

    import swf.api.run as arun
    import swf.core.paths as paths

    monkeypatch.setattr(paths, "FRONTEND_DIST", tmp_path)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    assert arun.run(argparse.Namespace(host="127.0.0.1", port=8000)) == 0
    assert "npm --prefix frontend run build" in capsys.readouterr().out
