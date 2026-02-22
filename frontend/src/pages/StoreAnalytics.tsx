import React, { useMemo, useState } from "react";

import { extractApiError } from "../api/client";
import { fetchPromoImpact, fetchSalesTimeseries, fetchStores, PromoImpactPoint, SalesPoint, Store } from "../api/endpoints";
import LoadingBlock from "../components/LoadingBlock";
import SalesChart from "../components/SalesChart";
import StoreSelector from "../components/StoreSelector";
import { rangeFromPastDays } from "../lib/dates";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";
import { useI18n } from "../lib/i18n";

function getDefaultRange() {
  return rangeFromPastDays(60);
}

export default function StoreAnalytics() {
  const { locale, localeTag } = useI18n();
  const defaults = useMemo(() => getDefaultRange(), []);

  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const [granularity, setGranularity] = useState<"daily" | "monthly">("daily");
  const [lastUpdated, setLastUpdated] = useState("-");

  const [series, setSeries] = useState<SalesPoint[]>([]);
  const [promoImpact, setPromoImpact] = useState<PromoImpactPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const invalidRange = dateFrom > dateTo;

  React.useEffect(() => {
    fetchStores()
      .then(setStores)
      .catch((errorResponse) =>
        setError(
          extractApiError(errorResponse, locale === "ru" ? "Не удалось загрузить список магазинов." : "Failed to load stores list.")
        )
      );
  }, []);

  const applyPreset = React.useCallback((days: number) => {
    const range = rangeFromPastDays(days);
    setDateFrom(range.from);
    setDateTo(range.to);
  }, []);

  const load = React.useCallback(async () => {
    if (invalidRange) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const [seriesData, promoData] = await Promise.all([
        fetchSalesTimeseries({
          granularity,
          date_from: dateFrom,
          date_to: dateTo,
          store_id: storeId,
        }),
        fetchPromoImpact(storeId),
      ]);

      setSeries(seriesData);
      setPromoImpact(
        [...promoData].sort((a, b) => {
          if (a.store_id !== b.store_id) {
            return a.store_id - b.store_id;
          }
          return b.avg_sales - a.avg_sales;
        })
      );
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить аналитику магазина. Проверьте соединение с backend." : "Failed to load store analytics. Check backend connectivity."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, granularity, invalidRange, locale, localeTag, storeId]);

  React.useEffect(() => {
    load();
  }, [load]);

  const chartData = series.map((row) => ({
    date: row.date,
    sales: row.sales,
    customers: row.customers,
  }));

  const summary = useMemo(() => {
    if (series.length === 0) {
      return null;
    }

    const totalSales = series.reduce((sum, row) => sum + row.sales, 0);
    const totalCustomers = series.reduce((sum, row) => sum + row.customers, 0);
    const promo = promoImpact.find((row) => row.promo_flag === "promo");
    const noPromo = promoImpact.find((row) => row.promo_flag === "no-promo");
    const uplift = promo && noPromo && noPromo.avg_sales > 0 ? ((promo.avg_sales - noPromo.avg_sales) / noPromo.avg_sales) * 100 : 0;

    return {
      totalSales,
      avgCustomers: totalCustomers / series.length,
      salesPerCustomer: totalCustomers > 0 ? totalSales / totalCustomers : 0,
      uplift,
    };
  }, [promoImpact, series]);

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Store Analytics</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Диагностика спроса по магазинам с учетом эффекта промо и клиентского состава."
              : "Demand behavior diagnostics by store, with promo effect and customer mix context."}
          </p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">{locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}</p>
          <div className="preset-row">
            <button className="button ghost" type="button" onClick={() => applyPreset(30)}>
              30D
            </button>
            <button className="button ghost" type="button" onClick={() => applyPreset(60)}>
              60D
            </button>
            <button className="button ghost" type="button" onClick={() => applyPreset(120)}>
              120D
            </button>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label={locale === "ru" ? "Магазин" : "Store"} includeAllOption id="analytics-store" />
          <div className="field">
            <label htmlFor="store-date-from">{locale === "ru" ? "Дата с" : "Date from"}</label>
            <input
              id="store-date-from"
              className="input"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="store-date-to">{locale === "ru" ? "Дата по" : "Date to"}</label>
            <input
              id="store-date-to"
              className="input"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="store-granularity">{locale === "ru" ? "Гранулярность" : "Granularity"}</label>
            <select
              id="store-granularity"
              className="select"
              value={granularity}
              onChange={(event) => setGranularity(event.target.value as "daily" | "monthly")}
            >
              <option value="daily">{locale === "ru" ? "День" : "Daily"}</option>
              <option value="monthly">{locale === "ru" ? "Месяц" : "Monthly"}</option>
            </select>
          </div>
          <button className="button primary" onClick={load} disabled={loading || invalidRange}>
            {loading ? (locale === "ru" ? "Загрузка..." : "Loading...") : locale === "ru" ? "Обновить" : "Refresh"}
          </button>
        </div>
      </div>

      {invalidRange && <p className="error">{locale === "ru" ? "Дата начала не может быть позже даты окончания." : "Date from cannot be greater than Date to."}</p>}
      {error && <p className="error">{error}</p>}

      {loading && series.length === 0 && (
        <div className="panel">
          <LoadingBlock lines={4} className="loading-stack" />
        </div>
      )}

      {summary && (
        <div className="insight-grid">
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Общие продажи" : "Total Sales"}</p>
            <p className="insight-value">{formatInt(summary.totalSales)}</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Средние клиенты / точка" : "Avg Customers / Point"}</p>
            <p className="insight-value">{formatDecimal(summary.avgCustomers)}</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Продажи на клиента" : "Sales per Customer"}</p>
            <p className="insight-value">{formatDecimal(summary.salesPerCustomer)}</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">{locale === "ru" ? "Прирост от промо" : "Promo Uplift"}</p>
            <p className={`insight-value ${summary.uplift >= 0 ? "positive" : "negative"}`}>{formatPercent(summary.uplift)}</p>
          </div>
        </div>
      )}

      {chartData.length > 0 ? (
        <SalesChart data={chartData} title={locale === "ru" ? "Тренд продаж и клиентов" : "Sales and Customers Trend"} showCustomers granularity={granularity} />
      ) : (
        !loading && <p className="muted">{locale === "ru" ? "Нет наблюдений за выбранный период." : "No daily observations for current filters."}</p>
      )}

      <div className="panel">
        <div className="panel-head">
          <h3>{locale === "ru" ? "Эффект промо" : "Promo Impact"}</h3>
          <p className="panel-subtitle">{locale === "ru" ? "Средние продажи и клиенты в разрезе статуса промо." : "Average sales and customer mix split by promo status."}</p>
        </div>
        {promoImpact.length === 0 ? (
          <p className="muted">{locale === "ru" ? "API не вернул строки по эффекту промо." : "No promo effect rows returned by API."}</p>
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
                    <td>
                      <span className={`badge ${row.promo_flag === "promo" ? "promo" : "no-promo"}`}>
                        {row.promo_flag}
                      </span>
                    </td>
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
