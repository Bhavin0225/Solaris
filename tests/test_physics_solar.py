import numpy as np
import pytest
from synth import canon_frame

from swf.physics.common import is_night
from swf.physics.solar import ac_cap_kw, pdc0_w, poa_global, simulate_solar


def cfg(s, **kw):
    return s.model_copy(update={"solar": s.solar.model_copy(update=kw)})


def test_cap_derived(settings):
    assert pdc0_w(settings) == pytest.approx(833333.33, rel=1e-6)
    assert ac_cap_kw(settings) == pytest.approx(800.0)
    assert ac_cap_kw(cfg(settings, dc_ac_ratio=1.25)) == pytest.approx(768.0)


def test_clearsky_day(settings):
    df = canon_frame("2024-03-21", 1, settings)
    p = simulate_solar(df, settings)
    assert p.name == "t1_kw" and p.index.equals(df.index)
    assert (p[is_night(df.index, settings)] == 0.0).all()
    assert 700 <= p.max() <= 800


def test_saturates_at_cap(settings):
    s = cfg(settings, loss_pct=0)
    df = canon_frame("2024-03-21", 1, s)
    df[["ghi", "dni", "dhi"]] *= 1.3
    p = simulate_solar(df, s)
    assert p.max() == pytest.approx(ac_cap_kw(s)) and p.max() <= ac_cap_kw(s) + 1e-9


def test_loss_from_config(settings):
    df = canon_frame("2024-03-21", 1, settings)
    lo = simulate_solar(df, cfg(settings, loss_pct=14)).sum()
    hi = simulate_solar(df, cfg(settings, loss_pct=20)).sum()
    assert hi < lo


def test_south_vs_north(settings):
    df = canon_frame("2024-12-21", 1, settings)
    south = poa_global(df, cfg(settings, azimuth_pvlib_deg=180)).sum()
    north = poa_global(df, cfg(settings, azimuth_pvlib_deg=0)).sum()
    assert south / north > 1.3


def test_nan_daytime_propagates(settings):
    df = canon_frame("2024-03-21", 1, settings)
    t = df.index[12]
    df.loc[t, ["ghi", "dni", "dhi"]] = np.nan
    p = simulate_solar(df, settings)
    assert p.isna().sum() == 1 and np.isnan(p[t])
