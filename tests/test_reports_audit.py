"""Success criterion 3: every evaluation figure/table exists, and the site only serves audited figures."""

import pytest

from swf.api.extras import FIGURES
from swf.core.paths import REPO_ROOT

REPORTS = REPO_ROOT / "reports"

REQUIRED = {
    "validation scatters": [
        "validation/solar_plant_1_scatter.png",
        "validation/solar_plant_2_scatter.png",
        "validation/wind_scatter.png",
        "validation/metrics.json",
    ],
    "leaderboard": ["evaluation/leaderboard.csv", "evaluation/breakdown.csv"],
    "skill charts": [
        "evaluation/skill_val.png",
        "evaluation/skill_heatmap_test.png",
        "evaluation/skill_heatmap_test.csv",
    ],
    "error by horizon": ["evaluation/rmse_by_horizon_val.png"],
    "probabilistic metrics": [
        "evaluation/prob_metrics.csv",
        "evaluation/reliability_val.png",
        "evaluation/reliability_test.png",
    ],
    "interpretability": [
        "evaluation/lgbm_gain_importance.png",
        "evaluation/lgbm_gain_importance.csv",
        "evaluation/tft_variable_selection.png",
        "evaluation/tft_variable_selection.csv",
        "evaluation/tft_training_curves.png",
    ],
    "other": [
        "evaluation/gfs_bias_val.csv",
        "evaluation/gfs_bias_val.png",
        "evaluation/wind_cf.csv",
        "evaluation/wind_cf.png",
    ],
}
ALL = [p for paths in REQUIRED.values() for p in paths]


@pytest.mark.parametrize("path", ALL)
def test_required_report_file_exists(path):
    f = REPORTS / path
    assert f.exists() and f.stat().st_size > 0, f"missing or empty: reports/{path}"


def test_site_figures_are_audited():
    assert set(FIGURES.values()) <= set(ALL)
