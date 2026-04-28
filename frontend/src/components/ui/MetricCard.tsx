import React from "react";

export type MetricCardVariant = "default" | "teal" | "slate" | "gold" | "danger" | "success";

type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  trend?: number;
  trendLabel?: string;
  variant?: MetricCardVariant;
  icon?: React.ReactNode;
};

function TrendBadge({ trend, label }: { trend: number; label?: string }) {
  const positive = trend >= 0;
  const arrow = positive ? "↑" : "↓";
  const cls = positive ? "metric-trend positive" : "metric-trend negative";
  const pct = `${positive ? "+" : ""}${trend.toFixed(1)}%`;
  return (
    <span className={cls} aria-label={`${positive ? "Up" : "Down"} ${Math.abs(trend).toFixed(1)}%`}>
      <span aria-hidden="true">{arrow}</span> {pct}
      {label ? <span className="metric-trend-label">{label}</span> : null}
    </span>
  );
}

export default function MetricCard({ label, value, hint, trend, trendLabel, variant = "default", icon }: MetricCardProps) {
  return (
    <div className={`insight-card metric-card metric-card-${variant}`}>
      <div className="metric-card-header">
        <p className="insight-label">{label}</p>
        {icon ? <span className="metric-card-icon" aria-hidden="true">{icon}</span> : null}
      </div>
      <p className="insight-value metric-value">{value}</p>
      <div className="metric-card-footer">
        {hint ? <p className="muted metric-hint">{hint}</p> : null}
        {trend !== undefined ? <TrendBadge trend={trend} label={trendLabel} /> : null}
      </div>
    </div>
  );
}
