import json

import pytest

from swf.fetch.parse import nasa_to_frame


def test_sentinel_to_nan(fixtures_dir):
    raw = (fixtures_dir / "nasa_sample.json").read_bytes()
    n = len(next(iter(json.loads(raw)["properties"]["parameter"].values())))
    df = nasa_to_frame(raw)
    assert str(df.index.tz) == "UTC" and len(df) == n
    assert not (df == -999).any().any() and (df.min() > -900).all()
    assert df["ALLSKY_KT"].isna().sum() > 0 and df["T2M"].isna().sum() == 0


def test_rejects_non_utc(fixtures_dir):
    d = json.loads((fixtures_dir / "nasa_sample.json").read_bytes())
    d["header"]["time_standard"] = "LST"
    with pytest.raises(ValueError):
        nasa_to_frame(json.dumps(d).encode())


def test_misaligned_keys_align_on_timestamp():
    d = {"header": {"fill_value": -999.0, "time_standard": "UTC"},
         "properties": {"parameter": {"A": {"2024010100": 1.0, "2024010101": 2.0},
                                      "B": {"2024010101": 20.0, "2024010100": 10.0}}}}
    df = nasa_to_frame(json.dumps(d).encode())
    assert df["B"].tolist() == [10.0, 20.0] and df["A"].tolist() == [1.0, 2.0]
