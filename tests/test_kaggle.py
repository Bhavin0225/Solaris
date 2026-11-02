import argparse
import subprocess

import pytest

from swf.core import paths
from swf.fetch import kaggle as K

EXP = {"a.csv": 3, "b.csv": 2}


def mk(d, a=3, b=2, bom=False, trailing_nl=True):
    d.mkdir(parents=True, exist_ok=True)
    pre = "\ufeff" if bom else ""
    (d / "a.csv").write_text(pre + "h\n" + "\n".join("x" * a) + ("\n" if trailing_nl else ""), encoding="utf-8")
    (d / "b.csv").write_text("h\n" + "\n".join("y" * b), encoding="utf-8")


def small(settings):
    return settings.model_copy(
        update={"kaggle": settings.kaggle.model_copy(update={"expected_rows": EXP, "row_tolerance": 0.0})}
    )


def test_check_ok_bom_no_trailing_newline(tmp_path):
    mk(tmp_path, bom=True, trailing_nl=False)
    assert K.check_files(tmp_path, EXP, 0.0) == []


def test_check_missing_and_off(tmp_path):
    mk(tmp_path, a=5)
    (tmp_path / "b.csv").unlink()
    p = K.check_files(tmp_path, EXP, 0.1)
    assert any("b.csv" in x for x in p) and any("a.csv" in x and "5" in x and "3" in x for x in p)


def test_download_no_exe(settings, tmp_path):
    def boom(*a, **k):
        raise AssertionError

    assert K.download(settings, tmp_path, runner=boom, which=lambda _: None) is False


def test_download_ok_and_fail(settings, tmp_path):
    calls = []

    def ok(argv, **kw):
        calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, "", "")

    assert K.download(settings, tmp_path, runner=ok, which=lambda _: "/k") is True
    assert [c[0] for c in calls] == [
        ["/k", "datasets", "download", "-d", slug, "-p", str(tmp_path), "--unzip", "-q"]
        for slug in (settings.kaggle.solar_slug, settings.kaggle.wind_slug)
    ]
    assert all(c[1] == {"capture_output": True, "text": True, "timeout": 1800} for c in calls)
    bad = lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", "You don't have access")
    assert K.download(settings, tmp_path, runner=bad, which=lambda _: "/k") is False


def test_download_timeout_returns_false(settings, tmp_path):
    def hang(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    assert K.download(settings, tmp_path, runner=hang, which=lambda _: "/k") is False


def test_manual_steps(settings, tmp_path):
    t = K.manual_steps(settings, tmp_path)
    assert "https://www.kaggle.com/datasets/" in t and str(tmp_path) in t
    assert all(n in t for n in settings.kaggle.expected_rows)


def test_require(settings, tmp_path):
    s = small(settings)
    with pytest.raises(SystemExit) as e:
        K.require_kaggle_files(s, tmp_path)
    assert "Manual Kaggle download" in str(e.value)
    mk(tmp_path)
    assert set(K.require_kaggle_files(s, tmp_path)) == set(EXP)


def test_run(settings, tmp_path, monkeypatch, capsys):
    s = small(settings)
    monkeypatch.setattr(K, "load_settings", lambda: s)
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path)
    monkeypatch.setattr(K, "download", lambda *a, **k: pytest.fail("download called"))
    assert K.run(argparse.Namespace(check=True)) == 1
    assert "Manual Kaggle download" in capsys.readouterr().out
    mk(tmp_path / "kaggle")
    assert K.run(argparse.Namespace(check=False)) == 0  # files exist: no re-download
