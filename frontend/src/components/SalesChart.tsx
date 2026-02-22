import React from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCompact, formatDateLabel, formatInt, formatMonthLabel } from "../lib/format";
import { useI18n } from "../lib/i18n";

type SalesPoint = {
  date: string;
  sales: number;
  customers?: number;
};

type SalesChartProps = {
  data: SalesPoint[];
  title: string;
  showCustomers?: boolean;
  granularity?: "daily" | "monthly";
};

type TooltipRow = {
  color: string;
  dataKey: string;
  value: number;
};

function salesTickFormatter(value: string, granularity: "daily" | "monthly") {
  return granularity === "monthly" ? formatMonthLabel(value) : formatDateLabel(value);
}

function ChartTooltip({
  active,
  payload,
  label,
  granularity,
  locale,
}: {
  active?: boolean;
  payload?: TooltipRow[];
  label?: string;
  granularity: "daily" | "monthly";
  locale: "en" | "ru";
}) {
  if (!active || !payload || payload.length === 0 || !label) {
    return null;
  }

  const sales = payload.find((item) => item.dataKey === "sales")?.value ?? 0;
  const customers = payload.find((item) => item.dataKey === "customers")?.value;

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{salesTickFormatter(label, granularity)}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "Продажи" : "Sales"}: {formatInt(sales)}</p>
      {typeof customers === "number" && <p className="chart-tooltip-line">{locale === "ru" ? "Клиенты" : "Customers"}: {formatInt(customers)}</p>}
    </div>
  );
}

export default function SalesChart({
  data,
  title,
  showCustomers = false,
  granularity = "daily",
}: SalesChartProps) {
  const { locale } = useI18n();
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <p className="panel-subtitle">
          {formatCompact(data.reduce((total, row) => total + row.sales, 0))}{" "}
          {locale === "ru" ? "сумма продаж в текущем окне" : "total sales in view"}
        </p>
      </div>
      <div style={{ width: "100%", height: 360 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="salesAreaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-primary)" stopOpacity={0.28} />
                <stop offset="100%" stopColor="var(--chart-primary)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis
              dataKey="date"
              minTickGap={30}
              stroke="var(--chart-axis)"
              tickFormatter={(value) => salesTickFormatter(value, granularity)}
            />
            <YAxis yAxisId="sales" stroke="var(--chart-axis)" tickFormatter={(value) => formatCompact(Number(value))} />
            {showCustomers && (
              <YAxis
                yAxisId="customers"
                orientation="right"
                stroke="var(--chart-axis)"
                tickFormatter={(value) => formatCompact(Number(value))}
              />
            )}
            <Tooltip
              content={<ChartTooltip granularity={granularity} locale={locale} />}
              wrapperStyle={{ outline: "none" }}
            />
            <Legend />
            <Area
              yAxisId="sales"
              type="monotone"
              dataKey="sales"
              stroke="none"
              fill="url(#salesAreaGradient)"
              name={locale === "ru" ? "Продажи (область)" : "Sales (area)"}
              fillOpacity={1}
              legendType="none"
            />
            <Line
              yAxisId="sales"
              type="monotone"
              dataKey="sales"
              name={locale === "ru" ? "Продажи" : "Sales"}
              stroke="var(--chart-primary)"
              strokeWidth={2.4}
              dot={false}
              activeDot={{ r: 4 }}
            />
            {showCustomers && (
              <Line
                yAxisId="customers"
                type="monotone"
                dataKey="customers"
                name={locale === "ru" ? "Клиенты" : "Customers"}
                stroke="var(--chart-secondary)"
                strokeWidth={1.8}
                dot={false}
                strokeDasharray="4 3"
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
