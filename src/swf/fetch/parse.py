"""Sentinel-aware parsing of raw NASA POWER JSON (DATA-03). Raw files stay verbatim (D-14)."""

import json

import pandas as pd


def nasa_to_frame(raw: bytes) -> pd.DataFrame:
    d = json.loads(raw)
    fill = d["header"]["fill_value"]
    if d["header"]["time_standard"] != "UTC":
        raise ValueError("NASA response is not time-standard UTC")
    params = d["properties"]["parameter"]
    idx = pd.to_datetime(list(next(iter(params.values()))), format="%Y%m%d%H", utc=True)
    df = pd.DataFrame({k: list(v.values()) for k, v in params.items()}, index=idx)
    df = df.mask(df == fill)  # sentinel -> NaN before anything else
    assert not (df == fill).any().any() and (df.min() > -900).all()
    return df
