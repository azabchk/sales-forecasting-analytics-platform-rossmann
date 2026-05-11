import { useMutation, UseMutationOptions, useQuery, UseQueryOptions } from "@tanstack/react-query";

import {
  ChatResponse,
  DataSource,
  fetchContract,
  fetchContractVersion,
  fetchContracts,
  fetchDataSourcePreflightRuns,
  fetchDataSources,
  fetchKpiSummary,
  fetchLatestPreflight,
  fetchMLExperiment,
  fetchMLExperiments,
  fetchModelMetadata,
  fetchNotificationDeliveries,
  fetchPreflightActiveAlerts,
  fetchPreflightAlertAudit,
  fetchPreflightAlertHistory,
  fetchPreflightAlertPolicies,
  fetchPreflightAlertSilences,
  fetchPreflightRuns,
  fetchPreflightSourceArtifacts,
  fetchPreflightSourceManifest,
  fetchPreflightSourceSemantic,
  fetchPreflightSourceValidation,
  fetchPreflightStats,
  fetchPreflightTopRules,
  fetchPreflightTrends,
  fetchPromoImpact,
  fetchSalesTimeseries,
  fetchStoreComparison,
  fetchStoreDetail,
  fetchStores,
  fetchSystemSummary,
  ForecastBatchRequest,
  ForecastBatchResponse,
  ForecastPoint,
  ForecastScenarioRequest,
  ForecastScenarioResponse,
  KpiSummary,
  ModelMetadata,
  MLExperimentsResponse,
  MLExperimentListItem,
  NotificationDeliveryPage,
  postChatQuery,
  postForecast,
  postForecastBatch,
  postForecastScenario,
  postScenarioRunV2,
  PromoImpactPoint,
  SalesPoint,
  ScenarioRunRequestV2,
  ScenarioRunResponseV2,
  Store,
  StoreComparisonResponse,
  SystemSummary,
} from "../api/endpoints";

// ─── Query key factory ────────────────────────────────────────────────────────

export const queryKeys = {
  stores: ["stores"] as const,
  storeDetail: (id: number) => ["store", id] as const,
  storeComparison: (params: { store_ids: string; date_from: string; date_to: string }) =>
    ["store-comparison", params] as const,
  systemSummary: ["system-summary"] as const,
  kpiSummary: (params: { date_from: string; date_to: string; store_id?: number }) =>
    ["kpi-summary", params] as const,
  salesTimeseries: (params: {
    granularity: "daily" | "monthly";
    date_from: string;
    date_to: string;
    store_id?: number;
  }) => ["sales-timeseries", params] as const,
  promoImpact: (storeId?: number) => ["promo-impact", storeId ?? null] as const,
  modelMetadata: ["model-metadata"] as const,
  mlExperiments: (params?: { limit?: number; data_source_id?: number }) =>
    ["ml-experiments", params ?? {}] as const,
  mlExperiment: (id: string) => ["ml-experiment", id] as const,
  dataSources: (params?: { include_inactive?: boolean }) => ["data-sources", params ?? {}] as const,
  dataSourcePreflightRuns: (id: number, limit?: number) => ["data-source-preflight-runs", id, limit ?? 25] as const,
  contracts: ["contracts"] as const,
  contractDetail: (id: string) => ["contract", id] as const,
  contractVersion: (id: string, version: string) => ["contract-version", id, version] as const,
  notificationDeliveries: (params?: { page?: number; page_size?: number; status?: string }) =>
    ["notification-deliveries", params ?? {}] as const,
  preflightRuns: (params?: object) => ["preflight-runs", params ?? {}] as const,
  preflightLatest: (dataSourceId?: number) => ["preflight-latest", dataSourceId ?? null] as const,
  preflightStats: (params?: object) => ["preflight-stats", params ?? {}] as const,
  preflightTrends: (params?: object) => ["preflight-trends", params ?? {}] as const,
  preflightTopRules: (params?: object) => ["preflight-top-rules", params ?? {}] as const,
  preflightSourceValidation: (runId: string, source: string) => ["preflight-validation", runId, source] as const,
  preflightSourceSemantic: (runId: string, source: string) => ["preflight-semantic", runId, source] as const,
  preflightSourceManifest: (runId: string, source: string) => ["preflight-manifest", runId, source] as const,
  preflightSourceArtifacts: (runId: string, source: string) => ["preflight-artifacts", runId, source] as const,
  preflightActiveAlerts: ["preflight-active-alerts"] as const,
  preflightAlertHistory: (params?: object) => ["preflight-alert-history", params ?? {}] as const,
  preflightAlertPolicies: ["preflight-alert-policies"] as const,
  preflightAlertSilences: ["preflight-alert-silences"] as const,
  preflightAlertAudit: (params?: object) => ["preflight-alert-audit", params ?? {}] as const,
};

