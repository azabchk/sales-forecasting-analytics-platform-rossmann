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
import { formatCompact, formatDateLabel, formatInt } from "../lib/format";

type TooltipRow = {
  dataKey: string;
  value: number;
};

function ScenarioTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipRow[];
  label?: string;
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
      <p className="chart-tooltip-line">Baseline: {formatInt(baseline)}</p>
      <p className="chart-tooltip-line">Scenario: {formatInt(scenario)}</p>
      <p className="chart-tooltip-line">Delta: {formatInt(delta)}</p>
    </div>
  );
}

export default function ScenarioChart({ data }: { data: ForecastScenarioPoint[] }) {
  const scenarioTotal = data.reduce((sum, row) => sum + row.scenario_sales, 0);

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Scenario vs Baseline</h3>
        <p className="panel-subtitle">{formatCompact(scenarioTotal)} projected with scenario controls</p>
      </div>
      <div style={{ width: "100%", height: 380 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 14, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfe9e4" />
            <XAxis dataKey="date" minTickGap={24} stroke="#53736a" tickFormatter={formatDateLabel} />
            <YAxis yAxisId="sales" stroke="#53736a" tickFormatter={(value) => formatCompact(Number(value))} />
            <YAxis yAxisId="delta" orientation="right" stroke="#53736a" tickFormatter={(value) => formatCompact(Number(value))} />
            <Tooltip content={<ScenarioTooltip />} wrapperStyle={{ outline: "none" }} />
            <Legend />
            <Bar yAxisId="delta" dataKey="delta_sales" name="Delta" fill="#a9cdbf" radius={[4, 4, 0, 0]} barSize={14} />
            <Line yAxisId="sales" dataKey="baseline_sales" name="Baseline" stroke="#3f5872" strokeWidth={2.2} dot={false} />
            <Line yAxisId="sales" dataKey="scenario_sales" name="Scenario" stroke="#0a7e64" strokeWidth={2.6} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

