import React from "react";

import { extractApiError } from "../api/client";
import {
  DataSource,
  DataSourcePreflightRun,
  fetchDataSourcePreflightRuns,
  fetchDataSources,
} from "../api/endpoints";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import { SmartColumn, SmartTable } from "../components/ui/DataTable";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import StatusBadge from "../components/StatusBadge";
import { useI18n } from "../lib/i18n";

function formatDateTime(value: string | null | undefined, localeTag: string): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(localeTag, { dateStyle: "medium", timeStyle: "short" });
}

export default function DataSourcesPage() {
  const { locale, localeTag } = useI18n();
  const [sources, setSources] = React.useState<DataSource[]>([]);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [runs, setRuns] = React.useState<DataSourcePreflightRun[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [runsLoading, setRunsLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [runsError, setRunsError] = React.useState("");

  const selected = React.useMemo(
    () => sources.find((item) => item.id === selectedId) ?? null,
    [selectedId, sources]
  );

  const loadSources = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchDataSources({ include_inactive: true });
      setSources(response);
      setSelectedId((current) => current ?? (response[0]?.id ?? null));
    } catch (err) {
      setError(extractApiError(err, locale === "ru" ? "Не удалось загрузить источники данных." : "Failed to load data sources."));
    } finally {
      setLoading(false);
    }
  }, [locale]);

  const loadRuns = React.useCallback(
    async (dataSourceId: number | null) => {
      if (!dataSourceId) { setRuns([]); return; }
      setRunsLoading(true);
      setRunsError("");
      try {
        const response = await fetchDataSourcePreflightRuns(dataSourceId, { limit: 50 });
        setRuns(response);
      } catch (err) {
        setRunsError(extractApiError(err, locale === "ru" ? "Не удалось загрузить preflight-историю." : "Failed to load preflight history."));
      } finally {
        setRunsLoading(false);
      }
    },
    [locale]
  );

  React.useEffect(() => { loadSources(); }, [loadSources]);
  React.useEffect(() => { loadRuns(selectedId); }, [loadRuns, selectedId]);

  const sourceColumns: SmartColumn<Record<string, unknown>>[] = [
    {
      key: "name", label: locale === "ru" ? "Источник" : "Source", sortable: true, searchable: true,
      render: (_, row) => (
        <span>
          <strong>{String(row.name ?? "")}</strong>
          {row.description ? <span className="muted"> — {String(row.description)}</span> : null}
        </span>
      ),
    },
    { key: "source_type", label: locale === "ru" ? "Тип" : "Type", sortable: true },
    {
      key: "is_active", label: locale === "ru" ? "Активен" : "Active", sortable: true,
      render: (v) => <StatusBadge status={v ? "PASS" : "SKIPPED"} />,
    },
    {
      key: "last_preflight_status", label: locale === "ru" ? "Последний preflight" : "Last Preflight",
      render: (v) => v ? <StatusBadge status={String(v)} /> : <span className="muted">—</span>,
    },
    {
      key: "last_preflight_at", label: locale === "ru" ? "Время" : "Timestamp",
      render: (v) => formatDateTime(v as string | null, localeTag),
    },
  ];

  const runsColumns: SmartColumn<Record<string, unknown>>[] = [
    { key: "run_id", label: "Run ID", searchable: true, render: (v) => <span className="mono-small">{String(v ?? "")}</span> },
    { key: "source_name", label: locale === "ru" ? "Источник" : "Source", sortable: true },
    { key: "validation_status", label: "Validation", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    { key: "semantic_status", label: "Semantic", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    { key: "final_status", label: locale === "ru" ? "Итог" : "Final", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    { key: "created_at", label: locale === "ru" ? "Время" : "Created", sortable: true, render: (v) => formatDateTime(v as string | null, localeTag) },
  ];

  return (
    <PageLayout
      title={locale === "ru" ? "Источники данных" : "Data Sources"}
      subtitle={locale === "ru" ? "Мультиклиентный реестр подключений и их статус preflight." : "Multi-client source registry with preflight lineage."}
      actions={
        <button className="button primary" onClick={loadSources} type="button" disabled={loading}>
          {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить" : "Refresh"}
        </button>
      }
    >
      {error ? <ErrorState message={error} onRetry={loadSources} /> : null}
      {loading && sources.length === 0 ? <LoadingState lines={5} /> : null}
      {!loading && !error && sources.length === 0 ? (
        <EmptyState message={locale === "ru" ? "Источники данных не найдены." : "No data sources found."} />
      ) : null}

      {sources.length > 0 ? (
        <Card
          title={locale === "ru" ? "Реестр источников" : "Source Registry"}
          subtitle={locale === "ru" ? "Выберите источник, чтобы посмотреть preflight-запуски." : "Select a source to inspect recent preflight runs."}
        >
          <SmartTable
            columns={sourceColumns}
            data={sources as Record<string, unknown>[]}
            pageSize={20}
            searchable
            searchPlaceholder={locale === "ru" ? "Поиск источника..." : "Search sources…"}
            rowKeyField="id"
            selectedKey={selectedId ?? undefined}
            onRowClick={(row) => setSelectedId(row.id as number)}
            emptyMessage={locale === "ru" ? "Нет источников." : "No sources."}
          />
        </Card>
      ) : null}

      {selected ? (
        <Card
          title={locale === "ru" ? `Preflight-запуски: ${selected.name}` : `Preflight Runs: ${selected.name}`}
          subtitle={locale === "ru" ? "Результаты последних валидаций и семантических проверок." : "Recent validation and semantic quality runs."}
        >
          {runsError ? <p className="error">{runsError}</p> : null}
          {runsLoading ? <LoadingState lines={3} /> : (
            <SmartTable
              columns={runsColumns}
              data={runs as Record<string, unknown>[]}
              pageSize={25}
              searchable
              searchPlaceholder={locale === "ru" ? "Поиск по run ID..." : "Search by run ID…"}
              rowKeyField="run_id"
              emptyMessage={locale === "ru" ? "Нет preflight-запусков." : "No preflight runs."}
            />
          )}
        </Card>
      ) : null}
    </PageLayout>
  );
}
