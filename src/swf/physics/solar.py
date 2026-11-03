"""pvlib solar chain: Perez POA -> Faiman cell temp -> PVWatts DC (loss on DC side) -> PVWatts inverter."""

import numpy as np
import pandas as pd
from pvlib import inverter, irradiance, pvsystem, temperature

from swf.physics.common import location, midpoints, solar_position


def pdc0_w(s) -> float:
    """Inverter DC input limit in W: dc_kwp / dc_ac_ratio."""
    return s.solar.dc_kwp * 1000 / s.solar.dc_ac_ratio


def ac_cap_kw(s) -> float:
    """AC clip in kW: eta_inv_nom x pdc0. Single source for inverter and constraint layer."""
    return pdc0_w(s) * s.solar.eta_inv_nom / 1000


def poa_global(df: pd.DataFrame, s) -> pd.Series:
    """Plane-of-array irradiance (W/m2): 0 at night, NaN where daytime inputs are NaN."""
    mid = midpoints(df.index)
    sp = solar_position(df.index, s).set_axis(mid)
    ghi, dni, dhi = (
        pd.Series(df[c].to_numpy(), index=mid) for c in ("ghi", "dni", "dhi")
    )
    am = location(s).get_airmass(solar_position=sp)["airmass_relative"]
    poa = irradiance.get_total_irradiance(
        s.solar.tilt_deg, s.solar.azimuth_pvlib_deg, sp["apparent_zenith"], sp["azimuth"],
        dni, ghi, dhi, dni_extra=irradiance.get_extra_radiation(mid), airmass=am,
        albedo=s.solar.albedo, model=s.solar.transposition,
    )["poa_global"]  # fmt: skip
    poa = poa.where(~(sp["zenith"] > 90), 0.0).clip(
        lower=0
    )  # zero only at night, never a blanket fillna
    return poa.set_axis(df.index)


def simulate_solar(df: pd.DataFrame, s) -> pd.Series:
    """AC output in kW on df.index (name t1_kw)."""
    poa = poa_global(df, s)
    tc = temperature.faiman(poa, df["temp"], df["ws10"])
    dc = pvsystem.pvwatts_dc(poa, tc, s.solar.dc_kwp * 1000, s.solar.gamma_pdc)
    dc = dc * (1 - s.solar.loss_pct / 100)
    ac = inverter.pvwatts(dc, pdc0_w(s), eta_inv_nom=s.solar.eta_inv_nom) / 1000
    night = solar_position(df.index, s)["zenith"] > 90
    ac = ac.where(~night, 0.0)
    return pd.Series(np.asarray(ac), index=df.index, name="t1_kw")
