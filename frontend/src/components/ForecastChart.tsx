import React from "react";
import { Area, AreaChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
}: {
  active?: boolean;
  label?: string;
  payload?: TooltipRow[];
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
      <p className="chart-tooltip-line">Predicted: {formatInt(predicted)}</p>
      {typeof lower === "number" && typeof upper === "number" && (
        <p className="chart-tooltip-line">
          Band: {formatInt(lower)} to {formatInt(upper)}
        </p>
      )}
    </div>
  );
}

export default function ForecastChart({ data }: { data: ForecastPoint[] }) {
  const total = data.reduce((acc, row) => acc + row.predicted_sales, 0);

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Forecast Horizon</h3>
        <p className="panel-subtitle">{formatCompact(total)} projected across selected horizon</p>
      </div>
      <div style={{ width: "100%", height: 360 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="intervalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0f7661" stopOpacity={0.24} />
                <stop offset="100%" stopColor="#0f7661" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfe9e4" />
            <XAxis dataKey="date" minTickGap={26} stroke="#53736a" tickFormatter={formatDateLabel} />
            <YAxis stroke="#53736a" tickFormatter={(value) => formatCompact(Number(value))} />
            <Tooltip
              content={<ForecastTooltip />}
              wrapperStyle={{ outline: "none" }}
            />
            <Legend />
            <Area type="monotone" dataKey="predicted_sales" stroke="none" fill="url(#intervalGradient)" isAnimationActive />
            <Line
              type="monotone"
              dataKey="predicted_sales"
              stroke="#0b5f4f"
              strokeWidth={2.6}
              dot={false}
              activeDot={{ r: 4 }}
              name="Predicted sales"
            />
            <Line
              type="monotone"
              dataKey="predicted_lower"
              stroke="#3a8f7b"
              strokeWidth={1.6}
              strokeDasharray="5 4"
              dot={false}
              name="Lower interval"
            />
            <Line
              type="monotone"
              dataKey="predicted_upper"
              stroke="#3a8f7b"
              strokeWidth={1.6}
              strokeDasharray="5 4"
              dot={false}
              name="Upper interval"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
