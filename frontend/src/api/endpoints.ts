import { apiClient } from "./client";

export type Store = {
  store_id: number;
  store_type?: string;
  assortment?: string;
};

export type KpiSummary = {
  date_from: string;
  date_to: string;
  store_id?: number | null;
  total_sales: number;
  total_customers: number;
  avg_daily_sales: number;
  promo_days: number;
  open_days: number;
};

export type SalesPoint = {
  date: string;
  store_id: number;
  sales: number;
  customers: number;
  promo?: number | null;
  open?: number | null;
};

export type PromoImpactPoint = {
  store_id: number;
  promo_flag: string;
  avg_sales: number;
  avg_customers: number;
  num_days: number;
};

export type ForecastPoint = {
  date: string;
  predicted_sales: number;
  predicted_lower?: number | null;
  predicted_upper?: number | null;
};

export type ForecastScenarioRequest = {
  store_id: number;
  horizon_days: number;
  promo_mode: "as_is" | "always_on" | "weekends_only" | "off";
  weekend_open: boolean;
  school_holiday: 0 | 1;
  demand_shift_pct: number;
  confidence_level: number;
};

export type ForecastScenarioPoint = {
  date: string;
  baseline_sales: number;
  scenario_sales: number;
  delta_sales: number;
  scenario_lower?: number | null;
  scenario_upper?: number | null;
};

export type ForecastScenarioSummary = {
  total_baseline_sales: number;
  total_scenario_sales: number;
  total_delta_sales: number;
  uplift_pct: number;
  avg_daily_delta: number;
  max_delta_date?: string | null;
  max_delta_value: number;
};

export type ForecastScenarioResponse = {
  request: ForecastScenarioRequest;
  summary: ForecastScenarioSummary;
  points: ForecastScenarioPoint[];
};

export type ForecastBatchRequest = {
  store_ids: number[];
  horizon_days: number;
};

export type ForecastBatchStoreSummary = {
  store_id: number;
  total_predicted_sales: number;
  avg_daily_sales: number;
  peak_date?: string | null;
  peak_sales: number;
  avg_interval_width: number;
};

export type ForecastBatchPortfolioSummary = {
  stores_count: number;
  horizon_days: number;
  total_predicted_sales: number;
  avg_daily_sales: number;
  peak_date?: string | null;
  peak_sales: number;
  avg_interval_width: number;
};

export type ForecastBatchResponse = {
  request: ForecastBatchRequest;
  store_summaries: ForecastBatchStoreSummary[];
  portfolio_summary: ForecastBatchPortfolioSummary;
  portfolio_series: ForecastPoint[];
};

export type HealthResponse = {
  status: string;
};

export type SystemSummary = {
  stores_count: number;
  sales_rows_count: number;
  date_from?: string | null;
  date_to?: string | null;
};

export type ModelMetricSet = {
  mae: number;
  rmse: number;
  mape?: number | null;
  wape?: number | null;
  smape?: number | null;
  mape_nonzero?: number | null;
};

export type ModelCandidate = {
  params: Record<string, number>;
  metrics: ModelMetricSet;
};

export type ModelFeatureImportanceItem = {
  feature: string;
  importance: number;
};

export type ModelMetadata = {
  selected_model: string;
  trained_at?: string | null;
  metrics: Record<string, ModelMetricSet>;
  catboost_candidates: ModelCandidate[];
  catboost_selected_params?: Record<string, number> | null;
  target_transform?: string | null;
  prediction_floor?: number | null;
  prediction_cap?: number | null;
  prediction_interval_sigma?: number | null;
  top_feature_importance: ModelFeatureImportanceItem[];
  train_period?: { date_from: string; date_to: string } | null;
  validation_period?: { date_from: string; date_to: string } | null;
  rows?: { train: number; validation: number } | null;
};

export type ChatInsight = {
  label: string;
  value: string;
};

export type ChatResponse = {
  answer: string;
  insights: ChatInsight[];
  suggestions: string[];
};

