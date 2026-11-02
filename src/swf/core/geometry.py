def to_openmeteo_azimuth(azimuth_pvlib_deg: float) -> float:
    """pvlib: 180 = south, 90 = east. Open-Meteo: 0 = south, -90 = east, +90 = west."""
    return (azimuth_pvlib_deg % 360) - 180
