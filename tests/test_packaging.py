import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
BANNED = ("torch", "darts", "kaggle", "matplotlib", "pytorch-lightning")


def test_core_deps_exclude_training_stack():
    for dep in PYPROJECT["project"]["dependencies"]:
        assert not dep.lower().startswith(BANNED), dep


def test_train_extra_and_cu134_index():
    train = PYPROJECT["project"]["optional-dependencies"]["train"]
    for need in ("torch==2.15.0", "kaggle==2.2.5", "six"):
        assert need in train
    uv = PYPROJECT["tool"]["uv"]
    assert uv["sources"]["torch"][0]["index"] == "pytorch-cu134"
    idx = {i["name"]: i for i in uv["index"]}
    assert idx["pytorch-cu134"]["explicit"] is True


def test_lock_has_single_cuda_torch():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    torch = [p for p in lock["package"] if p["name"] == "torch"]
    assert len(torch) == 1
    assert torch[0]["version"] == "2.15.0+cu134"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH")
def test_serve_export_is_torch_free():
    r = subprocess.run(
        ["uv", "export", "--no-dev", "--no-hashes", "--no-emit-project"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    for line in r.stdout.splitlines():
        assert not line.lower().startswith(("torch==", "darts==", "kaggle==")), line
