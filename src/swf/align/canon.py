"""Frozen canonical hourly weather contract (UTC, radiation = interval mean labelled at interval start)."""

import pandas as pd

# fmt: off
CANON_COLS = (
    "ghi", "dni", "dhi", "temp", "rh", "pressure",
    "ws10", "ws_hub", "wd10", "wd_hub", "precip", "cloud",
)

UNITS = {
    "ghi": "W/m2", "dni": "W/m2", "dhi": "W/m2", "temp": "degC", "rh": "%",
    "pressure": "hPa", "ws10": "m/s", "ws_hub": "m/s", "wd10": "deg",
    "wd_hub": "deg", "precip": "mm/h", "cloud": "%",
}

# Physical limits, not site values.
PHYS_RANGES = {
    "ghi": (0, 1400), "dni": (0, 1400), "dhi": (0, 800), "temp": (-10, 55),
    "rh": (0, 100), "pressure": (850, 1100), "ws10": (0, 50), "ws_hub": (0, 60),
    "wd10": (0, 360), "wd_hub": (0, 360), "precip": (0, 300), "cloud": (0, 100),
}
# fmt: on


def validate_canon(df: pd.DataFrame) -> pd.DataFrame:
    if tuple(df.columns) != CANON_COLS:
        raise ValueError(
            f"columns must be exactly {CANON_COLS}, got {tuple(df.columns)}"
        )
    bad = [c for c in df.columns if df[c].dtype != "float64"]
    if bad:
        raise ValueError(f"non-float64 dtypes: {bad}")
    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None or str(idx.tz) != "UTC":
        raise ValueError("index must be a tz-aware UTC DatetimeIndex")
    if idx.name != "time":
        raise ValueError("index must be named 'time'")
    if not idx.is_unique:
        raise ValueError("duplicate index labels")
    if not idx.is_monotonic_increasing:
        raise ValueError("index not sorted")
    if ((idx.minute != 0) | (idx.second != 0) | (idx.microsecond != 0)).any():
        raise ValueError("index labels must be on the hour")
    if (df <= -900).any().any():
        raise ValueError("sentinel value (<= -900) present")
    return df
