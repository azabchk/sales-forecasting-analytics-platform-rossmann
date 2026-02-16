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
