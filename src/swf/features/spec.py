"""FEATURE_SPEC (FEAT-01): the single definition of feature columns and time conventions shared by training and serving."""

import hashlib
import json
from pathlib import Path

from swf.core import paths
from swf.core.settings import FeaturesCfg, load_features_cfg, load_settings
from swf.physics.constraints import TARGET_COLS

TARGETS = tuple(TARGET_COLS.values())
CALENDAR_COLS = ["hour_sin", "hour_cos", "doy_sin", "doy_cos", "monsoon"]
GEOMETRY_COLS = ["zenith", "azimuth_sin", "azimuth_cos", "clearsky_ghi"]
COVARIATE_COLS = [
    "cov_ghi", "cov_dni", "cov_dhi", "cov_temp", "cov_rh", "cov_pressure", "cov_ws10", "cov_ws_hub",
    "cov_precip", "cov_cloud", "cov_wd10_sin", "cov_wd10_cos", "cov_wd_hub_sin", "cov_wd_hub_cos", "cov_csi",
]  # fmt: skip
SETS = ("weather_only", "covariate")


def history_cols(cfg: FeaturesCfg) -> list[str]:
    cols: list[str] = []
    for c in TARGETS:
        cols += [f"{c}_lag{k}" for k in cfg.lags]
        cols += [f"{c}_roll{w}_{stat}" for w in cfg.windows for stat in ("mean", "std")]
    return cols + ["csi_hist"]


def feature_columns(set_name: str, cfg: FeaturesCfg | None = None) -> list[str]:
    cfg = cfg or load_features_cfg()
    if set_name not in SETS:
        raise ValueError(f"unknown feature set {set_name!r}; expected one of {SETS}")
    cov = COVARIATE_COLS if set_name == "covariate" else []
    return history_cols(cfg) + CALENDAR_COLS + GEOMETRY_COLS + cov + ["horizon"]


def lead_k(h):
    """D-02: horizon h hours -> previous_day{k}, k = ceil(h/24). Works on ints and numpy int arrays."""
    return -(-h // 24)


def _coefs_sha(coefs_path: Path | None) -> str:
    p = Path(coefs_path) if coefs_path else paths.CONFIG_DIR / "bias_correction.json"
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()  # CRLF-stable across checkouts


def feature_spec(cfg: FeaturesCfg | None = None, s=None, coefs_path: Path | None = None) -> dict:
    cfg = cfg or load_features_cfg()
    s = s or load_settings()
    return {
        "spec_version": cfg.spec_version,
        "time_convention": (
            "origin t = last fully observed hourly label (interval-start labels, UTC); "
            "history uses labels <= t; targets are t+1..t+horizon_max; issue_time = t"
        ),
        "lead_mapping": "h -> previous_day{k}, k = ceil(h/24)",
        "targets": list(TARGETS),
        "lags": list(cfg.lags),
        "windows": list(cfg.windows),
        "horizon_max": cfg.horizon_max,
        "monsoon_months": list(cfg.monsoon_months),
        "night_zenith_deg": cfg.eval.daytime_zenith_deg,
        "rolling": "trailing window incl. origin, full window required, std ddof=1",
        "dtype": "float32",
        "notes": [
            "lag0 added to the FEAT-02 lag list",
            "GTI covariate dropped (D-05): not in CANON_COLS; GHI/DNI/DHI covariates plus solar geometry carry the same information",
            "no lead-age feature: constant in stitched training covariates (RESEARCH A7)",
            "splits purge origins whose 72 h targets cross a boundary; no extra 168 h embargo because history features are inputs, not labels (D-06)",
        ],
        "sets": {n: feature_columns(n, cfg) for n in SETS},
        "inputs": {
            "bias_correction_sha256": _coefs_sha(coefs_path),
            "solar_loss_pct": s.solar.loss_pct,
            "solar_dc_ac_ratio": s.solar.dc_ac_ratio,
        },
    }


def spec_hash(spec: dict | None = None) -> str:
    spec = spec if spec is not None else feature_spec()
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def artifact_meta(set_name: str | None = None, spec: dict | None = None) -> dict:
    """Metadata every artifact stores; feature-free artifacts (set_name None) carry the hash only."""
    spec = spec if spec is not None else feature_spec()
    meta = {"feature_spec_hash": spec_hash(spec)}
    if set_name is not None:
        meta |= {"feature_set": set_name, "feature_columns": list(spec["sets"][set_name])}
    return meta


def assert_spec(meta: dict, spec: dict | None = None) -> None:
    spec = spec if spec is not None else feature_spec()
    want = spec_hash(spec)
    got = meta.get("feature_spec_hash")
    cols = meta.get("feature_columns")
    missing: list[str] = []
    extra: list[str] = []
    if cols is not None:
        cur = spec["sets"].get(meta.get("feature_set"), [])
        missing = [c for c in cur if c not in cols]
        extra = [c for c in cols if c not in cur]
    if got != want or missing or extra or (cols is not None and meta.get("feature_set") not in spec["sets"]):
        raise ValueError(f"feature spec mismatch: artifact {got} vs current {want}; missing {missing}; extra {extra}")
