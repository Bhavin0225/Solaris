"""Validated site/plant settings loaded from config/*.yaml."""

import re
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from swf.core import paths

_MODEL_RE = re.compile(r"^[a-z0-9_]+$")
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CSV_PATTERN = r"^[A-Za-z0-9_.-]+\.csv$"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_model_name(name: str) -> str:
    if name == "best_match":  # unstable alias (D-06)
        raise ValueError("best_match is an unstable alias; name a concrete model")
    if not _MODEL_RE.fullmatch(name):
        raise ValueError(f"model name {name!r} must match ^[a-z0-9_]+$")
    return name


class Site(_Base):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float
    display_timezone: str


class NasaCfg(_Base):
    start_year: int = Field(ge=2001)
    end_year: int
    community: str
    min_interval_s: float = Field(ge=1.0)
    parameters: list[str] = Field(min_length=1, max_length=15)


class LiveCfg(_Base):
    past_days: int
    forecast_days: int


class OpenMeteoCfg(_Base):
    nwp_model: str
    era5_model: Literal["era5"]
    probe_models: list[str]
    hourly: list[str]
    previous_day_leads: list[int]
    era5_years: tuple[int, int]
    historical_forecast_years: tuple[int, int]
    previous_runs_years: tuple[int, int]
    min_interval_s: float = Field(ge=1.0)
    live: LiveCfg

    @field_validator("nwp_model")
    @classmethod
    def _nwp(cls, v: str) -> str:
        return _check_model_name(v)

    @field_validator("probe_models")
    @classmethod
    def _probes(cls, v: list[str]) -> list[str]:
        return [_check_model_name(m) for m in v]


class DataCfg(_Base):
    nasa: NasaCfg
    openmeteo: OpenMeteoCfg


class KaggleCfg(_Base):
    solar_slug: str
    wind_slug: str
    row_tolerance: float = Field(ge=0, le=0.5)
    expected_rows: dict[Annotated[str, Field(pattern=_CSV_PATTERN)], int]

    @field_validator("solar_slug", "wind_slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _SLUG_RE.fullmatch(v):
            raise ValueError(f"bad Kaggle slug {v!r}")
        return v


class SolarCfg(_Base):
    dc_kwp: float
    tilt_deg: float
    azimuth_pvlib_deg: float
    dc_ac_ratio: float
    eta_inv_nom: float
    gamma_pdc: float
    loss_pct: float
    transposition: str
    albedo: float = Field(ge=0, le=1)


class WindCfg(_Base):
    rated_kw: float
    hub_height_m: float
    availability_loss: float
    cut_in_ms: float
    rated_ms: float
    cut_out_ms: float
    power_curve_csv: Annotated[str, Field(pattern=_CSV_PATTERN)]  # bare filename: resolves under CONFIG_DIR


class AlignCfg(_Base):
    max_gap_h: int = Field(ge=1, le=6)
    fit_years: tuple[int, int]
    thresholds: dict[Literal["ghi", "rh", "ws10", "ws_hub"], float]
    wind_rel_threshold: float = Field(gt=0, lt=1)

    @field_validator("fit_years")
    @classmethod
    def _years(cls, v: tuple[int, int]) -> tuple[int, int]:
        if v[0] > v[1] or v[0] < 2001:
            raise ValueError("fit_years must be (first >= 2001, last >= first)")
        return v

    @field_validator("thresholds")
    @classmethod
    def _thr(cls, v: dict[str, float]) -> dict[str, float]:
        if set(v) != {"ghi", "rh", "ws10", "ws_hub"} or any(x <= 0 for x in v.values()):
            raise ValueError("thresholds need all of ghi, rh, ws10, ws_hub, each > 0")
        return v


class Settings(_Base):
    site: Site
    data: DataCfg
    kaggle: KaggleCfg
    solar: SolarCfg
    wind: WindCfg
    align: AlignCfg


def load_settings(config_dir: Path | None = None) -> Settings:
    d = Path(config_dir) if config_dir else paths.CONFIG_DIR
    site = yaml.safe_load((d / "site.yaml").read_text(encoding="utf-8"))
    plant = yaml.safe_load((d / "plant.yaml").read_text(encoding="utf-8"))
    return Settings(**site, **plant)
