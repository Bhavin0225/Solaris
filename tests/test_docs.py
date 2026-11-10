"""String checks that keep README.md and docs/viva.md consistent with the repo."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
VIVA = (ROOT / "docs" / "viva.md").read_text(encoding="utf-8")


def test_readme_commands():
    for s in ["uv sync --extra train", "python -m swf data", "python -m swf train",
              "python -m swf evaluate", "python -m swf serve",
              "npm --prefix frontend run build", "http://127.0.0.1:8000"]:
        assert s in README


def test_readme_guard_wording():
    for s in ["--accept-stale-results", "stable_by_utc", "hard_stop_utc", "SKIPPED"]:
        assert s in README
    assert "bit-identical" not in README.replace("not bit-identical", "")


def test_readme_credits():
    for s in ["Open-Meteo", "CC BY 4.0", "NASA POWER", "Kaggle", "MIT"]:
        assert s in README


def test_readme_results_match_leaderboard():
    with open(ROOT / "reports/evaluation/leaderboard.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == "test" and r["model"] == "tft"]
    assert len(rows) == 5
    for r in rows:
        assert f"{float(r['skill_vs_baseline3']):+.1%}" in README, r["target"]


def test_readme_screenshots_exist():
    paths = re.findall(r"docs/screenshots/[\w.-]+\.png", README)
    assert len(paths) >= 3
    for p in paths:
        assert (ROOT / p).exists(), p


def test_viva_sections():
    for s in ["Pre-viva checklist", "Demo script", "Code walkthrough", "Likely questions",
              "127.0.0.1:8000", "evaluate --final", "--accept-stale-results", "not bit-identical"]:
        assert s in VIVA
    assert VIVA.index("Pre-viva checklist") < VIVA.index("Demo script")
    assert len(re.findall(r"(?m)^### Q", VIVA)) >= 10
