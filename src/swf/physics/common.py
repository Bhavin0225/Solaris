"""Shared sun/atmosphere helpers. Radiation labels are interval starts, so sun geometry uses label + 30 min."""

import numpy as np
import pandas as pd
import pvlib

RHO0 = 1.225
R_DRY = 287.05
KPA_TO_HPA = 10.0  # NASA PS is kPa; canonical pressure is hPa
ALPHA_MIN = 0.05  # PRD 5.1 shear-exponent bounds
ALPHA_MAX = 0.40
ALPHA_DEFAULT = 0.143  # PRD 5.1 fallback when the lower-level speed is ~calm
WS_ALPHA_MIN = 0.5


def location(s):
    return pvlib.location.Location(
        s.site.latitude, s.site.longitude, tz="UTC", altitude=s.site.elevation_m
    )


def midpoints(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index + pd.Timedelta(minutes=30)


def solar_position(index, s) -> pd.DataFrame:
    sp = location(s).get_solarposition(midpoints(index))
    return sp.set_axis(index)


def is_night(index, s) -> pd.Series:
    return solar_position(index, s)["zenith"] > 90


def clearsky(index, s) -> pd.DataFrame:
    cs = location(s).get_clearsky(midpoints(index), model="ineichen")
    return cs.set_axis(index)


def hub_wind(ws_low, z_low, ws_up, z_up, z_hub):
    """Power-law extrapolation from two levels (PRD 5.1), alpha clipped to [0.05, 0.40]."""
    with np.errstate(divide="ignore", invalid="ignore"):
        alpha = np.log(ws_up / ws_low) / np.log(z_up / z_low)
        alpha = np.clip(alpha, ALPHA_MIN, ALPHA_MAX)
        alpha = np.where(np.asarray(ws_low) < WS_ALPHA_MIN, ALPHA_DEFAULT, alpha)
        out = ws_up * (z_hub / z_up) ** alpha
    if isinstance(ws_up, pd.Series):
        return pd.Series(np.asarray(out), index=ws_up.index, name=ws_up.name)
    return out


def air_density(pressure_hpa, temp_c):
    """Dry-air density in kg/m3; humidity term omitted (<1% effect)."""
    return pressure_hpa * 100 / (R_DRY * (temp_c + 273.15))
