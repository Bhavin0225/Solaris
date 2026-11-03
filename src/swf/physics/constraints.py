"""PRD 6 physical bounds, applied to every output (simulated targets now, model predictions in Phases 4-6)."""

import pandas as pd

from swf.physics.common import is_night
from swf.physics.solar import ac_cap_kw

TARGET_COLS = {"t1": "t1_kw", "t2": "rh", "t3": "ghi", "t4": "ws10", "t5": "t5_kw"}


def enforce(df: pd.DataFrame, s) -> pd.DataFrame:
    out = df.copy()
    night = is_night(out.index, s)
    bounds = {"t1_kw": (0, ac_cap_kw(s)), "t5_kw": (0, s.wind.rated_kw), "rh": (0, 100),
              "ghi": (0, None), "ws10": (0, None), "ws_hub": (0, None)}  # fmt: skip
    for col, (lo, hi) in bounds.items():
        if col in out:
            out[col] = out[col].clip(lo, hi)
    for col in ("t1_kw", "ghi"):
        if col in out:
            out.loc[night & out[col].notna(), col] = 0.0
    return out
