import React from "react";
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type ForecastPoint = {
  date: string;
  predicted_sales: number;
  predicted_lower?: number | null;
  predicted_upper?: number | null;
};

export default function ForecastChart({ data }: { data: ForecastPoint[] }) {
  return (
    <div className="panel">
      <h3>Forecast Horizon</h3>
      <div style={{ width: "100%", height: 340 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="intervalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0f7661" stopOpacity={0.24} />
                <stop offset="100%" stopColor="#0f7661" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfe9e4" />
            <XAxis dataKey="date" minTickGap={26} stroke="#6a7c74" />
            <YAxis stroke="#6a7c74" />
            <Tooltip
              contentStyle={{
                borderRadius: 10,
                border: "1px solid #cfe0d8",
                boxShadow: "0 8px 22px rgba(16, 58, 46, 0.12)",
              }}
            />
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
