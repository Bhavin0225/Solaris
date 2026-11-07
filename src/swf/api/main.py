"""FastAPI app: six sync endpoints over the SQLite cache, hourly refresh in a background scheduler (API-01..07)."""

import csv
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from swf.api import db
from swf.api.schemas import (
    UNITS,
    Forecast,
    Health,
    History,
    HistoryPoint,
    Metrics,
    MetricsRow,
    Point,
    SiteInfo,
    Summary,
    TargetForecast,
)
from swf.api.summary import ist_day_window, summarize
from swf.core.paths import DB_PATH, FRONTEND_DIST, REPORTS_DIR
from swf.core.settings import load_features_cfg, load_settings

STALE_AFTER = timedelta(hours=2)  # D-11
REFRESH_HOURS = 1  # API-02
_INT = {"n_own", "n_shared"}
_STR = {"split", "target", "model", "norm_kind", "feature_spec_hash"}


def _age(meta: dict) -> tuple[int | None, bool]:
    if "last_success" not in meta:
        return None, False
    delta = datetime.now(UTC) - datetime.fromisoformat(meta["last_success"])
    return int(delta.total_seconds() // 60), delta > STALE_AFTER


def create_app(
    db_path: Path | None = None,
    *,
    start_scheduler: bool = True,
    refresh_fn=None,
    static_dir: Path | None = FRONTEND_DIST,
    leaderboard_path: Path | None = None,
) -> FastAPI:
    db_path = db_path or DB_PATH
    leaderboard_path = leaderboard_path or REPORTS_DIR / "evaluation" / "leaderboard.csv"
    s = load_settings()
    hmax = load_features_cfg().horizon_max

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        fn = refresh_fn
        if fn is None:
            from swf.api.refresh import refresh as fn
        sched = BackgroundScheduler(timezone="UTC")
        # next_run_time=now: first refresh runs at once in the scheduler thread, cache is served meanwhile (D-10)
        sched.add_job(
            fn, "interval", hours=REFRESH_HOURS, id="refresh", max_instances=1, coalesce=True,
            next_run_time=datetime.now(UTC), kwargs={"db_path": db_path},
        )  # fmt: skip
        sched.start()
        app.state.scheduler = sched
        try:
            yield
        finally:
            sched.shutdown(wait=False)

    app = FastAPI(title="Solar-Wind Forecast", lifespan=lifespan if start_scheduler else None)

    def _forecast(hours: int):
        run_time, rows = db.read_forecast(db_path, hours)
        if run_time is None:
            raise HTTPException(503, "no forecast cached yet; first refresh pending")
        return run_time, rows

    @app.get("/api/health", response_model=Health)
    def health():
        meta = db.read_meta(db_path)
        age, stale = _age(meta)
        status = "empty" if age is None else "stale" if stale else "ok"
        return Health(
            status=status, last_success=meta.get("last_success"), run_time=meta.get("run_time"),
            stale=stale, age_minutes=age,
        )  # fmt: skip

    @app.get("/api/forecast", response_model=Forecast)
    def forecast(hours: int = Query(hmax, ge=1, le=hmax)):
        run_time, rows = _forecast(hours)
        age, stale = _age(db.read_meta(db_path))
        targets: dict[str, TargetForecast] = {}
        for r in rows:
            tf = targets.setdefault(r["target"], TargetForecast(unit=UNITS[r["target"]], model=r["model"], points=[]))
            tf.points.append(Point(time=r["target_time"], p10=r["p10"], p50=r["p50"], p90=r["p90"]))
        return Forecast(
            run_time=run_time, stale=stale, age_minutes=age or 0,
            display_timezone=s.site.display_timezone, targets=targets,
        )  # fmt: skip

    @app.get("/api/forecast/summary", response_model=Summary)
    def forecast_summary():
        run_time, rows = _forecast(hmax)
        _, stale = _age(db.read_meta(db_path))
        start, end = ist_day_window(datetime.now(UTC), s.site.display_timezone)
        return Summary(
            window_start=start, window_end=end, display_timezone=s.site.display_timezone,
            run_time=run_time, stale=stale, **summarize(rows, start, end),
        )  # fmt: skip

    @app.get("/api/history", response_model=History)
    def history(days: int = Query(7, ge=1, le=7)):
        h = db.read_history(db_path, days)
        return History(days=days, targets={t: [HistoryPoint(time=ts, value=v) for ts, v in pts] for t, pts in h.items()})

    @app.get("/api/metrics", response_model=Metrics)
    def metrics():
        if not leaderboard_path.exists():
            return Metrics(rows=[])
        with leaderboard_path.open(newline="", encoding="utf-8") as f:
            rows = []
            for r in csv.DictReader(f):
                row = {k: (None if v == "" else v if k in _STR else int(float(v)) if k in _INT else float(v)) for k, v in r.items()}
                rows.append(MetricsRow(**row))
        return Metrics(rows=rows)

    @app.get("/api/site", response_model=SiteInfo)
    def site():
        return SiteInfo(site=s.site, solar=s.solar, wind=s.wind)

    # mounted last so /api routes win (Pitfall 9)
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="site")
    return app


app = create_app()