// ─── Query hooks ──────────────────────────────────────────────────────────────

export function useStores(options?: Partial<UseQueryOptions<Store[]>>) {
  return useQuery<Store[]>({
    queryKey: queryKeys.stores,
    queryFn: fetchStores,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    ...options,
  });
}

export function useStoreDetail(storeId: number, options?: Partial<UseQueryOptions<Store>>) {
  return useQuery<Store>({
    queryKey: queryKeys.storeDetail(storeId),
    queryFn: () => fetchStoreDetail(storeId),
    staleTime: 5 * 60 * 1000,
    enabled: storeId > 0,
    ...options,
  });
}

export function useStoreComparison(
  params: { store_ids: string; date_from: string; date_to: string },
  options?: Partial<UseQueryOptions<StoreComparisonResponse>>
) {
  const ids = params.store_ids.split(",").filter(Boolean);
  return useQuery<StoreComparisonResponse>({
    queryKey: queryKeys.storeComparison(params),
    queryFn: () => fetchStoreComparison(params),
    staleTime: 2 * 60 * 1000,
    enabled: ids.length >= 2 && !!params.date_from && !!params.date_to && params.date_from <= params.date_to,
    ...options,
  });
}

export function useSystemSummary(options?: Partial<UseQueryOptions<SystemSummary>>) {
  return useQuery<SystemSummary>({
    queryKey: queryKeys.systemSummary,
    queryFn: fetchSystemSummary,
    staleTime: 2 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    ...options,
  });
}

export function useKpiSummary(
  params: { date_from: string; date_to: string; store_id?: number },
  options?: Partial<UseQueryOptions<KpiSummary>>
) {
  return useQuery<KpiSummary>({
    queryKey: queryKeys.kpiSummary(params),
    queryFn: () => fetchKpiSummary(params),
    staleTime: 60 * 1000,
    enabled: !!params.date_from && !!params.date_to && params.date_from <= params.date_to,
    ...options,
  });
}

export function useSalesTimeseries(
  params: { granularity: "daily" | "monthly"; date_from: string; date_to: string; store_id?: number },
  options?: Partial<UseQueryOptions<SalesPoint[]>>
) {
  return useQuery<SalesPoint[]>({
    queryKey: queryKeys.salesTimeseries(params),
    queryFn: () => fetchSalesTimeseries(params),
    staleTime: 60 * 1000,
    enabled: !!params.date_from && !!params.date_to && params.date_from <= params.date_to,
    ...options,
  });
}

export function usePromoImpact(storeId?: number, options?: Partial<UseQueryOptions<PromoImpactPoint[]>>) {
  return useQuery<PromoImpactPoint[]>({
    queryKey: queryKeys.promoImpact(storeId),
    queryFn: () => fetchPromoImpact(storeId),
    staleTime: 10 * 60 * 1000,
    ...options,
  });
}

