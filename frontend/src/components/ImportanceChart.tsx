import React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ModelFeatureImportanceItem } from "../api/endpoints";
import { useI18n } from "../lib/i18n";
import { formatDecimal } from "../lib/format";

type ImportanceChartProps = {
  data: ModelFeatureImportanceItem[];
};

type TooltipEntry = {
  value: number;
};

function ImportanceTooltip({
  active,
  label,
  payload,
  locale,
}: {
  active?: boolean;
  label?: string;
  payload?: TooltipEntry[];
  locale: "en" | "ru";
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{label}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "Важность" : "Importance"}: {formatDecimal(payload[0].value)}</p>
    </div>
  );
}

export default function ImportanceChart({ data }: ImportanceChartProps) {
  const { locale } = useI18n();
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{locale === "ru" ? "Топ важности признаков" : "Top Feature Importance"}</h3>
        <p className="panel-subtitle">{locale === "ru" ? "Объяснение ключевых факторов модели." : "Model explanation for decision drivers."}</p>
      </div>
      <div style={{ width: "100%", height: 360 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis
              dataKey="feature"
              stroke="var(--chart-axis)"
              interval={0}
              angle={-24}
              textAnchor="end"
              height={88}
              tick={{ fontSize: 11 }}
            />
            <YAxis stroke="var(--chart-axis)" tickFormatter={(value) => Number(value).toFixed(2)} />
            <Tooltip content={<ImportanceTooltip locale={locale} />} />
            <Bar dataKey="importance" name={locale === "ru" ? "Важность" : "Importance"} fill="var(--chart-primary)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
