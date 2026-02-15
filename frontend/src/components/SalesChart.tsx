import React from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type SalesPoint = {
  date: string;
  sales: number;
};

export default function SalesChart({ data, title }: { data: SalesPoint[]; title: string }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #dbe3f5", borderRadius: 12, padding: 12 }}>
      <h3 style={{ margin: "0 0 12px 0" }}>{title}</h3>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={data}>
            <XAxis dataKey="date" minTickGap={28} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="sales" stroke="#1f6feb" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
