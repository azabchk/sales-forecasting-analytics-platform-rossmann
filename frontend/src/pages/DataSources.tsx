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
import DataTable from "../components/ui/DataTable";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import StatusBadge from "../components/StatusBadge";
import { useI18n } from "../lib/i18n";

function formatDateTime(value: string | null | undefined, localeTag: string): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
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
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить источники данных." : "Failed to load data sources."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [locale]);

  const loadRuns = React.useCallback(
    async (dataSourceId: number | null) => {
      if (!dataSourceId) {
        setRuns([]);
        return;
      }
      setRunsLoading(true);
      setRunsError("");
      try {
        const response = await fetchDataSourcePreflightRuns(dataSourceId, { limit: 25 });
        setRuns(response);
      } catch (errorResponse) {
        setRunsError(
          extractApiError(
            errorResponse,
            locale === "ru"
              ? "Не удалось загрузить preflight-историю источника."
              : "Failed to load source preflight history."
          )
        );
      } finally {
        setRunsLoading(false);
      }
    },
    [locale]
  );

  React.useEffect(() => {
    loadSources();
  }, [loadSources]);

  React.useEffect(() => {
    loadRuns(selectedId);
  }, [loadRuns, selectedId]);

  return (
    <PageLayout
      title={locale === "ru" ? "Источники данных" : "Data Sources"}
      subtitle={
        locale === "ru"
          ? "Мультиклиентный реестр подключений и их статус preflight."
          : "Multi-client source registry with preflight lineage."
      }
      actions={
        <button className="button primary" onClick={loadSources} type="button" disabled={loading}>
          {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить" : "Refresh"}
        </button>
      }
    >
      {error ? <ErrorState message={error} /> : null}
      {loading && sources.length === 0 ? <LoadingState lines={5} /> : null}

      {!loading && sources.length === 0 ? (
        <EmptyState message={locale === "ru" ? "Источники данных не найдены." : "No data sources found."} />
      ) : null}

      {sources.length > 0 ? (
        <Card
          title={locale === "ru" ? "Реестр источников" : "Source Registry"}
          subtitle={
            locale === "ru"
              ? "Выберите источник, чтобы посмотреть последние preflight-запуски."
              : "Select a source to inspect recent preflight runs."
          }
        >
          <DataTable>
            <thead>
              <tr>
                <th>{locale === "ru" ? "Источник" : "Source"}</th>
                <th>{locale === "ru" ? "Тип" : "Type"}</th>
                <th>{locale === "ru" ? "Активен" : "Active"}</th>
                <th>{locale === "ru" ? "Последний preflight" : "Last Preflight"}</th>
                <th>{locale === "ru" ? "Время" : "Timestamp"}</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr
                  key={source.id}
                  onClick={() => setSelectedId(source.id)}
                  className={source.id === selectedId ? "table-row-active" : ""}
                >
                  <td>
                    <strong>{source.name}</strong>
                    <p className="muted">{source.description || "-"}</p>
                  </td>
                  <td>{source.source_type}</td>
                  <td>
                    <StatusBadge status={source.is_active ? "PASS" : "SKIPPED"} />
                  </td>
                  <td>{source.last_preflight_status ? <StatusBadge status={source.last_preflight_status} /> : "-"}</td>
                  <td>{formatDateTime(source.last_preflight_at, localeTag)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </Card>
      ) : null}

      {selected ? (
        <Card
          title={
            locale === "ru"
              ? `Preflight-запуски: ${selected.name}`
              : `Preflight Runs: ${selected.name}`
          }
          subtitle={
            locale === "ru"
              ? "Результаты последних валидаций и семантических проверок."
              : "Recent validation and semantic quality runs."
          }
        >
          {runsError ? <p className="error">{runsError}</p> : null}
          {runsLoading ? (
            <LoadingState lines={3} />
          ) : runs.length === 0 ? (
            <p className="muted">
              {locale === "ru"
                ? "Для источника пока нет запусков preflight."
                : "No preflight runs available for this source yet."}
            </p>
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <th>{locale === "ru" ? "Run ID" : "Run ID"}</th>
                  <th>{locale === "ru" ? "Источник" : "Source"}</th>
                  <th>{locale === "ru" ? "Validation" : "Validation"}</th>
                  <th>{locale === "ru" ? "Semantic" : "Semantic"}</th>
                  <th>{locale === "ru" ? "Итог" : "Final"}</th>
                  <th>{locale === "ru" ? "Время" : "Created"}</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((row) => (
                  <tr key={`${row.run_id}-${row.source_name}`}>
                    <td className="mono-small">{row.run_id}</td>
                    <td>{row.source_name}</td>
                    <td><StatusBadge status={row.validation_status} /></td>
                    <td><StatusBadge status={row.semantic_status} /></td>
                    <td><StatusBadge status={row.final_status} /></td>
                    <td>{formatDateTime(row.created_at, localeTag)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </Card>
      ) : null}
    </PageLayout>
  );
}
