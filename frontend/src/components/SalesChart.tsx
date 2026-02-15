import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type SalesPoint = {
  date: string;
  sales: number;
  customers?: number;
};

type SalesChartProps = {
  data: SalesPoint[];
  title: string;
  showCustomers?: boolean;
};

export default function SalesChart({ data, title, showCustomers = false }: SalesChartProps) {
  return (
    <div className="panel">
      <h3>{title}</h3>
      <div style={{ width: "100%", height: 340 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
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
            <Legend />
            <Line
              type="monotone"
              dataKey="sales"
              name="Sales"
              stroke="#0f7661"
              strokeWidth={2.4}
              dot={false}
              activeDot={{ r: 4 }}
            />
            {showCustomers && (
              <Line
                type="monotone"
                dataKey="customers"
                name="Customers"
                stroke="#2f8f79"
                strokeWidth={1.8}
                dot={false}
                strokeDasharray="4 3"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
