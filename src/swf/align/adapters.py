"""Two adapters (NASA, Open-Meteo) mapping every raw source onto the canonical contract (ALIGN-01).

Canonical radiation = interval mean labelled at interval START (UTC). NASA already is (D-14);
Open-Meteo labels radiation at interval END, so labels shift -1 h (D-15).
"""

import json
from pathlib import Path

import pandas as pd

from swf.align.canon import CANON_COLS, validate_canon
from swf.core.paths import RAW_DIR
from swf.core.settings import Settings
from swf.fetch.cache import is_cached
from swf.fetch.parse import nasa_to_frame
from swf.physics.common import KPA_TO_HPA, hub_wind

SOURCES = ("nasa", "era5", "gfs_hf", "gfs_pr_d1", "gfs_pr_d2", "gfs_pr_d3", "gfs_live")

_H = pd.Timedelta(hours=1)
# (source family, variable group) -> shift applied to the raw label. NASA "met" == Open-Meteo "instant".
OFFSETS: dict[tuple[str, str], pd.Timedelta] = {
    ("nasa", "radiation"): pd.Timedelta(0),
    ("nasa", "met"): pd.Timedelta(0),
    ("nasa", "precip"): pd.Timedelta(0),
    ("openmeteo", "radiation"): -_H,
    ("openmeteo", "instant"): -_H,
    ("openmeteo", "precip"): -_H,
}

NASA_MAP = {
    "ALLSKY_SFC_SW_DWN": "ghi", "ALLSKY_SFC_SW_DNI": "dni", "ALLSKY_SFC_SW_DIFF": "dhi",
    "T2M": "temp", "RH2M": "rh", "PS": "pressure", "WS10M": "ws10", "WD10M": "wd10",
    "WD50M": "wd_hub",  # 50 m direction is the hub-height proxy
    "PRECTOTCORR": "precip",
}  # fmt: skip
OM_MAP = {
    "shortwave_radiation": "ghi", "direct_normal_irradiance": "dni", "diffuse_radiation": "dhi",
    "temperature_2m": "temp", "relative_humidity_2m": "rh", "surface_pressure": "pressure",
    "wind_speed_10m": "ws10", "wind_direction_10m": "wd10", "wind_direction_80m": "wd_hub",
    "precipitation": "precip", "cloud_cover": "cloud",
}  # fmt: skip
OM_UPPER = {80: "wind_speed_80m", 120: "wind_speed_120m"}

_RADIATION = ("ghi", "dni", "dhi")


def _group(family: str, col: str) -> str:
    if col in _RADIATION:
        return "radiation"
    if col == "precip":
        return "precip"
    return "met" if family == "nasa" else "instant"


def _finish(df: pd.DataFrame, family: str) -> pd.DataFrame:
    parts = []
    for col in CANON_COLS:
        sub = df[col].astype("float64")
        parts.append(sub.shift(freq=OFFSETS[(family, _group(family, col))]))
    out = pd.concat(parts, axis=1, keys=CANON_COLS)
    out.index.name = "time"
    return validate_canon(out.sort_index())


def nasa_canon(raw: bytes, s: Settings) -> pd.DataFrame:
    df = nasa_to_frame(raw)
    out = pd.DataFrame(index=df.index)
    for src, dst in NASA_MAP.items():
        out[dst] = df[src]  # KeyError on a missing parameter: fail loud
    out["pressure"] = out["pressure"] * KPA_TO_HPA
    out["ws_hub"] = hub_wind(df["WS10M"], 10, df["WS50M"], 50, s.wind.hub_height_m)
    out["cloud"] = float("nan")
    return _finish(out, "nasa")


def openmeteo_canon(raw: bytes, s: Settings, lead: int | None = None) -> pd.DataFrame:
    h = json.loads(raw)["hourly"]
    suffix = "" if lead is None else f"_previous_day{lead}"
    idx = pd.to_datetime(h["time"], utc=True)

    def get(name):
        return pd.Series(h[name + suffix], index=idx, dtype="float64")

    out = pd.DataFrame(index=idx)
    for src, dst in OM_MAP.items():
        out[dst] = get(src)
    z_up = min(OM_UPPER, key=lambda z: abs(z - s.wind.hub_height_m))
    out["ws_hub"] = hub_wind(get("wind_speed_10m"), 10, get(OM_UPPER[z_up]), z_up, s.wind.hub_height_m)
    return _finish(out, "openmeteo")


def _year_files(source: str, s: Settings, root: Path) -> list[Path]:
    om = s.data.openmeteo
    rng = lambda a: range(a[0], a[1] + 1)
    if source == "nasa":
        return [root / "nasa" / f"{y}.json" for y in range(s.data.nasa.start_year, s.data.nasa.end_year + 1)]
    if source == "era5":
        return [root / "openmeteo/archive" / om.era5_model / f"{y}.json" for y in rng(om.era5_years)]
    if source == "gfs_hf":
        d = root / "openmeteo/historical_forecast" / om.nwp_model
        return [d / f"{y}.json" for y in rng(om.historical_forecast_years)]
    if source.startswith("gfs_pr_d"):
        n = int(source[-1])
        d = root / "openmeteo/previous_runs" / om.nwp_model
        return [d / f"{y}.json" if (d / f"{y}.json").exists() else d / f"{y}_day{n}.json" for y in rng(om.previous_runs_years)]
    if source == "gfs_live":
        d = root / "openmeteo/forecast" / om.nwp_model
        files = sorted(p for p in d.glob("*.json") if not p.name.endswith(".meta.json"))
        if not files:
            raise ValueError(f"no live forecast files in {d}")
        return [files[-1]]
    raise ValueError(f"unknown source {source!r}")


def load_source(source: str, s: Settings, raw_root: Path = RAW_DIR) -> pd.DataFrame:
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    frames = []
    for path in _year_files(source, s, raw_root):
        if not is_cached(path):
            raise ValueError(f"raw file missing or failed sha256 check: {path}")
        raw = path.read_bytes()
        if source == "nasa":
            frames.append(nasa_canon(raw, s))
        else:
            lead = int(source[-1]) if source.startswith("gfs_pr_d") else None
            frames.append(openmeteo_canon(raw, s, lead))
    df = pd.concat(frames).sort_index()
    if not df.index.is_unique:
        raise ValueError(f"duplicate labels across files for {source}")
    return validate_canon(df)
