import React, { useCallback, useMemo, useState } from "react";

import { API_BASE_URL } from "../api/client";
import KpiCards from "../components/KpiCards";
import SalesChart from "../components/SalesChart";
import StoreSelector from "../components/StoreSelector";
import { ErrorState } from "../components/ui/States";
import { useKpiSummary, useSalesTimeseries, useStores, useSystemSummary } from "../hooks/useApiQuery";
import { rangeFromPastDays, rangeYtd } from "../lib/dates";
import { formatInt, formatPercent } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { NoDataState } from "../components/ui/States";
import LoadingBlock from "../components/LoadingBlock";

type OverviewSalesPoint = { date: string; sales: number; customers: number };

function buildRangeFromSummary(dateFrom?: string | null, dateTo?: string | null) {
  if (dateFrom && dateTo) return { from: dateFrom, to: dateTo };
  return rangeFromPastDays(90);
}

function buildTrailingRange(dataTo: string | null | undefined, days: number) {
  const endBound = dataTo ? new Date(dataTo) : new Date();
  const from = new Date(endBound);
  from.setDate(from.getDate() - (days - 1));
  return { from: from.toISOString().slice(0, 10), to: endBound.toISOString().slice(0, 10) };
}

function buildYtdRange(dataFrom?: string | null, dataTo?: string | null) {
  if (!dataTo) return rangeYtd();
  const endBound = new Date(dataTo);
  const ytdStart = new Date(endBound.getFullYear(), 0, 1);
  const startBound = dataFrom ? new Date(dataFrom) : ytdStart;
  const effectiveFrom = ytdStart < startBound ? startBound : ytdStart;
  return { from: effectiveFrom.toISOString().slice(0, 10), to: endBound.toISOString().slice(0, 10) };
}

