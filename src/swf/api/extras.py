"""Read-only helpers for the site pages (D-43). Light imports only: stdlib, pandas, starlette, swf.core."""

import functools
import subprocess
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

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
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def resolve_registry(models_dir: Path) -> Path:
    """Same rule as refresh.default_registry_path (D-29), without importing swf.api.refresh."""
    p = Path(models_dir) / "deployed" / "registry.json"
    return p if p.exists() else Path(models_dir) / "registry.json"


class SPAStatic(StaticFiles):
    """Serve index.html for unknown non-/api paths so a reload on /performance works."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise
