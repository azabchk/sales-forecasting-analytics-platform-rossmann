import React from "react";

type Props = {
  title: string;
  value: string;
};

function Card({ title, value }: Props) {
  return (
    <div style={{ background: "#f4f7ff", borderRadius: 12, padding: 16, border: "1px solid #d7e1ff" }}>
      <div style={{ fontSize: 13, color: "#4b5a7a", marginBottom: 8 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: "#1e2a44" }}>{value}</div>
    </div>
  );
}

export default function KpiCards(props: {
  totalSales: number;
  totalCustomers: number;
  avgDailySales: number;
  promoDays: number;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
      <Card title="Общие продажи" value={props.totalSales.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} />
      <Card title="Клиенты" value={props.totalCustomers.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} />
      <Card title="Среднедневные продажи" value={props.avgDailySales.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} />
      <Card title="Промо-дни" value={props.promoDays.toLocaleString("ru-RU")} />
    </div>
  );
}
