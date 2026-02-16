import React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ModelFeatureImportanceItem } from "../api/endpoints";
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
}: {
  active?: boolean;
  label?: string;
  payload?: TooltipEntry[];
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{label}</p>
      <p className="chart-tooltip-line">Importance: {formatDecimal(payload[0].value)}</p>
    </div>
  );
}

export default function ImportanceChart({ data }: ImportanceChartProps) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Top Feature Importance</h3>
        <p className="panel-subtitle">Model explanation for decision drivers.</p>
      </div>
      <div style={{ width: "100%", height: 360 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dce8e3" />
            <XAxis
              dataKey="feature"
              stroke="#53736a"
              interval={0}
              angle={-24}
              textAnchor="end"
              height={88}
              tick={{ fontSize: 11 }}
            />
            <YAxis stroke="#53736a" tickFormatter={(value) => Number(value).toFixed(2)} />
            <Tooltip content={<ImportanceTooltip />} />
            <Bar dataKey="importance" name="Importance" fill="#0a7e64" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

