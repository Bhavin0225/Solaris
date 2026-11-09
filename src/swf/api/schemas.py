"""Pydantic response models. Timestamps are AwareDatetime so every JSON time is UTC with Z."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

from swf.core.settings import Site, SolarCfg, WindCfg

UNITS = {"t1_kw": "kW", "rh": "%", "ghi": "W/m2", "ws10": "m/s", "t5_kw": "kW"}


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(_Out):
    time: AwareDatetime
    p10: float | None
    p50: float | None
    p90: float | None


class TargetForecast(_Out):
    unit: str
    model: str
    points: list[Point]


class Forecast(_Out):
    run_time: AwareDatetime
    stale: bool
    age_minutes: int
    display_timezone: str
    targets: dict[str, TargetForecast]


class Health(_Out):
    status: Literal["ok", "stale", "empty"]
    last_success: AwareDatetime | None
    run_time: AwareDatetime | None
    stale: bool
    age_minutes: int | None


class Summary(_Out):
    window_start: AwareDatetime
    window_end: AwareDatetime
    display_timezone: str
    n_hours: int
    solar_kwh: float
    wind_kwh: float
    peak_hour: AwareDatetime | None
    mean_rh: float | None
    max_wind: float | None
    run_time: AwareDatetime
    stale: bool


class HistoryPoint(_Out):
    time: AwareDatetime
    value: float | None


class History(_Out):
    days: int
    targets: dict[str, list[HistoryPoint]]


class MetricsRow(_Out):
    split: str
    target: str
    model: str
    norm_kind: str | None
    feature_spec_hash: str | None
    n_own: int | None
    n_shared: int | None
    rmse_own: float | None
    shared_frac: float | None
    mae: float | None
    rmse: float | None
    mbe: float | None
    nrmse_pct: float | None
    norm: float | None
    skill_vs_baseline3: float | None
    skill_vs_persistence: float | None


class Metrics(_Out):
    rows: list[MetricsRow]


class KaggleInfo(_Out):
    solar_slug: str
    wind_slug: str


class BuildInfo(_Out):
    git_sha: str | None
    registry_git_sha: str | None
    schema_version: int | None
    final_split: str | None
    models: dict[str, str]
    data_through: AwareDatetime | None
    kaggle: KaggleInfo


class SiteInfo(_Out):
    site: Site
    solar: SolarCfg
    wind: WindCfg