export type PreflightSourceName = "train" | "store";
export type PreflightStatus = "PASS" | "WARN" | "FAIL" | "SKIPPED" | string;
export type PreflightMode = "off" | "report_only" | "enforce" | string;

export type PreflightRunSummary = {
  run_id: string;
  created_at: string;
  mode: string;
  source_name: PreflightSourceName;
  validation_status: PreflightStatus;
  semantic_status: PreflightStatus;
  final_status: PreflightStatus;
  blocked: boolean;
  block_reason?: string | null;
  used_unified: boolean;
  used_input_path: string;
  artifact_dir?: string | null;
  validation_report_path?: string | null;
  manifest_path?: string | null;
  data_source_id?: number | null;
  contract_id?: string | null;
  contract_version?: string | null;
};

export type PreflightRunsListResponse = {
  items: PreflightRunSummary[];
  limit: number;
  source_name?: PreflightSourceName | null;
};

export type PreflightRunDetailResponse = {
  run_id: string;
  created_at: string;
  mode: string;
  final_status: PreflightStatus;
  blocked: boolean;
  records: PreflightRunSummary[];
};

export type PreflightArtifactType = "validation" | "semantic" | "manifest" | "preflight" | "unified_csv";

export type PreflightArtifactIndexItem = {
  artifact_type: PreflightArtifactType;
  available: boolean;
  file_name?: string | null;
  path?: string | null;
  size_bytes?: number | null;
  content_type?: string | null;
  download_url?: string | null;
};

export type PreflightSourceArtifactsResponse = {
  run_id: string;
  source_name: PreflightSourceName;
  artifact_dir?: string | null;
  artifacts: PreflightArtifactIndexItem[];
};

export type PreflightValidationArtifactResponse = {
  run_id: string;
  source_name: PreflightSourceName;
  status: PreflightStatus;
  contract_version?: string | null;
  profile?: string | null;
  checks: Record<string, string>;
  errors: string[];
  warnings: string[];
  summary?: string | null;
  metadata: Record<string, unknown>;
  artifact_path?: string | null;
};

export type PreflightSemanticRule = {
  rule_id: string;
  rule_type: string;
  severity: string;
  status: PreflightStatus;
  message: string;
  target: string[];
  observed: Record<string, unknown>;
};

export type PreflightSemanticArtifactResponse = {
  run_id: string;
  source_name: PreflightSourceName;
  status: PreflightStatus;
  summary?: string | null;
  counts: {
    total: number;
    passed: number;
    warned: number;
    failed: number;
  };
  rules: PreflightSemanticRule[];
  artifact_path?: string | null;
};

export type PreflightManifestArtifactResponse = {
  run_id: string;
  source_name: PreflightSourceName;
  contract_version?: string | null;
  profile?: string | null;
  validation_status?: PreflightStatus | null;
  renamed_columns: Record<string, string>;
  extra_columns_dropped: string[];
  coercion_stats: Record<string, unknown>;
  final_canonical_columns: string[];
  retained_extra_columns: string[];
  output_row_count?: number | null;
  output_column_count?: number | null;
  semantic_quality?: Record<string, unknown> | null;
  artifact_path?: string | null;
};

export type PreflightAnalyticsFilters = {
  source_name?: PreflightSourceName | null;
  mode?: PreflightMode | null;
  final_status?: "PASS" | "WARN" | "FAIL" | null;
  date_from?: string | null;
  date_to?: string | null;
  days?: number | null;
};

export type PreflightStatsCounts = {
  total_runs: number;
  pass_count: number;
  warn_count: number;
  fail_count: number;
  blocked_count: number;
  used_unified_count: number;
  used_unified_rate: number;
};

export type PreflightStatsResponse = PreflightStatsCounts & {
  by_source: Record<string, PreflightStatsCounts>;
  filters: PreflightAnalyticsFilters;
};

export type PreflightTrendBucket = {
  bucket_start: string;
  pass_count: number;
  warn_count: number;
  fail_count: number;
  blocked_count: number;
};

