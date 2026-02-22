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

export function buildPreflightArtifactDownloadUrl(
  runId: string,
  sourceName: PreflightSourceName,
  artifactType: PreflightArtifactType
): string {
  const baseUrl = String(apiClient.defaults.baseURL ?? "").replace(/\/$/, "");
  const runEncoded = encodeURIComponent(runId);
  return `${baseUrl}/diagnostics/preflight/runs/${runEncoded}/sources/${sourceName}/download/${artifactType}`;
}
