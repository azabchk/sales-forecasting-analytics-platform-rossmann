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
    data_source_id: int | None = Field(default=None, gt=0)


class ForecastBatchRequest(BaseModel):
    store_ids: list[int] = Field(..., min_length=1, max_length=50)
    horizon_days: int = Field(30, ge=1, le=180)
    data_source_id: int | None = Field(default=None, gt=0)


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
    data_source_id: int | None = Field(default=None, gt=0)


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


class DataAvailabilityDatasetResponse(BaseModel):
    table_name: str
    rows: int
    min_date: date | None = None
    max_date: date | None = None


class DataAvailabilityResponse(BaseModel):
    generated_at: datetime
    data_source_ids: list[int] = Field(default_factory=list)
    datasets: list[DataAvailabilityDatasetResponse] = Field(default_factory=list)


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
    data_source_id: int | None = None
    contract_id: str | None = None
    contract_version: str | None = None


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


class PreflightAnalyticsFilters(BaseModel):
    source_name: str | None = None
    data_source_id: int | None = None
    mode: str | None = None
    final_status: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    days: int | None = None


class PreflightStatsCounts(BaseModel):
    total_runs: int
    pass_count: int
    warn_count: int
    fail_count: int
    blocked_count: int
    used_unified_count: int
    used_unified_rate: float


class PreflightStatsResponse(PreflightStatsCounts):
    by_source: dict[str, PreflightStatsCounts] = Field(default_factory=dict)
    filters: PreflightAnalyticsFilters


class PreflightTrendBucket(BaseModel):
    bucket_start: datetime
    pass_count: int
    warn_count: int
    fail_count: int
    blocked_count: int


class PreflightTrendsResponse(BaseModel):
    bucket: Literal["day", "hour"]
    items: list[PreflightTrendBucket] = Field(default_factory=list)
    filters: PreflightAnalyticsFilters


class PreflightTopRuleItem(BaseModel):
    rule_id: str
    rule_type: str
    severity: str
    warn_count: int
    fail_count: int
    last_seen_at: datetime | None = None
    sample_message: str | None = None


class PreflightTopRulesResponse(BaseModel):
    items: list[PreflightTopRuleItem] = Field(default_factory=list)
    limit: int
    filters: PreflightAnalyticsFilters


class PreflightAlertPolicyResponse(BaseModel):
    id: str
    enabled: bool
    severity: str
    source_name: str | None = None
    window_days: int
    metric_type: str
    operator: str
    threshold: float
    pending_evaluations: int
    description: str
    rule_id: str | None = None


class PreflightAlertSilenceResponse(BaseModel):
    silence_id: str
    policy_id: str | None = None
    source_name: str | None = None
    severity: str | None = None
    rule_id: str | None = None
    starts_at: datetime
    ends_at: datetime
    reason: str
    created_by: str
    created_at: datetime
    expired_at: datetime | None = None
    is_active: bool = False


class PreflightAlertAcknowledgementResponse(BaseModel):
    alert_id: str
    acknowledged_by: str
    acknowledged_at: datetime
    note: str | None = None
    cleared_at: datetime | None = None
    updated_at: datetime | None = None


class PreflightAlertItemResponse(BaseModel):
    alert_id: str
    policy_id: str
    status: str
    severity: str
    source_name: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    resolved_at: datetime | None = None
    current_value: float | None = None
    threshold: float | None = None
    message: str
    evaluated_at: datetime | None = None
    evaluation_context_json: dict[str, Any] = Field(default_factory=dict)
    policy: PreflightAlertPolicyResponse | None = None
    is_silenced: bool = False
    silence: PreflightAlertSilenceResponse | None = None
    is_acknowledged: bool = False
    acknowledgement: PreflightAlertAcknowledgementResponse | None = None


class PreflightActiveAlertsResponse(BaseModel):
    evaluated_at: datetime
    total_active: int
    items: list[PreflightAlertItemResponse] = Field(default_factory=list)


class PreflightAlertHistoryResponse(BaseModel):
    limit: int
    items: list[PreflightAlertItemResponse] = Field(default_factory=list)


class PreflightAlertPoliciesResponse(BaseModel):
    path: str
    version: str
    items: list[PreflightAlertPolicyResponse] = Field(default_factory=list)


class PreflightAlertEvaluationResponse(BaseModel):
    evaluated_at: datetime
    total_policies: int
    active_count: int
    items: list[PreflightAlertItemResponse] = Field(default_factory=list)
    policy_path: str
    version: str


