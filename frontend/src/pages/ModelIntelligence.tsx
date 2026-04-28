import React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { apiClient, extractApiError } from "../api/client";
import { MLExperimentDetail } from "../api/endpoints";
import ImportanceChart from "../components/ImportanceChart";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import { SmartColumn, SmartTable } from "../components/ui/DataTable";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import StatusBadge from "../components/StatusBadge";
import {
  useMlExperiment,
  useMlExperiments,
  useModelMetadata,
  useSystemSummary,
} from "../hooks/useApiQuery";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";
import { useI18n } from "../lib/i18n";

type DriftItem = { metric: string; current: number; previous: number; delta_pct: number; drift_status: string };
type DriftResult = { overall_drift: string; drift: DriftItem[]; latest_trained_at: string; previous_trained_at: string; status?: string; message?: string };

function formatIsoDate(value: string | null | undefined): string {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString().slice(0, 10);
}

function utcOrDash(value: string | null | undefined): string {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toUTCString();
}

function metricToNumber(value: unknown): number | null {
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

export default function ModelIntelligence() {
  const { locale } = useI18n();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [retraining, setRetraining] = React.useState(false);
  const [retrainMsg, setRetrainMsg] = React.useState<string | null>(null);
  const [drift, setDrift] = React.useState<DriftResult | null>(null);
  const [driftLoading, setDriftLoading] = React.useState(false);

  async function handleRetrain() {
    setRetraining(true);
    setRetrainMsg(null);
    try {
      const { data } = await apiClient.post<{ pid: number; message: string }>("/ml/retrain");
      setRetrainMsg(`✓ ${data.message} (PID: ${data.pid})`);
    } catch (e) {
      setRetrainMsg("✗ " + extractApiError(e, "Failed to start training"));
    } finally {
      setRetraining(false);
    }
  }

  async function loadDrift() {
    setDriftLoading(true);
    try {
      const { data } = await apiClient.get<DriftResult>("/ml/drift");
      setDrift(data);
    } catch { setDrift(null); }
    finally { setDriftLoading(false); }
  }

  React.useEffect(() => { loadDrift(); }, []);

  const summaryQ = useSystemSummary();
  const metadataQ = useModelMetadata();
  const experimentsQ = useMlExperiments({ limit: 100 });
  const experimentDetailQ = useMlExperiment(selectedId ?? "", { enabled: !!selectedId });

  // Auto-select first experiment when list loads
  React.useEffect(() => {
    if (!selectedId && experimentsQ.data?.items?.length) {
      setSelectedId(experimentsQ.data.items[0].experiment_id);
    }
  }, [experimentsQ.data, selectedId]);

  const bestMetrics = metadataQ.data?.metrics?.best;
  const featureData = (metadataQ.data?.top_feature_importance ?? []).slice(0, 12);
  const experiments = experimentsQ.data?.items ?? [];
  const selectedExperiment = experimentDetailQ.data as MLExperimentDetail | undefined;

  const experimentMetricChartData = React.useMemo(() => {
    if (!selectedExperiment?.metrics) return [] as Array<{ key: string; value: number }>;
    const raw = selectedExperiment.metrics;
    return (
      [
        ["RMSE", metricToNumber(raw.rmse)],
        ["MAE", metricToNumber(raw.mae)],
        ["MAPE", metricToNumber(raw.mape)],
        ["WAPE", metricToNumber(raw.wape)],
        ["sMAPE", metricToNumber(raw.smape)],
      ] as Array<[string, number | null]>
    ).flatMap(([key, value]) => (value === null ? [] : [{ key, value }]));
  }, [selectedExperiment]);

  const isLoading = summaryQ.isLoading || metadataQ.isLoading || experimentsQ.isLoading;
  const error = summaryQ.error || metadataQ.error || experimentsQ.error;

  const expColumns: SmartColumn<Record<string, unknown>>[] = [
    {
      key: "experiment_id", label: "Experiment ID", sortable: true, searchable: true,
      render: (v) => <span className="mono-small">{String(v ?? "")}</span>,
    },
    { key: "model_type", label: locale === "ru" ? "Модель" : "Model", sortable: true },
    { key: "status", label: locale === "ru" ? "Статус" : "Status", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    {
      key: "metrics", label: "RMSE",
      render: (v) => {
        const m = v as Record<string, unknown> | null;
        return typeof m?.rmse === "number" ? formatDecimal(m.rmse) : "-";
      },
    },
    {
      key: "metrics", label: "MAPE",
      render: (v) => {
        const m = v as Record<string, unknown> | null;
        return typeof m?.mape === "number" ? formatPercent(m.mape) : "-";
      },
    },
    { key: "created_at", label: locale === "ru" ? "Создан" : "Created", sortable: true, render: (v) => utcOrDash(v as string) },
  ];

  return (
    <PageLayout
      title={locale === "ru" ? "Интеллект модели" : "Model Intelligence"}
      subtitle={locale === "ru" ? "Качество продакшн-модели и реестр ML-экспериментов." : "Production model quality with ML experiment tracking."}
      actions={
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="retrain-btn" type="button" onClick={handleRetrain} disabled={retraining}>
            {retraining ? <><span className="login-spinner" style={{ width: 14, height: 14 }} /> Training…</> : "⚡ Retrain Model"}
          </button>
          <button className="button ghost" type="button" onClick={() => { summaryQ.refetch(); metadataQ.refetch(); experimentsQ.refetch(); loadDrift(); }} disabled={isLoading}>
            {isLoading ? "Refreshing…" : "↻ Refresh"}
          </button>
        </div>
      }
    >
      {error ? <ErrorState message={(error as Error).message} onRetry={() => { summaryQ.refetch(); metadataQ.refetch(); experimentsQ.refetch(); }} /> : null}
      {isLoading && !metadataQ.data ? <LoadingState lines={5} /> : null}

      {/* Retrain progress message */}
      {retrainMsg && (
        <div className="retrain-progress" style={{ marginBottom: 16, color: retrainMsg.startsWith("✓") ? "var(--status-pass)" : "var(--status-fail)" }}>
          {retrainMsg}
        </div>
      )}

      {/* Drift Detection Card */}
      {!driftLoading && drift && drift.drift && drift.drift.length > 0 && (
        <div className="panel" style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <h2 className="section-title" style={{ margin: 0 }}>Model Drift Detection</h2>
            <span className={`status-badge ${drift.overall_drift === "stable" ? "status-pass" : drift.overall_drift === "degrading" ? "status-fail" : "status-warn"}`}>
              {drift.overall_drift.toUpperCase()}
            </span>
          </div>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: 16 }}>
            Comparing latest vs previous completed experiment.
          </p>
          {drift.drift.map((d) => (
            <div className="drift-row" key={d.metric}>
              <span className="drift-metric-name">{d.metric}</span>
              <span className="drift-val">now: <strong>{d.current}</strong></span>
              <span className="drift-val">prev: {d.previous}</span>
              <span className={`drift-delta ${d.drift_status}`}>
                {d.delta_pct > 0 ? "+" : ""}{d.delta_pct}%
              </span>
              <span className={`status-badge ${d.drift_status === "stable" ? "status-skipped" : d.drift_status === "degrading" ? "status-fail" : "status-pass"}`} style={{ marginLeft: 8 }}>
                {d.drift_status}
              </span>
            </div>
          ))}
        </div>
      )}
      {!driftLoading && drift?.status === "insufficient_data" && (
        <div className="panel" style={{ marginBottom: 24, color: "var(--text-muted)", fontSize: "0.875rem" }}>
          Drift detection needs at least 2 completed training experiments.
        </div>
      )}

      {summaryQ.data && metadataQ.data ? (
        <div className="insight-grid">
          <MetricCard label={locale === "ru" ? "Выбранная модель" : "Selected Model"} value={metadataQ.data.selected_model.toUpperCase()} />
          <MetricCard label="RMSE" value={formatDecimal(bestMetrics?.rmse ?? 0)} />
          <MetricCard label="MAE" value={formatDecimal(bestMetrics?.mae ?? 0)} />
          <MetricCard label="WAPE" value={typeof bestMetrics?.wape === "number" ? formatPercent(bestMetrics.wape) : "-"} />
          <MetricCard label={locale === "ru" ? "Магазины" : "Stores"} value={formatInt(summaryQ.data.stores_count)} />
          <MetricCard label={locale === "ru" ? "Строк продаж" : "Sales Rows"} value={formatInt(summaryQ.data.sales_rows_count)} />
        </div>
      ) : null}

      {metadataQ.data ? (
        <Card title={locale === "ru" ? "Модель в production" : "Production Model Metadata"}>
          <div className="grid-two">
            <div className="panel stack">
              <p className="muted">{locale === "ru" ? "Период обучения" : "Training Period"}: {formatIsoDate(metadataQ.data.train_period?.date_from)} — {formatIsoDate(metadataQ.data.train_period?.date_to)}</p>
              <p className="muted">{locale === "ru" ? "Период валидации" : "Validation Period"}: {formatIsoDate(metadataQ.data.validation_period?.date_from)} — {formatIsoDate(metadataQ.data.validation_period?.date_to)}</p>
              <p className="muted">{locale === "ru" ? "Обучена" : "Trained At"}: {utcOrDash(metadataQ.data.trained_at)}</p>
              <p className="muted">rows train/val: {formatInt(metadataQ.data.rows?.train ?? 0)} / {formatInt(metadataQ.data.rows?.validation ?? 0)}</p>
            </div>
            {featureData.length > 0 ? <ImportanceChart data={featureData} /> : null}
          </div>
        </Card>
      ) : null}

      <Card
        title={locale === "ru" ? "Реестр экспериментов" : "Experiment Registry"}
        subtitle={locale === "ru" ? "Автоматические записи из каждого train-run." : "Automatically captured for each train run."}
      >
        {experimentsQ.isLoading && experiments.length === 0 ? (
          <LoadingState lines={3} />
        ) : experiments.length === 0 ? (
          <EmptyState message={locale === "ru" ? "Эксперименты пока не зарегистрированы." : "No experiments recorded yet."} />
        ) : (
          <SmartTable
            columns={expColumns}
            data={experiments as Record<string, unknown>[]}
            pageSize={20}
            searchable
            rowKeyField="experiment_id"
            selectedKey={selectedId ?? undefined}
            onRowClick={(row) => setSelectedId(String(row.experiment_id))}
          />
        )}
      </Card>

      {experimentDetailQ.isLoading ? <LoadingState lines={2} /> : null}

      {selectedExperiment ? (
        <Card title={locale === "ru" ? "Детали эксперимента" : "Experiment Detail"} subtitle={selectedExperiment.experiment_id}>
          <div className="grid-two">
            <div className="panel stack">
              <p className="muted">model_type: <strong>{selectedExperiment.model_type}</strong></p>
              <p className="muted">status: <StatusBadge status={selectedExperiment.status} /></p>
              <p className="muted">train: {formatIsoDate(selectedExperiment.training_period.start)} — {formatIsoDate(selectedExperiment.training_period.end)}</p>
              <p className="muted">validation: {formatIsoDate(selectedExperiment.validation_period.start)} — {formatIsoDate(selectedExperiment.validation_period.end)}</p>
              <p className="muted">artifact: {selectedExperiment.artifact_path || "-"}</p>
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
              ) : <p className="muted">{locale === "ru" ? "Нет метрик." : "No metrics to visualize."}</p>}
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