export type PreflightTrendsResponse = {
  bucket: "day" | "hour";
  items: PreflightTrendBucket[];
  filters: PreflightAnalyticsFilters;
};

export type PreflightTopRuleItem = {
  rule_id: string;
  rule_type: string;
  severity: string;
  warn_count: number;
  fail_count: number;
  last_seen_at?: string | null;
  sample_message?: string | null;
};

export type PreflightTopRulesResponse = {
  items: PreflightTopRuleItem[];
  limit: number;
  filters: PreflightAnalyticsFilters;
};

export type PreflightAlertSeverity = "LOW" | "MEDIUM" | "HIGH" | string;
export type PreflightAlertStatus = "OK" | "PENDING" | "FIRING" | "RESOLVED" | string;

export type PreflightAlertPolicy = {
  id: string;
  enabled: boolean;
  severity: PreflightAlertSeverity;
  source_name?: PreflightSourceName | null;
  window_days: number;
  metric_type: string;
  operator: string;
  threshold: number;
  pending_evaluations: number;
  description: string;
  rule_id?: string | null;
};

export type PreflightAlertSilence = {
  silence_id: string;
  policy_id?: string | null;
  source_name?: PreflightSourceName | null;
  severity?: PreflightAlertSeverity | null;
  rule_id?: string | null;
  starts_at: string;
  ends_at: string;
  reason: string;
  created_by: string;
  created_at: string;
  expired_at?: string | null;
  is_active: boolean;
};

export type PreflightAlertAcknowledgement = {
  alert_id: string;
  acknowledged_by: string;
  acknowledged_at: string;
  note?: string | null;
  cleared_at?: string | null;
  updated_at?: string | null;
};

export type PreflightAlertItem = {
  alert_id: string;
  policy_id: string;
  status: PreflightAlertStatus;
  severity: PreflightAlertSeverity;
  source_name?: PreflightSourceName | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  resolved_at?: string | null;
  current_value?: number | null;
  threshold?: number | null;
  message: string;
  evaluated_at?: string | null;
  evaluation_context_json: Record<string, unknown>;
  policy?: PreflightAlertPolicy | null;
  is_silenced?: boolean;
  silence?: PreflightAlertSilence | null;
  is_acknowledged?: boolean;
  acknowledgement?: PreflightAlertAcknowledgement | null;
};

export type PreflightActiveAlertsResponse = {
  evaluated_at: string;
  total_active: number;
  items: PreflightAlertItem[];
};

export type PreflightAlertHistoryResponse = {
  limit: number;
  items: PreflightAlertItem[];
};

export type PreflightAlertPoliciesResponse = {
  path: string;
  version: string;
  items: PreflightAlertPolicy[];
};

export type PreflightAlertEvaluationResponse = {
  evaluated_at: string;
  total_policies: number;
  active_count: number;
  items: PreflightAlertItem[];
  policy_path: string;
  version: string;
};

export type PreflightAlertSilencesResponse = {
  limit: number;
  include_expired: boolean;
  items: PreflightAlertSilence[];
};

export type PreflightCreateSilenceRequest = {
  starts_at?: string;
  ends_at: string;
  reason?: string;
  policy_id?: string;
  source_name?: PreflightSourceName;
  severity?: PreflightAlertSeverity;
  rule_id?: string;
};

export type PreflightAcknowledgeAlertRequest = {
  note?: string;
};

export type PreflightAlertAuditEvent = {
  event_id: number;
  alert_id: string;
  event_type: string;
  actor: string;
  event_at: string;
  payload_json: Record<string, unknown>;
};

export type PreflightAlertAuditResponse = {
  limit: number;
  items: PreflightAlertAuditEvent[];
};

export type PreflightAnalyticsQueryParams = {
  source_name?: PreflightSourceName;
  mode?: "off" | "report_only" | "enforce";
  final_status?: "PASS" | "WARN" | "FAIL";
  date_from?: string;
  date_to?: string;
  days?: number;
};

export async function fetchStores(): Promise<Store[]> {
  const { data } = await apiClient.get<Store[]>('/stores');
  return data;
}

