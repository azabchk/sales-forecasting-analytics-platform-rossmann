import React, { useEffect, useMemo, useState } from "react";

import KpiCards from "../components/KpiCards";
import SalesChart from "../components/SalesChart";
import { fetchKpiSummary, fetchSalesTimeseries, KpiSummary } from "../api/endpoints";

type OverviewSalesPoint = {
  date: string;
  sales: number;
};

function getDefaultRange() {
  const dateTo = new Date();
  const dateFrom = new Date();
  dateFrom.setMonth(dateFrom.getMonth() - 3);

  const to = dateTo.toISOString().slice(0, 10);
  const from = dateFrom.toISOString().slice(0, 10);
  return { from, to };
}

export default function Overview() {
  const range = useMemo(() => getDefaultRange(), []);
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [series, setSeries] = useState<OverviewSalesPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [kpiResp, seriesResp] = await Promise.all([
          fetchKpiSummary({ date_from: range.from, date_to: range.to }),
          fetchSalesTimeseries({
            granularity: "daily",
            date_from: range.from,
            date_to: range.to
          })
        ]);
        const grouped = Object.values(
          seriesResp.reduce<Record<string, OverviewSalesPoint>>((acc, row) => {
            if (!acc[row.date]) {
              acc[row.date] = { date: row.date, sales: 0 };
            }
            acc[row.date].sales += row.sales;
            return acc;
          }, {})
        );

        setKpi(kpiResp);
        setSeries(grouped);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [range.from, range.to]);

  if (loading) {
    return <p>Загрузка...</p>;
  }

  if (!kpi) {
    return <p>Нет данных.</p>;
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h2>Overview</h2>
      <KpiCards
        totalSales={kpi.total_sales}
        totalCustomers={kpi.total_customers}
        avgDailySales={kpi.avg_daily_sales}
        promoDays={kpi.promo_days}
      />
      <SalesChart data={series} title="Динамика продаж (все магазины)" />
    </div>
  );
}
