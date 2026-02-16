import React from "react";

import { extractApiError } from "../api/client";
import {
  fetchStores,
  ForecastScenarioPoint,
  ForecastScenarioResponse,
  postForecastScenario,
  Store,
} from "../api/endpoints";
import LoadingBlock from "../components/LoadingBlock";
import ScenarioChart from "../components/ScenarioChart";
import StoreSelector from "../components/StoreSelector";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";

type PresetName = "baseline" | "promo_boost" | "cost_guard" | "risk_downturn";

function applyPreset(preset: PresetName) {
  if (preset === "promo_boost") {
    return {
      promoMode: "always_on" as const,
      weekendOpen: true,
      schoolHoliday: 0 as 0 | 1,
      demandShiftPct: 12,
      confidenceLevel: 0.9,
    };
  }
  if (preset === "cost_guard") {
    return {
      promoMode: "off" as const,
      weekendOpen: false,
      schoolHoliday: 0 as 0 | 1,
      demandShiftPct: -8,
      confidenceLevel: 0.9,
    };
  }
  if (preset === "risk_downturn") {
    return {
      promoMode: "as_is" as const,
      weekendOpen: true,
      schoolHoliday: 1 as 0 | 1,
      demandShiftPct: -15,
      confidenceLevel: 0.95,
    };
  }
  return {
    promoMode: "as_is" as const,
    weekendOpen: true,
    schoolHoliday: 0 as 0 | 1,
    demandShiftPct: 0,
    confidenceLevel: 0.8,
  };
}

