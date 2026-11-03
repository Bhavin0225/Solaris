from datetime import date

import pandas as pd
import pytest

from swf.core.settings import load_validation_cfg
from swf.validate.kaggle_solar import heldout_start_utc, load_plant

GEN_HDR = "DATE_TIME,PLANT_ID,SOURCE_KEY,DC_POWER,AC_POWER,DAILY_YIELD,TOTAL_YIELD\n"
WX_HDR = (
    "DATE_TIME,PLANT_ID,SOURCE_KEY,AMBIENT_TEMPERATURE,MODULE_TEMPERATURE,IRRADIATION\n"
)
WX_DEFAULT = [
    ("2020-06-05 12:00:00", 0.9),
    ("2020-06-05 12:15:00", 1.0),
    ("2020-06-05 12:30:00", 0.1),
]


def _fixture(tmp_path, gen_rows, wx_rows=None, **kw):
    base = {
        "n_inverters": 3,
        "span_local": (date(2020, 6, 5), date(2020, 6, 5)),
        "heldout_start_local": date(2020, 6, 30),
    }
    vs = load_validation_cfg().solar.model_copy(update={**base, **kw})
    g, w = tmp_path / "g.csv", tmp_path / "w.csv"
    g.write_text(
        GEN_HDR + "".join(f"{t},1,{k},9999,{ac},0,0\n" for t, k, ac in gen_rows)
    )
    w.write_text(
        WX_HDR + "".join(f"{t},1,s,30,40,{i}\n" for t, i in (wx_rows or WX_DEFAULT))
    )
    return g, w, vs


def _load(g, w, vs):
    return load_plant(g, w, vs.plants["plant_1"], vs)


def test_parse_sum_partial_and_utc(tmp_path):
    rows = [("05-06-2020 12:00", k, 10 * (i + 1)) for i, k in enumerate("abc")]
    rows += [("05-06-2020 12:15", "a", 5), ("05-06-2020 12:15", "b", 5)]  # partial
    rows += [("05-06-2020 12:30", k, 1) for k in "abc"]
    rows += [("05-06-2020 12:45", k, 1) for k in "abc"]  # no weather
    df, st = _load(*_fixture(tmp_path, rows))
    assert list(df.index) == [
        pd.Timestamp("2020-06-05 06:30", tz="UTC"),
        pd.Timestamp("2020-06-05 07:00", tz="UTC"),
    ]
    assert df["ac_kw"].iloc[0] == 60
    assert st["ts_partial_dropped"] == 1 and st["ts_total"] == 4 and st["rows_out"] == 2
    assert st["peak_ac_kw"] == 60 and st["irr_max_kw_m2"] == 1.0


def test_no_weather_counted(tmp_path):
    rows = [("05-06-2020 12:00", k, 1) for k in "abc"] + [
        ("05-06-2020 12:45", k, 1) for k in "abc"
    ]
    _, st = _load(*_fixture(tmp_path, rows))
    assert st["ts_no_weather"] == 1


def test_wrong_date_format_fails(tmp_path):
    rows = [("2020-06-05 12:00:00", k, 1) for k in "abc"]
    with pytest.raises(ValueError):
        _load(*_fixture(tmp_path, rows))


def test_span_mismatch_fails(tmp_path):
    rows = [("05-06-2020 12:00", k, 1) for k in "abc"]
    with pytest.raises(ValueError, match="span"):
        _load(
            *_fixture(tmp_path, rows, span_local=(date(2020, 5, 15), date(2020, 6, 17)))
        )


def test_duplicate_weather_fails(tmp_path):
    rows = [("05-06-2020 12:00", k, 1) for k in "abc"]
    wx = [("2020-06-05 12:00:00", 0.9), ("2020-06-05 12:00:00", 0.9)]
    with pytest.raises(ValueError, match="duplicate"):
        _load(*_fixture(tmp_path, rows, wx_rows=wx))


@pytest.mark.parametrize("irr", [850, 0.3])
def test_irradiation_units_fail(tmp_path, irr):
    rows = [("05-06-2020 12:00", k, 1) for k in "abc"]
    with pytest.raises(ValueError, match="IRRADIATION"):
        _load(*_fixture(tmp_path, rows, wx_rows=[("2020-06-05 12:00:00", irr)]))


def test_heldout_start_utc():
    assert heldout_start_utc(load_validation_cfg().solar) == pd.Timestamp(
        "2020-05-31 18:30", tz="UTC"
    )


def test_dropout_stats(tmp_path):
    # bright rows (irr > 0.3): 12:00 and 12:15; a 0% zero, b 50%, c 100%
    rows = [
        ("05-06-2020 12:00", "a", 5),
        ("05-06-2020 12:00", "b", 0),
        ("05-06-2020 12:00", "c", 0),
    ]
    rows += [
        ("05-06-2020 12:15", "a", 5),
        ("05-06-2020 12:15", "b", 5),
        ("05-06-2020 12:15", "c", 0),
    ]
    _, st = _load(*_fixture(tmp_path, rows))
    assert st["zero_ac_daytime_pct_worst_inverter"] == 100.0
    assert st["zero_ac_daytime_pct_median_inverter"] == 50.0


def test_peak_anchor_ignores_heldout(tmp_path):
    rows = [(f"0{d}-06-2020 12:00", k, ac) for d, ac in ((4, 10), (5, 99)) for k in "abc"]
    wx = [("2020-06-04 12:00:00", 0.9), ("2020-06-05 12:00:00", 0.9)]
    g, w, vs = _fixture(
        tmp_path, rows, wx, span_local=(date(2020, 6, 4), date(2020, 6, 5)), heldout_start_local=date(2020, 6, 5)
    )
    _, st = _load(g, w, vs)
    assert st["peak_ac_kw"] == 30 and st["peak_ac_kw_all_rows"] == 297


def test_duplicate_inverter_rows_rejected(tmp_path):
    rows = [("05-06-2020 12:00", k, 1) for k in "abc"] + [("05-06-2020 12:00", "a", 1)]
    with pytest.raises(ValueError, match="duplicate"):
        _load(*_fixture(tmp_path, rows))


def test_nan_ac_drops_timestamp(tmp_path):
    rows = [("05-06-2020 12:00", "a", ""), ("05-06-2020 12:00", "b", 1), ("05-06-2020 12:00", "c", 1)]
    rows += [("05-06-2020 12:30", k, 1) for k in "abc"]
    df, st = _load(*_fixture(tmp_path, rows))
    assert len(df) == 1 and st["ts_partial_dropped"] == 1