export function useModelMetadata(options?: Partial<UseQueryOptions<ModelMetadata>>) {
  return useQuery<ModelMetadata>({
    queryKey: queryKeys.modelMetadata,
    queryFn: fetchModelMetadata,
    staleTime: 10 * 60 * 1000,
    ...options,
  });
}

export function useMlExperiments(
  params?: { limit?: number; data_source_id?: number },
  options?: Partial<UseQueryOptions<MLExperimentsResponse>>
) {
  return useQuery<MLExperimentsResponse>({
    queryKey: queryKeys.mlExperiments(params),
    queryFn: () => fetchMLExperiments(params),
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

export function useMlExperiment(id: string, options?: Partial<UseQueryOptions<MLExperimentListItem>>) {
  return useQuery<MLExperimentListItem>({
    queryKey: queryKeys.mlExperiment(id),
    queryFn: () => fetchMLExperiment(id),
    staleTime: 5 * 60 * 1000,
    enabled: !!id,
    ...options,
  });
}

export function useDataSources(
  params?: { include_inactive?: boolean },
  options?: Partial<UseQueryOptions<DataSource[]>>
) {
  return useQuery<DataSource[]>({
    queryKey: queryKeys.dataSources(params),
    queryFn: () => fetchDataSources(params),
    staleTime: 2 * 60 * 1000,
    ...options,
  });
}

export function useDataSourcePreflightRuns(
  dataSourceId: number,
  limit = 25,
  options?: Partial<UseQueryOptions<unknown>>
) {
  return useQuery({
    queryKey: queryKeys.dataSourcePreflightRuns(dataSourceId, limit),
    queryFn: () => fetchDataSourcePreflightRuns(dataSourceId, { limit }),
    staleTime: 60 * 1000,
    enabled: dataSourceId > 0,
    ...options,
  });
}

export function useContracts(options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.contracts,
    queryFn: fetchContracts,
    staleTime: 10 * 60 * 1000,
    ...options,
  });
}

export function useContractDetail(id: string, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.contractDetail(id),
    queryFn: () => fetchContract(id),
    staleTime: 10 * 60 * 1000,
    enabled: !!id,
    ...options,
  });
}

export function useContractVersion(id: string, version: string, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.contractVersion(id, version),
    queryFn: () => fetchContractVersion(id, version),
    staleTime: 10 * 60 * 1000,
    enabled: !!id && !!version,
    ...options,
  });
}

export function useNotificationDeliveries(
  params?: { page?: number; page_size?: number; status?: string },
  options?: Partial<UseQueryOptions<NotificationDeliveryPage>>
) {
  return useQuery<NotificationDeliveryPage>({
    queryKey: queryKeys.notificationDeliveries(params),
    queryFn: () => fetchNotificationDeliveries(params),
    staleTime: 30 * 1000,
    ...options,
  });
}

