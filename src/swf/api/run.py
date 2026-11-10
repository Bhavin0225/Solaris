"""`python -m swf serve`: local API + built page, one uvicorn worker (one scheduler)."""

import argparse


def run(args: argparse.Namespace) -> int:
    import uvicorn

    from swf.core.paths import FRONTEND_DIST

    if not (FRONTEND_DIST / "index.html").exists():
        print("frontend/dist missing: run `npm --prefix frontend ci` and `npm --prefix frontend run build` first; the API still starts at /docs")

    uvicorn.run("swf.api.main:app", host=args.host, port=args.port, workers=1)
    return 0
