"""Sentinel-aware parsing of raw NASA POWER JSON (DATA-03). Raw files stay verbatim (D-14)."""

import json

import pandas as pd


def nasa_to_frame(raw: bytes) -> pd.DataFrame:
    d = json.loads(raw)
    fill = d["header"]["fill_value"]
    if d["header"]["time_standard"] != "UTC":
        raise ValueError("NASA response is not time-standard UTC")
    params = d["properties"]["parameter"]
    df = pd.DataFrame(params)  # dict of dicts: aligns on the timestamp keys, never on position
    df.index = pd.to_datetime(df.index, format="%Y%m%d%H", utc=True)
    df = df.mask(df == fill)  # sentinel -> NaN before anything else
    assert not (df == fill).any().any() and (df.min() > -900).all()
    return df