export async function fetchKpiSummary(params: {
  date_from: string;
  date_to: string;
  store_id?: number;
}): Promise<KpiSummary> {
  const { data } = await apiClient.get<KpiSummary>('/kpi/summary', { params });
  return data;
}

export async function fetchSalesTimeseries(params: {
  granularity: 'daily' | 'monthly';
  date_from: string;
  date_to: string;
  store_id?: number;
}): Promise<SalesPoint[]> {
  const { data } = await apiClient.get<SalesPoint[]>('/sales/timeseries', { params });
  return data;
}

export async function fetchPromoImpact(store_id?: number): Promise<PromoImpactPoint[]> {
  const { data } = await apiClient.get<PromoImpactPoint[]>('/kpi/promo-impact', {
    params: store_id ? { store_id } : {}
  });
  return data;
}

export async function postForecast(payload: {
  store_id: number;
  horizon_days: number;
}): Promise<ForecastPoint[]> {
  const { data } = await apiClient.post<ForecastPoint[]>('/forecast', payload);
  return data;
}

export async function postForecastBatch(payload: ForecastBatchRequest): Promise<ForecastBatchResponse> {
  const { data } = await apiClient.post<ForecastBatchResponse>("/forecast/batch", payload);
  return data;
}

export async function postForecastScenario(payload: ForecastScenarioRequest): Promise<ForecastScenarioResponse> {
  const { data } = await apiClient.post<ForecastScenarioResponse>("/forecast/scenario", payload);
  return data;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/health");
  return data;
}

export async function fetchSystemSummary(): Promise<SystemSummary> {
  const { data } = await apiClient.get<SystemSummary>("/system/summary");
  return data;
}

export async function fetchModelMetadata(): Promise<ModelMetadata> {
  const { data } = await apiClient.get<ModelMetadata>("/model/metadata");
  return data;
}

export async function postChatQuery(payload: { message: string }): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/chat/query", payload);
  return data;
}

export async function fetchPreflightRuns(params: {
  limit: number;
  source_name?: PreflightSourceName;
  data_source_id?: number;
}): Promise<PreflightRunsListResponse> {
  const { data } = await apiClient.get<PreflightRunsListResponse>("/diagnostics/preflight/runs", { params });
  return data;
}

export async function fetchPreflightRunDetails(runId: string): Promise<PreflightRunDetailResponse> {
  const { data } = await apiClient.get<PreflightRunDetailResponse>(`/diagnostics/preflight/runs/${encodeURIComponent(runId)}`);
  return data;
}

export async function fetchLatestPreflight(): Promise<PreflightRunDetailResponse> {
  const { data } = await apiClient.get<PreflightRunDetailResponse>("/diagnostics/preflight/latest");
  return data;
}

export async function fetchLatestPreflightBySource(sourceName: PreflightSourceName): Promise<PreflightRunSummary> {
  const { data } = await apiClient.get<PreflightRunSummary>(`/diagnostics/preflight/latest/${sourceName}`);
  return data;
}

export async function fetchPreflightSourceArtifacts(
  runId: string,
  sourceName: PreflightSourceName
): Promise<PreflightSourceArtifactsResponse> {
  const { data } = await apiClient.get<PreflightSourceArtifactsResponse>(
    `/diagnostics/preflight/runs/${encodeURIComponent(runId)}/sources/${sourceName}/artifacts`
  );
  return data;
}

export async function fetchPreflightSourceValidation(
  runId: string,
  sourceName: PreflightSourceName
): Promise<PreflightValidationArtifactResponse> {
  const { data } = await apiClient.get<PreflightValidationArtifactResponse>(
    `/diagnostics/preflight/runs/${encodeURIComponent(runId)}/sources/${sourceName}/validation`
  );
  return data;
}

export async function fetchPreflightSourceSemantic(
  runId: string,
  sourceName: PreflightSourceName
): Promise<PreflightSemanticArtifactResponse> {
  const { data } = await apiClient.get<PreflightSemanticArtifactResponse>(
    `/diagnostics/preflight/runs/${encodeURIComponent(runId)}/sources/${sourceName}/semantic`
  );
  return data;
}

