"""Kaggle plant files via the kaggle CLI (subprocess). Credentials stay with the CLI; swf never touches them."""

import argparse
import logging
import shutil
import subprocess
from pathlib import Path

from swf.core import paths
from swf.core.settings import Settings, load_settings

log = logging.getLogger(__name__)
DATASET_URL = "https://www.kaggle.com/datasets/{slug}"


def _rows(p: Path) -> int:
    with p.open("rb") as f:
        return max(sum(1 for _ in f) - 1, 0)  # lines minus header; counts a last line without newline


def check_files(kdir: Path, expected: dict[str, int], tol: float) -> list[str]:
    problems = []
    for name, exp in expected.items():
        p = kdir / name
        if not p.is_file():
            problems.append(f"missing: {name}")
            continue
        n = _rows(p)
        if abs(n - exp) > tol * exp:
            problems.append(f"{name}: {n} rows, expected {exp} +/- {tol:.0%}")
    return problems


def manual_steps(s: Settings, kdir: Path) -> str:
    names = "\n".join(f"    {n}" for n in s.kaggle.expected_rows)
    return (
        "Manual Kaggle download needed:\n"
        f"  1. Sign in and click Download on both datasets:\n"
        f"     {DATASET_URL.format(slug=s.kaggle.solar_slug)}\n"
        f"     {DATASET_URL.format(slug=s.kaggle.wind_slug)}\n"
        f"  2. Extract both ZIPs flat (no sub-folders) into: {kdir}\n"
        f"  3. Expected files:\n{names}\n"
        "  (CLI auth: token at ~/.kaggle/kaggle.json or the KAGGLE_API_TOKEN environment variable)"
    )


def download(s: Settings, kdir: Path, *, runner=subprocess.run, which=shutil.which) -> bool:
    exe = which("kaggle")
    if not exe:
        log.error("kaggle executable not found on PATH")
        return False
    kdir.mkdir(parents=True, exist_ok=True)
    for slug in (s.kaggle.solar_slug, s.kaggle.wind_slug):
        try:
            r = runner(
                [exe, "datasets", "download", "-d", slug, "-p", str(kdir), "--unzip", "-q"],
                capture_output=True,
                text=True,
                timeout=1800,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            log.error("kaggle download of %s failed: %s", slug, e)
            return False
        if r.returncode != 0:
            log.error("kaggle download of %s failed (exit %s): %s", slug, r.returncode, (r.stderr or "")[:500])
            return False
    return True


def require_kaggle_files(s: Settings, kdir: Path | None = None) -> dict[str, Path]:
    kdir = kdir or paths.RAW_DIR / "kaggle"
    problems = check_files(kdir, s.kaggle.expected_rows, s.kaggle.row_tolerance)
    if problems:
        raise SystemExit(manual_steps(s, kdir) + "\n\nProblems:\n  " + "\n  ".join(problems))
    return {n: kdir / n for n in s.kaggle.expected_rows}


def run(args: argparse.Namespace) -> int:
    s = load_settings()
    kdir = paths.RAW_DIR / "kaggle"
    k = s.kaggle
    problems = check_files(kdir, k.expected_rows, k.row_tolerance)
    if problems and not args.check:
        if download(s, kdir):
            problems = check_files(kdir, k.expected_rows, k.row_tolerance)
    if problems:
        print("\n".join(problems))
        print(manual_steps(s, kdir))
        return 1
    print(f"{'file':40} {'rows':>8} {'expected':>8}")
    for n, exp in k.expected_rows.items():
        print(f"{n:40} {_rows(kdir / n):>8} {exp:>8}")
    return 0
