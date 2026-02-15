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
