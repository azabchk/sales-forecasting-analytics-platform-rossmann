import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { extractApiError } from "../api/client";
import { fetchStores, ForecastPoint, postForecast, Store } from "../api/endpoints";
import ForecastChart from "../components/ForecastChart";
import LoadingBlock from "../components/LoadingBlock";
import StoreSelector from "../components/StoreSelector";
import { useI18n } from "../lib/i18n";
import { formatDecimal, formatInt } from "../lib/format";

function summarizeForecast(rows: ForecastPoint[]) {
  if (rows.length === 0) {
    return {
      total: 0,
      avg: 0,
      peak: 0,
      peakDate: "-",
      avgBandWidth: 0,
    };
  }

  const total = rows.reduce((acc, row) => acc + row.predicted_sales, 0);
  const avg = total / rows.length;
  const peakRow = rows.reduce((maxRow, row) => (row.predicted_sales > maxRow.predicted_sales ? row : maxRow), rows[0]);
  const intervals = rows
    .map((row) => {
      if (typeof row.predicted_lower !== "number" || typeof row.predicted_upper !== "number") {
        return 0;
      }
      return row.predicted_upper - row.predicted_lower;
    })
    .filter((value) => value > 0);

  return {
    total,
    avg,
    peak: peakRow.predicted_sales,
    peakDate: peakRow.date,
    avgBandWidth: intervals.length > 0 ? intervals.reduce((sum, value) => sum + value, 0) / intervals.length : 0,
  };
}

export default function ForecastPage() {
  const { locale, localeTag } = useI18n();
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [horizon, setHorizon] = useState<number>(30);
  const [data, setData] = useState<ForecastPoint[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("-");

  React.useEffect(() => {
    fetchStores()
      .then((rows) => {
        setStores(rows);
        if (rows.length > 0) {
          setStoreId(rows[0].store_id);
        }
      })
      .catch((errorResponse) =>
        setError(
          extractApiError(errorResponse, locale === "ru" ? "Не удалось загрузить список магазинов." : "Failed to load stores list.")
        )
      );
  }, [locale]);

  async function generateForecast() {
    if (!storeId) {
      setError(locale === "ru" ? "Выберите магазин для запуска прогноза." : "Select a store to run forecast.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const result = await postForecast({ store_id: storeId, horizon_days: horizon });
      setData(result);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru"
            ? "Не удалось сформировать прогноз. Проверьте backend и обученную модель."
            : "Unable to generate forecast. Ensure backend and trained model are available."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => summarizeForecast(data), [data]);
  const topRows = useMemo(() => data.slice(0, 14), [data]);

  function setHorizonPreset(value: number) {
    setHorizon(value);
  }

  function downloadForecastCsv() {
    if (data.length === 0) {
      return;
    }

    const header = "date,predicted_sales,predicted_lower,predicted_upper";
    const rows = data.map(
      (row) =>
        `${row.date},${row.predicted_sales},${row.predicted_lower ?? ""},${row.predicted_upper ?? ""}`
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `forecast_store_${storeId}_${horizon}d.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">{locale === "ru" ? "Студия прогноза" : "Forecast Studio"}</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Рекурсивный многодневный прогноз с доверительными интервалами и экспортом."
              : "Recursive multi-day forecasting with confidence bands and export-ready outputs."}
          </p>
          <p className="page-note">
            {locale === "ru" ? "Нужна диагностика модели? Откройте " : "Need model diagnostics? Open "}
            <Link to="/model-intelligence" className="inline-link">
              {locale === "ru" ? "Интеллект модели" : "Model Intelligence"}
            </Link>
            {locale === "ru" ? ". Нужна симуляция планирования? Откройте " : ". Need planning simulation? Open "}
            <Link to="/scenario-lab" className="inline-link">
              {locale === "ru" ? "Сценарии" : "Scenario Lab"}
            </Link>
            .
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}</p>
          <div className="preset-row">
            <button type="button" className="button ghost" onClick={() => setHorizonPreset(7)}>
              7D
            </button>
            <button type="button" className="button ghost" onClick={() => setHorizonPreset(30)}>
              30D
            </button>
            <button type="button" className="button ghost" onClick={() => setHorizonPreset(90)}>
              90D
            </button>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector
            stores={stores}
            value={storeId}
            onChange={setStoreId}
            label={locale === "ru" ? "Магазин" : "Store"}
            includeAllOption={false}
            id="forecast-store"
          />
          <div className="field">
            <label htmlFor="forecast-horizon">{locale === "ru" ? "Горизонт (дни)" : "Horizon (days)"}</label>
            <input
              id="forecast-horizon"
              className="input"
              type="number"
              min={1}
              max={180}
              value={horizon}
              onChange={(e) => setHorizon(Math.max(1, Math.min(180, Number(e.target.value) || 1)))}
            />
          </div>
          <button onClick={generateForecast} className="button primary" disabled={loading || !storeId}>
            {loading ? (locale === "ru" ? "Выполняется..." : "Running...") : locale === "ru" ? "Сформировать прогноз" : "Generate forecast"}
          </button>
          <button onClick={downloadForecastCsv} className="button" type="button" disabled={data.length === 0}>
            {locale === "ru" ? "Скачать CSV" : "Download CSV"}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {loading && data.length === 0 && (
        <div className="panel">
          <LoadingBlock lines={4} className="loading-stack" />
        </div>
      )}

      {data.length > 0 && (
        <>
          <div className="forecast-summary">
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Суммарный прогноз" : "Total forecast"}</p>
              <p className="value">{formatInt(summary.total)}</p>
            </div>
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Среднее в день" : "Average per day"}</p>
              <p className="value">{formatDecimal(summary.avg)}</p>
            </div>
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Пиковый день" : "Peak day"}</p>
              <p className="value">
                {formatInt(summary.peak)} ({summary.peakDate})
              </p>
            </div>
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Средняя ширина интервала" : "Avg interval width"}</p>
              <p className="value">
                {summary.avgBandWidth > 0 ? formatDecimal(summary.avgBandWidth) : locale === "ru" ? "Н/Д" : "N/A"}
              </p>
            </div>
          </div>
          <ForecastChart data={data} />
          <div className="panel">
            <div className="panel-head">
              <h3>{locale === "ru" ? "Первые 14 строк прогноза" : "First 14 Forecast Rows"}</h3>
              <p className="panel-subtitle">{locale === "ru" ? "Операционный предпросмотр для быстрых решений." : "Operational preview for immediate planning decisions."}</p>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{locale === "ru" ? "Дата" : "Date"}</th>
                    <th>{locale === "ru" ? "Прогноз продаж" : "Predicted Sales"}</th>
                    <th>{locale === "ru" ? "Нижняя граница" : "Lower Band"}</th>
                    <th>{locale === "ru" ? "Верхняя граница" : "Upper Band"}</th>
                  </tr>
                </thead>
                <tbody>
                  {topRows.map((row) => (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td>{formatInt(row.predicted_sales)}</td>
                      <td>{typeof row.predicted_lower === "number" ? formatInt(row.predicted_lower) : "-"}</td>
                      <td>{typeof row.predicted_upper === "number" ? formatInt(row.predicted_upper) : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!loading && data.length === 0 && !error && (
        <p className="muted">{locale === "ru" ? "Выберите параметры прогноза и запустите модель." : "Select forecast settings and run the model to display results."}</p>
      )}
    </section>
  );
}
