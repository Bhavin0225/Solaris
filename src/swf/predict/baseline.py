"""Live baseline 3 (Open-Meteo + physics) and its runtime; same chain as the Phase 4 history frame."""

import numpy as np
import pandas as pd

from swf.align.adapters import openmeteo_canon
from swf.align.clean import clean
from swf.features.history import history_frame
from swf.features.spec import TARGETS


def live_tables(raw: bytes, s, coefs, curve, choice: dict) -> pd.DataFrame:
    """Baseline 3 over the whole live canon index (forecast window and past-days history)."""
    canon = clean(openmeteo_canon(raw, s), s, source="live")[0]
    corrected = history_frame(canon, s, curve, coefs)
    raw_tab = history_frame(canon, s, curve, None)
    return pd.DataFrame({t: (corrected if choice[t] == "corrected" else raw_tab)[t] for t in TARGETS}, index=canon.index)


def predict_p50(entry: dict, X: pd.DataFrame, b3: np.ndarray, target: str, models_root) -> np.ndarray:
    return np.asarray(b3, dtype=float)