export default function ScenarioLab() {
  const [stores, setStores] = React.useState<Store[]>([]);
  const [storeId, setStoreId] = React.useState<number | undefined>(undefined);
  const [horizon, setHorizon] = React.useState(30);
  const [promoMode, setPromoMode] = React.useState<"as_is" | "always_on" | "weekends_only" | "off">("as_is");
  const [weekendOpen, setWeekendOpen] = React.useState(true);
  const [schoolHoliday, setSchoolHoliday] = React.useState<0 | 1>(0);
  const [demandShiftPct, setDemandShiftPct] = React.useState(0);
  const [confidenceLevel, setConfidenceLevel] = React.useState(0.8);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [result, setResult] = React.useState<ForecastScenarioResponse | null>(null);
  const [lastUpdated, setLastUpdated] = React.useState("-");

  React.useEffect(() => {
    fetchStores()
      .then((rows) => {
        setStores(rows);
        if (rows.length > 0) {
          setStoreId(rows[0].store_id);
        }
      })
      .catch((errorResponse) => setError(extractApiError(errorResponse, "Failed to load stores list.")));
  }, []);

  const points = result?.points ?? [];
  const summary = result?.summary;

  const topPositiveDays = React.useMemo(
    () =>
      [...points]
        .filter((row) => row.delta_sales > 0)
        .sort((a, b) => b.delta_sales - a.delta_sales)
        .slice(0, 8),
    [points]
  );

  const topRiskDays = React.useMemo(
    () =>
      [...points]
        .filter((row) => row.delta_sales < 0)
        .sort((a, b) => a.delta_sales - b.delta_sales)
        .slice(0, 8),
    [points]
  );

  async function runScenario() {
    if (!storeId) {
      setError("Select a store to run scenario simulation.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const response = await postForecastScenario({
        store_id: storeId,
        horizon_days: horizon,
        promo_mode: promoMode,
        weekend_open: weekendOpen,
        school_holiday: schoolHoliday,
        demand_shift_pct: demandShiftPct,
        confidence_level: confidenceLevel,
      });
      setResult(response);
      setLastUpdated(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(extractApiError(errorResponse, "Scenario simulation failed. Verify backend and model artifacts."));
    } finally {
      setLoading(false);
    }
  }

  function applyScenarioPreset(name: PresetName) {
    const next = applyPreset(name);
    setPromoMode(next.promoMode);
    setWeekendOpen(next.weekendOpen);
    setSchoolHoliday(next.schoolHoliday);
    setDemandShiftPct(next.demandShiftPct);
    setConfidenceLevel(next.confidenceLevel);
  }

  function downloadScenarioCsv() {
    if (points.length === 0 || !storeId) {
      return;
    }

    const header = "date,baseline_sales,scenario_sales,delta_sales,scenario_lower,scenario_upper";
    const rows = points.map(
      (row) =>
        `${row.date},${row.baseline_sales},${row.scenario_sales},${row.delta_sales},${row.scenario_lower ?? ""},${row.scenario_upper ?? ""}`
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `scenario_store_${storeId}_${horizon}d.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  function renderOpportunityTable(title: string, rows: ForecastScenarioPoint[], mode: "up" | "down") {
    return (
      <div className="panel">
        <div className="panel-head">
          <h3>{title}</h3>
          <p className="panel-subtitle">
            {mode === "up" ? "Days with highest upside under current scenario." : "Days with highest downside risk under current scenario."}
          </p>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Baseline</th>
                <th>Scenario</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4}>No rows in this category for current settings.</td>
                </tr>
              )}
              {rows.map((row) => (
                <tr key={`${title}-${row.date}`}>
                  <td>{row.date}</td>
                  <td>{formatInt(row.baseline_sales)}</td>
                  <td>{formatInt(row.scenario_sales)}</td>
                  <td className={row.delta_sales >= 0 ? "td-positive" : "td-negative"}>{formatInt(row.delta_sales)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Scenario Lab</h2>
          <p className="page-note">What-if simulator for demand planning using promo strategy, operating rules, and demand shift assumptions.</p>
        </div>
        <div className="inline-meta">
          <p className="meta-text">Last update: {lastUpdated}</p>
          <div className="preset-row">
            <button className="button ghost" type="button" onClick={() => applyScenarioPreset("baseline")}>
              Baseline
            </button>
            <button className="button ghost" type="button" onClick={() => applyScenarioPreset("promo_boost")}>
              Promo Boost
            </button>
            <button className="button ghost" type="button" onClick={() => applyScenarioPreset("cost_guard")}>
              Cost Guard
            </button>
            <button className="button ghost" type="button" onClick={() => applyScenarioPreset("risk_downturn")}>
              Risk Downturn
            </button>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label="Store" includeAllOption={false} id="scenario-store" />
          <div className="field">
            <label htmlFor="scenario-horizon">Horizon (days)</label>
            <input
              id="scenario-horizon"
              className="input"
              type="number"
              min={1}
              max={180}
              value={horizon}
              onChange={(event) => setHorizon(Math.max(1, Math.min(180, Number(event.target.value) || 1)))}
            />
          </div>
          <div className="field">
            <label htmlFor="scenario-promo-mode">Promo mode</label>
            <select
              id="scenario-promo-mode"
              className="select"
              value={promoMode}
              onChange={(event) => setPromoMode(event.target.value as "as_is" | "always_on" | "weekends_only" | "off")}
            >
              <option value="as_is">As Is (default no promo)</option>
              <option value="always_on">Always On</option>
              <option value="weekends_only">Weekends Only</option>
              <option value="off">Always Off</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="scenario-confidence">Confidence level</label>
            <select
              id="scenario-confidence"
              className="select"
              value={confidenceLevel}
              onChange={(event) => setConfidenceLevel(Number(event.target.value))}
            >
              <option value={0.8}>80%</option>
              <option value={0.9}>90%</option>
              <option value={0.95}>95%</option>
            </select>
          </div>
        </div>
        <div className="controls scenario-controls-row">
          <label className="toggle-field" htmlFor="scenario-weekend-open">
            <input
              id="scenario-weekend-open"
              type="checkbox"
              checked={weekendOpen}
              onChange={(event) => setWeekendOpen(event.target.checked)}
            />
            Keep weekend open
          </label>
          <label className="toggle-field" htmlFor="scenario-school-holiday">
            <input
              id="scenario-school-holiday"
              type="checkbox"
              checked={schoolHoliday === 1}
              onChange={(event) => setSchoolHoliday(event.target.checked ? 1 : 0)}
            />
            Force school holiday
          </label>
          <div className="field slider-field">
            <label htmlFor="scenario-shift">Demand shift ({demandShiftPct}%)</label>
            <input
              id="scenario-shift"
              type="range"
              min={-50}
              max={50}
              step={1}
              value={demandShiftPct}
              onChange={(event) => setDemandShiftPct(Number(event.target.value))}
            />
          </div>
          <button className="button primary" type="button" onClick={runScenario} disabled={loading || !storeId}>
            {loading ? "Running..." : "Run scenario"}
          </button>
          <button className="button" type="button" onClick={downloadScenarioCsv} disabled={points.length === 0}>
            Download CSV
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {loading && !result && (
        <div className="panel">
          <LoadingBlock lines={4} className="loading-stack" />
        </div>
      )}

      {summary && (
        <>
          <div className="forecast-summary">
            <div className="summary-box">
              <p className="label">Baseline total</p>
              <p className="value">{formatInt(summary.total_baseline_sales)}</p>
            </div>
            <div className="summary-box">
              <p className="label">Scenario total</p>
              <p className="value">{formatInt(summary.total_scenario_sales)}</p>
            </div>
            <div className="summary-box">
              <p className="label">Total delta</p>
              <p className={`value ${summary.total_delta_sales >= 0 ? "positive" : "negative"}`}>{formatInt(summary.total_delta_sales)}</p>
            </div>
            <div className="summary-box">
              <p className="label">Uplift</p>
              <p className={`value ${summary.uplift_pct >= 0 ? "positive" : "negative"}`}>{formatPercent(summary.uplift_pct)}</p>
            </div>
            <div className="summary-box">
              <p className="label">Avg daily delta</p>
              <p className={`value ${summary.avg_daily_delta >= 0 ? "positive" : "negative"}`}>{formatDecimal(summary.avg_daily_delta)}</p>
            </div>
            <div className="summary-box">
              <p className="label">Best delta day</p>
              <p className="value">
                {summary.max_delta_date ?? "-"} ({formatInt(summary.max_delta_value)})
              </p>
            </div>
          </div>

          {points.length > 0 && <ScenarioChart data={points} />}

          {renderOpportunityTable("Top Opportunity Days", topPositiveDays, "up")}
          {renderOpportunityTable("Top Risk Days", topRiskDays, "down")}
        </>
      )}

      {!loading && !summary && !error && <p className="muted">Configure scenario controls and run the simulator to compare outcomes.</p>}
    </section>
  );
}

