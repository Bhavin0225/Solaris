"""Validated site/plant settings loaded from config/*.yaml."""

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    dc_kwp: float = Field(gt=0)
    tilt_deg: float
    azimuth_pvlib_deg: float
    dc_ac_ratio: float = Field(gt=0)
    eta_inv_nom: float = Field(gt=0, le=1)
    gamma_pdc: float
    loss_pct: float = Field(ge=0, lt=100)  # percent, e.g. 14
    transposition: str
    albedo: float = Field(ge=0, le=1)


class WindCfg(_Base):
    rated_kw: float = Field(gt=0)
    hub_height_m: float = Field(gt=0)
    availability_loss: float = Field(ge=0, lt=1)
    cut_in_ms: float
    rated_ms: float
    cut_out_ms: float
    power_curve_csv: Annotated[str, Field(pattern=_CSV_PATTERN)]  # bare filename: resolves under CONFIG_DIR

    @model_validator(mode="after")
    def _speeds(self):
        if not 0 <= self.cut_in_ms < self.rated_ms < self.cut_out_ms:
            raise ValueError("wind speeds need 0 <= cut_in < rated < cut_out")
        return self


class AlignCfg(_Base):
    max_gap_h: int = Field(ge=1, le=6)
    fit_years: tuple[int, int]
    thresholds: dict[Literal["ghi", "rh", "ws10", "ws_hub"], float]
    wind_rel_threshold: float = Field(gt=0, lt=1)
    skip: dict[Literal["ghi", "rh", "ws10", "ws_hub"], str] = {}  # variable -> reason, overrides D-17

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


class SolarPlantVal(_Base):
    generation_csv: Annotated[str, Field(pattern=_CSV_PATTERN)]
    weather_csv: Annotated[str, Field(pattern=_CSV_PATTERN)]
    generation_date_format: str
    gating: bool


class SolarVal(_Base):
    n_inverters: int = Field(gt=0)
    local_timezone: str
    weather_date_format: str
    span_local: tuple[date, date]
    heldout_start_local: date
    day_irradiation_kw_m2: float = Field(gt=0)
    dropout_irradiation_kw_m2: float = Field(gt=0)
    irradiation_max_range_kw_m2: tuple[float, float]
    loss_grid_pct: tuple[int, int]
    target_nrmse_pct: float = Field(gt=0)
    plants: dict[str, SolarPlantVal]

    @field_validator("loss_grid_pct")
    @classmethod
    def _grid(cls, v: tuple[int, int]) -> tuple[int, int]:
        if not 0 <= v[0] <= v[1] < 100:
            raise ValueError("loss_grid_pct needs 0 <= lo <= hi < 100")
        return v

    @field_validator("irradiation_max_range_kw_m2")
    @classmethod
    def _irr(cls, v: tuple[float, float]) -> tuple[float, float]:
        if not 0 < v[0] < v[1]:
            raise ValueError("irradiation_max_range_kw_m2 needs 0 < lo < hi")
        return v

    @model_validator(mode="after")
    def _gating(self):
        if not any(p.gating for p in self.plants.values()):
            raise ValueError("at least one plant must be gating")
        return self


class WindVal(_Base):
    t1_csv: Annotated[str, Field(pattern=_CSV_PATTERN)]
    date_format: str
    year: int
    pressure_hpa: float = Field(gt=0)
    temp_c: float
    reference_slice: tuple[date, date]
    availability_ws_ms: float = Field(gt=0)
    target_nrmse_pct: float = Field(gt=0)
    prd_reference_nrmse_pct: float = Field(gt=0)

    @field_validator("reference_slice")
    @classmethod
    def _slice(cls, v: tuple[date, date]) -> tuple[date, date]:
        if v[0] > v[1]:
            raise ValueError("reference_slice start must be <= end")
        return v


class ValidationCfg(_Base):
    solar: SolarVal
    wind: WindVal