export function usePreflightRuns(
  params?: { limit?: number; source_name?: string; data_source_id?: number },
  options?: Partial<UseQueryOptions<unknown>>
) {
  return useQuery({
    queryKey: queryKeys.preflightRuns(params),
    queryFn: () => fetchPreflightRuns({ limit: params?.limit ?? 20, ...params } as any),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function usePreflightLatest(options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightLatest(),
    queryFn: () => fetchLatestPreflight(),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function usePreflightStats(params?: object, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightStats(params),
    queryFn: () => fetchPreflightStats(params as any),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function usePreflightTrends(params?: object, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightTrends(params),
    queryFn: () => fetchPreflightTrends(params as any),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function usePreflightTopRules(params?: object, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightTopRules(params),
    queryFn: () => fetchPreflightTopRules(params as any),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function usePreflightSourceValidation(
  runId: string,
  source: string,
  options?: Partial<UseQueryOptions<unknown>>
) {
  return useQuery({
    queryKey: queryKeys.preflightSourceValidation(runId, source),
    queryFn: () => fetchPreflightSourceValidation(runId, source as any),
    staleTime: 5 * 60 * 1000,
    enabled: !!runId && !!source,
    ...options,
  });
}

export function usePreflightSourceSemantic(
  runId: string,
  source: string,
  options?: Partial<UseQueryOptions<unknown>>
) {
  return useQuery({
    queryKey: queryKeys.preflightSourceSemantic(runId, source),
    queryFn: () => fetchPreflightSourceSemantic(runId, source as any),
    staleTime: 5 * 60 * 1000,
    enabled: !!runId && !!source,
    ...options,
  });
}

export function usePreflightSourceManifest(
  runId: string,
  source: string,
  options?: Partial<UseQueryOptions<unknown>>
) {
  return useQuery({
    queryKey: queryKeys.preflightSourceManifest(runId, source),
    queryFn: () => fetchPreflightSourceManifest(runId, source as any),
    staleTime: 5 * 60 * 1000,
    enabled: !!runId && !!source,
    ...options,
  });
}

export function usePreflightSourceArtifacts(
  runId: string,
  source: string,
  options?: Partial<UseQueryOptions<unknown>>
) {
  return useQuery({
    queryKey: queryKeys.preflightSourceArtifacts(runId, source),
    queryFn: () => fetchPreflightSourceArtifacts(runId, source as any),
    staleTime: 5 * 60 * 1000,
    enabled: !!runId && !!source,
    ...options,
  });
}

export function usePreflightActiveAlerts(options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightActiveAlerts,
    queryFn: () => fetchPreflightActiveAlerts(),
    staleTime: 30 * 1000,
    ...options,
  });
}

export function usePreflightAlertHistory(params?: object, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightAlertHistory(params),
    queryFn: () => fetchPreflightAlertHistory(params as any),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function usePreflightAlertPolicies(options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightAlertPolicies,
    queryFn: () => fetchPreflightAlertPolicies(),
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

export function usePreflightAlertSilences(options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightAlertSilences,
    queryFn: () => fetchPreflightAlertSilences(),
    staleTime: 30 * 1000,
    ...options,
  });
}

export function usePreflightAlertAudit(params?: object, options?: Partial<UseQueryOptions<unknown>>) {
  return useQuery({
    queryKey: queryKeys.preflightAlertAudit(params),
    queryFn: () => fetchPreflightAlertAudit(params as any),
    staleTime: 60 * 1000,
    ...options,
  });
}

// ─── Mutation hooks ───────────────────────────────────────────────────────────

export function useForecast(
  options?: Partial<UseMutationOptions<ForecastPoint[], Error, { store_id: number; horizon_days: number }>>
) {
  return useMutation<ForecastPoint[], Error, { store_id: number; horizon_days: number }>({
    mutationFn: postForecast,
    ...options,
  });
}

export function useForecastBatch(
  options?: Partial<UseMutationOptions<ForecastBatchResponse, Error, ForecastBatchRequest>>
) {
  return useMutation<ForecastBatchResponse, Error, ForecastBatchRequest>({
    mutationFn: postForecastBatch,
    ...options,
  });
}

export function useForecastScenario(
  options?: Partial<UseMutationOptions<ForecastScenarioResponse, Error, ForecastScenarioRequest>>
) {
  return useMutation<ForecastScenarioResponse, Error, ForecastScenarioRequest>({
    mutationFn: postForecastScenario,
    ...options,
  });
}

export function useScenarioRun(
  options?: Partial<UseMutationOptions<ScenarioRunResponseV2, Error, ScenarioRunRequestV2>>
) {
  return useMutation<ScenarioRunResponseV2, Error, ScenarioRunRequestV2>({
    mutationFn: postScenarioRunV2,
    ...options,
  });
}

export function useChatQuery(
  options?: Partial<UseMutationOptions<ChatResponse, Error, { message: string }>>
) {
  return useMutation<ChatResponse, Error, { message: string }>({
    mutationFn: postChatQuery,
    ...options,
  });
}