class PreflightSilencesResponse(BaseModel):
    limit: int
    include_expired: bool = False
    items: list[PreflightAlertSilenceResponse] = Field(default_factory=list)


class PreflightCreateSilenceRequest(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime
    reason: str = ""
    policy_id: str | None = None
    source_name: str | None = None
    severity: str | None = None
    rule_id: str | None = None


class PreflightAcknowledgeAlertRequest(BaseModel):
    note: str | None = None


class PreflightAlertAuditEventResponse(BaseModel):
    event_id: int
    alert_id: str
    event_type: str
    actor: str
    event_at: datetime
    payload_json: dict[str, Any] = Field(default_factory=dict)


class PreflightAlertAuditResponse(BaseModel):
    limit: int
    items: list[PreflightAlertAuditEventResponse] = Field(default_factory=list)


class PreflightNotificationOutboxItemResponse(BaseModel):
    id: str
    event_id: str | None = None
    delivery_id: str | None = None
    replayed_from_id: str | None = None
    event_type: str
    alert_id: str
    policy_id: str
    severity: str | None = None
    source_name: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    channel_type: str
    channel_target: str
    status: str
    attempt_count: int
    max_attempts: int
    next_retry_at: datetime | None = None
    last_error: str | None = None
    last_http_status: int | None = None
    last_error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None


class PreflightNotificationOutboxResponse(BaseModel):
    limit: int
    items: list[PreflightNotificationOutboxItemResponse] = Field(default_factory=list)


class PreflightNotificationDispatchResponse(BaseModel):
    actor: str
    dispatched_at: datetime
    processed_count: int
    sent_count: int
    retrying_count: int
    dead_count: int
    failed_count: int


class PreflightNotificationReplayResponse(BaseModel):
    actor: str
    replayed_count: int
    items: list[PreflightNotificationOutboxItemResponse] = Field(default_factory=list)


class PreflightNotificationAnalyticsFilters(BaseModel):
    days: int | None = None
    event_type: str | None = None
    channel_target: str | None = None
    status: str | None = None
    attempt_status: str | None = None
    alert_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class PreflightNotificationStatsResponse(BaseModel):
    filters: PreflightNotificationAnalyticsFilters
    total_events: int
    sent_count: int
    retry_count: int
    dead_count: int
    replay_count: int
    pending_count: int
    success_rate: float
    avg_delivery_latency_ms: float | None = None
    p95_delivery_latency_ms: float | None = None
    oldest_pending_age_seconds: int | None = None
    runtime_observability: dict[str, Any] = Field(default_factory=dict)


class PreflightNotificationTrendBucket(BaseModel):
    bucket_start: datetime
    sent_count: int
    retry_count: int
    dead_count: int
    replay_count: int
    avg_delivery_latency_ms: float | None = None


class PreflightNotificationTrendsResponse(BaseModel):
    bucket: Literal["day", "hour"]
    filters: PreflightNotificationAnalyticsFilters
    items: list[PreflightNotificationTrendBucket] = Field(default_factory=list)


class PreflightNotificationChannelErrorCode(BaseModel):
    error_code: str
    count: int


class PreflightNotificationChannelSummary(BaseModel):
    channel_target: str
    sent_count: int
    retry_count: int
    dead_count: int
    pending_count: int
    replay_count: int
    success_rate: float
    avg_delivery_latency_ms: float | None = None
    last_sent_at: datetime | None = None
    last_error_at: datetime | None = None
    top_error_codes: list[PreflightNotificationChannelErrorCode] = Field(default_factory=list)


class PreflightNotificationChannelsResponse(BaseModel):
    filters: PreflightNotificationAnalyticsFilters
    items: list[PreflightNotificationChannelSummary] = Field(default_factory=list)


class PreflightNotificationAttemptItemResponse(BaseModel):
    attempt_id: str
    outbox_item_id: str
    event_id: str | None = None
    delivery_id: str | None = None
    replayed_from_id: str | None = None
    channel_type: str
    channel_target: str
    event_type: str
    alert_id: str
    policy_id: str
    source_name: str | None = None
    attempt_number: int
    attempt_status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    http_status: int | None = None
    error_code: str | None = None
    error_message_safe: str | None = None
    created_at: datetime


class PreflightNotificationAttemptsResponse(BaseModel):
    limit: int
    filters: PreflightNotificationAnalyticsFilters
    items: list[PreflightNotificationAttemptItemResponse] = Field(default_factory=list)


class DataSourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    source_type: str = Field(default="cms", min_length=1, max_length=64)
    related_contract_id: str | None = Field(default=None, max_length=128)
    related_contract_version: str | None = Field(default=None, max_length=64)
    is_active: bool = True
    is_default: bool = False


class DataSourceResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    source_type: str
    related_contract_id: str | None = None
    related_contract_version: str | None = None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    last_preflight_status: str | None = None
    last_preflight_at: datetime | None = None
    last_preflight_run_id: str | None = None


class ContractSummaryResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool = True
    latest_version: str | None = None
    versions_count: int = 0


class ContractVersionSummaryResponse(BaseModel):
    version: str
    created_at: str | None = None
    changed_by: str | None = None
    changelog: str | None = None
    schema_path: str


class ContractProfileSchemaResponse(BaseModel):
    required_columns: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    dtypes: dict[str, str] = Field(default_factory=dict)


class ContractVersionDetailResponse(ContractVersionSummaryResponse):
    contract_version: str
    profiles: dict[str, ContractProfileSchemaResponse] = Field(default_factory=dict)


class ContractDetailResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool = True
    versions: list[ContractVersionSummaryResponse] = Field(default_factory=list)


class MLPeriodResponse(BaseModel):
    start: date | None = None
    end: date | None = None


class MLExperimentListItemResponse(BaseModel):
    experiment_id: str
    data_source_id: int | None = None
    model_type: str
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    training_period: MLPeriodResponse
    validation_period: MLPeriodResponse
    metrics: dict[str, Any] = Field(default_factory=dict)
    status: str
    artifact_path: str | None = None
    metadata_path: str | None = None
    created_at: datetime
    updated_at: datetime


class MLExperimentsResponse(BaseModel):
    items: list[MLExperimentListItemResponse] = Field(default_factory=list)
    limit: int
    data_source_id: int | None = None


class ScenarioSegmentRequest(BaseModel):
    store_type: str | None = Field(default=None, max_length=32)
    assortment: str | None = Field(default=None, max_length=32)
    promo2: int | None = Field(default=None, ge=0, le=1)


class ScenarioRunRequestV2(BaseModel):
    store_id: int | None = Field(default=None, gt=0)
    segment: ScenarioSegmentRequest | None = None
    price_change_pct: float = Field(default=0.0, ge=-80.0, le=200.0)
    promo_mode: Literal["as_is", "always_on", "weekends_only", "off"] = "as_is"
    weekend_open: bool = True
    school_holiday: int = Field(default=0, ge=0, le=1)
    demand_shift_pct: float = Field(default=0.0, ge=-80.0, le=200.0)
    confidence_level: float = Field(default=0.8, ge=0.5, le=0.99)
    horizon_days: int = Field(default=30, ge=1, le=180)
    data_source_id: int | None = Field(default=None, gt=0)


class ScenarioTargetResponse(BaseModel):
    mode: Literal["store", "segment"]
    store_id: int | None = None
    segment: dict[str, Any] | None = None
    stores_count: int | None = None
    store_ids: list[int] | None = None


class ScenarioAssumptionsResponse(BaseModel):
    price_change_pct: float
    price_elasticity: float
    price_effect_pct: float
    effective_demand_shift_pct: float


class ScenarioRunResponseV2(BaseModel):
    run_id: str
    target: ScenarioTargetResponse
    assumptions: ScenarioAssumptionsResponse
    request: dict[str, Any]
    summary: ForecastScenarioSummary
    points: list[ForecastScenarioPoint] = Field(default_factory=list)


class NotificationEndpointResponse(BaseModel):
    id: str
    channel_type: str
    enabled: bool
    target_hint: str | None = None
    has_target_url: bool
    timeout_seconds: int
    max_attempts: int
    backoff_seconds: int
    enabled_event_types: list[str] = Field(default_factory=list)


class NotificationEndpointsResponse(BaseModel):
    version: str
    path: str
    items: list[NotificationEndpointResponse] = Field(default_factory=list)


class NotificationDeliveryItemResponse(BaseModel):
    attempt_id: str
    outbox_item_id: str
    event_id: str | None = None
    delivery_id: str | None = None
    replayed_from_id: str | None = None
    channel_type: str
    channel_target: str
    event_type: str
    alert_id: str
    policy_id: str
    source_name: str | None = None
    attempt_number: int
    attempt_status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    http_status: int | None = None
    error_code: str | None = None
    error_message_safe: str | None = None
    created_at: datetime


class NotificationDeliveryPageResponse(BaseModel):
    page: int
    page_size: int
    total: int
    status: str | None = None
    items: list[NotificationDeliveryItemResponse] = Field(default_factory=list)
