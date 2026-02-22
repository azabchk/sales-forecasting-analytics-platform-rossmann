from datetime import date, datetime
from typing import Any
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


class ForecastBatchRequest(BaseModel):
    store_ids: list[int] = Field(..., min_length=1, max_length=50)
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


class ForecastBatchStoreSummary(BaseModel):
    store_id: int
    total_predicted_sales: float
    avg_daily_sales: float
    peak_date: date | None = None
    peak_sales: float
    avg_interval_width: float


class ForecastBatchPortfolioSummary(BaseModel):
    stores_count: int
    horizon_days: int
    total_predicted_sales: float
    avg_daily_sales: float
    peak_date: date | None = None
    peak_sales: float
    avg_interval_width: float


class ForecastBatchResponse(BaseModel):
    request: ForecastBatchRequest
    store_summaries: list[ForecastBatchStoreSummary]
    portfolio_summary: ForecastBatchPortfolioSummary
    portfolio_series: list[ForecastPoint]


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


class ChatQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class ChatInsight(BaseModel):
    label: str
    value: str


class ChatResponse(BaseModel):
    answer: str
    insights: list[ChatInsight] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class PreflightRunSummary(BaseModel):
    run_id: str
    created_at: datetime
    mode: str
    source_name: str
    validation_status: str
    semantic_status: str
    final_status: str
    blocked: bool
    block_reason: str | None = None
    used_unified: bool
    used_input_path: str
    artifact_dir: str | None = None
    validation_report_path: str | None = None
    manifest_path: str | None = None


class PreflightRunsListResponse(BaseModel):
    items: list[PreflightRunSummary]
    limit: int
    source_name: str | None = None


class PreflightRunDetailResponse(BaseModel):
    run_id: str
    created_at: datetime
    mode: str
    final_status: str
    blocked: bool
    records: list[PreflightRunSummary]


PreflightArtifactType = Literal["validation", "semantic", "manifest", "preflight", "unified_csv"]


class PreflightArtifactIndexItem(BaseModel):
    artifact_type: PreflightArtifactType
    available: bool
    file_name: str | None = None
    path: str | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    download_url: str | None = None


class PreflightSourceArtifactsResponse(BaseModel):
    run_id: str
    source_name: str
    artifact_dir: str | None = None
    artifacts: list[PreflightArtifactIndexItem]


class PreflightValidationArtifactResponse(BaseModel):
    run_id: str
    source_name: str
    status: str
    contract_version: str | None = None
    profile: str | None = None
    checks: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifact_path: str | None = None


class PreflightSemanticRuleResponse(BaseModel):
    rule_id: str
    rule_type: str
    severity: str
    status: str
    message: str
    target: list[str] = Field(default_factory=list)
    observed: dict[str, Any] = Field(default_factory=dict)


class PreflightSemanticArtifactResponse(BaseModel):
    run_id: str
    source_name: str
    status: str
    summary: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    rules: list[PreflightSemanticRuleResponse] = Field(default_factory=list)
    artifact_path: str | None = None


class PreflightManifestArtifactResponse(BaseModel):
    run_id: str
    source_name: str
    contract_version: str | None = None
    profile: str | None = None
    validation_status: str | None = None
    renamed_columns: dict[str, str] = Field(default_factory=dict)
    extra_columns_dropped: list[str] = Field(default_factory=list)
    coercion_stats: dict[str, Any] = Field(default_factory=dict)
    final_canonical_columns: list[str] = Field(default_factory=list)
    retained_extra_columns: list[str] = Field(default_factory=list)
    output_row_count: int | None = None
    output_column_count: int | None = None
    semantic_quality: dict[str, Any] | None = None
    artifact_path: str | None = None
