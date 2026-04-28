import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ForecastPoint } from "../api/endpoints";
import ForecastChart from "../components/ForecastChart";
import LoadingBlock from "../components/LoadingBlock";
import StoreSelector from "../components/StoreSelector";
import { ErrorState } from "../components/ui/States";
import { useForecast, useStores } from "../hooks/useApiQuery";
import { useToast } from "../components/ui/Toast";
import { extractApiError } from "../api/client";
import { formatDecimal, formatInt } from "../lib/format";
import { useI18n } from "../lib/i18n";

function summarizeForecast(rows: ForecastPoint[]) {
  if (rows.length === 0) return { total: 0, avg: 0, peak: 0, peakDate: "-", avgBandWidth: 0 };
  const total = rows.reduce((a, r) => a + r.predicted_sales, 0);
  const peakRow = rows.reduce((m, r) => (r.predicted_sales > m.predicted_sales ? r : m), rows[0]);
  const bands = rows
    .map((r) => (typeof r.predicted_lower === "number" && typeof r.predicted_upper === "number" ? r.predicted_upper - r.predicted_lower : 0))
    .filter((v) => v > 0);
  return {
    total,
    avg: total / rows.length,
    peak: peakRow.predicted_sales,
    peakDate: peakRow.date,
    avgBandWidth: bands.length ? bands.reduce((s, v) => s + v, 0) / bands.length : 0,
  };
}

export default function ForecastPage() {
  const { locale, localeTag } = useI18n();
  const { success, error: toastError } = useToast();

  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [horizon, setHorizon] = useState(30);
  const [data, setData] = useState<ForecastPoint[]>([]);
  const [lastUpdated, setLastUpdated] = useState("-");

  const storesQ = useStores();

  // Auto-select first store
  React.useEffect(() => {
    if (!storeId && storesQ.data?.length) setStoreId(storesQ.data[0].store_id);
  }, [storesQ.data, storeId]);

  const forecastMutation = useForecast({
    onSuccess: (result) => {
      setData(result);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
      success(locale === "ru" ? "Прогноз готов!" : "Forecast ready!");
    },
    onError: (err) => {
      toastError(extractApiError(err, locale === "ru" ? "Не удалось сформировать прогноз." : "Unable to generate forecast."));
    },
  });

  function generateForecast() {
    if (!storeId) return;
    forecastMutation.mutate({ store_id: storeId, horizon_days: horizon });
  }

  function downloadCsv() {
    if (!data.length) return;
    const csv = ["date,predicted_sales,predicted_lower,predicted_upper",
      ...data.map((r) => `${r.date},${r.predicted_sales},${r.predicted_lower ?? ""},${r.predicted_upper ?? ""}`)
    ].join("\n");
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" })),
      download: `forecast_store_${storeId}_${horizon}d.csv`,
    });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }

  const summary = useMemo(() => summarizeForecast(data), [data]);
  const topRows = useMemo(() => data.slice(0, 14), [data]);
  const loading = forecastMutation.isPending;

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">{locale === "ru" ? "Студия прогноза" : "Forecast Studio"}</h2>
          <p className="page-note">
            {locale === "ru" ? "Рекурсивный многодневный прогноз с доверительными интервалами и экспортом." : "Recursive multi-day forecasting with confidence bands and export-ready outputs."}
          </p>
          <p className="page-note">
            {locale === "ru" ? "Нужна диагностика модели? Откройте " : "Need model diagnostics? Open "}
            <Link to="/model-intelligence" className="inline-link">{locale === "ru" ? "Интеллект модели" : "Model Intelligence"}</Link>
            {locale === "ru" ? ". Нужна симуляция? Откройте " : ". Need simulation? Open "}
            <Link to="/scenario-lab" className="inline-link">{locale === "ru" ? "Сценарии" : "Scenario Lab"}</Link>.
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}</p>
          <div className="preset-row">
            {[7, 30, 90].map((d) => (
              <button key={d} type="button" className="button ghost" onClick={() => setHorizon(d)}>{d}D</button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={storesQ.data ?? []} value={storeId} onChange={setStoreId} label={locale === "ru" ? "Магазин" : "Store"} includeAllOption={false} id="forecast-store" />
          <div className="field">
            <label htmlFor="forecast-horizon">{locale === "ru" ? "Горизонт (дни)" : "Horizon (days)"}</label>
            <input id="forecast-horizon" className="input" type="number" min={1} max={180} value={horizon}
              onChange={(e) => setHorizon(Math.max(1, Math.min(180, Number(e.target.value) || 1)))} />
          </div>
          <button onClick={generateForecast} className="button primary" disabled={loading || !storeId}>
            {loading ? (locale === "ru" ? "Выполняется..." : "Running...") : locale === "ru" ? "Сформировать прогноз" : "Generate forecast"}
          </button>
          <button onClick={downloadCsv} className="button" type="button" disabled={!data.length}>
            {locale === "ru" ? "Скачать CSV" : "Download CSV"}
          </button>
        </div>
      </div>

      {forecastMutation.error ? (
        <ErrorState message={extractApiError(forecastMutation.error, "Forecast failed")} onRetry={generateForecast} />
      ) : null}

      {loading && !data.length && (
        <div className="panel"><LoadingBlock lines={4} className="loading-stack" /></div>
      )}

      {data.length > 0 && (
        <>
          <div className="forecast-summary">
            <div className="summary-box"><p className="label">{locale === "ru" ? "Суммарный прогноз" : "Total forecast"}</p><p className="value">{formatInt(summary.total)}</p></div>
            <div className="summary-box"><p className="label">{locale === "ru" ? "Среднее в день" : "Average per day"}</p><p className="value">{formatDecimal(summary.avg)}</p></div>
            <div className="summary-box"><p className="label">{locale === "ru" ? "Пиковый день" : "Peak day"}</p><p className="value">{formatInt(summary.peak)} ({summary.peakDate})</p></div>
            <div className="summary-box"><p className="label">{locale === "ru" ? "Средняя ширина интервала" : "Avg interval width"}</p><p className="value">{summary.avgBandWidth > 0 ? formatDecimal(summary.avgBandWidth) : "N/A"}</p></div>
          </div>
          <ForecastChart data={data} />
          <div className="panel">
            <div className="panel-head">
              <h3>{locale === "ru" ? "Первые 14 строк прогноза" : "First 14 Forecast Rows"}</h3>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{locale === "ru" ? "Дата" : "Date"}</th>
                    <th>{locale === "ru" ? "Прогноз" : "Predicted Sales"}</th>
                    <th>{locale === "ru" ? "Нижняя" : "Lower"}</th>
                    <th>{locale === "ru" ? "Верхняя" : "Upper"}</th>
                  </tr>
                </thead>
                <tbody>
                  {topRows.map((r) => (
                    <tr key={r.date}>
                      <td>{r.date}</td>
                      <td>{formatInt(r.predicted_sales)}</td>
                      <td>{typeof r.predicted_lower === "number" ? formatInt(r.predicted_lower) : "-"}</td>
                      <td>{typeof r.predicted_upper === "number" ? formatInt(r.predicted_upper) : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!loading && !data.length && !forecastMutation.error && (
        <p className="muted">{locale === "ru" ? "Выберите параметры прогноза и запустите модель." : "Select forecast settings and run the model to display results."}</p>
      )}
    </section>
  );
}
