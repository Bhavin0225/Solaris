"""Read-only helpers for the site pages (D-43). Light imports only: stdlib, pandas, starlette, swf.core."""

import csv
import functools
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from swf.api import db
from swf.core.paths import REPO_ROOT

# name -> path under reports/. The only files /api/figures may serve (T-07-01).
FIGURES = {
    "solar_plant_1_scatter": "validation/solar_plant_1_scatter.png",
    "solar_plant_2_scatter": "validation/solar_plant_2_scatter.png",
    "wind_scatter": "validation/wind_scatter.png",
    "reliability_test": "evaluation/reliability_test.png",
    "wind_cf": "evaluation/wind_cf.png",
}


@functools.cache
def git_short_sha() -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def resolve_registry(models_dir: Path) -> Path:
    """Same rule as refresh.default_registry_path (D-29), without importing swf.api.refresh."""
    p = Path(models_dir) / "deployed" / "registry.json"
    return p if p.exists() else Path(models_dir) / "registry.json"


CORR_COLS = ["t1_kw", "t5_kw", "ghi", "rh", "ws10"]


def read_csv_rows(path: Path, str_cols: set[str], int_cols: set[str] = frozenset()) -> list[dict]:
    """CSV -> dicts: '' -> None, str_cols kept, int_cols int, rest float. Missing file -> []."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [
            {k: (None if v == "" else v if k in str_cols else int(float(v)) if k in int_cols else float(v)) for k, v in r.items()}
            for r in csv.DictReader(f)
        ]


def weather_points(raw: bytes, s, start: datetime, end: datetime) -> list[dict]:
    # lazy: pvlib stays out of `import swf.api.main`
    from swf.align.adapters import openmeteo_canon
    from swf.physics.common import is_night

    c = openmeteo_canon(raw, s)[["temp", "cloud", "precip"]].loc[start:end]
    day = ~is_night(c.index, s)
    c = c.astype(object).where(c.notna(), None)
    return [{"time": db.iso(t), **r, "is_day": bool(d)} for (t, r), d in zip(c.to_dict("index").items(), day, strict=True)]


def correlation(interim_dir: Path) -> dict:
    """Pearson matrix over the evaluation truth (simulated energy + NASA weather). FileNotFoundError if absent."""
    e = pd.read_parquet(Path(interim_dir) / "energy_sim.parquet", columns=["t1_kw", "t5_kw"])
    w = pd.read_parquet(Path(interim_dir) / "weather_nasa.parquet", columns=["ghi", "rh", "ws10"])
    df = e.join(w, how="inner").dropna()[CORR_COLS]
    return {
        "targets": CORR_COLS,
        "matrix": df.corr().to_numpy().tolist(),
        "period_start": df.index.min().to_pydatetime(),
        "period_end": df.index.max().to_pydatetime(),
        "n": len(df),
    }


class SPAStatic(StaticFiles):
    """Serve index.html for unknown non-/api paths so a reload on /performance works."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise
