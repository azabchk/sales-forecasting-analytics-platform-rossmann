from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class StoreItem(BaseModel):
    store_id: int
    store_type: str | None = None
    assortment: str | None = None


class KpiSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    store_id: int | None = None
    total_sales: float
    total_customers: float
    avg_daily_sales: float
    promo_days: int
    open_days: int


class SalesTimeseriesPoint(BaseModel):
    date: date
    store_id: int
    sales: float
    customers: float
    promo: int | None = None
    open: int | None = None


class PromoImpactPoint(BaseModel):
    store_id: int
    promo_flag: str
    avg_sales: float
    avg_customers: float
    num_days: int


class ForecastRequest(BaseModel):
    store_id: int = Field(..., gt=0)
    horizon_days: int = Field(30, ge=1, le=180)


class ForecastPoint(BaseModel):
    date: date
    predicted_sales: float
    predicted_lower: float | None = None
    predicted_upper: float | None = None


class ForecastScenarioRequest(BaseModel):
    store_id: int = Field(..., gt=0)
    horizon_days: int = Field(30, ge=1, le=180)
    promo_mode: Literal["as_is", "always_on", "weekends_only", "off"] = "as_is"
    weekend_open: bool = True
    school_holiday: int = Field(0, ge=0, le=1)
    demand_shift_pct: float = Field(0.0, ge=-50.0, le=50.0)
    confidence_level: float = Field(0.8, ge=0.5, le=0.99)


class ForecastScenarioPoint(BaseModel):
    date: date
    baseline_sales: float
    scenario_sales: float
    delta_sales: float
    scenario_lower: float | None = None
    scenario_upper: float | None = None


class ForecastScenarioSummary(BaseModel):
    total_baseline_sales: float
    total_scenario_sales: float
    total_delta_sales: float
    uplift_pct: float
    avg_daily_delta: float
    max_delta_date: date | None = None
    max_delta_value: float


class ForecastScenarioResponse(BaseModel):
    request: ForecastScenarioRequest
    summary: ForecastScenarioSummary
    points: list[ForecastScenarioPoint]


class SystemSummaryResponse(BaseModel):
    stores_count: int
    sales_rows_count: int
    date_from: date | None = None
    date_to: date | None = None


class ModelMetricSet(BaseModel):
    mae: float
    rmse: float
    mape: float | None = None
    wape: float | None = None
    smape: float | None = None
    mape_nonzero: float | None = None


class ModelFeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class ModelPeriod(BaseModel):
    date_from: date
    date_to: date


class ModelRows(BaseModel):
    train: int
    validation: int


class ModelCandidate(BaseModel):
    params: dict[str, float | int]
    metrics: ModelMetricSet


class ModelMetadataResponse(BaseModel):
    selected_model: str
    trained_at: str | None = None
    metrics: dict[str, ModelMetricSet]
    catboost_candidates: list[ModelCandidate] = []
    catboost_selected_params: dict[str, float | int] | None = None
    target_transform: str | None = None
    prediction_floor: float | None = None
    prediction_cap: float | None = None
    prediction_interval_sigma: float | None = None
    top_feature_importance: list[ModelFeatureImportanceItem] = []
    train_period: ModelPeriod | None = None
    validation_period: ModelPeriod | None = None
    rows: ModelRows | None = None
