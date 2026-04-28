import React, { useMemo, useState } from "react";

import { API_BASE_URL } from "../api/client";
import LoadingBlock from "../components/LoadingBlock";
import SalesChart from "../components/SalesChart";
import StoreSelector from "../components/StoreSelector";
import { ErrorState, NoDataState } from "../components/ui/States";
import { usePromoImpact, useSalesTimeseries, useStores, useSystemSummary } from "../hooks/useApiQuery";
import { rangeFromPastDays } from "../lib/dates";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";
import { useI18n } from "../lib/i18n";

function buildTrailingRange(dataTo: string | null | undefined, days: number) {
  const end = dataTo ? new Date(dataTo) : new Date();
  const from = new Date(end);
  from.setDate(from.getDate() - (days - 1));
  return { from: from.toISOString().slice(0, 10), to: end.toISOString().slice(0, 10) };
}

export default function StoreAnalytics() {
  const { locale, localeTag } = useI18n();

  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [dateFrom, setDateFrom] = useState(rangeFromPastDays(60).from);
  const [dateTo, setDateTo] = useState(rangeFromPastDays(60).to);
  const [granularity, setGranularity] = useState<"daily" | "monthly">("daily");
  const [rangeInitialized, setRangeInitialized] = useState(false);

  const storesQ = useStores();
  const summaryQ = useSystemSummary();

  React.useEffect(() => {
    if (rangeInitialized || !summaryQ.data?.date_from) return;
    setDateFrom(summaryQ.data.date_from);
    setDateTo(summaryQ.data.date_to ?? dateTo);
    setRangeInitialized(true);
  }, [summaryQ.data, rangeInitialized]);

  const invalidRange = dateFrom > dateTo;

  const applyPreset = React.useCallback((days: number) => {
    const r = buildTrailingRange(summaryQ.data?.date_to, days);
    setDateFrom(r.from); setDateTo(r.to);
  }, [summaryQ.data]);

  const resetFilters = React.useCallback(() => {
    if (summaryQ.data?.date_from) { setDateFrom(summaryQ.data.date_from); setDateTo(summaryQ.data.date_to ?? dateTo); }
    setStoreId(undefined); setGranularity("daily");
  }, [summaryQ.data]);

  const seriesQ = useSalesTimeseries({ granularity, date_from: dateFrom, date_to: dateTo, store_id: storeId }, { enabled: !invalidRange });
  const promoQ = usePromoImpact(storeId);

  const chartData = useMemo(() => (seriesQ.data ?? []).map((r) => ({ date: r.date, sales: r.sales, customers: r.customers })), [seriesQ.data]);

  const promoImpact = useMemo(
    () => [...(promoQ.data ?? [])].sort((a, b) => a.store_id !== b.store_id ? a.store_id - b.store_id : b.avg_sales - a.avg_sales),
    [promoQ.data]
  );

  const summary = useMemo(() => {
    const series = seriesQ.data;
    if (!series || series.length === 0) return null;
    const totalSales = series.reduce((s, r) => s + r.sales, 0);
    const totalCustomers = series.reduce((s, r) => s + r.customers, 0);
    const promo = promoImpact.find((r) => r.promo_flag === "promo");
    const noPromo = promoImpact.find((r) => r.promo_flag === "no_promo" || r.promo_flag === "no-promo");
    const uplift = promo && noPromo && noPromo.avg_sales > 0 ? ((promo.avg_sales - noPromo.avg_sales) / noPromo.avg_sales) * 100 : 0;
    return { totalSales, avgCustomers: totalCustomers / series.length, salesPerCustomer: totalCustomers > 0 ? totalSales / totalCustomers : 0, uplift };
  }, [seriesQ.data, promoImpact]);

  const isLoading = seriesQ.isLoading;
  const lastUpdated = seriesQ.dataUpdatedAt
    ? new Date(seriesQ.dataUpdatedAt).toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" })
    : "-";

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Store Analytics</h2>
          <p className="page-note">
            {locale === "ru" ? "Диагностика спроса по магазинам с учетом эффекта промо." : "Demand behavior diagnostics by store with promo effect context."}
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Обновлено" : "Updated"}: {lastUpdated}</p>
          <div className="preset-row">
            {[30, 60, 120].map((d) => (
              <button key={d} className="button ghost" type="button" onClick={() => applyPreset(d)}>{d}D</button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={storesQ.data ?? []} value={storeId} onChange={setStoreId} label={locale === "ru" ? "Магазин" : "Store"} includeAllOption id="analytics-store" />
          <div className="field">
            <label htmlFor="sa-from">{locale === "ru" ? "Дата с" : "Date from"}</label>
            <input id="sa-from" className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="sa-to">{locale === "ru" ? "Дата по" : "Date to"}</label>
            <input id="sa-to" className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="sa-gran">{locale === "ru" ? "Гранулярность" : "Granularity"}</label>
            <select id="sa-gran" className="select" value={granularity} onChange={(e) => setGranularity(e.target.value as "daily" | "monthly")}>
              <option value="daily">{locale === "ru" ? "День" : "Daily"}</option>
              <option value="monthly">{locale === "ru" ? "Месяц" : "Monthly"}</option>
            </select>
          </div>
          <button className="button primary" onClick={() => { seriesQ.refetch(); promoQ.refetch(); }} disabled={isLoading || invalidRange}>
            {isLoading ? (locale === "ru" ? "Загрузка..." : "Loading...") : locale === "ru" ? "Обновить" : "Refresh"}
          </button>
        </div>
      </div>

      {invalidRange && <p className="error">{locale === "ru" ? "Дата начала не может быть позже даты окончания." : "Date from cannot be greater than Date to."}</p>}
      {seriesQ.error ? <ErrorState message={(seriesQ.error as Error).message} onRetry={() => seriesQ.refetch()} /> : null}

      {isLoading && !chartData.length && <div className="panel"><LoadingBlock lines={4} className="loading-stack" /></div>}

      {summary && (
        <div className="insight-grid">
          <div className="insight-card"><p className="insight-label">{locale === "ru" ? "Общие продажи" : "Total Sales"}</p><p className="insight-value">{formatInt(summary.totalSales)}</p></div>
          <div className="insight-card"><p className="insight-label">{locale === "ru" ? "Средние клиенты" : "Avg Customers"}</p><p className="insight-value">{formatDecimal(summary.avgCustomers)}</p></div>
          <div className="insight-card"><p className="insight-label">{locale === "ru" ? "Продажи на клиента" : "Sales per Customer"}</p><p className="insight-value">{formatDecimal(summary.salesPerCustomer)}</p></div>
          <div className="insight-card"><p className="insight-label">{locale === "ru" ? "Прирост от промо" : "Promo Uplift"}</p><p className={`insight-value ${summary.uplift >= 0 ? "positive" : "negative"}`}>{formatPercent(summary.uplift)}</p></div>
        </div>
      )}

      {chartData.length > 0 ? (
        <SalesChart data={chartData} title={locale === "ru" ? "Тренд продаж и клиентов" : "Sales and Customers Trend"} showCustomers granularity={granularity} />
      ) : (
        !isLoading && (
          <NoDataState
            message={locale === "ru" ? "Нет наблюдений за выбранный период." : "No daily observations for current filters."}
            filtersLabel={`store=${storeId ?? "all"}, from=${dateFrom}, to=${dateTo}`}
            apiBaseUrl={API_BASE_URL}
            hint="DEMO=1 bash scripts/dev_up.sh"
            onReset={resetFilters}
            resetLabel={locale === "ru" ? "Сбросить фильтры" : "Reset filters"}
          />
        )
      )}

      <div className="panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Эффект промо" : "Promo Impact"}</h3>
          <p className="panel-subtitle">{locale === "ru" ? "Средние продажи в разрезе статуса промо." : "Average sales split by promo status."}</p>
        </div>
        {promoImpact.length === 0 ? (
          <p className="muted">{locale === "ru" ? "Нет данных по эффекту промо." : "No promo effect data."}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{locale === "ru" ? "Магазин" : "Store"}</th>
                  <th>{locale === "ru" ? "Статус промо" : "Promo Status"}</th>
                  <th>{locale === "ru" ? "Средние продажи" : "Avg Sales"}</th>
                  <th>{locale === "ru" ? "Средние клиенты" : "Avg Customers"}</th>
                  <th>{locale === "ru" ? "Дни" : "Days"}</th>
                </tr>
              </thead>
              <tbody>
                {promoImpact.map((row) => (
                  <tr key={`${row.store_id}-${row.promo_flag}`}>
                    <td>{row.store_id}</td>
                    <td><span className={`badge ${row.promo_flag === "promo" ? "promo" : "no-promo"}`}>{row.promo_flag}</span></td>
                    <td>{row.avg_sales.toLocaleString(localeTag, { maximumFractionDigits: 2 })}</td>
                    <td>{row.avg_customers.toLocaleString(localeTag, { maximumFractionDigits: 2 })}</td>
                    <td>{row.num_days.toLocaleString(localeTag)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