export async function fetchPreflightSourceManifest(
  runId: string,
  sourceName: PreflightSourceName
): Promise<PreflightManifestArtifactResponse> {
  const { data } = await apiClient.get<PreflightManifestArtifactResponse>(
    `/diagnostics/preflight/runs/${encodeURIComponent(runId)}/sources/${sourceName}/manifest`
  );
  return data;
}

export async function fetchPreflightStats(
  params: PreflightAnalyticsQueryParams
): Promise<PreflightStatsResponse> {
  const { data } = await apiClient.get<PreflightStatsResponse>("/diagnostics/preflight/stats", { params });
  return data;
}

export async function fetchPreflightTrends(
  params: PreflightAnalyticsQueryParams & { bucket?: "day" | "hour" }
): Promise<PreflightTrendsResponse> {
  const { data } = await apiClient.get<PreflightTrendsResponse>("/diagnostics/preflight/trends", { params });
  return data;
}

export async function fetchPreflightTopRules(
  params: PreflightAnalyticsQueryParams & { limit?: number }
): Promise<PreflightTopRulesResponse> {
  const { data } = await apiClient.get<PreflightTopRulesResponse>("/diagnostics/preflight/rules/top", { params });
  return data;
}

export async function fetchPreflightActiveAlerts(params?: {
  auto_evaluate?: boolean;
}): Promise<PreflightActiveAlertsResponse> {
  const { data } = await apiClient.get<PreflightActiveAlertsResponse>("/diagnostics/preflight/alerts/active", {
    params,
  });
  return data;
}

export async function fetchPreflightAlertHistory(params?: {
  limit?: number;
}): Promise<PreflightAlertHistoryResponse> {
  const { data } = await apiClient.get<PreflightAlertHistoryResponse>("/diagnostics/preflight/alerts/history", {
    params,
  });
  return data;
}

export async function fetchPreflightAlertPolicies(): Promise<PreflightAlertPoliciesResponse> {
  const { data } = await apiClient.get<PreflightAlertPoliciesResponse>("/diagnostics/preflight/alerts/policies");
  return data;
}

export async function fetchPreflightAlertSilences(params?: {
  limit?: number;
  include_expired?: boolean;
}): Promise<PreflightAlertSilencesResponse> {
  const { data } = await apiClient.get<PreflightAlertSilencesResponse>("/diagnostics/preflight/alerts/silences", {
    params,
  });
  return data;
}

export async function postPreflightAlertSilence(
  payload: PreflightCreateSilenceRequest
): Promise<PreflightAlertSilence> {
  const { data } = await apiClient.post<PreflightAlertSilence>("/diagnostics/preflight/alerts/silences", payload);
  return data;
}

export async function postPreflightAlertSilenceExpire(
  silenceId: string
): Promise<PreflightAlertSilence> {
  const { data } = await apiClient.post<PreflightAlertSilence>(
    `/diagnostics/preflight/alerts/silences/${encodeURIComponent(silenceId)}/expire`,
    {}
  );
  return data;
}

export async function postPreflightAlertAcknowledge(
  alertId: string,
  payload: PreflightAcknowledgeAlertRequest
): Promise<PreflightAlertAcknowledgement> {
  const { data } = await apiClient.post<PreflightAlertAcknowledgement>(
    `/diagnostics/preflight/alerts/${encodeURIComponent(alertId)}/ack`,
    payload
  );
  return data;
}

export async function postPreflightAlertUnacknowledge(
  alertId: string
): Promise<PreflightAlertAcknowledgement> {
  const { data } = await apiClient.post<PreflightAlertAcknowledgement>(
    `/diagnostics/preflight/alerts/${encodeURIComponent(alertId)}/unack`,
    {}
  );
  return data;
}

