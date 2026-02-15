import React from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type ForecastPoint = {
  date: string;
  predicted_sales: number;
};

export default function ForecastChart({ data }: { data: ForecastPoint[] }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #dbe3f5", borderRadius: 12, padding: 12 }}>
      <h3 style={{ margin: "0 0 12px 0" }}>Прогноз продаж</h3>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={data}>
            <XAxis dataKey="date" minTickGap={28} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="predicted_sales" stroke="#0b7f5f" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
