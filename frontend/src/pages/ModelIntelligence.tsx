import React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { extractApiError } from "../api/client";
import {
  fetchMLExperiment,
  fetchMLExperiments,
  fetchModelMetadata,
  fetchSystemSummary,
  MLExperimentDetail,
  MLExperimentListItem,
  ModelMetadata,
  SystemSummary,
} from "../api/endpoints";
import ImportanceChart from "../components/ImportanceChart";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import DataTable from "../components/ui/DataTable";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import StatusBadge from "../components/StatusBadge";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";
import { useI18n } from "../lib/i18n";

function formatIsoDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toISOString().slice(0, 10);
}

function utcOrDash(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toUTCString();
}

function metricToNumber(value: unknown): number | null {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return value;
}

export default function ModelIntelligence() {
  const { locale, localeTag } = useI18n();
  const [summary, setSummary] = React.useState<SystemSummary | null>(null);
  const [metadata, setMetadata] = React.useState<ModelMetadata | null>(null);

  const [experiments, setExperiments] = React.useState<MLExperimentListItem[]>([]);
  const [selectedExperimentId, setSelectedExperimentId] = React.useState<string | null>(null);
  const [selectedExperiment, setSelectedExperiment] = React.useState<MLExperimentDetail | null>(null);

  const [loading, setLoading] = React.useState(false);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [lastUpdated, setLastUpdated] = React.useState("-");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryResponse, metadataResponse, experimentsResponse] = await Promise.all([
        fetchSystemSummary(),
        fetchModelMetadata(),
        fetchMLExperiments({ limit: 100 }),
      ]);
      setSummary(summaryResponse);
      setMetadata(metadataResponse);
      setExperiments(experimentsResponse.items);

      const firstExperiment = experimentsResponse.items[0];
      if (firstExperiment) {
        setSelectedExperimentId(firstExperiment.experiment_id);
      }

      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить данные по модели." : "Unable to load model intelligence data."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [locale, localeTag]);

  const loadExperiment = React.useCallback(
    async (experimentId: string) => {
      setDetailLoading(true);
      setError("");
      setSelectedExperimentId(experimentId);
      try {
        const detail = await fetchMLExperiment(experimentId);
        setSelectedExperiment(detail);
      } catch (errorResponse) {
        setError(
          extractApiError(
            errorResponse,
            locale === "ru"
              ? "Не удалось загрузить детали эксперимента."
              : "Unable to load experiment detail."
          )
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [locale]
  );

  React.useEffect(() => {
    load();
  }, [load]);

  React.useEffect(() => {
    if (!selectedExperimentId) {
      setSelectedExperiment(null);
      return;
    }
    loadExperiment(selectedExperimentId);
  }, [loadExperiment, selectedExperimentId]);

  const bestMetrics = metadata?.metrics?.best;
  const featureData = (metadata?.top_feature_importance ?? []).slice(0, 12);

  const experimentMetricChartData = React.useMemo(() => {
    if (!selectedExperiment?.metrics) {
      return [] as Array<{ key: string; value: number }>;
    }

    const raw = selectedExperiment.metrics;
    const candidates: Array<[string, number | null]> = [
      ["RMSE", metricToNumber(raw.rmse)],
      ["MAE", metricToNumber(raw.mae)],
      ["MAPE", metricToNumber(raw.mape)],
      ["WAPE", metricToNumber(raw.wape)],
      ["sMAPE", metricToNumber(raw.smape)],
    ];

    return candidates.flatMap(([key, value]) => {
      if (value === null) {
        return [];
      }
      return [{ key, value }];
    });
  }, [selectedExperiment]);

  return (
    <PageLayout
      title={locale === "ru" ? "Интеллект модели" : "Model Intelligence"}
      subtitle={
        locale === "ru"
          ? "Качество продакшн-модели и внутренний реестр ML-экспериментов."
          : "Production model quality with internal ML experiment tracking."
      }
      actions={
        <>
          <p className="meta-text">{locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}</p>
          <button className="button primary" type="button" onClick={load} disabled={loading}>
            {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить" : "Refresh"}
          </button>
        </>
      }
    >
      {error ? <ErrorState message={error} /> : null}
      {loading && !metadata ? <LoadingState lines={5} /> : null}

      {summary && metadata ? (
        <div className="insight-grid">
          <MetricCard label={locale === "ru" ? "Выбранная модель" : "Selected Model"} value={metadata.selected_model.toUpperCase()} />
          <MetricCard label="RMSE" value={formatDecimal(bestMetrics?.rmse ?? 0)} />
          <MetricCard label="MAE" value={formatDecimal(bestMetrics?.mae ?? 0)} />
          <MetricCard label="WAPE" value={typeof bestMetrics?.wape === "number" ? formatPercent(bestMetrics.wape) : "-"} />
          <MetricCard label={locale === "ru" ? "Магазины" : "Stores"} value={formatInt(summary.stores_count)} />
          <MetricCard label={locale === "ru" ? "Строк продаж" : "Sales Rows"} value={formatInt(summary.sales_rows_count)} />
        </div>
      ) : null}

      {metadata ? (
        <Card title={locale === "ru" ? "Модель в production" : "Production Model Metadata"}>
          <div className="grid-two">
            <div className="panel stack">
              <p className="muted">{locale === "ru" ? "Период обучения" : "Training Period"}: {formatIsoDate(metadata.train_period?.date_from)} - {formatIsoDate(metadata.train_period?.date_to)}</p>
              <p className="muted">{locale === "ru" ? "Период валидации" : "Validation Period"}: {formatIsoDate(metadata.validation_period?.date_from)} - {formatIsoDate(metadata.validation_period?.date_to)}</p>
              <p className="muted">{locale === "ru" ? "Обучена" : "Trained At"}: {utcOrDash(metadata.trained_at)}</p>
              <p className="muted">rows train/val: {formatInt(metadata.rows?.train ?? 0)} / {formatInt(metadata.rows?.validation ?? 0)}</p>
            </div>
            {featureData.length > 0 ? <ImportanceChart data={featureData} /> : null}
          </div>
        </Card>
      ) : null}

      <Card
        title={locale === "ru" ? "Реестр экспериментов" : "Experiment Registry"}
        subtitle={locale === "ru" ? "Автоматические записи из каждого train-run." : "Automatically captured for each train run."}
      >
        {loading && experiments.length === 0 ? (
          <LoadingState lines={3} />
        ) : experiments.length === 0 ? (
          <EmptyState message={locale === "ru" ? "Эксперименты пока не зарегистрированы." : "No experiments recorded yet."} />
        ) : (
          <DataTable>
            <thead>
              <tr>
                <th>{locale === "ru" ? "Experiment ID" : "Experiment ID"}</th>
                <th>{locale === "ru" ? "Модель" : "Model"}</th>
                <th>{locale === "ru" ? "Статус" : "Status"}</th>
                <th>RMSE</th>
                <th>MAPE</th>
                <th>{locale === "ru" ? "Создан" : "Created"}</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((experiment) => (
                <tr
                  key={experiment.experiment_id}
                  className={selectedExperimentId === experiment.experiment_id ? "table-row-active" : ""}
                  onClick={() => loadExperiment(experiment.experiment_id)}
                >
                  <td className="mono-small">{experiment.experiment_id}</td>
                  <td>{experiment.model_type}</td>
                  <td><StatusBadge status={experiment.status} /></td>
                  <td>{typeof experiment.metrics.rmse === "number" ? formatDecimal(experiment.metrics.rmse) : "-"}</td>
                  <td>{typeof experiment.metrics.mape === "number" ? formatPercent(experiment.metrics.mape) : "-"}</td>
                  <td>{utcOrDash(experiment.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </Card>

      {detailLoading ? <LoadingState lines={2} /> : null}

      {selectedExperiment ? (
        <Card
          title={locale === "ru" ? "Детали эксперимента" : "Experiment Detail"}
          subtitle={selectedExperiment.experiment_id}
        >
          <div className="grid-two">
            <div className="panel stack">
              <p className="muted">model_type: <strong>{selectedExperiment.model_type}</strong></p>
              <p className="muted">status: <StatusBadge status={selectedExperiment.status} /></p>
              <p className="muted">train: {formatIsoDate(selectedExperiment.training_period.start)} - {formatIsoDate(selectedExperiment.training_period.end)}</p>
              <p className="muted">validation: {formatIsoDate(selectedExperiment.validation_period.start)} - {formatIsoDate(selectedExperiment.validation_period.end)}</p>
              <p className="muted">artifact: {selectedExperiment.artifact_path || "-"}</p>
              <p className="muted">metadata: {selectedExperiment.metadata_path || "-"}</p>
            </div>
            <div className="panel" style={{ minHeight: 240 }}>
              {experimentMetricChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={experimentMetricChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                    <XAxis dataKey="key" stroke="var(--chart-axis)" />
                    <YAxis stroke="var(--chart-axis)" />
                    <Tooltip />
                    <Bar dataKey="value" fill="var(--chart-primary)" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="muted">{locale === "ru" ? "Нет метрик для визуализации." : "No metrics to visualize."}</p>
              )}
            </div>
          </div>

          <div className="panel stack">
            <h4>{locale === "ru" ? "Гиперпараметры" : "Hyperparameters"}</h4>
            <pre className="json-block">{JSON.stringify(selectedExperiment.hyperparameters, null, 2)}</pre>
            <h4>{locale === "ru" ? "Метрики" : "Metrics"}</h4>
            <pre className="json-block">{JSON.stringify(selectedExperiment.metrics, null, 2)}</pre>
          </div>
        </Card>
      ) : null}
    </PageLayout>
  );
}
