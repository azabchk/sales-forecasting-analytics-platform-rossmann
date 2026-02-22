import React from "react";
import axios from "axios";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { extractApiError } from "../api/client";
import {
  buildPreflightArtifactDownloadUrl,
  fetchPreflightActiveAlerts,
  fetchPreflightAlertAudit,
  fetchPreflightAlertHistory,
  fetchPreflightAlertSilences,
  fetchLatestPreflight,
  postPreflightAlertAcknowledge,
  postPreflightAlertSilence,
  postPreflightAlertSilenceExpire,
  postPreflightAlertUnacknowledge,
  fetchPreflightStats,
  fetchPreflightTopRules,
  fetchPreflightTrends,
  fetchPreflightRunDetails,
  fetchPreflightRuns,
  fetchPreflightSourceArtifacts,
  fetchPreflightSourceManifest,
  fetchPreflightSourceSemantic,
  fetchPreflightSourceValidation,
  PreflightAnalyticsQueryParams,
  PreflightActiveAlertsResponse,
  PreflightAlertAuditResponse,
  PreflightAlertHistoryResponse,
  PreflightAlertSilencesResponse,
  PreflightManifestArtifactResponse,
  PreflightMode,
  PreflightRunDetailResponse,
  PreflightRunSummary,
  PreflightSemanticArtifactResponse,
  PreflightSourceArtifactsResponse,
  PreflightSourceName,
  PreflightStatsResponse,
  PreflightTopRulesResponse,
  PreflightTrendsResponse,
  PreflightValidationArtifactResponse,
} from "../api/endpoints";
import LoadingBlock from "../components/LoadingBlock";
import StatusBadge from "../components/StatusBadge";
import { useI18n } from "../lib/i18n";

type SourceFilter = "all" | PreflightSourceName;
type FinalStatusFilter = "all" | "PASS" | "WARN" | "FAIL";
type TrendRow = { status: "PASS" | "WARN" | "FAIL"; count: number };
type AnalyticsWindow = "7" | "30" | "custom";
type AnalyticsModeFilter = "all" | Extract<PreflightMode, "off" | "report_only" | "enforce">;
type ArtifactTab = "validation" | "semantic" | "manifest" | "artifacts";
type TabLoadingState = Record<ArtifactTab, boolean>;
type TabErrorState = Record<ArtifactTab, string>;

function formatTimestamp(value: string | null | undefined, localeTag: string): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(localeTag, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTrendBucket(value: string, localeTag: string, bucket: "day" | "hour"): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  if (bucket === "hour") {
    return parsed.toLocaleString(localeTag, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
    });
  }
  return parsed.toLocaleDateString(localeTag, {
    month: "short",
    day: "2-digit",
  });
}

function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function truncateMiddle(value: string, maxLength = 72): string {
  if (value.length <= maxLength) {
    return value;
  }
  const keep = Math.floor((maxLength - 3) / 2);
  return `${value.slice(0, keep)}...${value.slice(value.length - keep)}`;
}

function formatMetricValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(4);
}

function addHoursIso(hours: number): string {
  const value = new Date();
  value.setHours(value.getHours() + hours);
  return value.toISOString();
}

function sourceLabel(sourceName: string, locale: "en" | "ru"): string {
  if (sourceName === "train") {
    return locale === "ru" ? "Train (продажи)" : "Train";
  }
  if (sourceName === "store") {
    return locale === "ru" ? "Store (справочник)" : "Store";
  }
  return sourceName;
}

function TrendTooltip({
  active,
  payload,
  label,
  locale,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
  locale: "en" | "ru";
}) {
  if (!active || !payload || payload.length === 0 || !label) {
    return null;
  }
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{locale === "ru" ? "Статус" : "Status"}: {label}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "Количество" : "Count"}: {payload[0].value}</p>
    </div>
  );
}