export default function Overview() {
  const { locale, localeTag } = useI18n();

  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [dateFrom, setDateFrom] = useState(rangeFromPastDays(90).from);
  const [dateTo, setDateTo] = useState(rangeFromPastDays(90).to);
  const [granularity, setGranularity] = useState<"daily" | "monthly">("daily");
  const [rangeInitialized, setRangeInitialized] = useState(false);

  const storesQ = useStores();
  const summaryQ = useSystemSummary();

  // Auto-apply full data range on first load
  React.useEffect(() => {
    if (rangeInitialized || !summaryQ.data) return;
    const range = buildRangeFromSummary(summaryQ.data.date_from, summaryQ.data.date_to);
    setDateFrom(range.from);
    setDateTo(range.to);
    setRangeInitialized(true);
  }, [summaryQ.data, rangeInitialized]);

  const invalidRange = dateFrom > dateTo;

  const applyPreset = useCallback((type: "30d" | "90d" | "365d" | "ytd") => {
    const dt = summaryQ.data?.date_to;
    const df = summaryQ.data?.date_from;
    const range = type === "ytd"
      ? buildYtdRange(df, dt)
      : buildTrailingRange(dt, type === "30d" ? 30 : type === "90d" ? 90 : 365);
    setDateFrom(range.from);
    setDateTo(range.to);
  }, [summaryQ.data]);

  const resetFilters = useCallback(() => {
    const range = buildRangeFromSummary(summaryQ.data?.date_from, summaryQ.data?.date_to);
    setStoreId(undefined);
    setGranularity("daily");
    setDateFrom(range.from);
    setDateTo(range.to);
  }, [summaryQ.data]);

  const kpiQ = useKpiSummary({ date_from: dateFrom, date_to: dateTo, store_id: storeId }, { enabled: !invalidRange });
  const seriesQ = useSalesTimeseries({ granularity, date_from: dateFrom, date_to: dateTo, store_id: storeId }, { enabled: !invalidRange });

  const series = useMemo<OverviewSalesPoint[]>(() => {
    if (!seriesQ.data) return [];
    return Object.values(
      seriesQ.data.reduce<Record<string, OverviewSalesPoint>>((acc, row) => {
        if (!acc[row.date]) acc[row.date] = { date: row.date, sales: 0, customers: 0 };
        acc[row.date].sales += row.sales;
        acc[row.date].customers += row.customers;
        return acc;
      }, {})
    ).sort((a, b) => a.date.localeCompare(b.date));
  }, [seriesQ.data]);

  const insights = useMemo(() => {
    if (series.length === 0) return null;
    const first = series[0].sales;
    const last = series[series.length - 1].sales;
    const peakRow = series.reduce((p, r) => (r.sales > p.sales ? r : p), series[0]);
    const trend = first > 0 ? ((last - first) / first) * 100 : 0;
    const spanDays = Math.max(1, Math.round((new Date(dateTo).getTime() - new Date(dateFrom).getTime()) / 86_400_000) + 1);
    return { peakDate: peakRow.date, peakSales: peakRow.sales, trend, spanDays };
  }, [dateFrom, dateTo, series]);

  const lastUpdated = seriesQ.dataUpdatedAt
    ? new Date(seriesQ.dataUpdatedAt).toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" })
    : "-";

  const isLoading = kpiQ.isLoading || seriesQ.isLoading;
  const error = kpiQ.error || seriesQ.error;

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Executive Overview</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Мониторинг KPI портфеля, диагностика трендов и фильтры по магазинам."
              : "Portfolio KPI tracking, trend diagnostics, and store-level focus filters."}
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Обновлено" : "Updated"}: {lastUpdated}</p>
          <div className="preset-row">
            {(["30d", "90d", "365d", "ytd"] as const).map((p) => (
              <button key={p} className="button ghost" onClick={() => applyPreset(p)} type="button">
                {p === "ytd" ? "YTD" : p === "365d" ? "1Y" : p === "90d" ? "90D" : "30D"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector
            stores={storesQ.data ?? []}
            value={storeId}
            onChange={setStoreId}
            label={locale === "ru" ? "Фокус по магазину" : "Store focus"}
            includeAllOption
            id="overview-store"
          />
          <div className="field">
            <label htmlFor="ov-date-from">{locale === "ru" ? "Дата с" : "Date from"}</label>
            <input id="ov-date-from" className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="ov-date-to">{locale === "ru" ? "Дата по" : "Date to"}</label>
            <input id="ov-date-to" className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="ov-gran">{locale === "ru" ? "Гранулярность" : "Granularity"}</label>
            <select id="ov-gran" className="select" value={granularity} onChange={(e) => setGranularity(e.target.value as "daily" | "monthly")}>
              <option value="daily">{locale === "ru" ? "День" : "Daily"}</option>
              <option value="monthly">{locale === "ru" ? "Месяц" : "Monthly"}</option>
            </select>
          </div>
          <button className="button primary" onClick={() => { kpiQ.refetch(); seriesQ.refetch(); }} disabled={isLoading || invalidRange}>
            {isLoading ? (locale === "ru" ? "Загрузка..." : "Loading...") : locale === "ru" ? "Обновить" : "Refresh"}
          </button>
        </div>
      </div>

      {invalidRange && <p className="error">{locale === "ru" ? "Дата начала не может быть позже даты окончания." : "Date from cannot be greater than Date to."}</p>}
      {error ? <ErrorState message={(error as Error).message} onRetry={() => { kpiQ.refetch(); seriesQ.refetch(); }} /> : null}

      {isLoading && !kpiQ.data && (
        <div className="panel"><LoadingBlock lines={4} className="loading-stack" /></div>
      )}

      {kpiQ.data && (
        <KpiCards
          totalSales={kpiQ.data.total_sales}
          totalCustomers={kpiQ.data.total_customers}
          avgDailySales={kpiQ.data.avg_daily_sales}
          promoDays={kpiQ.data.promo_days}
          openDays={kpiQ.data.open_days}
        />
      )}

      {insights && (
        <div className="insight-grid">
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Период" : "Period Span"}</p>
            <p className="insight-value">{formatInt(insights.spanDays)} {locale === "ru" ? "дней" : "days"}</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Тренд" : "Trend Direction"}</p>
            <p className={`insight-value ${insights.trend >= 0 ? "positive" : "negative"}`}>{formatPercent(insights.trend)}</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Пик продаж" : "Peak Sales Day"}</p>
            <p className="insight-value">{formatInt(insights.peakSales)} {locale === "ru" ? "в" : "on"} {insights.peakDate}</p>
          </div>
        </div>
      )}

      {series.length > 0 ? (
        <SalesChart data={series} title={locale === "ru" ? "Тренд общих продаж" : "Total Sales Trend"} granularity={granularity} />
      ) : (
        !isLoading && (
          <NoDataState
            message={locale === "ru" ? "Нет данных продаж для выбранных фильтров." : "No sales rows for selected filters."}
            filtersLabel={`store=${storeId ?? "all"}, from=${dateFrom}, to=${dateTo}`}
            apiBaseUrl={API_BASE_URL}
            hint={locale === "ru" ? "Подсказка: DEMO=1 bash scripts/dev_up.sh" : "Hint: DEMO=1 bash scripts/dev_up.sh"}
            onReset={resetFilters}
            resetLabel={locale === "ru" ? "Сбросить фильтры" : "Reset filters"}
          />
        )
      )}
    </section>
  );
}