export async function fetchPreflightAlertAudit(params?: {
  limit?: number;
}): Promise<PreflightAlertAuditResponse> {
  const { data } = await apiClient.get<PreflightAlertAuditResponse>("/diagnostics/preflight/alerts/audit", {
    params,
  });
  return data;
}

export async function triggerPreflightAlertEvaluation(): Promise<PreflightAlertEvaluationResponse> {
  const { data } = await apiClient.post<PreflightAlertEvaluationResponse>("/diagnostics/preflight/alerts/evaluate", {});
  return data;
}

export function buildPreflightArtifactDownloadUrl(
  runId: string,
  sourceName: PreflightSourceName,
  artifactType: PreflightArtifactType
): string {
  const baseUrl = String(apiClient.defaults.baseURL ?? "").replace(/\/$/, "");
  const runEncoded = encodeURIComponent(runId);
  return `${baseUrl}/diagnostics/preflight/runs/${runEncoded}/sources/${sourceName}/download/${artifactType}`;
}

export type DataSource = {
  id: number;
  name: string;
  description?: string | null;
  source_type: string;
  related_contract_id?: string | null;
  related_contract_version?: string | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  last_preflight_status?: string | null;
  last_preflight_at?: string | null;
  last_preflight_run_id?: string | null;
};

export type DataSourceCreateRequest = {
  name: string;
  description?: string;
  source_type?: string;
  related_contract_id?: string;
  related_contract_version?: string;
  is_active?: boolean;
  is_default?: boolean;
};

export type DataSourcePreflightRun = PreflightRunSummary;

export async function fetchDataSources(params?: {
  include_inactive?: boolean;
}): Promise<DataSource[]> {
  const { data } = await apiClient.get<DataSource[]>("/data-sources", { params });
  return data;
}

export async function postDataSource(payload: DataSourceCreateRequest): Promise<DataSource> {
  const { data } = await apiClient.post<DataSource>("/data-sources", payload);
  return data;
}

export async function fetchDataSource(dataSourceId: number): Promise<DataSource> {
  const { data } = await apiClient.get<DataSource>(`/data-sources/${dataSourceId}`);
  return data;
}

export async function fetchDataSourcePreflightRuns(
  dataSourceId: number,
  params?: { limit?: number }
): Promise<DataSourcePreflightRun[]> {
  const { data } = await apiClient.get<DataSourcePreflightRun[]>(
    `/data-sources/${dataSourceId}/preflight-runs`,
    { params }
  );
  return data;
}

export type ContractSummary = {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  latest_version?: string | null;
  versions_count: number;
};

export type ContractVersionSummary = {
  version: string;
  created_at?: string | null;
  changed_by?: string | null;
  changelog?: string | null;
  schema_path: string;
};

export type ContractSchemaSummary = {
  required_columns: string[];
  aliases: Record<string, string[]>;
  dtypes: Record<string, string>;
};

export type ContractVersionDetail = ContractVersionSummary & {
  contract_version: string;
  profiles: Record<string, ContractSchemaSummary>;
};

export type ContractDetail = {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  versions: ContractVersionSummary[];
};

export async function fetchContracts(): Promise<ContractSummary[]> {
  const { data } = await apiClient.get<ContractSummary[]>("/contracts");
  return data;
}

export async function fetchContract(contractId: string): Promise<ContractDetail> {
  const { data } = await apiClient.get<ContractDetail>(`/contracts/${encodeURIComponent(contractId)}`);
  return data;
}

export async function fetchContractVersions(contractId: string): Promise<ContractVersionSummary[]> {
  const { data } = await apiClient.get<ContractVersionSummary[]>(
    `/contracts/${encodeURIComponent(contractId)}/versions`
  );
  return data;
}

export async function fetchContractVersion(
  contractId: string,
  version: string
): Promise<ContractVersionDetail> {
  const { data } = await apiClient.get<ContractVersionDetail>(
    `/contracts/${encodeURIComponent(contractId)}/versions/${encodeURIComponent(version)}`
  );
  return data;
}

export type MLPeriod = {
  start?: string | null;
  end?: string | null;
};

