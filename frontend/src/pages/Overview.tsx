import React, { useCallback, useMemo, useState } from "react";

import { extractApiError } from "../api/client";
import { fetchKpiSummary, fetchSalesTimeseries, fetchStores, KpiSummary, Store } from "../api/endpoints";
import KpiCards from "../components/KpiCards";
import LoadingBlock from "../components/LoadingBlock";
import SalesChart from "../components/SalesChart";
import StoreSelector from "../components/StoreSelector";
import { rangeFromPastDays, rangeYtd } from "../lib/dates";
import { formatInt, formatPercent } from "../lib/format";

type OverviewSalesPoint = {
  date: string;
  sales: number;
  customers: number;
};

function getDefaultRange() {
  return rangeFromPastDays(90);
}

export default function Overview() {
  const defaults = useMemo(() => getDefaultRange(), []);

  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const [granularity, setGranularity] = useState<"daily" | "monthly">("daily");
  const [lastUpdated, setLastUpdated] = useState<string>("-");

  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [series, setSeries] = useState<OverviewSalesPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [storesError, setStoresError] = useState("");

  React.useEffect(() => {
    fetchStores()
      .then(setStores)
      .catch((errorResponse) => setStoresError(extractApiError(errorResponse, "Failed to load stores list.")));
  }, []);

  const invalidRange = dateFrom > dateTo;

  const applyPreset = useCallback((type: "30d" | "90d" | "365d" | "ytd") => {
    const range = type === "ytd" ? rangeYtd() : rangeFromPastDays(type === "30d" ? 30 : type === "90d" ? 90 : 365);
    setDateFrom(range.from);
    setDateTo(range.to);
  }, []);

  const load = useCallback(async () => {
    if (invalidRange) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const [kpiResp, seriesResp] = await Promise.all([
        fetchKpiSummary({ date_from: dateFrom, date_to: dateTo, store_id: storeId }),
        fetchSalesTimeseries({
          granularity,
          date_from: dateFrom,
          date_to: dateTo,
          store_id: storeId,
        }),
      ]);

      const grouped = Object.values(
        seriesResp.reduce<Record<string, OverviewSalesPoint>>((acc, row) => {
          if (!acc[row.date]) {
            acc[row.date] = { date: row.date, sales: 0, customers: 0 };
          }
          acc[row.date].sales += row.sales;
          acc[row.date].customers += row.customers;
          return acc;
        }, {})
      ).sort((a, b) => a.date.localeCompare(b.date));

      setKpi(kpiResp);
      setSeries(grouped);
      setLastUpdated(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(extractApiError(errorResponse, "Failed to load overview metrics. Ensure backend is running and date range is valid."));
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, granularity, invalidRange, storeId]);

  React.useEffect(() => {
    load();
  }, [load]);

  const insights = useMemo(() => {
    if (series.length === 0) {
      return null;
    }

    const first = series[0].sales;
    const last = series[series.length - 1].sales;
    const peakRow = series.reduce((peak, row) => (row.sales > peak.sales ? row : peak), series[0]);
    const trend = first > 0 ? ((last - first) / first) * 100 : 0;
    const spanDays = Math.max(1, Math.round((new Date(dateTo).getTime() - new Date(dateFrom).getTime()) / 86_400_000) + 1);

    return {
      peakDate: peakRow.date,
      peakSales: peakRow.sales,
      trend,
      spanDays,
    };
  }, [dateFrom, dateTo, series]);

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Executive Overview</h2>
          <p className="page-note">Portfolio KPI tracking, trend diagnostics, and store-level focus filters.</p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">Last update: {lastUpdated}</p>
          <div className="preset-row">
            <button className="button ghost" onClick={() => applyPreset("30d")} type="button">
              30D
            </button>
            <button className="button ghost" onClick={() => applyPreset("90d")} type="button">
              90D
            </button>
            <button className="button ghost" onClick={() => applyPreset("365d")} type="button">
              1Y
            </button>
            <button className="button ghost" onClick={() => applyPreset("ytd")} type="button">
              YTD
            </button>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label="Store focus" includeAllOption id="overview-store" />
          <div className="field">
            <label htmlFor="overview-date-from">Date from</label>
            <input
              id="overview-date-from"
              className="input"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="overview-date-to">Date to</label>
            <input
              id="overview-date-to"
              className="input"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="overview-granularity">Granularity</label>
            <select
              id="overview-granularity"
              className="select"
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as "daily" | "monthly")}
            >
              <option value="daily">Daily</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <button className="button primary" onClick={load} disabled={loading || invalidRange}>
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {storesError && <p className="error">{storesError}</p>}
      {invalidRange && <p className="error">Date from cannot be greater than Date to.</p>}
      {error && <p className="error">{error}</p>}

      {loading && !kpi && (
        <div className="panel">
          <LoadingBlock lines={4} className="loading-stack" />
        </div>
      )}

      {kpi && (
        <KpiCards
          totalSales={kpi.total_sales}
          totalCustomers={kpi.total_customers}
          avgDailySales={kpi.avg_daily_sales}
          promoDays={kpi.promo_days}
          openDays={kpi.open_days}
        />
      )}

      {insights && (
        <div className="insight-grid">
          <div className="insight-card">
            <p className="insight-label">Period Span</p>
            <p className="insight-value">{formatInt(insights.spanDays)} days</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">Trend Direction</p>
            <p className={`insight-value ${insights.trend >= 0 ? "positive" : "negative"}`}>{formatPercent(insights.trend)}</p>
          </div>
          <div className="insight-card">
            <p className="insight-label">Peak Sales Day</p>
            <p className="insight-value">
              {formatInt(insights.peakSales)} on {insights.peakDate}
            </p>
          </div>
        </div>
      )}

      {series.length > 0 ? (
        <SalesChart data={series} title="Total Sales Trend" granularity={granularity} />
      ) : (
        !loading && <p className="muted">No sales rows for selected filters.</p>
      )}
    </section>
  );
}
