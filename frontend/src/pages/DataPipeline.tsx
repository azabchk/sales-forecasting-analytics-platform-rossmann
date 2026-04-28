import React from "react";
import { apiClient, extractApiError } from "../api/client";
import { exportToCsv } from "../lib/exportCsv";

type SystemSummary = {
  stores_count: number;
  sales_rows_count: number;
  date_from?: string | null;
  date_to?: string | null;
};

type DataAvailabilityDataset = {
  table_name: string;
  rows: number;
  min_date?: string | null;
  max_date?: string | null;
};

type DataAvailability = {
  generated_at: string;
  data_source_ids: number[];
  datasets: DataAvailabilityDataset[];
};

type PreflightRun = {
  run_id: string;
  created_at: string;
  source_name: string;
  final_status: string;
  blocked: boolean;
  validation_status: string;
  semantic_status: string;
  mode: string;
};

type PreflightList = { items: PreflightRun[]; limit: number };

function fmt(n: number) {
  return n.toLocaleString();
}

function statusColor(s: string) {
  if (s === "PASS") return "status-pass";
  if (s === "FAIL") return "status-fail";
  if (s === "WARN") return "status-warn";
  return "status-skipped";
}

export default function DataPipeline() {
  const [summary, setSummary] = React.useState<SystemSummary | null>(null);
  const [availability, setAvailability] = React.useState<DataAvailability | null>(null);
  const [runs, setRuns] = React.useState<PreflightRun[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [triggering, setTriggering] = React.useState(false);
  const [triggerMsg, setTriggerMsg] = React.useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, avaRes, runsRes] = await Promise.all([
        apiClient.get<SystemSummary>("/system/summary"),
        apiClient.get<DataAvailability>("/diagnostics/preflight/data-availability").catch(() => ({ data: null })),
        apiClient.get<PreflightList>("/diagnostics/preflight/runs", { params: { limit: 20 } }).catch(() => ({ data: { items: [] } })),
      ]);
      setSummary(sumRes.data);
      setAvailability(avaRes.data);
      setRuns((runsRes.data as PreflightList)?.items ?? []);
    } catch (e) {
      setError(extractApiError(e, "Failed to load pipeline data"));
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => { load(); }, []);

  async function handleTriggerPreflight() {
    setTriggering(true);
    setTriggerMsg(null);
    try {
      await apiClient.post("/diagnostics/preflight/alerts/evaluate", {});
      setTriggerMsg("✓ Preflight evaluation triggered successfully.");
      setTimeout(load, 1500);
    } catch (e) {
      setTriggerMsg("✗ " + extractApiError(e, "Trigger failed"));
    } finally {
      setTriggering(false);
    }
  }

  function handleExport() {
    exportToCsv("preflight_runs.csv", runs.map((r) => ({
      run_id: r.run_id,
      source_name: r.source_name,
      final_status: r.final_status,
      validation_status: r.validation_status,
      semantic_status: r.semantic_status,
      mode: r.mode,
      blocked: r.blocked,
      created_at: r.created_at,
    })));
  }

  if (loading) return <section className="page"><div className="panel" style={{ padding: 32, textAlign: "center", color: "var(--text-muted)" }}>Loading pipeline data…</div></section>;
  if (error) return <section className="page"><div className="login-error">{error}</div></section>;

  const daysSinceUpdate = summary?.date_to
    ? Math.round((Date.now() - new Date(summary.date_to).getTime()) / 86400000)
    : null;

  const freshnessColor = daysSinceUpdate === null ? "var(--text-muted)"
    : daysSinceUpdate <= 1 ? "var(--status-pass)"
    : daysSinceUpdate <= 7 ? "var(--status-warn)"
    : "var(--status-fail)";

  return (
    <section className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Data Pipeline</h1>
          <p className="page-note">Monitor data freshness, source availability, and preflight validation history.</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="export-btn" onClick={handleExport} disabled={!runs.length}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 10v2h10v-2M7 2v7M4 6l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Export CSV
          </button>
          <button className="button primary" onClick={load} disabled={loading}>↻ Refresh</button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="pipeline-grid">
        <div className="pipeline-card">
          <span className="pipeline-card-label">Total Stores</span>
          <span className="pipeline-card-value">{fmt(summary?.stores_count ?? 0)}</span>
          <span className="pipeline-card-sub">in dim_store</span>
        </div>
        <div className="pipeline-card">
          <span className="pipeline-card-label">Sales Rows</span>
          <span className="pipeline-card-value">{fmt(summary?.sales_rows_count ?? 0)}</span>
          <span className="pipeline-card-sub">in fact_sales_daily</span>
        </div>
        <div className="pipeline-card">
          <span className="pipeline-card-label">Date Range</span>
          <span className="pipeline-card-value" style={{ fontSize: "1.1rem" }}>
            {summary?.date_from ?? "—"} → {summary?.date_to ?? "—"}
          </span>
          <span className="pipeline-card-sub">historical coverage</span>
        </div>
        <div className="pipeline-card">
          <span className="pipeline-card-label">Data Freshness</span>
          <span className="pipeline-card-value" style={{ fontSize: "1.3rem", color: freshnessColor }}>
            {daysSinceUpdate !== null ? `${daysSinceUpdate}d ago` : "—"}
          </span>
          <span className="pipeline-card-sub">since last data date</span>
        </div>
      </div>

      {/* Dataset availability */}
      {availability?.datasets && availability.datasets.length > 0 && (
        <div className="panel" style={{ marginBottom: 24 }}>
          <h2 className="section-title" style={{ marginBottom: 16 }}>Dataset Availability</h2>
          <table className="data-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Table</th>
                <th>Rows</th>
                <th>Min Date</th>
                <th>Max Date</th>
              </tr>
            </thead>
            <tbody>
              {availability.datasets.map((d) => (
                <tr key={d.table_name}>
                  <td><code style={{ fontSize: "0.8125rem" }}>{d.table_name}</code></td>
                  <td>{fmt(d.rows)}</td>
                  <td style={{ color: "var(--text-muted)" }}>{d.min_date ?? "—"}</td>
                  <td style={{ color: "var(--text-muted)" }}>{d.max_date ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Preflight trigger */}
      <div className="panel" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 className="section-title" style={{ marginBottom: 4 }}>Preflight Validation</h2>
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-muted)" }}>
              Run alert evaluation across all active preflight policies.
            </p>
          </div>
          <button className="retrain-btn" onClick={handleTriggerPreflight} disabled={triggering}>
            {triggering ? <><span className="login-spinner" style={{ width: 14, height: 14 }} /> Running…</> : "▶ Run Evaluation"}
          </button>
        </div>
        {triggerMsg && (
          <div className="retrain-progress" style={{ marginTop: 12, color: triggerMsg.startsWith("✓") ? "var(--status-pass)" : "var(--status-fail)" }}>
            {triggerMsg}
          </div>
        )}
      </div>

      {/* Preflight run history */}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 className="section-title" style={{ margin: 0 }}>Preflight Run History</h2>
          <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>Last 20 runs</span>
        </div>
        {runs.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)" }}>No preflight runs recorded yet.</div>
        ) : (
          <table className="data-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Source</th>
                <th>Final Status</th>
                <th>Validation</th>
                <th>Semantic</th>
                <th>Mode</th>
                <th>Blocked</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={`${r.run_id}-${r.source_name}`}>
                  <td style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {r.run_id.slice(0, 16)}…
                  </td>
                  <td><span className="status-badge status-skipped">{r.source_name}</span></td>
                  <td><span className={`status-badge ${statusColor(r.final_status)}`}>{r.final_status}</span></td>
                  <td><span className={`status-badge ${statusColor(r.validation_status)}`}>{r.validation_status}</span></td>
                  <td><span className={`status-badge ${statusColor(r.semantic_status)}`}>{r.semantic_status}</span></td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>{r.mode}</td>
                  <td>
                    {r.blocked
                      ? <span className="status-badge status-fail">BLOCKED</span>
                      : <span className="status-badge status-pass">OK</span>}
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
