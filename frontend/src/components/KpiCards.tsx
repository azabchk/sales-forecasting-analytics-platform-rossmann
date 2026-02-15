import React from "react";

type MetricCardProps = {
  title: string;
  value: string;
};

function MetricCard({ title, value }: MetricCardProps) {
  return (
    <div className="kpi-card">
      <p className="kpi-title">{title}</p>
      <p className="kpi-value">{value}</p>
    </div>
  );
}

export default function KpiCards(props: {
  totalSales: number;
  totalCustomers: number;
  avgDailySales: number;
  promoDays: number;
}) {
  return (
    <div className="kpi-grid">
      <MetricCard title="Total Sales" value={props.totalSales.toLocaleString("en-US", { maximumFractionDigits: 0 })} />
      <MetricCard title="Customers" value={props.totalCustomers.toLocaleString("en-US", { maximumFractionDigits: 0 })} />
      <MetricCard title="Avg Daily Sales" value={props.avgDailySales.toLocaleString("en-US", { maximumFractionDigits: 2 })} />
      <MetricCard title="Promo Days" value={props.promoDays.toLocaleString("en-US")} />
    </div>
  );
}
