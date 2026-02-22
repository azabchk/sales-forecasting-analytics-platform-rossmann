import React from "react";

import { useI18n } from "../lib/i18n";
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
  const { locale } = useI18n();
  const salesPerCustomer = props.totalCustomers > 0 ? props.totalSales / props.totalCustomers : 0;
  const promoShare = props.openDays > 0 ? (props.promoDays / props.openDays) * 100 : 0;

  return (
    <div className="kpi-grid">
      <MetricCard
        title={locale === "ru" ? "Общие продажи" : "Total Sales"}
        value={formatCompact(props.totalSales)}
        hint={locale === "ru" ? `${formatInt(props.totalSales)} валовые` : `${formatInt(props.totalSales)} gross`}
        accent="teal"
      />
      <MetricCard
        title={locale === "ru" ? "Клиенты" : "Customers"}
        value={formatCompact(props.totalCustomers)}
        hint={locale === "ru" ? `${formatInt(props.totalCustomers)} транзакций` : `${formatInt(props.totalCustomers)} transactions`}
        accent="slate"
      />
      <MetricCard
        title={locale === "ru" ? "Средние дневные продажи" : "Avg Daily Sales"}
        value={formatDecimal(props.avgDailySales)}
        hint={locale === "ru" ? `За ${formatInt(props.openDays)} открытых дней` : `Across ${formatInt(props.openDays)} open days`}
        accent="teal"
      />
      <MetricCard
        title={locale === "ru" ? "Промо-дни" : "Promo Days"}
        value={formatInt(props.promoDays)}
        hint={locale === "ru" ? `${promoShare.toFixed(1)}% открытых дней` : `${promoShare.toFixed(1)}% of open days`}
        accent="gold"
      />
      <MetricCard
        title={locale === "ru" ? "Продажи на клиента" : "Sales per Customer"}
        value={formatDecimal(salesPerCustomer)}
        hint={locale === "ru" ? "Прокси среднего чека" : "Average basket value proxy"}
        accent="slate"
      />
    </div>
  );
}