class Settings(_Base):
    site: Site
    data: DataCfg
    kaggle: KaggleCfg
    solar: SolarCfg
    wind: WindCfg
    align: AlignCfg

    @model_validator(mode="after")
    def _years(self):
        n, e, f = self.data.nasa, self.data.openmeteo.era5_years, self.align.fit_years
        if n.start_year > n.end_year:
            raise ValueError("nasa start_year must be <= end_year")
        if not (max(n.start_year, e[0]) <= f[0] and f[1] <= min(n.end_year, e[1])):
            raise ValueError("align.fit_years must lie inside both the NASA and ERA5 year ranges")
        return self


def load_settings(config_dir: Path | None = None) -> Settings:
    d = Path(config_dir) if config_dir else paths.CONFIG_DIR
    site = yaml.safe_load((d / "site.yaml").read_text(encoding="utf-8"))
    plant = yaml.safe_load((d / "plant.yaml").read_text(encoding="utf-8"))
    return Settings(**site, **plant)


def load_validation_cfg(config_dir: Path | None = None) -> ValidationCfg:
    d = Path(config_dir) if config_dir else paths.CONFIG_DIR
    return ValidationCfg(**yaml.safe_load((d / "validation.yaml").read_text(encoding="utf-8")))


class SplitsCfg(_Base):
    train_weather_only: tuple[datetime, datetime]
    train_covariate: tuple[datetime, datetime]
    val: tuple[datetime, datetime]
    test: tuple[datetime, datetime]

    @field_validator("*")
    @classmethod
    def _utc_ordered(cls, v):
        for d in v:
            if d.tzinfo is None or d.utcoffset() != timedelta(0):
                raise ValueError("split bounds must be tz-aware UTC (end with Z)")
        if v[0] >= v[1]:
            raise ValueError("split start must be before end")
        return tuple(d.astimezone(UTC) for d in v)

    @model_validator(mode="after")
    def _chronological(self):
        w, c = self.train_weather_only, self.train_covariate
        if not (w[0] <= c[0] and c[1] <= w[1]):
            raise ValueError("train_covariate must lie inside train_weather_only")
        if not (w[1] < self.val[0] and self.val[1] < self.test[0]):
            raise ValueError("splits must be chronological: train < val < test, no overlap")
        return self


class EvalCfg(_Base):
    horizons: list[int]
    daytime_zenith_deg: float = Field(gt=0, lt=90)
    min_shared_frac: float = Field(gt=0, le=1)
    csi_min_clearsky_wm2: float = Field(ge=0)


class FeaturesCfg(_Base):
    spec_version: int = Field(ge=1)
    horizon_max: int = Field(ge=1)
    lags: list[int]
    windows: list[int]
    monsoon_months: list[int]
    splits: SplitsCfg
    eval: EvalCfg

    @model_validator(mode="after")
    def _check(self):
        if any(b <= a for a, b in zip(self.lags, self.lags[1:], strict=False)) or any(x < 0 for x in self.lags):
            raise ValueError("lags must be strictly increasing and >= 0")
        if any(b <= a for a, b in zip(self.windows, self.windows[1:], strict=False)) or any(w < 2 for w in self.windows):
            raise ValueError("windows must be strictly increasing and >= 2")
        if len(set(self.monsoon_months)) != len(self.monsoon_months) or not all(1 <= m <= 12 for m in self.monsoon_months):
            raise ValueError("monsoon_months must be unique values in 1..12")
        if not all(1 <= h <= self.horizon_max for h in self.eval.horizons):
            raise ValueError("eval horizons must lie in 1..horizon_max")
        return self


def load_features_cfg(config_dir: Path | None = None) -> FeaturesCfg:
    d = Path(config_dir) if config_dir else paths.CONFIG_DIR
    return FeaturesCfg(**yaml.safe_load((d / "features.yaml").read_text(encoding="utf-8")))
