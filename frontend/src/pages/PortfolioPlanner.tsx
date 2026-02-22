import React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { extractApiError } from "../api/client";
import {
  fetchStores,
  ForecastBatchResponse,
  postForecastBatch,
  Store,
} from "../api/endpoints";
import LoadingBlock from "../components/LoadingBlock";
import { useI18n } from "../lib/i18n";
import { formatCompact, formatDateLabel, formatInt } from "../lib/format";

function parseStoreIds(raw: string): number[] {
  const seen = new Set<number>();
  const parsed: number[] = [];
  for (const token of raw.split(/[,\s]+/)) {
    const trimmed = token.trim();
    if (!trimmed) {
      continue;
    }
    const value = Number(trimmed);
    if (!Number.isInteger(value) || value <= 0 || seen.has(value)) {
      continue;
    }
    seen.add(value);
    parsed.push(value);
  }
  return parsed;
}

export default function PortfolioPlanner() {
  const { locale, localeTag } = useI18n();
  const [stores, setStores] = React.useState<Store[]>([]);
  const [storeIdsInput, setStoreIdsInput] = React.useState("1,2,3,4,5");
  const [horizon, setHorizon] = React.useState(30);
  const [result, setResult] = React.useState<ForecastBatchResponse | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [lastUpdated, setLastUpdated] = React.useState("-");

  React.useEffect(() => {
    fetchStores()
      .then((rows) => {
        setStores(rows);
        setStoreIdsInput((current) => {
          if (current.trim() || rows.length === 0) {
            return current;
          }
          const defaults = rows.slice(0, 5).map((store) => String(store.store_id));
          return defaults.join(",");
        });
      })
      .catch((errorResponse) => {
        setError(
          extractApiError(
            errorResponse,
            locale === "ru" ? "Не удалось загрузить магазины." : "Failed to load stores."
          )
        );
      });
  }, [locale]);

  async function runPortfolioForecast() {
    const parsedStoreIds = parseStoreIds(storeIdsInput);
    if (parsedStoreIds.length === 0) {
      setError(locale === "ru" ? "Укажите минимум один ID магазина." : "Provide at least one store ID.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const data = await postForecastBatch({ store_ids: parsedStoreIds, horizon_days: horizon });
      setResult(data);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru"
            ? "Не удалось выполнить портфельный прогноз."
            : "Failed to run portfolio forecast."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  function useTopStores() {
    const top = stores.slice(0, 10).map((store) => store.store_id);
    setStoreIdsInput(top.join(","));
  }

  function downloadCsv() {
    if (!result) {
      return;
    }

    const header = "date,predicted_sales,predicted_lower,predicted_upper";
    const rows = result.portfolio_series.map(
      (row) => `${row.date},${row.predicted_sales},${row.predicted_lower ?? ""},${row.predicted_upper ?? ""}`
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `portfolio_forecast_${result.request.store_ids.length}stores_${result.request.horizon_days}d.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">{locale === "ru" ? "Портфельный планировщик" : "Portfolio Planner"}</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Сводный прогноз для группы магазинов: общий объём, пиковые даты и разброс неопределенности."
              : "Batch forecasting for a store portfolio with aggregate volume, peak timing, and uncertainty spread."}
          </p>
        </div>
        <p className="meta-text">
          {locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}
        </p>
      </div>

      <div className="panel">
        <div className="controls controls-grid-portfolio">
          <div className="field">
            <label htmlFor="portfolio-store-ids">
              {locale === "ru" ? "Store IDs (через запятую)" : "Store IDs (comma-separated)"}
            </label>
            <textarea
              id="portfolio-store-ids"
              className="textarea"
              rows={2}
              value={storeIdsInput}
              onChange={(event) => setStoreIdsInput(event.target.value)}
              placeholder={locale === "ru" ? "Пример: 1,2,5,11" : "Example: 1,2,5,11"}
            />
          </div>
          <div className="field">
            <label htmlFor="portfolio-horizon">{locale === "ru" ? "Горизонт (дни)" : "Horizon (days)"}</label>
            <input
              id="portfolio-horizon"
              className="input"
              type="number"
              min={1}
              max={180}
              value={horizon}
              onChange={(event) => setHorizon(Math.max(1, Math.min(180, Number(event.target.value) || 1)))}
            />
          </div>
          <div className="portfolio-actions">
            <button type="button" className="button ghost" onClick={useTopStores}>
              {locale === "ru" ? "Топ-10 магазинов" : "Use top-10 stores"}
            </button>
            <button type="button" className="button primary" onClick={runPortfolioForecast} disabled={loading}>
              {loading ? (locale === "ru" ? "Выполняется..." : "Running...") : locale === "ru" ? "Запустить" : "Run"}
            </button>
            <button type="button" className="button" onClick={downloadCsv} disabled={!result}>
              {locale === "ru" ? "Скачать CSV" : "Download CSV"}
            </button>
          </div>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {loading && !result && (
        <div className="panel">
          <LoadingBlock lines={4} className="loading-stack" />
        </div>
      )}

      {result && (
        <>
          <div className="forecast-summary">
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Магазинов" : "Stores"}</p>
              <p className="value">{formatInt(result.portfolio_summary.stores_count)}</p>
            </div>
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Суммарный прогноз" : "Total forecast"}</p>
              <p className="value">{formatCompact(result.portfolio_summary.total_predicted_sales)}</p>
            </div>
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Среднее в день" : "Daily average"}</p>
              <p className="value">{formatInt(result.portfolio_summary.avg_daily_sales)}</p>
            </div>
            <div className="summary-box">
              <p className="label">{locale === "ru" ? "Пиковый день" : "Peak day"}</p>
              <p className="value">
                {result.portfolio_summary.peak_date || "-"} ({formatInt(result.portfolio_summary.peak_sales)})
              </p>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>{locale === "ru" ? "Тренд портфеля" : "Portfolio Trend"}</h3>
              <p className="panel-subtitle">
                {locale === "ru" ? "Общий прогноз по выбранным магазинам" : "Aggregate projected sales across selected stores"}
              </p>
            </div>
            <div style={{ width: "100%", height: 340 }}>
              <ResponsiveContainer>
                <LineChart data={result.portfolio_series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis dataKey="date" minTickGap={24} tickFormatter={formatDateLabel} stroke="var(--chart-axis)" />
                  <YAxis tickFormatter={(value) => formatCompact(Number(value))} stroke="var(--chart-axis)" />
                  <Tooltip labelFormatter={(value) => formatDateLabel(String(value))} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="predicted_sales"
                    stroke="var(--chart-primary)"
                    strokeWidth={2.5}
                    dot={false}
                    name={locale === "ru" ? "Прогноз" : "Forecast"}
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted_lower"
                    stroke="var(--chart-tertiary)"
                    strokeWidth={1.3}
                    strokeDasharray="5 4"
                    dot={false}
                    name={locale === "ru" ? "Нижняя граница" : "Lower band"}
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted_upper"
                    stroke="var(--chart-tertiary)"
                    strokeWidth={1.3}
                    strokeDasharray="5 4"
                    dot={false}
                    name={locale === "ru" ? "Верхняя граница" : "Upper band"}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>{locale === "ru" ? "Срез по магазинам" : "Per-store Breakdown"}</h3>
              <p className="panel-subtitle">
                {locale === "ru" ? "Ключевые показатели для каждого магазина" : "Key summary metrics for each selected store"}
              </p>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{locale === "ru" ? "Магазин" : "Store"}</th>
                    <th>{locale === "ru" ? "Сумма" : "Total"}</th>
                    <th>{locale === "ru" ? "Среднее/день" : "Daily avg"}</th>
                    <th>{locale === "ru" ? "Пик" : "Peak"}</th>
                    <th>{locale === "ru" ? "Ср. ширина интервала" : "Avg interval width"}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.store_summaries.map((row) => (
                    <tr key={row.store_id}>
                      <td>#{row.store_id}</td>
                      <td>{formatInt(row.total_predicted_sales)}</td>
                      <td>{formatInt(row.avg_daily_sales)}</td>
                      <td>
                        {row.peak_date || "-"} ({formatInt(row.peak_sales)})
                      </td>
                      <td>{formatInt(row.avg_interval_width)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!loading && !result && !error && (
        <p className="muted">
          {locale === "ru"
            ? "Укажите магазины и запустите пакетный прогноз."
            : "Provide store IDs and run a batch forecast."}
        </p>
      )}
    </section>
  );
}
