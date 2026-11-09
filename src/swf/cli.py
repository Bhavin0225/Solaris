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

    sub.add_parser("curve", help="build config/power_curve.csv from Kaggle T1.csv").set_defaults(
        handler=lambda a: _run("swf.physics.wind", a)
    )

    sub.add_parser("build-weather", help="raw cache -> canonical clean weather + data_notes tables").set_defaults(
        handler=lambda a: _run("swf.align.build", a)
    )
    sub.add_parser("simulate-energy", help="NASA weather -> simulated T1/T5 kW + physics notes").set_defaults(
        handler=lambda a: _run("swf.physics.simulate", a)
    )

    sub.add_parser("validate", help="physics validation vs Kaggle plants -> reports/validation + data_notes").set_defaults(
        handler=lambda a: _run("swf.validate.run", a)
    )

    sub.add_parser("features", help="feature spec hash + split ranges -> data_notes AUTO:features").set_defaults(
        handler=lambda a: _run("swf.features.run", a)
    )
    sub.add_parser("baselines", help="persistence, climatology, baseline 3 -> data/processed/predictions").set_defaults(
        handler=lambda a: _run("swf.evaluate.baselines", a)
    )
    ev = sub.add_parser(
        "evaluate", help="leaderboard + breakdowns -> reports/evaluation; test needs the frozen baseline-3 choice"
    )
    ev.add_argument("--split", choices=["val", "test", "all"], default="all")
    ev.add_argument("--final", action="store_true", help="select on validation, evaluate test once, write models/deployed/registry.json (refuses if models/deployed/test_started.json or registry.json exists; D-22, D-28)")
    ev.set_defaults(handler=lambda a: _run("swf.evaluate.report", a))

    sub.add_parser("train-lgbm", help="LightGBM residual models -> models/ + val predictions + models/registry.json").set_defaults(
        handler=lambda a: _run("swf.models.lgbm", a)
    )
    sub.add_parser("train-lstm", help="LSTM/GRU seq2seq residual models -> models/<rnn>/ + val predictions").set_defaults(
        handler=lambda a: _run("swf.models.seq", a)
    )
    tf = sub.add_parser("train-tft", help="darts TFT (D-19 time box): --timing-only, full run, or --stop write-up")
    g = tf.add_mutually_exclusive_group()
    g.add_argument("--timing-only", action="store_true", help="time one epoch + predict, write models/tft/timing.json")
    g.add_argument("--stop", action="store_true", help="write the stop attempt (timing, curves, reason) to docs/data_notes.md")
    tf.set_defaults(handler=lambda a: _run("swf.models.tft", a))
    sv = sub.add_parser("serve", help="run the local API + built page on 127.0.0.1 (one uvicorn worker)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(handler=lambda a: _run("swf.api.run", a))

    d = sub.add_parser("data",help="nasa + openmeteo all + kaggle")
    d.add_argument("--force", action="store_true")
    d.set_defaults(handler=_data)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.handler(args)
