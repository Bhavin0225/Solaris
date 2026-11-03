import numpy as np
import pandas as pd
import pytest

from swf.core.settings import load_validation_cfg
from swf.physics.common import RHO0, air_density
from swf.physics.wind import simulate_wind
from swf.validate.kaggle_wind import load_t1, simulate_t1, wind_metrics

HDR = "Date/Time,LV ActivePower (kW),Wind Speed (m/s),Theoretical_Power_Curve (KWh),Wind Direction (°)\n"
CURVE = pd.DataFrame({"speed_ms": [0.0, 5.0, 10.0, 25.0], "kw": [0.0, 500.0, 2000.0, 3600.0]})
WC = load_validation_cfg().wind


def _csv(tmp_path, rows, hdr=HDR):
    p = tmp_path / "T1.csv"
    p.write_text(hdr + "".join(f"{d},{lv},{ws},{th},0\n" for d, lv, ws, th in rows), encoding="utf-8-sig")
    return p


def test_load_parses(tmp_path):
    t = load_t1(_csv(tmp_path, [("01 02 2018 00:10", 5, 4.0, 6), ("01 02 2018 00:30", 7, 5.0, 8)]), WC)
    assert list(t.columns) == ["lv_kw", "ws", "theo_kw"]
    assert t.index[0] == pd.Timestamp("2018-02-01 00:10")
    assert len(t) == 2  # gap stays a gap


@pytest.mark.parametrize(
    "rows,hdr",
    [
        ([("01 02 2018 00:10", 1, 1, 1)], HDR.replace("Date/Time", "Time")),
        ([("2018-02-01 00:10", 1, 1, 1)], HDR),
        ([("01 02 2018 00:10", 1, 1, 1)] * 2, HDR),
        ([("01 02 2019 00:10", 1, 1, 1)], HDR),
    ],
)
def test_load_rejects(tmp_path, rows, hdr):
    with pytest.raises(ValueError):
        load_t1(_csv(tmp_path, rows, hdr), WC)


def test_simulate_matches_production(settings, tmp_path):
    t = load_t1(_csv(tmp_path, [("01 02 2018 00:10", 0, 5.0, 0), ("01 02 2018 00:20", 0, 7.5, 0)]), WC)
    df = pd.DataFrame({"ws_hub": t["ws"], "pressure": 1013.25, "temp": 15.0}, index=t.index)
    pd.testing.assert_series_equal(simulate_t1(t, settings, WC, CURVE), simulate_wind(df, settings, CURVE))
    assert abs((air_density(WC.pressure_hpa, WC.temp_c) / RHO0) ** (1 / 3) - 1) < 1e-5


def _frame(dates, lv, theo):
    return pd.DataFrame({"lv_kw": lv, "ws": 8.0, "theo_kw": theo}, index=pd.to_datetime(dates))


def test_slices_and_reference(settings):
    d = ["2018-01-05 00:00", "2018-10-18 23:50", "2018-10-19 00:00", "2018-12-31 23:50"]
    t = _frame(d, [1000.0] * 4, [1000.0, 1000.0 + 3600.0, 1000.0, 1000.0])
    sim = pd.Series([1000.0] * 4, index=t.index)
    sl = wind_metrics(t, sim, settings, WC)["slices"]
    assert (sl["full_year"]["n"], sl["ref_slice"]["n"], sl["jan_to_ref"]["n"]) == (4, 2, 2)
    assert sl["jan_to_ref"]["reference_nrmse_pct"] == pytest.approx(np.sqrt(3600**2 / 2) / 3600 * 100)
    assert sl["ref_slice"]["reference_nrmse_pct"] == 0


def test_gate_and_diagnostics(settings):
    t = _frame(["2018-01-05 00:00", "2018-11-01 00:00"], [1000.0, 1000.0], [1000.0, 1000.0])
    good = pd.Series([1000.0, 1000.0], index=t.index)
    m = wind_metrics(t, good, settings, WC)
    assert m["pass"] is True
    assert m["normalisation_kw"] == settings.wind.rated_kw
    assert m["availability_measured_pct"] == 0
    assert m["energy_ratio"] == pytest.approx(1 - settings.wind.availability_loss)
    worse = pd.Series([1100.0, 1100.0], index=t.index)
    assert wind_metrics(t, worse, settings, WC)["pass"] is False
    t2 = _frame(["2018-01-05 00:00", "2018-11-01 00:00"], [1000.0, 1000.0], [0.0, 0.0])
    assert wind_metrics(t2, pd.Series([1600.0, 1600.0], index=t.index), settings, WC)["pass"] is False
