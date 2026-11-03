"""Shared error metrics for solar and wind validation."""

import numpy as np


def error_stats(sim, act, norm: float) -> dict:
    """RMSE/MAE/MBE on complete pairs; nRMSE = RMSE / norm * 100."""
    sim, act = np.asarray(sim, float), np.asarray(act, float)
    m = ~np.isnan(sim) & ~np.isnan(act)
    sim, act = sim[m], act[m]
    rmse = float(np.sqrt(np.mean((sim - act) ** 2)))
    return {
        "n": int(m.sum()),
        "rmse_kw": rmse,
        "mae_kw": float(np.mean(np.abs(sim - act))),
        "mbe_pct": float(np.mean(sim - act) / np.mean(act) * 100),
        "nrmse_pct": rmse / norm * 100,
    }
