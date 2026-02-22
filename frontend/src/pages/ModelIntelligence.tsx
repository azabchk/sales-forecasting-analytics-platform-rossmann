import React from "react";

import { extractApiError } from "../api/client";
import { fetchModelMetadata, fetchSystemSummary, ModelMetadata, SystemSummary } from "../api/endpoints";
import ImportanceChart from "../components/ImportanceChart";
import { useI18n } from "../lib/i18n";
import LoadingBlock from "../components/LoadingBlock";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";

function formatIsoDate(date: string | null | undefined): string {
  if (!date) {
    return "-";
  }
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) {
    return date;
  }
  return parsed.toISOString().slice(0, 10);
}

function metricOrDash(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }
  return formatDecimal(value);
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

export default function ModelIntelligence() {
  const { locale, localeTag } = useI18n();
  const [summary, setSummary] = React.useState<SystemSummary | null>(null);
  const [metadata, setMetadata] = React.useState<ModelMetadata | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [lastUpdated, setLastUpdated] = React.useState("-");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryResponse, metadataResponse] = await Promise.all([fetchSystemSummary(), fetchModelMetadata()]);
      setSummary(summaryResponse);
      setMetadata(metadataResponse);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить данные по качеству модели." : "Unable to load model intelligence data."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [locale, localeTag]);

  React.useEffect(() => {
    load();
  }, [load]);

  const bestMetrics = metadata?.metrics?.best;
  const featureData = (metadata?.top_feature_importance ?? []).slice(0, 12);
  const candidates = metadata?.catboost_candidates ?? [];
  const nonZeroMape =
    typeof bestMetrics?.mape_nonzero === "number"
      ? bestMetrics.mape_nonzero
      : typeof bestMetrics?.mape === "number" && bestMetrics.mape > 10_000
        ? null
        : bestMetrics?.mape;

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">{locale === "ru" ? "Интеллект модели" : "Model Intelligence"}</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Управленческий обзор качества модели, масштаба данных и вклада признаков."
              : "Governance view for model quality, data scale, and feature contribution."}
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}</p>
          <button className="button primary" type="button" onClick={load} disabled={loading}>
            {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить диагностику" : "Refresh diagnostics"}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {loading && !metadata && (
        <div className="panel">
          <LoadingBlock lines={4} className="loading-stack" />
        </div>
      )}

      {summary && metadata && (
        <>
          <div className="insight-grid">
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Выбранная модель" : "Selected Model"}</p>
              <p className="insight-value">{metadata.selected_model.toUpperCase()}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "RMSE валидации" : "Validation RMSE"}</p>
              <p className="insight-value">{metricOrDash(bestMetrics?.rmse)}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "WAPE валидации" : "Validation WAPE"}</p>
              <p className="insight-value">
                {typeof bestMetrics?.wape === "number" ? formatPercent(bestMetrics.wape) : "-"}
              </p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "MAE валидации" : "Validation MAE"}</p>
              <p className="insight-value">{metricOrDash(bestMetrics?.mae)}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "sMAPE валидации" : "Validation sMAPE"}</p>
              <p className="insight-value">{typeof bestMetrics?.smape === "number" ? formatPercent(bestMetrics.smape) : "-"}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "MAPE валидации (ненул.)" : "Validation MAPE (non-zero)"}</p>
              <p className="insight-value">{typeof bestMetrics?.mape_nonzero === "number" ? formatPercent(bestMetrics.mape_nonzero) : "-"}</p>
            </div>
          </div>

          <div className="insight-grid">
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Магазины в БД" : "Stores in DB"}</p>
              <p className="insight-value">{formatInt(summary.stores_count)}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Строк продаж в БД" : "Sales Rows in DB"}</p>
              <p className="insight-value">{formatInt(summary.sales_rows_count)}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Период обучения" : "Train Window"}</p>
              <p className="insight-value">
                {formatIsoDate(metadata.train_period?.date_from)} {locale === "ru" ? "до" : "to"} {formatIsoDate(metadata.train_period?.date_to)}
              </p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Период валидации" : "Validation Window"}</p>
              <p className="insight-value">
                {formatIsoDate(metadata.validation_period?.date_from)} {locale === "ru" ? "до" : "to"} {formatIsoDate(metadata.validation_period?.date_to)}
              </p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Время обучения (UTC)" : "Trained At (UTC)"}</p>
              <p className="insight-value">{utcOrDash(metadata.trained_at)}</p>
            </div>
            <div className="insight-card">
              <p className="insight-label">{locale === "ru" ? "Строк валидации" : "Validation Rows"}</p>
              <p className="insight-value">{formatInt(metadata.rows?.validation ?? 0)}</p>
            </div>
          </div>

          {featureData.length > 0 && <ImportanceChart data={featureData} />}

          <div className="panel">
            <div className="panel-head">
              <h3>{locale === "ru" ? "Диагностика модели" : "Model Diagnostics"}</h3>
              <p className="panel-subtitle">{locale === "ru" ? "Метрики кандидатов и основание финального выбора." : "Candidate metrics and final selection evidence."}</p>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{locale === "ru" ? "Кандидат" : "Candidate"}</th>
                    <th>RMSE</th>
                    <th>MAE</th>
                    <th>WAPE</th>
                    <th>MAPE*</th>
                    <th>sMAPE</th>
                    <th>MAPE NZ</th>
                    <th>{locale === "ru" ? "Параметры" : "Params"}</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate, index) => (
                    <tr key={`candidate-${index}`}>
                      <td>{locale === "ru" ? "CatBoost" : "CatBoost"} #{index + 1}</td>
                      <td>{metricOrDash(candidate.metrics.rmse)}</td>
                      <td>{metricOrDash(candidate.metrics.mae)}</td>
                      <td>{typeof candidate.metrics.wape === "number" ? formatPercent(candidate.metrics.wape) : "-"}</td>
                      <td>{typeof candidate.metrics.mape === "number" ? formatDecimal(candidate.metrics.mape) : "-"}</td>
                      <td>{typeof candidate.metrics.smape === "number" ? formatPercent(candidate.metrics.smape) : "-"}</td>
                      <td>{typeof candidate.metrics.mape_nonzero === "number" ? formatPercent(candidate.metrics.mape_nonzero) : "-"}</td>
                      <td>
                        <code className="mono-small">{Object.entries(candidate.params).map(([key, value]) => `${key}=${value}`).join(", ")}</code>
                      </td>
                    </tr>
                  ))}
                  {candidates.length === 0 && (
                    <tr>
                      <td colSpan={8}>{locale === "ru" ? "Нет записей кандидатов в metadata." : "No candidate records available in metadata."}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="muted">
              {locale === "ru"
                ? `* Если MAPE слишком большой, ориентируйтесь на WAPE или MAPE по ненулевым значениям. Текущий non-zero MAPE: ${metricOrDash(nonZeroMape)}`
                : `* If MAPE is extremely large, prefer WAPE or non-zero MAPE. Current non-zero MAPE: ${metricOrDash(nonZeroMape)}`}
            </p>
          </div>
        </>
      )}
    </section>
  );
}