export default function PreflightDiagnostics() {
  const { locale, localeTag } = useI18n();

  const [sourceFilter, setSourceFilter] = React.useState<SourceFilter>("all");
  const [limit, setLimit] = React.useState<number>(20);
  const [finalStatusFilter, setFinalStatusFilter] = React.useState<FinalStatusFilter>("all");
  const [lastUpdated, setLastUpdated] = React.useState("-");

  const [latest, setLatest] = React.useState<PreflightRunDetailResponse | null>(null);
  const [latestLoading, setLatestLoading] = React.useState(false);
  const [latestError, setLatestError] = React.useState("");

  const [runs, setRuns] = React.useState<PreflightRunSummary[]>([]);
  const [runsLoading, setRunsLoading] = React.useState(false);
  const [runsError, setRunsError] = React.useState("");

  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [selectedRun, setSelectedRun] = React.useState<PreflightRunDetailResponse | null>(null);
  const [detailsLoading, setDetailsLoading] = React.useState(false);
  const [detailsError, setDetailsError] = React.useState("");

  const [analyticsSourceFilter, setAnalyticsSourceFilter] = React.useState<SourceFilter>("all");
  const [analyticsModeFilter, setAnalyticsModeFilter] = React.useState<AnalyticsModeFilter>("all");
  const [analyticsWindow, setAnalyticsWindow] = React.useState<AnalyticsWindow>("7");
  const [analyticsDateFrom, setAnalyticsDateFrom] = React.useState("");
  const [analyticsDateTo, setAnalyticsDateTo] = React.useState("");

  const [stats, setStats] = React.useState<PreflightStatsResponse | null>(null);
  const [trends, setTrends] = React.useState<PreflightTrendsResponse | null>(null);
  const [topRules, setTopRules] = React.useState<PreflightTopRulesResponse | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = React.useState(false);
  const [analyticsError, setAnalyticsError] = React.useState("");

  const [activeAlerts, setActiveAlerts] = React.useState<PreflightActiveAlertsResponse | null>(null);
  const [alertHistory, setAlertHistory] = React.useState<PreflightAlertHistoryResponse | null>(null);
  const [alertSilences, setAlertSilences] = React.useState<PreflightAlertSilencesResponse | null>(null);
  const [alertAudit, setAlertAudit] = React.useState<PreflightAlertAuditResponse | null>(null);
  const [apiKeyInput, setApiKeyInput] = React.useState("");
  const [apiKeyConfigured, setApiKeyConfigured] = React.useState(false);
  const [authMessage, setAuthMessage] = React.useState("");
  const [alertsActionError, setAlertsActionError] = React.useState("");
  const [alertsActionLoading, setAlertsActionLoading] = React.useState<Record<string, boolean>>({});
  const [alertsLoading, setAlertsLoading] = React.useState(false);
  const [alertsError, setAlertsError] = React.useState("");

  const [selectedSourceName, setSelectedSourceName] = React.useState<PreflightSourceName | null>(null);
  const [activeArtifactTab, setActiveArtifactTab] = React.useState<ArtifactTab>("validation");

  const [validationCache, setValidationCache] = React.useState<Record<string, PreflightValidationArtifactResponse>>({});
  const [semanticCache, setSemanticCache] = React.useState<Record<string, PreflightSemanticArtifactResponse>>({});
  const [manifestCache, setManifestCache] = React.useState<Record<string, PreflightManifestArtifactResponse>>({});
  const [artifactsCache, setArtifactsCache] = React.useState<Record<string, PreflightSourceArtifactsResponse>>({});

  const [tabLoading, setTabLoading] = React.useState<TabLoadingState>({
    validation: false,
    semantic: false,
    manifest: false,
    artifacts: false,
  });
  const [tabErrors, setTabErrors] = React.useState<TabErrorState>({
    validation: "",
    semantic: "",
    manifest: "",
    artifacts: "",
  });

  const isAuthError = React.useCallback((errorResponse: unknown): string | null => {
    if (!axios.isAxiosError(errorResponse)) {
      return null;
    }

    const statusCode = errorResponse.response?.status;
    if (statusCode === 401) {
      return locale === "ru"
        ? "Доступ запрещен: API ключ отсутствует или недействителен."
        : "Unauthorized: API key is missing or invalid.";
    }
    if (statusCode === 403) {
      return locale === "ru"
        ? "Недостаточно прав для этого действия. Проверьте scope API ключа."
        : "Forbidden: this API key does not have the required diagnostics scope.";
    }
    return null;
  }, [locale]);

  React.useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const storedKey = (window.sessionStorage.getItem("diagnostics_api_key") ?? "").trim();
    if (storedKey) {
      setApiKeyInput(storedKey);
      setApiKeyConfigured(true);
      setAuthMessage("");
      return;
    }

    setApiKeyInput("");
    setApiKeyConfigured(false);
    setAuthMessage(
      locale === "ru"
        ? "Укажите X-API-Key для доступа к Diagnostics API."
        : "Set X-API-Key to access protected diagnostics endpoints."
    );
  }, [locale]);

  const handleSaveApiKey = React.useCallback(() => {
    const normalized = apiKeyInput.trim();
    if (!normalized) {
      setApiKeyConfigured(false);
      setAuthMessage(
        locale === "ru" ? "API ключ не может быть пустым." : "API key cannot be empty."
      );
      return;
    }

    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("diagnostics_api_key", normalized);
    }
    setApiKeyInput(normalized);
    setApiKeyConfigured(true);
    setAuthMessage("");
  }, [apiKeyInput, locale]);

  const handleClearApiKey = React.useCallback(() => {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem("diagnostics_api_key");
    }

    setApiKeyInput("");
    setApiKeyConfigured(false);
    setAuthMessage(
      locale === "ru"
        ? "API ключ очищен. Для продолжения введите новый ключ."
        : "API key cleared. Enter a new key to continue."
    );
  }, [locale]);

  const loadLatest = React.useCallback(async () => {
    if (!apiKeyConfigured) {
      setLatest(null);
      setLatestError("");
      return;
    }
    setLatestLoading(true);
    setLatestError("");
    try {
      const response = await fetchLatestPreflight();
      setLatest(response);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      if (axios.isAxiosError(errorResponse) && errorResponse.response?.status === 404) {
        setLatest(null);
        setLatestError("");
        return;
      }
      const authError = isAuthError(errorResponse);
      if (authError) {
        setAuthMessage(authError);
      }
      setLatest(null);
      setLatestError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить последний запуск preflight." : "Unable to load latest preflight run."
        )
      );
    } finally {
      setLatestLoading(false);
    }
  }, [apiKeyConfigured, isAuthError, locale, localeTag]);

  const loadRuns = React.useCallback(async () => {
    if (!apiKeyConfigured) {
      setRuns([]);
      setRunsError("");
      setSelectedRunId(null);
      return;
    }
    setRunsLoading(true);
    setRunsError("");
    try {
      const response = await fetchPreflightRuns({
        limit,
        ...(sourceFilter === "all" ? {} : { source_name: sourceFilter }),
      });
      setRuns(response.items);
      setSelectedRunId((current) => {
        if (current && response.items.some((item) => item.run_id === current)) {
          return current;
        }
        return response.items.length > 0 ? response.items[0].run_id : null;
      });
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      const authError = isAuthError(errorResponse);
      if (authError) {
        setAuthMessage(authError);
      }
      setRuns([]);
      setSelectedRunId(null);
      setRunsError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить историю запусков preflight." : "Unable to load preflight run history."
        )
      );
    } finally {
      setRunsLoading(false);
    }
  }, [apiKeyConfigured, isAuthError, limit, locale, localeTag, sourceFilter]);

  const loadSelectedRun = React.useCallback(async () => {
    if (!apiKeyConfigured) {
      setSelectedRun(null);
      setDetailsError("");
      return;
    }
    if (!selectedRunId) {
      setSelectedRun(null);
      setDetailsError("");
      return;
    }
    setDetailsLoading(true);
    setDetailsError("");
    try {
      const response = await fetchPreflightRunDetails(selectedRunId);
      setSelectedRun(response);
    } catch (errorResponse) {
      const authError = isAuthError(errorResponse);
      if (authError) {
        setAuthMessage(authError);
      }
      setSelectedRun(null);
      setDetailsError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить детали запуска." : "Unable to load run details."
        )
      );
    } finally {
      setDetailsLoading(false);
    }
  }, [apiKeyConfigured, isAuthError, locale, selectedRunId]);

  const loadAnalytics = React.useCallback(async () => {
    if (!apiKeyConfigured) {
      setStats(null);
      setTrends(null);
      setTopRules(null);
      setAnalyticsError("");
      return;
    }
    setAnalyticsLoading(true);
    setAnalyticsError("");

    const params: PreflightAnalyticsQueryParams = {
      ...(analyticsSourceFilter === "all" ? {} : { source_name: analyticsSourceFilter }),
      ...(analyticsModeFilter === "all" ? {} : { mode: analyticsModeFilter }),
    };

    if (analyticsWindow === "custom") {
      if (analyticsDateFrom) {
        params.date_from = analyticsDateFrom;
      }
      if (analyticsDateTo) {
        params.date_to = analyticsDateTo;
      }
    } else {
      params.days = Number(analyticsWindow);
    }

    try {
      const [statsResponse, trendsResponse, topRulesResponse] = await Promise.all([
        fetchPreflightStats(params),
        fetchPreflightTrends({ ...params, bucket: "day" }),
        fetchPreflightTopRules({ ...params, limit: 10 }),
      ]);
      setStats(statsResponse);
      setTrends(trendsResponse);
      setTopRules(topRulesResponse);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      const authError = isAuthError(errorResponse);
      if (authError) {
        setAuthMessage(authError);
      }
      setStats(null);
      setTrends(null);
      setTopRules(null);
      setAnalyticsError(
        extractApiError(
          errorResponse,
          locale === "ru"
            ? "Не удалось загрузить агрегированную аналитику preflight."
            : "Unable to load aggregated preflight analytics."
        )
      );
    } finally {
      setAnalyticsLoading(false);
    }
  }, [
    analyticsDateFrom,
    analyticsDateTo,
    apiKeyConfigured,
    analyticsModeFilter,
    analyticsSourceFilter,
    analyticsWindow,
    isAuthError,
    locale,
    localeTag,
  ]);

  const loadAlerts = React.useCallback(async () => {
    if (!apiKeyConfigured) {
      setActiveAlerts(null);
      setAlertHistory(null);
      setAlertSilences(null);
      setAlertAudit(null);
      setAlertsError("");
      return;
    }
    setAlertsLoading(true);
    setAlertsError("");
    try {
      const [activeResponse, historyResponse, silencesResponse, auditResponse] = await Promise.all([
        fetchPreflightActiveAlerts({ auto_evaluate: true }),
        fetchPreflightAlertHistory({ limit: 20 }),
        fetchPreflightAlertSilences({ limit: 50, include_expired: false }),
        fetchPreflightAlertAudit({ limit: 50 }),
      ]);
      setActiveAlerts(activeResponse);
      setAlertHistory(historyResponse);
      setAlertSilences(silencesResponse);
      setAlertAudit(auditResponse);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      const authError = isAuthError(errorResponse);
      if (authError) {
        setAuthMessage(authError);
      }
      setActiveAlerts(null);
      setAlertHistory(null);
      setAlertSilences(null);
      setAlertAudit(null);
      setAlertsError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить preflight alerts." : "Unable to load preflight alerts."
        )
      );
    } finally {
      setAlertsLoading(false);
    }
  }, [apiKeyConfigured, isAuthError, locale, localeTag]);

  const runAlertAction = React.useCallback(
    async (key: string, task: () => Promise<void>) => {
      setAlertsActionError("");
      setAlertsActionLoading((prev) => ({ ...prev, [key]: true }));
      try {
        await task();
        await loadAlerts();
      } catch (errorResponse) {
        const authError = isAuthError(errorResponse);
        if (authError) {
          setAuthMessage(authError);
        }
        setAlertsActionError(
          extractApiError(
            errorResponse,
            locale === "ru" ? "Не удалось выполнить действие по alert." : "Unable to apply alert action."
          )
        );
      } finally {
        setAlertsActionLoading((prev) => ({ ...prev, [key]: false }));
      }
    },
    [isAuthError, loadAlerts, locale]
  );

  const handleAckAlert = React.useCallback(
    async (alertId: string) => {
      const note = window.prompt(
        locale === "ru" ? "Комментарий ACK (опционально):" : "ACK note (optional):",
        ""
      );
      if (note === null) {
        return;
      }
      await runAlertAction(`ack:${alertId}`, async () => {
        await postPreflightAlertAcknowledge(alertId, { note: note || undefined });
      });
    },
    [locale, runAlertAction]
  );

  const handleUnackAlert = React.useCallback(
    async (alertId: string) => {
      await runAlertAction(`unack:${alertId}`, async () => {
        await postPreflightAlertUnacknowledge(alertId);
      });
    },
    [runAlertAction]
  );

  const handleSilenceAlert = React.useCallback(
    async (payload: {
      alertId: string;
      policyId: string;
      sourceName?: PreflightSourceName | null;
      severity?: string | null;
      ruleId?: string | null;
      hours: number;
    }) => {
      const defaultReason =
        locale === "ru"
          ? `Временный silence (${payload.hours}ч) из Diagnostics UI`
          : `Temporary silence (${payload.hours}h) from diagnostics UI`;
      const reason = window.prompt(
        locale === "ru" ? "Причина silence:" : "Silence reason:",
        defaultReason
      );
      if (reason === null) {
        return;
      }
      await runAlertAction(`silence:${payload.alertId}:${payload.hours}`, async () => {
        await postPreflightAlertSilence(
          {
            ends_at: addHoursIso(payload.hours),
            reason: reason || defaultReason,
            policy_id: payload.policyId,
            source_name: payload.sourceName ?? undefined,
            severity: payload.severity ?? undefined,
            rule_id: payload.ruleId ?? undefined,
          },
        );
      });
    },
    [locale, runAlertAction]
  );

  const handleExpireSilence = React.useCallback(
    async (silenceId: string) => {
      await runAlertAction(`expire:${silenceId}`, async () => {
        await postPreflightAlertSilenceExpire(silenceId);
      });
    },
    [runAlertAction]
  );

  React.useEffect(() => {
    void loadLatest();
  }, [loadLatest]);

  React.useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  React.useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  React.useEffect(() => {
    void loadAlerts();
  }, [loadAlerts]);

  React.useEffect(() => {
    void loadSelectedRun();
  }, [loadSelectedRun]);

  React.useEffect(() => {
    setActiveArtifactTab("validation");
  }, [selectedRunId]);

  React.useEffect(() => {
    if (!selectedRun || selectedRun.records.length === 0) {
      setSelectedSourceName(null);
      return;
    }

    setSelectedSourceName((current) => {
      if (current && selectedRun.records.some((record) => record.source_name === current)) {
        return current;
      }
      return selectedRun.records[0].source_name;
    });
  }, [selectedRun]);

  const visibleRuns = React.useMemo(() => {
    if (finalStatusFilter === "all") {
      return runs;
    }
    return runs.filter((run) => run.final_status.toUpperCase() === finalStatusFilter);
  }, [finalStatusFilter, runs]);

  const trendData = React.useMemo<TrendRow[]>(() => {
    const counts: Record<"PASS" | "WARN" | "FAIL", number> = { PASS: 0, WARN: 0, FAIL: 0 };
    for (const run of visibleRuns) {
      const key = run.final_status.toUpperCase();
      if (key === "PASS" || key === "WARN" || key === "FAIL") {
        counts[key] += 1;
      }
    }
    return [
      { status: "PASS", count: counts.PASS },
      { status: "WARN", count: counts.WARN },
      { status: "FAIL", count: counts.FAIL },
    ];
  }, [visibleRuns]);

  const trendColors: Record<TrendRow["status"], string> = {
    PASS: "var(--status-pass)",
    WARN: "var(--status-warn)",
    FAIL: "var(--status-fail)",
  };

  const analyticsTrendData = React.useMemo(() => {
    if (!trends?.items) {
      return [];
    }
    return trends.items.map((item) => ({
      ...item,
      bucket_label: formatTrendBucket(item.bucket_start, localeTag, trends.bucket),
    }));
  }, [localeTag, trends]);

  const refreshAll = React.useCallback(() => {
    void Promise.all([loadLatest(), loadRuns(), loadSelectedRun(), loadAnalytics(), loadAlerts()]);
  }, [loadAlerts, loadAnalytics, loadLatest, loadRuns, loadSelectedRun]);

  const latestRecords = latest?.records ?? [];
  const activeAlertItems = activeAlerts?.items ?? [];
  const alertHistoryItems = alertHistory?.items ?? [];
  const alertSilenceItems = alertSilences?.items ?? [];
  const alertAuditItems = alertAudit?.items ?? [];

  const selectedRecord = React.useMemo(() => {
    if (!selectedRun || !selectedSourceName) {
      return null;
    }
    return selectedRun.records.find((record) => record.source_name === selectedSourceName) ?? null;
  }, [selectedRun, selectedSourceName]);

  const detailCacheKey = React.useMemo(() => {
    if (!selectedRun || !selectedSourceName) {
      return null;
    }
    return `${selectedRun.run_id}:${selectedSourceName}`;
  }, [selectedRun, selectedSourceName]);

  React.useEffect(() => {
    if (!apiKeyConfigured || !selectedRun || !selectedSourceName || !detailCacheKey) {
      return;
    }

    let active = true;
    const runId = selectedRun.run_id;
    const sourceName: PreflightSourceName = selectedSourceName;
    const cacheKey: string = detailCacheKey;

    async function loadActiveTab(): Promise<void> {
      const setLoading = (value: boolean) => {
        setTabLoading((prev) => ({ ...prev, [activeArtifactTab]: value }));
      };
      const clearError = () => {
        setTabErrors((prev) => ({ ...prev, [activeArtifactTab]: "" }));
      };
      const setError = (message: string) => {
        setTabErrors((prev) => ({ ...prev, [activeArtifactTab]: message }));
      };

      try {
        if (activeArtifactTab === "validation") {
          if (validationCache[cacheKey]) {
            return;
          }
          clearError();
          setLoading(true);
          const payload = await fetchPreflightSourceValidation(runId, sourceName);
          if (!active) {
            return;
          }
          setValidationCache((prev) => ({ ...prev, [cacheKey]: payload }));
          return;
        }

        if (activeArtifactTab === "semantic") {
          if (semanticCache[cacheKey]) {
            return;
          }
          clearError();
          setLoading(true);
          const payload = await fetchPreflightSourceSemantic(runId, sourceName);
          if (!active) {
            return;
          }
          setSemanticCache((prev) => ({ ...prev, [cacheKey]: payload }));
          return;
        }

        if (activeArtifactTab === "manifest") {
          if (manifestCache[cacheKey]) {
            return;
          }
          clearError();
          setLoading(true);
          const payload = await fetchPreflightSourceManifest(runId, sourceName);
          if (!active) {
            return;
          }
          setManifestCache((prev) => ({ ...prev, [cacheKey]: payload }));
          return;
        }

        if (artifactsCache[cacheKey]) {
          return;
        }
        clearError();
        setLoading(true);
        const payload = await fetchPreflightSourceArtifacts(runId, sourceName);
        if (!active) {
          return;
        }
        setArtifactsCache((prev) => ({ ...prev, [cacheKey]: payload }));
      } catch (errorResponse) {
        if (!active) {
          return;
        }
        const authError = isAuthError(errorResponse);
        if (authError) {
          setAuthMessage(authError);
        }
        setError(
          extractApiError(
            errorResponse,
            locale === "ru" ? "Не удалось загрузить артефакт preflight." : "Unable to load preflight artifact."
          )
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadActiveTab();

    return () => {
      active = false;
    };
  }, [
    activeArtifactTab,
    apiKeyConfigured,
    artifactsCache,
    detailCacheKey,
    isAuthError,
    locale,
    manifestCache,
    selectedRun,
    selectedSourceName,
    semanticCache,
    validationCache,
  ]);

  const validationData = detailCacheKey ? validationCache[detailCacheKey] ?? null : null;
  const semanticData = detailCacheKey ? semanticCache[detailCacheKey] ?? null : null;
  const manifestData = detailCacheKey ? manifestCache[detailCacheKey] ?? null : null;
  const artifactsData = detailCacheKey ? artifactsCache[detailCacheKey] ?? null : null;

  const tabDefs = React.useMemo(
    () => [
      { key: "validation" as const, label: locale === "ru" ? "Validation" : "Validation" },
      { key: "semantic" as const, label: locale === "ru" ? "Semantic Rules" : "Semantic Rules" },
      { key: "manifest" as const, label: locale === "ru" ? "Manifest" : "Unification Manifest" },
      { key: "artifacts" as const, label: locale === "ru" ? "Artifacts" : "Artifacts" },
    ],
    [locale]
  );

  const activeTabHasData =
    (activeArtifactTab === "validation" && validationData !== null) ||
    (activeArtifactTab === "semantic" && semanticData !== null) ||
    (activeArtifactTab === "manifest" && manifestData !== null) ||
    (activeArtifactTab === "artifacts" && artifactsData !== null);

  const renderArtifactTabContent = () => {
    if (!selectedRun || !selectedSourceName || !selectedRecord) {
      return <p className="muted">{locale === "ru" ? "Нет выбранного источника." : "No source selected."}</p>;
    }

    if (tabLoading[activeArtifactTab] && !activeTabHasData) {
      return <LoadingBlock lines={4} className="loading-stack" />;
    }

    if (tabErrors[activeArtifactTab]) {
      return <p className="error">{tabErrors[activeArtifactTab]}</p>;
    }

    if (activeArtifactTab === "validation") {
      if (!validationData) {
        return <p className="muted">{locale === "ru" ? "Validation отчет недоступен." : "Validation report is not available."}</p>;
      }

      const checkEntries = Object.entries(validationData.checks ?? {});

      return (
        <div className="diagnostics-tab-stack">
          <div className="diagnostics-mini-grid">
            <div className="diagnostics-mini-card">
              <p className="insight-label">Status</p>
              <p className="insight-value"><StatusBadge status={validationData.status} /></p>
            </div>
            <div className="diagnostics-mini-card">
              <p className="insight-label">Contract</p>
              <p className="insight-value mono-small">{validationData.contract_version ?? "-"}</p>
            </div>
            <div className="diagnostics-mini-card">
              <p className="insight-label">Profile</p>
              <p className="insight-value mono-small">{validationData.profile ?? "-"}</p>
            </div>
          </div>

          {validationData.summary ? <p className="panel-subtitle">{validationData.summary}</p> : null}

          <div className="diagnostics-checks-grid">
            {checkEntries.length > 0 ? (
              checkEntries.map(([checkName, status]) => (
                <div key={checkName} className="diagnostics-mini-card">
                  <p className="insight-label mono-small">{checkName}</p>
                  <p className="insight-value"><StatusBadge status={status} /></p>
                </div>
              ))
            ) : (
              <p className="muted">{locale === "ru" ? "Нет check-данных." : "No validation checks found."}</p>
            )}
          </div>

          <div className="diagnostics-list-grid">
            <div>
              <p className="diagnostics-list-title">{locale === "ru" ? "Errors" : "Errors"}</p>
              {validationData.errors.length > 0 ? (
                <ul className="diagnostics-list">
                  {validationData.errors.map((item) => (
                    <li key={`validation-error-${item}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">{locale === "ru" ? "Нет ошибок." : "No errors."}</p>
              )}
            </div>
            <div>
              <p className="diagnostics-list-title">{locale === "ru" ? "Warnings" : "Warnings"}</p>
              {validationData.warnings.length > 0 ? (
                <ul className="diagnostics-list">
                  {validationData.warnings.map((item) => (
                    <li key={`validation-warn-${item}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">{locale === "ru" ? "Нет предупреждений." : "No warnings."}</p>
              )}
            </div>
          </div>

          <p className="diagnostics-path-label">artifact_path</p>
          <p className="diagnostics-path-value mono-small" title={validationData.artifact_path ?? ""}>
            {validationData.artifact_path ? truncateMiddle(validationData.artifact_path) : "-"}
          </p>
        </div>
      );
    }

    if (activeArtifactTab === "semantic") {
      if (!semanticData) {
        return <p className="muted">{locale === "ru" ? "Semantic отчет недоступен." : "Semantic report is not available."}</p>;
      }

      return (
        <div className="diagnostics-tab-stack">
          <div className="diagnostics-mini-grid">
            <div className="diagnostics-mini-card">
              <p className="insight-label">Status</p>
              <p className="insight-value"><StatusBadge status={semanticData.status} /></p>
            </div>
            <div className="diagnostics-mini-card">
              <p className="insight-label">Rules</p>
              <p className="insight-value">{semanticData.counts.total}</p>
            </div>
            <div className="diagnostics-mini-card">
              <p className="insight-label">PASS/WARN/FAIL</p>
              <p className="insight-value mono-small">
                {semanticData.counts.passed}/{semanticData.counts.warned}/{semanticData.counts.failed}
              </p>
            </div>
          </div>

          {semanticData.summary ? <p className="panel-subtitle">{semanticData.summary}</p> : null}

          {semanticData.rules.length > 0 ? (
            <div className="table-wrap">
              <table className="table diagnostics-rules-table">
                <thead>
                  <tr>
                    <th>rule_id</th>
                    <th>rule_type</th>
                    <th>severity</th>
                    <th>status</th>
                    <th>{locale === "ru" ? "Сообщение" : "Message"}</th>
                    <th>{locale === "ru" ? "Метрики" : "Observed"}</th>
                  </tr>
                </thead>
                <tbody>
                  {semanticData.rules.map((rule) => (
                    <tr key={`${rule.rule_id}-${rule.rule_type}`}>
                      <td><code className="mono-small">{rule.rule_id}</code></td>
                      <td><code className="mono-small">{rule.rule_type}</code></td>
                      <td><StatusBadge status={rule.severity} /></td>
                      <td><StatusBadge status={rule.status} /></td>
                      <td>{rule.message}</td>
                      <td>
                        <details className="diagnostics-observed-block">
                          <summary>{locale === "ru" ? "Показать" : "View"}</summary>
                          <pre className="diagnostics-json-block">
                            {JSON.stringify(rule.observed, null, 2)}
                          </pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">{locale === "ru" ? "Нет semantic-правил." : "No semantic rule results."}</p>
          )}

          <p className="diagnostics-path-label">artifact_path</p>
          <p className="diagnostics-path-value mono-small" title={semanticData.artifact_path ?? ""}>
            {semanticData.artifact_path ? truncateMiddle(semanticData.artifact_path) : "-"}
          </p>
        </div>
      );
    }

    if (activeArtifactTab === "manifest") {
      if (!manifestData) {
        return <p className="muted">{locale === "ru" ? "Manifest недоступен." : "Manifest is not available."}</p>;
      }

      const renamedColumns = Object.entries(manifestData.renamed_columns ?? {});
      const coercionRows = Object.entries(manifestData.coercion_stats ?? {}).map(([column, payload]) => {
        const info = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
        return {
          column,
          expected: typeof info.expected_dtype === "string" ? info.expected_dtype : "-",
          invalidToNull: typeof info.invalid_to_null === "number" ? info.invalid_to_null : 0,
          nullCountAfter: typeof info.null_count_after === "number" ? info.null_count_after : 0,
        };
      });

      return (
        <div className="diagnostics-tab-stack">
          <div className="diagnostics-mini-grid">
            <div className="diagnostics-mini-card">
              <p className="insight-label">Validation</p>
              <p className="insight-value"><StatusBadge status={manifestData.validation_status ?? "UNKNOWN"} /></p>
            </div>
            <div className="diagnostics-mini-card">
              <p className="insight-label">Rows</p>
              <p className="insight-value">{manifestData.output_row_count ?? "-"}</p>
            </div>
            <div className="diagnostics-mini-card">
              <p className="insight-label">Columns</p>
              <p className="insight-value">{manifestData.output_column_count ?? "-"}</p>
            </div>
          </div>

          <div className="diagnostics-list-grid">
            <div>
              <p className="diagnostics-list-title">{locale === "ru" ? "Renamed columns" : "Renamed columns"}</p>
              {renamedColumns.length > 0 ? (
                <ul className="diagnostics-list">
                  {renamedColumns.map(([from, to]) => (
                    <li key={`${from}-${to}`}>
                      <code className="mono-small">{from}</code> → <code className="mono-small">{to}</code>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">{locale === "ru" ? "Переименований нет." : "No renamed columns."}</p>
              )}
            </div>
            <div>
              <p className="diagnostics-list-title">{locale === "ru" ? "Canonical columns" : "Canonical columns"}</p>
              {manifestData.final_canonical_columns.length > 0 ? (
                <div className="diagnostics-chip-wrap">
                  {manifestData.final_canonical_columns.map((column) => (
                    <span key={`canonical-${column}`} className="diagnostics-chip mono-small">{column}</span>
                  ))}
                </div>
              ) : (
                <p className="muted">{locale === "ru" ? "Не указаны." : "No canonical columns listed."}</p>
              )}
            </div>
          </div>

          {coercionRows.length > 0 ? (
            <div className="table-wrap">
              <table className="table diagnostics-rules-table">
                <thead>
                  <tr>
                    <th>{locale === "ru" ? "Колонка" : "Column"}</th>
                    <th>{locale === "ru" ? "Ожидаемый тип" : "Expected dtype"}</th>
                    <th>{locale === "ru" ? "Invalid→null" : "Invalid→null"}</th>
                    <th>{locale === "ru" ? "Null after" : "Null after"}</th>
                  </tr>
                </thead>
                <tbody>
                  {coercionRows.map((row) => (
                    <tr key={`coercion-${row.column}`}>
                      <td><code className="mono-small">{row.column}</code></td>
                      <td><code className="mono-small">{row.expected}</code></td>
                      <td>{row.invalidToNull}</td>
                      <td>{row.nullCountAfter}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <p className="diagnostics-path-label">artifact_path</p>
          <p className="diagnostics-path-value mono-small" title={manifestData.artifact_path ?? ""}>
            {manifestData.artifact_path ? truncateMiddle(manifestData.artifact_path) : "-"}
          </p>
        </div>
      );
    }

    if (!artifactsData) {
      return <p className="muted">{locale === "ru" ? "Список артефактов недоступен." : "Artifacts index is not available."}</p>;
    }

    const artifacts = artifactsData.artifacts ?? [];
    return (
      <div className="diagnostics-tab-stack">
        <p className="diagnostics-path-label">artifact_dir</p>
        <p className="diagnostics-path-value mono-small" title={artifactsData.artifact_dir ?? ""}>
          {artifactsData.artifact_dir ? truncateMiddle(artifactsData.artifact_dir) : "-"}
        </p>

        {artifacts.length > 0 ? (
          <div className="table-wrap">
            <table className="table diagnostics-rules-table">
              <thead>
                <tr>
                  <th>{locale === "ru" ? "Тип" : "Type"}</th>
                  <th>{locale === "ru" ? "Доступность" : "Available"}</th>
                  <th>{locale === "ru" ? "Размер" : "Size"}</th>
                  <th>{locale === "ru" ? "Путь" : "Path"}</th>
                  <th>{locale === "ru" ? "Скачать" : "Download"}</th>
                </tr>
              </thead>
              <tbody>
                {artifacts.map((artifact) => {
                  const fallbackUrl = buildPreflightArtifactDownloadUrl(
                    selectedRun.run_id,
                    selectedSourceName,
                    artifact.artifact_type
                  );
                  const downloadUrl = artifact.download_url ?? fallbackUrl;
                  const pathText = artifact.path ? truncateMiddle(artifact.path) : "-";
                  return (
                    <tr key={`artifact-${artifact.artifact_type}`}>
                      <td><code className="mono-small">{artifact.artifact_type}</code></td>
                      <td><StatusBadge status={artifact.available ? "PASS" : "SKIPPED"} /></td>
                      <td>{formatBytes(artifact.size_bytes ?? null)}</td>
                      <td title={artifact.path ?? ""}><code className="mono-small">{pathText}</code></td>
                      <td>
                        {artifact.available ? (
                          <a className="button ghost" href={downloadUrl} target="_blank" rel="noreferrer">
                            {locale === "ru" ? "Скачать" : "Download"}
                          </a>
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">{locale === "ru" ? "Файлы не зарегистрированы." : "No registered artifacts."}</p>
        )}
      </div>
    );
  };

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">{locale === "ru" ? "Диагностика Preflight" : "Preflight Diagnostics"}</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Контроль статуса preflight, истории запусков и drill-down по validation/semantic/manifest артефактам."
              : "Monitor preflight status, run history, and drill down into validation/semantic/manifest artifacts."}
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}</p>
          <button
            className="button primary"
            type="button"
            onClick={refreshAll}
            disabled={latestLoading || runsLoading || detailsLoading || analyticsLoading || alertsLoading}
          >
            {latestLoading || runsLoading || detailsLoading || analyticsLoading || alertsLoading
              ? locale === "ru"
                ? "Обновление..."
                : "Refreshing..."
              : locale === "ru"
                ? "Обновить"
                : "Refresh"}
          </button>
        </div>
      </div>

      <div className="panel diagnostics-auth-panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Diagnostics API Auth" : "Diagnostics API Auth"}</h3>
          <p className="panel-subtitle">
            {locale === "ru"
              ? "Доступ к diagnostics endpoint через X-API-Key (сохраняется в sessionStorage)."
              : "Access diagnostics endpoints with X-API-Key (stored in sessionStorage)."}
          </p>
        </div>
        <div className="controls diagnostics-auth-controls">
          <div className="field diagnostics-auth-key">
            <label htmlFor="diagnostics-api-key">X-API-Key</label>
            <input
              id="diagnostics-api-key"
              className="input"
              type="password"
              value={apiKeyInput}
              onChange={(event) => setApiKeyInput(event.target.value)}
              placeholder={locale === "ru" ? "Введите diagnostics API key" : "Enter diagnostics API key"}
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <div className="diagnostics-auth-actions">
            <button className="button primary" type="button" onClick={handleSaveApiKey}>
              {locale === "ru" ? "Сохранить ключ" : "Save key"}
            </button>
            <button className="button ghost" type="button" onClick={handleClearApiKey}>
              {locale === "ru" ? "Очистить" : "Clear"}
            </button>
          </div>
        </div>
        <p className="meta-text">
          {locale === "ru" ? "Статус доступа" : "Access status"}:{" "}
          <strong>{apiKeyConfigured ? (locale === "ru" ? "настроен" : "configured") : (locale === "ru" ? "отсутствует" : "missing")}</strong>
        </p>
        {authMessage ? <p className="error">{authMessage}</p> : null}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Active Alerts" : "Active Alerts"}</h3>
          <p className="panel-subtitle">
            {locale === "ru"
              ? "Текущие policy-based оповещения по качеству preflight и история переходов."
              : "Current policy-based quality alerts with pending/firing status and recent transition history."}
          </p>
        </div>

        {alertsError && <p className="error">{alertsError}</p>}
        {alertsActionError && <p className="error">{alertsActionError}</p>}

        {alertsLoading && !activeAlerts && !alertHistory ? (
          <LoadingBlock lines={4} className="loading-stack" />
        ) : (
          <div className="diagnostics-alerts-grid">
            <div className="diagnostics-alerts-stack">
              <div className="diagnostics-mini-grid">
                <div className="diagnostics-mini-card">
                  <p className="insight-label">{locale === "ru" ? "Активные alert" : "Active alerts"}</p>
                  <p className="insight-value">{activeAlerts?.total_active ?? 0}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">{locale === "ru" ? "Silences" : "Silences"}</p>
                  <p className="insight-value">{alertSilenceItems.length}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">{locale === "ru" ? "Audit events" : "Audit events"}</p>
                  <p className="insight-value">{alertAuditItems.length}</p>
                </div>
              </div>

              {activeAlertItems.length > 0 ? (
                <div className="table-wrap">
                  <table className="table diagnostics-alerts-table">
                    <thead>
                      <tr>
                        <th>{locale === "ru" ? "Severity" : "Severity"}</th>
                        <th>{locale === "ru" ? "Status" : "Status"}</th>
                        <th>{locale === "ru" ? "Policy" : "Policy"}</th>
                        <th>{locale === "ru" ? "Flags" : "Flags"}</th>
                        <th>{locale === "ru" ? "Silence until" : "Silence until"}</th>
                        <th>{locale === "ru" ? "Source" : "Source"}</th>
                        <th>{locale === "ru" ? "Current/Threshold" : "Current/Threshold"}</th>
                        <th>{locale === "ru" ? "Message" : "Message"}</th>
                        <th>{locale === "ru" ? "Actions" : "Actions"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeAlertItems.map((item) => {
                        const ackBusy = Boolean(alertsActionLoading[`ack:${item.alert_id}`] || alertsActionLoading[`unack:${item.alert_id}`]);
                        const silenceBusy = Boolean(alertsActionLoading[`silence:${item.alert_id}:1`] || alertsActionLoading[`silence:${item.alert_id}:24`]);
                        const rowBusy = ackBusy || silenceBusy;
                        return (
                          <tr key={`active-alert-${item.alert_id}`}>
                            <td><StatusBadge status={item.severity} /></td>
                            <td><StatusBadge status={item.status} /></td>
                            <td>
                              <code className="mono-small">{item.policy_id}</code>
                              {item.policy?.description ? (
                                <p className="diagnostics-inline-note">{item.policy.description}</p>
                              ) : null}
                            </td>
                            <td>
                              <div className="diagnostics-flag-stack">
                                {item.is_acknowledged ? <StatusBadge status="ACKED" /> : <span className="muted">ACK: -</span>}
                                {item.is_silenced ? <StatusBadge status="SILENCED" /> : <span className="muted">SILENCE: -</span>}
                              </div>
                            </td>
                            <td>{formatTimestamp(item.silence?.ends_at ?? null, localeTag)}</td>
                            <td>{item.source_name ? sourceLabel(item.source_name, locale) : "-"}</td>
                            <td className="mono-small">
                              {formatMetricValue(item.current_value)} / {formatMetricValue(item.threshold)}
                            </td>
                            <td>{item.message}</td>
                            <td>
                              <div className="diagnostics-alert-actions">
                                {item.is_acknowledged ? (
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={() => void handleUnackAlert(item.alert_id)}
                                    disabled={rowBusy}
                                  >
                                    {locale === "ru" ? "Unack" : "Unack"}
                                  </button>
                                ) : (
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={() => void handleAckAlert(item.alert_id)}
                                    disabled={rowBusy}
                                  >
                                    {locale === "ru" ? "Ack" : "Ack"}
                                  </button>
                                )}
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() =>
                                    void handleSilenceAlert({
                                      alertId: item.alert_id,
                                      policyId: item.policy_id,
                                      sourceName: item.source_name ?? undefined,
                                      severity: item.severity,
                                      ruleId: item.policy?.rule_id ?? undefined,
                                      hours: 1,
                                    })
                                  }
                                  disabled={rowBusy}
                                >
                                  {locale === "ru" ? "Silence 1h" : "Silence 1h"}
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() =>
                                    void handleSilenceAlert({
                                      alertId: item.alert_id,
                                      policyId: item.policy_id,
                                      sourceName: item.source_name ?? undefined,
                                      severity: item.severity,
                                      ruleId: item.policy?.rule_id ?? undefined,
                                      hours: 24,
                                    })
                                  }
                                  disabled={rowBusy}
                                >
                                  {locale === "ru" ? "Silence 24h" : "Silence 24h"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">
                  {locale === "ru"
                    ? "Активных alert нет (PENDING/FIRING)."
                    : "No active alerts (PENDING/FIRING) for current diagnostics data."}
                </p>
              )}
            </div>

            <div className="diagnostics-alerts-right-stack">
              <div className="panel diagnostics-embedded-panel">
                <div className="panel-head">
                  <h3>{locale === "ru" ? "Silences" : "Silences"}</h3>
                  <p className="panel-subtitle">
                    {locale === "ru" ? "Активные suppress-правила для alert." : "Active silence windows and matchers."}
                  </p>
                </div>
                {alertSilenceItems.length > 0 ? (
                  <div className="table-wrap">
                    <table className="table diagnostics-alerts-table">
                      <thead>
                        <tr>
                          <th>silence_id</th>
                          <th>{locale === "ru" ? "Matchers" : "Matchers"}</th>
                          <th>{locale === "ru" ? "Window" : "Window"}</th>
                          <th>{locale === "ru" ? "Reason" : "Reason"}</th>
                          <th>{locale === "ru" ? "Created by" : "Created by"}</th>
                          <th>{locale === "ru" ? "Action" : "Action"}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {alertSilenceItems.map((silence) => (
                          <tr key={`silence-${silence.silence_id}`}>
                            <td><code className="mono-small">{silence.silence_id}</code></td>
                            <td>
                              <div className="diagnostics-chip-wrap">
                                {silence.policy_id ? <span className="diagnostics-chip mono-small">policy:{silence.policy_id}</span> : null}
                                {silence.source_name ? <span className="diagnostics-chip mono-small">source:{silence.source_name}</span> : null}
                                {silence.severity ? <span className="diagnostics-chip mono-small">severity:{silence.severity}</span> : null}
                                {silence.rule_id ? <span className="diagnostics-chip mono-small">rule:{silence.rule_id}</span> : null}
                              </div>
                            </td>
                            <td className="mono-small">
                              {formatTimestamp(silence.starts_at, localeTag)}<br />
                              {formatTimestamp(silence.ends_at, localeTag)}
                            </td>
                            <td>{silence.reason || "-"}</td>
                            <td><code className="mono-small">{silence.created_by}</code></td>
                            <td>
                              {silence.is_active ? (
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() => void handleExpireSilence(silence.silence_id)}
                                  disabled={Boolean(alertsActionLoading[`expire:${silence.silence_id}`])}
                                >
                                  {locale === "ru" ? "Expire" : "Expire"}
                                </button>
                              ) : (
                                <span className="muted">{locale === "ru" ? "Expired" : "Expired"}</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted">{locale === "ru" ? "Активные silences отсутствуют." : "No active silences."}</p>
                )}
              </div>

              <div className="panel diagnostics-embedded-panel">
                <div className="panel-head">
                  <h3>{locale === "ru" ? "Alert Audit Trail" : "Alert Audit Trail"}</h3>
                  <p className="panel-subtitle">
                    {locale === "ru" ? "История действий ACK/SILENCE/EVALUATION." : "Audit stream for ACK/SILENCE/EVALUATION events."}
                  </p>
                </div>
                {alertAuditItems.length > 0 ? (
                  <div className="table-wrap">
                    <table className="table diagnostics-alerts-table">
                      <thead>
                        <tr>
                          <th>{locale === "ru" ? "Time" : "Time"}</th>
                          <th>{locale === "ru" ? "Event" : "Event"}</th>
                          <th>alert_id</th>
                          <th>{locale === "ru" ? "Actor" : "Actor"}</th>
                          <th>{locale === "ru" ? "Payload" : "Payload"}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {alertAuditItems.map((event) => (
                          <tr key={`audit-${event.event_id}`}>
                            <td>{formatTimestamp(event.event_at, localeTag)}</td>
                            <td><StatusBadge status={event.event_type} /></td>
                            <td><code className="mono-small">{event.alert_id}</code></td>
                            <td><code className="mono-small">{event.actor}</code></td>
                            <td>
                              <details className="diagnostics-observed-block">
                                <summary>{locale === "ru" ? "Показать" : "View"}</summary>
                                <pre className="diagnostics-json-block">
                                  {JSON.stringify(event.payload_json, null, 2)}
                                </pre>
                              </details>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted">{locale === "ru" ? "События аудита отсутствуют." : "No audit events yet."}</p>
                )}
              </div>

              <div className="panel diagnostics-embedded-panel">
                <div className="panel-head">
                  <h3>{locale === "ru" ? "Recent Alert History" : "Recent Alert History"}</h3>
                  <p className="panel-subtitle">
                    {locale === "ru" ? "Последние переходы PENDING/FIRING/RESOLVED." : "Most recent alert status transitions."}
                  </p>
                </div>
                {alertHistoryItems.length > 0 ? (
                  <div className="table-wrap">
                    <table className="table diagnostics-alerts-table">
                      <thead>
                        <tr>
                          <th>{locale === "ru" ? "Evaluated" : "Evaluated"}</th>
                          <th>{locale === "ru" ? "Policy" : "Policy"}</th>
                          <th>{locale === "ru" ? "Status" : "Status"}</th>
                          <th>{locale === "ru" ? "Severity" : "Severity"}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {alertHistoryItems.map((item) => (
                          <tr key={`history-alert-${item.alert_id}`}>
                            <td>{formatTimestamp(item.evaluated_at ?? null, localeTag)}</td>
                            <td>
                              <code className="mono-small">{item.policy_id}</code>
                            </td>
                            <td><StatusBadge status={item.status} /></td>
                            <td><StatusBadge status={item.severity} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted">
                    {locale === "ru" ? "История alert пока пуста." : "No alert history recorded yet."}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Quality Analytics" : "Quality Analytics"}</h3>
          <p className="panel-subtitle">
            {locale === "ru"
              ? "Агрегированные метрики, тренд статусов и частота semantic-правил."
              : "Aggregated quality counters, status trends, and semantic rule frequency over time."}
          </p>
        </div>

        <div className="controls diagnostics-analytics-controls">
          <div className="field">
            <label htmlFor="analytics-source-filter">{locale === "ru" ? "Источник" : "Source"}</label>
            <select
              id="analytics-source-filter"
              className="select"
              value={analyticsSourceFilter}
              onChange={(event) => setAnalyticsSourceFilter(event.target.value as SourceFilter)}
            >
              <option value="all">{locale === "ru" ? "Все" : "All"}</option>
              <option value="train">Train</option>
              <option value="store">Store</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="analytics-mode-filter">Mode</label>
            <select
              id="analytics-mode-filter"
              className="select"
              value={analyticsModeFilter}
              onChange={(event) => setAnalyticsModeFilter(event.target.value as AnalyticsModeFilter)}
            >
              <option value="all">{locale === "ru" ? "Все" : "All"}</option>
              <option value="off">off</option>
              <option value="report_only">report_only</option>
              <option value="enforce">enforce</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="analytics-window">{locale === "ru" ? "Период" : "Window"}</label>
            <select
              id="analytics-window"
              className="select"
              value={analyticsWindow}
              onChange={(event) => setAnalyticsWindow(event.target.value as AnalyticsWindow)}
            >
              <option value="7">{locale === "ru" ? "Последние 7 дней" : "Last 7 days"}</option>
              <option value="30">{locale === "ru" ? "Последние 30 дней" : "Last 30 days"}</option>
              <option value="custom">{locale === "ru" ? "Кастомный период" : "Custom range"}</option>
            </select>
          </div>
          {analyticsWindow === "custom" ? (
            <>
              <div className="field">
                <label htmlFor="analytics-date-from">{locale === "ru" ? "Дата от" : "Date from"}</label>
                <input
                  id="analytics-date-from"
                  className="input"
                  type="date"
                  value={analyticsDateFrom}
                  onChange={(event) => setAnalyticsDateFrom(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="analytics-date-to">{locale === "ru" ? "Дата до" : "Date to"}</label>
                <input
                  id="analytics-date-to"
                  className="input"
                  type="date"
                  value={analyticsDateTo}
                  onChange={(event) => setAnalyticsDateTo(event.target.value)}
                />
              </div>
            </>
          ) : null}
        </div>

        {analyticsError && <p className="error">{analyticsError}</p>}

        {analyticsLoading && !stats && !trends && !topRules ? (
          <LoadingBlock lines={5} className="loading-stack" />
        ) : (
          <div className="diagnostics-analytics-grid">
            <div className="diagnostics-analytics-stack">
              <div className="diagnostics-analytics-cards">
                <div className="diagnostics-mini-card">
                  <p className="insight-label">{locale === "ru" ? "Всего запусков" : "Total runs"}</p>
                  <p className="insight-value">{stats?.total_runs ?? 0}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">PASS</p>
                  <p className="insight-value"><StatusBadge status="PASS" /> {stats?.pass_count ?? 0}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">WARN</p>
                  <p className="insight-value"><StatusBadge status="WARN" /> {stats?.warn_count ?? 0}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">FAIL</p>
                  <p className="insight-value"><StatusBadge status="FAIL" /> {stats?.fail_count ?? 0}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">{locale === "ru" ? "Blocked" : "Blocked"}</p>
                  <p className="insight-value">{stats?.blocked_count ?? 0}</p>
                </div>
                <div className="diagnostics-mini-card">
                  <p className="insight-label">{locale === "ru" ? "Unified rate" : "Unified rate"}</p>
                  <p className="insight-value">{stats ? `${(stats.used_unified_rate * 100).toFixed(1)}%` : "-"}</p>
                </div>
              </div>

              <div className="panel diagnostics-embedded-panel">
                <div className="panel-head">
                  <h3>{locale === "ru" ? "Status Trend (Server)" : "Status Trend (Server)"}</h3>
                  <p className="panel-subtitle">
                    {locale === "ru"
                      ? "Группировка по дням на стороне API."
                      : "Server-side daily aggregation from diagnostics API."}
                  </p>
                </div>
                {analyticsTrendData.length > 0 ? (
                  <div style={{ width: "100%", height: 260 }}>
                    <ResponsiveContainer>
                      <BarChart data={analyticsTrendData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="bucket_label" stroke="var(--chart-axis)" />
                        <YAxis allowDecimals={false} stroke="var(--chart-axis)" />
                        <Tooltip />
                        <Bar dataKey="pass_count" stackId="status" fill="var(--status-pass)" name="PASS" />
                        <Bar dataKey="warn_count" stackId="status" fill="var(--status-warn)" name="WARN" />
                        <Bar dataKey="fail_count" stackId="status" fill="var(--status-fail)" name="FAIL" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="muted">
                    {locale === "ru" ? "Нет данных тренда для выбранных фильтров." : "No trend data for selected filters."}
                  </p>
                )}
              </div>
            </div>

            <div className="panel diagnostics-embedded-panel">
              <div className="panel-head">
                <h3>{locale === "ru" ? "Top Quality Rules" : "Top Quality Rules"}</h3>
                <p className="panel-subtitle">
                  {locale === "ru"
                    ? "Лидеры по WARN/FAIL из semantic правил."
                    : "Most frequent WARN/FAIL semantic rules in selected window."}
                </p>
              </div>
              {topRules?.items && topRules.items.length > 0 ? (
                <div className="table-wrap">
                  <table className="table diagnostics-rules-table">
                    <thead>
                      <tr>
                        <th>rule_id</th>
                        <th>rule_type</th>
                        <th>severity</th>
                        <th>WARN</th>
                        <th>FAIL</th>
                        <th>{locale === "ru" ? "Last seen" : "Last seen"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topRules.items.map((item) => (
                        <tr key={`${item.rule_id}-${item.rule_type}-${item.severity}`}>
                          <td>
                            <code className="mono-small">{item.rule_id}</code>
                            {item.sample_message ? <p className="diagnostics-inline-note">{item.sample_message}</p> : null}
                          </td>
                          <td><code className="mono-small">{item.rule_type}</code></td>
                          <td><StatusBadge status={item.severity} /></td>
                          <td>{item.warn_count}</td>
                          <td>{item.fail_count}</td>
                          <td>{formatTimestamp(item.last_seen_at ?? null, localeTag)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">
                  {locale === "ru" ? "Нет данных правил для выбранных фильтров." : "No top-rule data for selected filters."}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Latest Preflight Summary" : "Latest Preflight Summary"}</h3>
          <p className="panel-subtitle">
            {locale === "ru" ? "Сводка по последнему запуску с разбивкой по train/store." : "Latest run snapshot with train/store source breakdown."}
          </p>
        </div>

        {latestError && <p className="error">{latestError}</p>}

        {latestLoading && !latest ? (
          <LoadingBlock lines={4} className="loading-stack" />
        ) : latest ? (
          <>
            <div className="diagnostics-overview-grid">
              <div className="diagnostics-meta-item">
                <p className="insight-label">Run ID</p>
                <p className="insight-value mono-small">{latest.run_id}</p>
              </div>
              <div className="diagnostics-meta-item">
                <p className="insight-label">{locale === "ru" ? "Время" : "Created at"}</p>
                <p className="insight-value">{formatTimestamp(latest.created_at, localeTag)}</p>
              </div>
              <div className="diagnostics-meta-item">
                <p className="insight-label">Mode</p>
                <p className="insight-value">{latest.mode}</p>
              </div>
              <div className="diagnostics-meta-item">
                <p className="insight-label">{locale === "ru" ? "Итоговый статус" : "Final status"}</p>
                <p className="insight-value"><StatusBadge status={latest.final_status} /></p>
              </div>
              <div className="diagnostics-meta-item">
                <p className="insight-label">{locale === "ru" ? "Блокировка" : "Blocked"}</p>
                <p className="insight-value">{latest.blocked ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}</p>
              </div>
            </div>

            <div className="diagnostics-source-grid">
              {latestRecords.length > 0 ? (
                latestRecords.map((record) => (
                  <div key={`latest-source-${record.run_id}-${record.source_name}`} className="diagnostics-source-card">
                    <p className="insight-label">{sourceLabel(record.source_name, locale)}</p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Schema" : "Schema"}:</span> <StatusBadge status={record.validation_status} /></p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Semantic" : "Semantic"}:</span> <StatusBadge status={record.semantic_status} /></p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Final" : "Final"}:</span> <StatusBadge status={record.final_status} /></p>
                    <p className="diagnostics-source-line">
                      <span>{locale === "ru" ? "Unified input" : "Unified input"}:</span>{" "}
                      {record.used_unified ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}
                    </p>
                  </div>
                ))
              ) : (
                <p className="muted">{locale === "ru" ? "Нет source-данных в последнем запуске." : "No source records in latest run."}</p>
              )}
            </div>
          </>
        ) : (
          <p className="muted">{locale === "ru" ? "Запуски preflight пока не найдены." : "No preflight runs found yet."}</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Recent Runs" : "Recent Runs"}</h3>
          <p className="panel-subtitle">
            {locale === "ru"
              ? "Фильтры списка и выбор запуска для просмотра детальной расшифровки."
              : "Filter current list and select a run to inspect source-level details."}
          </p>
        </div>
        <div className="controls">
          <div className="field">
            <label htmlFor="diagnostics-source-filter">{locale === "ru" ? "Источник" : "Source"}</label>
            <select
              id="diagnostics-source-filter"
              className="select"
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}
            >
              <option value="all">{locale === "ru" ? "Все" : "All"}</option>
              <option value="train">Train</option>
              <option value="store">Store</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="diagnostics-limit-filter">{locale === "ru" ? "Лимит" : "Limit"}</label>
            <select
              id="diagnostics-limit-filter"
              className="select"
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="diagnostics-status-filter">{locale === "ru" ? "Final status" : "Final status"}</label>
            <select
              id="diagnostics-status-filter"
              className="select"
              value={finalStatusFilter}
              onChange={(event) => setFinalStatusFilter(event.target.value as FinalStatusFilter)}
            >
              <option value="all">{locale === "ru" ? "Все" : "All"}</option>
              <option value="PASS">PASS</option>
              <option value="WARN">WARN</option>
              <option value="FAIL">FAIL</option>
            </select>
          </div>
        </div>
      </div>

      <div className="diagnostics-main-grid">
        <div className="diagnostics-left-stack">
          <div className="panel">
            <div className="panel-head">
              <h3>{locale === "ru" ? "Status Trend" : "Status Trend"}</h3>
              <p className="panel-subtitle">
                {locale === "ru" ? "Распределение PASS/WARN/FAIL в текущем списке." : "PASS/WARN/FAIL distribution in the current list."}
              </p>
            </div>
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={trendData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis dataKey="status" stroke="var(--chart-axis)" />
                  <YAxis allowDecimals={false} stroke="var(--chart-axis)" />
                  <Tooltip content={<TrendTooltip locale={locale} />} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {trendData.map((entry) => (
                      <Cell key={`status-cell-${entry.status}`} fill={trendColors[entry.status]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            {runsError && <p className="error">{runsError}</p>}
            {runsLoading && runs.length === 0 ? (
              <LoadingBlock lines={6} className="loading-stack" />
            ) : visibleRuns.length > 0 ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{locale === "ru" ? "Время" : "Created at"}</th>
                      <th>Run ID</th>
                      <th>{locale === "ru" ? "Источник" : "Source"}</th>
                      <th>Mode</th>
                      <th>{locale === "ru" ? "Schema" : "Schema"}</th>
                      <th>{locale === "ru" ? "Semantic" : "Semantic"}</th>
                      <th>{locale === "ru" ? "Final" : "Final"}</th>
                      <th>{locale === "ru" ? "Blocked" : "Blocked"}</th>
                      <th>{locale === "ru" ? "Unified" : "Unified"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRuns.map((run) => (
                      <tr
                        key={`${run.run_id}-${run.source_name}`}
                        className={`diagnostics-table-row${selectedRunId === run.run_id ? " selected" : ""}`}
                        onClick={() => setSelectedRunId(run.run_id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedRunId(run.run_id);
                          }
                        }}
                        tabIndex={0}
                        role="button"
                        aria-label={`${locale === "ru" ? "Открыть детали запуска" : "Open run details"} ${run.run_id}`}
                      >
                        <td>{formatTimestamp(run.created_at, localeTag)}</td>
                        <td><code className="mono-small">{run.run_id}</code></td>
                        <td>{sourceLabel(run.source_name, locale)}</td>
                        <td>{run.mode}</td>
                        <td><StatusBadge status={run.validation_status} /></td>
                        <td><StatusBadge status={run.semantic_status} /></td>
                        <td><StatusBadge status={run.final_status} /></td>
                        <td>{run.blocked ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}</td>
                        <td>{run.used_unified ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">{locale === "ru" ? "Нет запусков preflight для выбранных фильтров." : "No preflight runs for current filters."}</p>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>{locale === "ru" ? "Run Details" : "Run Details"}</h3>
            <p className="panel-subtitle">
              {selectedRunId ? selectedRunId : locale === "ru" ? "Выберите запуск из таблицы." : "Select a run from the table."}
            </p>
          </div>

          {detailsError && <p className="error">{detailsError}</p>}

          {detailsLoading && !selectedRun ? (
            <LoadingBlock lines={5} className="loading-stack" />
          ) : selectedRun ? (
            <div className="diagnostics-details-stack">
              <div className="diagnostics-overview-grid">
                <div className="diagnostics-meta-item">
                  <p className="insight-label">Run ID</p>
                  <p className="insight-value mono-small">{selectedRun.run_id}</p>
                </div>
                <div className="diagnostics-meta-item">
                  <p className="insight-label">{locale === "ru" ? "Время" : "Created at"}</p>
                  <p className="insight-value">{formatTimestamp(selectedRun.created_at, localeTag)}</p>
                </div>
                <div className="diagnostics-meta-item">
                  <p className="insight-label">Mode</p>
                  <p className="insight-value">{selectedRun.mode}</p>
                </div>
                <div className="diagnostics-meta-item">
                  <p className="insight-label">{locale === "ru" ? "Final" : "Final"}</p>
                  <p className="insight-value"><StatusBadge status={selectedRun.final_status} /></p>
                </div>
                <div className="diagnostics-meta-item">
                  <p className="insight-label">{locale === "ru" ? "Blocked" : "Blocked"}</p>
                  <p className="insight-value">{selectedRun.blocked ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}</p>
                </div>
              </div>

              <div className="diagnostics-source-grid">
                {selectedRun.records.map((record) => (
                  <div
                    key={`detail-${record.run_id}-${record.source_name}`}
                    className={`diagnostics-source-card${selectedSourceName === record.source_name ? " selected" : ""}`}
                  >
                    <p className="insight-label">{sourceLabel(record.source_name, locale)}</p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Schema" : "Schema"}:</span> <StatusBadge status={record.validation_status} /></p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Semantic" : "Semantic"}:</span> <StatusBadge status={record.semantic_status} /></p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Final" : "Final"}:</span> <StatusBadge status={record.final_status} /></p>
                    <p className="diagnostics-source-line"><span>{locale === "ru" ? "Blocked" : "Blocked"}:</span> {record.blocked ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}</p>
                    <p className="diagnostics-source-line">
                      <span>{locale === "ru" ? "Unified" : "Unified"}:</span>{" "}
                      {record.used_unified ? (locale === "ru" ? "Да" : "Yes") : (locale === "ru" ? "Нет" : "No")}
                    </p>
                    <button
                      className="button ghost diagnostics-source-select"
                      type="button"
                      onClick={() => setSelectedSourceName(record.source_name)}
                    >
                      {locale === "ru" ? "Выбрать" : "Select"}
                    </button>
                  </div>
                ))}
              </div>

              <div className="diagnostics-drill-panel">
                <div className="diagnostics-drill-controls">
                  <div className="field">
                    <label htmlFor="diagnostics-source-detail-select">{locale === "ru" ? "Источник" : "Source"}</label>
                    <select
                      id="diagnostics-source-detail-select"
                      className="select"
                      value={selectedSourceName ?? ""}
                      onChange={(event) => setSelectedSourceName(event.target.value as PreflightSourceName)}
                    >
                      {selectedRun.records.map((record) => (
                        <option key={`source-option-${record.source_name}`} value={record.source_name}>
                          {sourceLabel(record.source_name, locale)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="diagnostics-tab-row" role="tablist" aria-label="Preflight artifact tabs">
                    {tabDefs.map((tab) => (
                      <button
                        key={tab.key}
                        type="button"
                        role="tab"
                        aria-selected={activeArtifactTab === tab.key}
                        className={`diagnostics-tab-btn${activeArtifactTab === tab.key ? " active" : ""}`}
                        onClick={() => setActiveArtifactTab(tab.key)}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="diagnostics-tab-body">
                  {renderArtifactTabContent()}
                </div>
              </div>
            </div>
          ) : (
            <p className="muted">{locale === "ru" ? "Выберите запуск из таблицы слева." : "Select a run from the table on the left."}</p>
          )}
        </div>
      </div>
    </section>
  );
}
