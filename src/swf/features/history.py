"""Target-space history (FEAT-03): the one chain used for ERA5 history in training, Open-Meteo past_days at serving, and GFS in baseline 3."""

import pandas as pd

from swf.align.consistency import apply_correction
from swf.physics.constraints import TARGET_COLS, enforce
from swf.physics.simulate import simulate

TARGETS = tuple(TARGET_COLS.values())


def history_frame(canon: pd.DataFrame, s, curve, coefs=None) -> pd.DataFrame:
    """Canonical weather -> (t1_kw, rh, ghi, ws10, t5_kw). coefs=None means raw (no correction)."""
    w = apply_correction(canon, coefs, s) if coefs is not None else canon
    energy = simulate(w, s, curve)
    out = pd.concat(
        [energy["t1_kw"], w[["rh", "ghi", "ws10"]], energy["t5_kw"]], axis=1
    )[list(TARGETS)]
    return enforce(out.astype("float64"), s)
