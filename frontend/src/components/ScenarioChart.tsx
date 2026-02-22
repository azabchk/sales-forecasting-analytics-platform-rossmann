import React from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ForecastScenarioPoint } from "../api/endpoints";
import { useI18n } from "../lib/i18n";
import { formatCompact, formatDateLabel, formatInt } from "../lib/format";

type TooltipRow = {
  dataKey: string;
  value: number;
};

function ScenarioTooltip({
  active,
  payload,
  label,
  locale,
}: {
  active?: boolean;
  payload?: TooltipRow[];
  label?: string;
  locale: "en" | "ru";
}) {
  if (!active || !payload || !label) {
    return null;
  }

  const baseline = payload.find((row) => row.dataKey === "baseline_sales")?.value ?? 0;
  const scenario = payload.find((row) => row.dataKey === "scenario_sales")?.value ?? 0;
  const delta = payload.find((row) => row.dataKey === "delta_sales")?.value ?? 0;

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{formatDateLabel(label)}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "База" : "Baseline"}: {formatInt(baseline)}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "Сценарий" : "Scenario"}: {formatInt(scenario)}</p>
      <p className="chart-tooltip-line">{locale === "ru" ? "Дельта" : "Delta"}: {formatInt(delta)}</p>
    </div>
  );
}

export default function ScenarioChart({ data }: { data: ForecastScenarioPoint[] }) {
  const { locale } = useI18n();
  const scenarioTotal = data.reduce((sum, row) => sum + row.scenario_sales, 0);

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{locale === "ru" ? "Сценарий vs База" : "Scenario vs Baseline"}</h3>
        <p className="panel-subtitle">
          {formatCompact(scenarioTotal)} {locale === "ru" ? "прогноз при параметрах сценария" : "projected with scenario controls"}
        </p>
      </div>
      <div style={{ width: "100%", height: 380 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 14, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis dataKey="date" minTickGap={24} stroke="var(--chart-axis)" tickFormatter={formatDateLabel} />
            <YAxis yAxisId="sales" stroke="var(--chart-axis)" tickFormatter={(value) => formatCompact(Number(value))} />
            <YAxis yAxisId="delta" orientation="right" stroke="var(--chart-axis)" tickFormatter={(value) => formatCompact(Number(value))} />
            <Tooltip content={<ScenarioTooltip locale={locale} />} wrapperStyle={{ outline: "none" }} />
            <Legend />
            <Bar yAxisId="delta" dataKey="delta_sales" name={locale === "ru" ? "Дельта" : "Delta"} fill="var(--chart-bar)" radius={[4, 4, 0, 0]} barSize={14} />
            <Line yAxisId="sales" dataKey="baseline_sales" name={locale === "ru" ? "База" : "Baseline"} stroke="var(--chart-secondary)" strokeWidth={2.2} dot={false} />
            <Line yAxisId="sales" dataKey="scenario_sales" name={locale === "ru" ? "Сценарий" : "Scenario"} stroke="var(--chart-primary)" strokeWidth={2.6} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
