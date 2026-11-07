"""models/registry.json: which runtime serves each target. Contract written by train-lgbm, read by serving.

{"schema_version": 1, "feature_spec_hash": str, "baseline3_choice": {target: "corrected"|"raw"},
 "buckets": [[1,6],[7,24],[25,72]], "selection_split": "val",
 "targets": {target: {"selected": "baseline3"|"lightgbm", "runtime": same, "reason": str,
   "artifacts": {"1-6": "lightgbm/<target>_1-6.txt", ...}  (relative to models/, may be {}),
   "bands": {"baseline3": {"1-6": [q10, q90], ...}, "lightgbm": {...}},
   "val_rmse": {"baseline3": float, "lightgbm": float}}}}
"""

import importlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from swf.core.paths import MODELS_DIR
from swf.features.spec import assert_spec, spec_hash

SCHEMA_VERSION = 1
RUNTIMES = {"baseline3": "swf.predict.baseline", "lightgbm": "swf.predict.lgbm"}  # whitelist, T-05-02
_REMEDY = "run `python -m swf train-lgbm`"


def _round(x):
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v) for v in x]
    return x


def _path(path):
    return Path(path) if path else MODELS_DIR / "registry.json"


def save_registry(reg: dict, path: Path | None = None) -> None:
    path = _path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reg = _round({**reg, "feature_spec_hash": spec_hash(), "schema_version": SCHEMA_VERSION})
    text = json.dumps(reg, indent=2, sort_keys=True) + "\n"
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_registry(path: Path | None = None) -> dict:
    path = _path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; {_REMEDY}")
    d = json.loads(path.read_text(encoding="utf-8"))
    try:
        assert_spec({"feature_spec_hash": d.get("feature_spec_hash")})
    except ValueError as e:
        raise ValueError(f"{e}; {_REMEDY}") from e
    return d


def artifact_path(rel: str, root: Path | None = None) -> Path:
    root = Path(root) if root else MODELS_DIR
    if PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).is_absolute() or ".." in PureWindowsPath(rel).parts:
        raise ValueError(f"artifact path {rel!r} must be relative and stay inside models/")
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError(f"artifact path {rel!r} escapes {root}")
    return p


def runtime_module(name: str):
    if name not in RUNTIMES:
        raise ValueError(f"unknown runtime {name!r}; allowed: {sorted(RUNTIMES)}")
    return importlib.import_module(RUNTIMES[name])
