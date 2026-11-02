"""`python -m swf <command>` entry point. Handlers lazy-import so the serving set never loads torch."""

import argparse
import importlib
import logging
import time

OPENMETEO_APIS = ["era5", "historical", "previous", "live", "all"]


def check_gpu() -> int:
    try:
        import torch
    except ImportError:
        print("torch not installed: run uv sync --extra train")
        return 1
    if not torch.cuda.is_available():
        print(f"FAIL: CUDA not available (torch {torch.__version__}, cuda {torch.version.cuda})")
        return 1
    print(f"torch {torch.__version__} cuda {torch.version.cuda} device {torch.cuda.get_device_name(0)}")
    return 0


def _run(module: str, args: argparse.Namespace) -> int:
    return importlib.import_module(module).run(args)


def _data(args: argparse.Namespace) -> int:
    force = args.force
    steps = [
        ("swf.fetch.nasa", argparse.Namespace(force=force)),
        ("swf.fetch.openmeteo", argparse.Namespace(api="all", force=force)),
        ("swf.fetch.kaggle", argparse.Namespace(check=False)),
    ]
    return max(_run(m, a) for m, a in steps)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="swf", description="Solar-wind forecast pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("check-gpu", help="assert CUDA is visible and print the device").set_defaults(
        handler=lambda a: check_gpu()
    )

    fetch = sub.add_parser("fetch", help="download raw weather data")
    fsub = fetch.add_subparsers(dest="source", required=True)
    n = fsub.add_parser("nasa", help="NASA POWER hourly")
    n.add_argument("--force", action="store_true")
    n.set_defaults(handler=lambda a: _run("swf.fetch.nasa", a))
    o = fsub.add_parser("openmeteo", help="Open-Meteo APIs")
    o.add_argument("api", choices=OPENMETEO_APIS)
    o.add_argument("--force", action="store_true")
    o.set_defaults(handler=lambda a: _run("swf.fetch.openmeteo", a))

    k = sub.add_parser("kaggle", help="download/check Kaggle plant files")
    k.add_argument("--check", action="store_true")
    k.set_defaults(handler=lambda a: _run("swf.fetch.kaggle", a))

    pr = sub.add_parser("probe", help="probe API coverage (network)")
    pr.add_argument("--force", action="store_true")
    pr.set_defaults(handler=lambda a: _run("swf.coverage.probe", a))

    sub.add_parser("coverage", help="write the coverage report").set_defaults(
        handler=lambda a: _run("swf.coverage.report", a)
    )

    d = sub.add_parser("data", help="nasa + openmeteo all + kaggle")
    d.add_argument("--force", action="store_true")
    d.set_defaults(handler=_data)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.handler(args)
