"""FastAPI app: eleven sync read-only endpoints (cache, reports, interim data), hourly refresh in a background scheduler (API-01..07, D-43)."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from swf.api import db
from swf.api.extras import (
    FIGURES,
    SPAStatic,
    correlation,
    git_short_sha,
    read_csv_rows,
    resolve_registry,
    weather_points,
)
from swf.api.schemas import (
    UNITS,
    BuildInfo,
    Correlation,
    CoverageRow,
    Forecast,
    Health,
    HeatmapRow,
    History,
    HistoryPoint,
    HorizonRow,
    KaggleInfo,
    Metrics,
    MetricsRow,
    Performance,
    Point,
    SiteInfo,
    Summary,
    TargetForecast,
    Weather,
    WeatherPoint,
    WindCfRow,
)
from swf.api.summary import ist_day_window, summarize
from swf.core.paths import (
    DB_PATH,
    FRONTEND_DIST,
    INTERIM_DIR,
    MODELS_DIR,
    RAW_DIR,
    REPORTS_DIR,
)
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
    reports_dir: Path | None = None,
    interim_dir: Path | None = None,
    raw_root: Path | None = None,
    registry_path: Path | None = None,
    models_dir: Path | None = None,
) -> FastAPI:
    db_path = db_path or DB_PATH
    reports_dir = reports_dir or REPORTS_DIR
    interim_dir = interim_dir or INTERIM_DIR
    raw_root = raw_root or RAW_DIR
    models_dir = models_dir or MODELS_DIR
    leaderboard_path = leaderboard_path or reports_dir / "evaluation" / "leaderboard.csv"
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
    def forecast_summary(day: Literal["today", "tomorrow"] = "tomorrow"):
        run_time, rows = _forecast(hmax)
        _, stale = _age(db.read_meta(db_path))
        start, end = ist_day_window(datetime.now(UTC), s.site.display_timezone, day)
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
        return Metrics(rows=[MetricsRow(**r) for r in read_csv_rows(leaderboard_path, _STR, _INT)])

    @app.get("/api/weather", response_model=Weather)
    def weather():
        # lazy: keeps httpx out of `import swf.api.main`
        from swf.fetch.openmeteo import live_path

        run_time = db.read_meta(db_path).get("run_time")
        if run_time is None:
            raise HTTPException(503, "no forecast cached yet")
        origin = datetime.fromisoformat(run_time)
        stamp = origin + timedelta(hours=1)  # live file is named after the refresh wall clock = run_time + 1 h
        path = live_path(s, raw_root, stamp)
        if not path.exists():
            raise HTTPException(503, "weather not cached yet")
        tz = ZoneInfo(s.site.display_timezone)
        midnight = datetime.combine(stamp.astimezone(tz).date(), time(), tzinfo=tz).astimezone(UTC)
        start = midnight.replace(minute=0)  # hour label containing local midnight (IST is UTC+5:30)
        pts = weather_points(path.read_bytes(), s, start, origin + timedelta(hours=hmax))
        return Weather(
            display_timezone=s.site.display_timezone, run_time=run_time, points=[WeatherPoint(**p) for p in pts]
        )

    corr_cache: dict = {}

    @app.get("/api/correlation", response_model=Correlation)
    def correlation_matrix():
        if not corr_cache:  # cache only a success
            try:
                corr_cache.update(correlation(interim_dir))
            except FileNotFoundError:
                raise HTTPException(503, "interim data not built yet") from None
        return Correlation(**corr_cache)

    @app.get("/api/performance", response_model=Performance)
    def performance():
        ev = reports_dir / "evaluation"
        pick = lambda cls, r: cls(**{k: r[k] for k in cls.model_fields})
        prob = read_csv_rows(ev / "prob_metrics.csv", {"split", "target", "model"}, {"n"})
        brk_str = {"split", "target", "model", "horizon", "season", "norm_kind", "feature_spec_hash"}
        brk = read_csv_rows(ev / "breakdown.csv", brk_str, {"n"})
        heat = read_csv_rows(ev / "skill_heatmap_test.csv", {"target", "model", "season"}, {"horizon"})
        cf = read_csv_rows(ev / "wind_cf.csv", {"season", "model"}, {"n"})
        return Performance(
            coverage=[pick(CoverageRow, r) for r in prob if r["split"] == "test"],
            horizon=[
                pick(HorizonRow, {**r, "horizon": int(r["horizon"])})
                for r in brk if r["split"] == "test" and r["season"] == "all" and r["horizon"] != "all"
            ],
            heatmap=[pick(HeatmapRow, r) for r in heat],
            wind_cf=[pick(WindCfRow, r) for r in cf],
        )  # fmt: skip

    @app.get("/api/site", response_model=SiteInfo)
    def site():
        return SiteInfo(site=s.site, solar=s.solar, wind=s.wind)

    @app.get("/api/build", response_model=BuildInfo)
    def build():
        try:
            reg = json.loads((registry_path or resolve_registry(models_dir)).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            reg = {}
        run_time = db.read_meta(db_path).get("run_time")
        return BuildInfo(
            git_sha=git_short_sha(), registry_git_sha=reg.get("git_sha"), schema_version=reg.get("schema_version"),
            final_split=reg.get("final_split"),
            models={t: v["runtime"] for t, v in reg.get("targets", {}).items() if "runtime" in v},
            # D-44: end of the last observed hour (run_time is that hour's interval-start label)
            data_through=datetime.fromisoformat(run_time) + timedelta(hours=1) if run_time else None,
            kaggle=KaggleInfo(solar_slug=s.kaggle.solar_slug, wind_slug=s.kaggle.wind_slug),
        )  # fmt: skip

    @app.get("/api/figures/{name}")
    def figure(name: str):
        rel = FIGURES.get(name)  # allowlist lookup only; the request never becomes a path (T-07-01)
        if rel is None or not (reports_dir / rel).is_file():
            raise HTTPException(404, "unknown figure")
        return FileResponse(reports_dir / rel, media_type="image/png")

    # mounted last so /api routes win (Pitfall 9)
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", SPAStatic(directory=static_dir, html=True), name="site")
    return app


app = create_app()