export type MLExperimentListItem = {
  experiment_id: string;
  data_source_id?: number | null;
  model_type: string;
  hyperparameters: Record<string, unknown>;
  training_period: MLPeriod;
  validation_period: MLPeriod;
  metrics: Record<string, unknown>;
  status: string;
  artifact_path?: string | null;
  metadata_path?: string | null;
  created_at: string;
  updated_at: string;
};

export type MLExperimentsResponse = {
  items: MLExperimentListItem[];
  limit: number;
  data_source_id?: number | null;
};

export type MLExperimentDetail = MLExperimentListItem;

export async function fetchMLExperiments(params?: {
  limit?: number;
  data_source_id?: number;
}): Promise<MLExperimentsResponse> {
  const { data } = await apiClient.get<MLExperimentsResponse>("/ml/experiments", { params });
  return data;
}

export async function fetchMLExperiment(experimentId: string): Promise<MLExperimentDetail> {
  const { data } = await apiClient.get<MLExperimentDetail>(`/ml/experiments/${encodeURIComponent(experimentId)}`);
  return data;
}

export type ScenarioSegmentFilter = {
  store_type?: string;
  assortment?: string;
  promo2?: 0 | 1;
};

export type ScenarioRunRequestV2 = {
  store_id?: number;
  segment?: ScenarioSegmentFilter;
  price_change_pct: number;
  promo_mode: "as_is" | "always_on" | "weekends_only" | "off";
  weekend_open: boolean;
  school_holiday: 0 | 1;
  demand_shift_pct: number;
  confidence_level: number;
  horizon_days: number;
  data_source_id?: number;
};

export type ScenarioRunTarget = {
  mode: "store" | "segment";
  store_id?: number;
  segment?: Record<string, unknown>;
  stores_count?: number;
  store_ids?: number[];
};

export type ScenarioRunAssumptions = {
  price_change_pct: number;
  price_elasticity: number;
  price_effect_pct: number;
  effective_demand_shift_pct: number;
};

export type ScenarioRunResponseV2 = {
  run_id: string;
  target: ScenarioRunTarget;
  assumptions: ScenarioRunAssumptions;
  request: Record<string, unknown>;
  summary: ForecastScenarioSummary;
  points: ForecastScenarioPoint[];
};

export async function postScenarioRunV2(payload: ScenarioRunRequestV2): Promise<ScenarioRunResponseV2> {
  const { data } = await apiClient.post<ScenarioRunResponseV2>("/scenario/run", payload);
  return data;
}

export type NotificationEndpoint = {
  id: string;
  channel_type: string;
  enabled: boolean;
  target_hint?: string | null;
  has_target_url: boolean;
  timeout_seconds: number;
  max_attempts: number;
  backoff_seconds: number;
  enabled_event_types: string[];
};

export type NotificationEndpointsResponse = {
  version: string;
  path: string;
  items: NotificationEndpoint[];
};

export type NotificationDelivery = {
  attempt_id: string;
  outbox_item_id: string;
  event_id?: string | null;
  delivery_id?: string | null;
  replayed_from_id?: string | null;
  channel_type: string;
  channel_target: string;
  event_type: string;
  alert_id: string;
  policy_id: string;
  source_name?: string | null;
  attempt_number: number;
  attempt_status: string;
  started_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  http_status?: number | null;
  error_code?: string | null;
  error_message_safe?: string | null;
  created_at: string;
};

export type NotificationDeliveryPage = {
  page: number;
  page_size: number;
  total: number;
  status?: string | null;
  items: NotificationDelivery[];
};

export async function fetchNotificationEndpoints(): Promise<NotificationEndpointsResponse> {
  const { data } = await apiClient.get<NotificationEndpointsResponse>(
    "/diagnostics/preflight/notifications/endpoints"
  );
  return data;
}

export async function fetchNotificationDeliveries(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<NotificationDeliveryPage> {
  const { data } = await apiClient.get<NotificationDeliveryPage>(
    "/diagnostics/preflight/notifications/deliveries",
    { params }
  );
  return data;
}
