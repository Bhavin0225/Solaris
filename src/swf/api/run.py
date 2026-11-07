"""`python -m swf serve`: local API + built page, one uvicorn worker (one scheduler)."""

import argparse


def run(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("swf.api.main:app", host=args.host, port=args.port, workers=1)
    return 0
