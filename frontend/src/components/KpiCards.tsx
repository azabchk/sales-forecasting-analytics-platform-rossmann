import React from "react";

import { formatCompact, formatDecimal, formatInt } from "../lib/format";

type MetricCardProps = {
  title: string;
  value: string;
  hint: string;
  accent: "teal" | "slate" | "gold";
};

function MetricCard({ title, value, hint, accent }: MetricCardProps) {
  return (
    <div className={`kpi-card ${accent}`}>
      <p className="kpi-title">{title}</p>
      <p className="kpi-value">{value}</p>
      <p className="kpi-hint">{hint}</p>
    </div>
  );
}

export default function KpiCards(props: {
  totalSales: number;
  totalCustomers: number;
  avgDailySales: number;
  promoDays: number;
  openDays: number;
}) {
  const salesPerCustomer = props.totalCustomers > 0 ? props.totalSales / props.totalCustomers : 0;
  const promoShare = props.openDays > 0 ? (props.promoDays / props.openDays) * 100 : 0;

  return (
    <div className="kpi-grid">
      <MetricCard title="Total Sales" value={formatCompact(props.totalSales)} hint={`${formatInt(props.totalSales)} gross`} accent="teal" />
      <MetricCard title="Customers" value={formatCompact(props.totalCustomers)} hint={`${formatInt(props.totalCustomers)} transactions`} accent="slate" />
      <MetricCard title="Avg Daily Sales" value={formatDecimal(props.avgDailySales)} hint={`Across ${formatInt(props.openDays)} open days`} accent="teal" />
      <MetricCard title="Promo Days" value={formatInt(props.promoDays)} hint={`${promoShare.toFixed(1)}% of open days`} accent="gold" />
      <MetricCard title="Sales per Customer" value={formatDecimal(salesPerCustomer)} hint="Average basket value proxy" accent="slate" />
    </div>
  );
}
