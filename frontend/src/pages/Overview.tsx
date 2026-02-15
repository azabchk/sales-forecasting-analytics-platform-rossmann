import React, { useCallback, useMemo, useState } from "react";

import { fetchKpiSummary, fetchSalesTimeseries, KpiSummary } from "../api/endpoints";
import KpiCards from "../components/KpiCards";
import SalesChart from "../components/SalesChart";

type OverviewSalesPoint = {
  date: string;
  sales: number;
};

function getDefaultRange() {
  const dateTo = new Date();
  const dateFrom = new Date();
  dateFrom.setMonth(dateFrom.getMonth() - 3);

  return {
    from: dateFrom.toISOString().slice(0, 10),
    to: dateTo.toISOString().slice(0, 10),
  };
}

export default function Overview() {
  const defaults = useMemo(() => getDefaultRange(), []);

  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const [granularity, setGranularity] = useState<"daily" | "monthly">("daily");

  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [series, setSeries] = useState<OverviewSalesPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [kpiResp, seriesResp] = await Promise.all([
        fetchKpiSummary({ date_from: dateFrom, date_to: dateTo }),
        fetchSalesTimeseries({
          granularity,
          date_from: dateFrom,
          date_to: dateTo,
        }),
      ]);

      const grouped = Object.values(
        seriesResp.reduce<Record<string, OverviewSalesPoint>>((acc, row) => {
          if (!acc[row.date]) {
            acc[row.date] = { date: row.date, sales: 0 };
          }
          acc[row.date].sales += row.sales;
          return acc;
        }, {})
      ).sort((a, b) => a.date.localeCompare(b.date));

      setKpi(kpiResp);
      setSeries(grouped);
    } catch {
      setError("Failed to load overview metrics. Ensure backend is running and date range is valid.");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, granularity]);

  React.useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Executive Overview</h2>
          <p className="page-note">Portfolio KPI tracking with configurable time granularity.</p>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
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
          <button className="button primary" onClick={load} disabled={loading || dateFrom > dateTo}>
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {dateFrom > dateTo && <p className="error">Date from cannot be greater than Date to.</p>}
      {error && <p className="error">{error}</p>}

      {kpi && <KpiCards totalSales={kpi.total_sales} totalCustomers={kpi.total_customers} avgDailySales={kpi.avg_daily_sales} promoDays={kpi.promo_days} />}

      {series.length > 0 ? (
        <SalesChart data={series} title="Total Sales Trend" />
      ) : (
        !loading && <p className="muted">No sales rows for selected filters.</p>
      )}
    </section>
  );
}
