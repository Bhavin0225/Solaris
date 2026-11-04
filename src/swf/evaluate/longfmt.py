"""Common long prediction format (EVAL-04); every model in Phases 4-6 writes it."""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from swf.core.paths import PROCESSED_DIR
from swf.core.settings import load_features_cfg
from swf.features.spec import artifact_meta, assert_spec
from swf.fetch.cache import safe_part
from swf.physics.constraints import TARGET_COLS

TARGETS = tuple(TARGET_COLS.values())
LONG_COLS = (
    "issue_time",
    "horizon",
    "target_time",
    "target",
    "model",
    "y_true",
    "p10",
    "p50",
    "p90",
)
_F = ("y_true", "p10", "p50", "p90")
_UTC = "datetime64[ns, UTC]"


def grid(origins: pd.DatetimeIndex, horizons):
    """Origin-major, horizon-minor: (issue_time, horizon, target_time)."""
    hs = np.asarray(list(horizons), dtype="int16")
    origins = pd.DatetimeIndex(origins)
    issue = np.repeat(np.asarray(origins), len(hs))
    hor = np.tile(hs, len(origins))
    tt = pd.DatetimeIndex(issue, tz="UTC") + pd.to_timedelta(
        hor.astype("int64"), unit="h"
    )
    return issue, hor, tt


def _cast(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["horizon"] = out["horizon"].astype("int16")
    for c in ("issue_time", "target_time"):
        out[c] = out[c].astype(_UTC)  # pandas 3 infers us/ms units; pin ns
    out["target"] = pd.Categorical(out["target"], categories=TARGETS)
    out["model"] = out["model"].astype("category")
    for c in _F:
        out[c] = out[c].astype("float32")
    return out


def make_long(
    issue_time, horizon, target, model, y_true, p50, p10=None, p90=None
) -> pd.DataFrame:
    issue = pd.DatetimeIndex(issue_time)
    if issue.tz is None:
        issue = issue.tz_localize("UTC")
    hor = np.asarray(horizon)
    n = len(issue)
    nan = np.full(n, np.nan)
    df = pd.DataFrame(
        {
            "issue_time": issue,
            "horizon": hor,
            "target_time": issue + pd.to_timedelta(hor.astype("int64"), unit="h"),
            "target": np.full(n, target)
            if isinstance(target, str)
            else np.asarray(target),
            "model": np.full(n, model) if isinstance(model, str) else np.asarray(model),
            "y_true": np.asarray(y_true, dtype="float64"),
            "p10": nan if p10 is None else np.asarray(p10, dtype="float64"),
            "p50": np.asarray(p50, dtype="float64"),
            "p90": nan if p90 is None else np.asarray(p90, dtype="float64"),
        }
    )
    return _cast(df)[list(LONG_COLS)]


def validate_long(
    df: pd.DataFrame, truth: pd.DataFrame | None = None, origins=None
) -> pd.DataFrame:
    if tuple(df.columns) != LONG_COLS:
        raise ValueError(
            f"columns must be exactly {LONG_COLS}, got {tuple(df.columns)}"
        )
    for c in ("issue_time", "target_time"):
        if str(df[c].dtype) != _UTC:
            raise ValueError(f"{c} must be {_UTC}, got {df[c].dtype}")
    if df["horizon"].dtype != "int16":
        raise ValueError(f"horizon must be int16, got {df['horizon'].dtype}")
    for c in ("target", "model"):
        if not isinstance(df[c].dtype, pd.CategoricalDtype):
            raise ValueError(f"{c} must be category, got {df[c].dtype}")  # noqa: TRY004
    if tuple(df["target"].cat.categories) != TARGETS:
        raise ValueError(
            f"target categories must be {TARGETS}, got {tuple(df['target'].cat.categories)}"
        )
    if df["target"].isna().any():
        raise ValueError(f"target values must be in {TARGETS}")
    bad = [c for c in _F if df[c].dtype != "float32"]
    if bad:
        raise ValueError(f"non-float32 columns: {bad}")
    hmax = load_features_cfg().horizon_max
    if not df["horizon"].between(1, hmax).all():
        raise ValueError(f"horizon must be within 1..{hmax}")
    if df.duplicated(["issue_time", "horizon", "target", "model"]).any():
        raise ValueError("duplicate (issue_time, horizon, target, model) keys")
    expected = df["issue_time"] + pd.to_timedelta(
        df["horizon"].astype("int64"), unit="h"
    )
    if not (df["target_time"] == expected).all():
        raise ValueError("target_time must equal issue_time + horizon hours")
    if (
        origins is not None
        and not df["issue_time"].isin(pd.DatetimeIndex(origins)).all()
    ):
        raise ValueError("issue_time outside the supplied origins")
    if truth is not None:
        for t, g in df.groupby("target", observed=True):
            ref = (
                truth[t].reindex(pd.DatetimeIndex(g["target_time"])).to_numpy("float32")
            )
            if not np.array_equal(g["y_true"].to_numpy(), ref, equal_nan=True):
                raise ValueError(f"y_true disagrees with truth for target {t}")
    return df


def pred_path(split: str, model: str, root=None) -> Path:
    root = Path(root) if root else PROCESSED_DIR / "predictions"
    return root / safe_part(split) / f"{safe_part(model)}.parquet"


def write_long(df: pd.DataFrame, split: str, model: str, root=None) -> Path:
    validate_long(df)
    path = pred_path(split, model, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.sort_values(["target", "issue_time", "horizon"]).reset_index(drop=True)
    tmp = path.with_suffix(".parquet.tmp")
    table = pa.Table.from_pandas(out, preserve_index=False)
    meta = {
        **(table.schema.metadata or {}),
        b"swf_meta": json.dumps(artifact_meta(None), sort_keys=True).encode(),
    }
    pq.write_table(table.replace_schema_metadata(meta), tmp, compression="zstd")
    os.replace(tmp, path)
    return path


def read_long(
    split: str,
    model: str,
    root=None,
    target: str | None = None,
    check_spec: bool = True,
) -> pd.DataFrame:
    path = pred_path(split, model, root)
    if check_spec:
        raw = (pq.read_schema(path).metadata or {}).get(b"swf_meta")
        if raw is None:
            raise ValueError(
                f"{path}: no feature_spec_hash; rerun `python -m swf baselines`"
            )
        assert_spec(json.loads(raw))
    filters = [("target", "==", target)] if target is not None else None
    df = _cast(pd.read_parquet(path, filters=filters))
    return validate_long(df)
