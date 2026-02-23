import React from "react";

type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
};

export default function MetricCard({ label, value, hint }: MetricCardProps) {
  return (
    <div className="insight-card">
      <p className="insight-label">{label}</p>
      <p className="insight-value">{value}</p>
      {hint ? <p className="muted">{hint}</p> : null}
    </div>
  );
}
