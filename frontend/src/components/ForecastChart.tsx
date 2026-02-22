import React from "react";
import { Area, AreaChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useI18n } from "../lib/i18n";
import { formatCompact, formatDateLabel, formatInt } from "../lib/format";

type ForecastPoint = {
  date: string;
  predicted_sales: number;
  predicted_lower?: number | null;
  predicted_upper?: number | null;
};

type TooltipRow = {
  dataKey: string;
  value: number;
};

function ForecastTooltip({
  active,
  label,
  payload,
  locale,
}: {
  active?: boolean;
  label?: string;
  payload?: TooltipRow[];
  locale: "en" | "ru";
}) {
  if (!active || !payload || !label) {
    return null;
  }

  const predicted = payload.find((entry) => entry.dataKey === "predicted_sales")?.value ?? 0;
  const lower = payload.find((entry) => entry.dataKey === "predicted_lower")?.value;
  const upper = payload.find((entry) => entry.dataKey === "predicted_upper")?.value;

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{formatDateLabel(label)}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "Прогноз" : "Predicted"}: {formatInt(predicted)}</p>
      {typeof lower === "number" && typeof upper === "number" && (
        <p className="chart-tooltip-line">
          {locale === "ru" ? "Диапазон" : "Band"}: {formatInt(lower)} {locale === "ru" ? "до" : "to"} {formatInt(upper)}
        </p>
      )}
    </div>
  );
}

export default function ForecastChart({ data }: { data: ForecastPoint[] }) {
  const { locale } = useI18n();
  const total = data.reduce((acc, row) => acc + row.predicted_sales, 0);

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{locale === "ru" ? "Горизонт прогноза" : "Forecast Horizon"}</h3>
        <p className="panel-subtitle">
          {formatCompact(total)} {locale === "ru" ? "прогноз на выбранном горизонте" : "projected across selected horizon"}
        </p>
      </div>
      <div style={{ width: "100%", height: 360 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="intervalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-primary)" stopOpacity={0.24} />
                <stop offset="100%" stopColor="var(--chart-primary)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis dataKey="date" minTickGap={26} stroke="var(--chart-axis)" tickFormatter={formatDateLabel} />
            <YAxis stroke="var(--chart-axis)" tickFormatter={(value) => formatCompact(Number(value))} />
            <Tooltip
              content={<ForecastTooltip locale={locale} />}
              wrapperStyle={{ outline: "none" }}
            />
            <Legend />
            <Area type="monotone" dataKey="predicted_sales" stroke="none" fill="url(#intervalGradient)" isAnimationActive />
            <Line
              type="monotone"
              dataKey="predicted_sales"
              stroke="var(--chart-primary)"
              strokeWidth={2.6}
              dot={false}
              activeDot={{ r: 4 }}
              name={locale === "ru" ? "Прогноз продаж" : "Predicted sales"}
            />
            <Line
              type="monotone"
              dataKey="predicted_lower"
              stroke="var(--chart-tertiary)"
              strokeWidth={1.6}
              strokeDasharray="5 4"
              dot={false}
              name={locale === "ru" ? "Нижний интервал" : "Lower interval"}
            />
            <Line
              type="monotone"
              dataKey="predicted_upper"
              stroke="var(--chart-tertiary)"
              strokeWidth={1.6}
              strokeDasharray="5 4"
              dot={false}
              name={locale === "ru" ? "Верхний интервал" : "Upper interval"}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
