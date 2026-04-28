import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchStoreComparison, fetchStores, Store, StoreComparisonMetrics } from "../api/endpoints";
import { extractApiError } from "../api/client";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import { SmartColumn, SmartTable } from "../components/ui/DataTable";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useI18n } from "../lib/i18n";
import { useThemeMode } from "../lib/theme";

const PALETTE = ["#0d7a63", "#47cca8", "#2196f3", "#ff9800", "#9c27b0", "#f44336", "#607d8b", "#795548", "#00bcd4", "#8bc34a"];

function fmt(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function rangePreset(days: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);
  from.setDate(from.getDate() - days);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

const DATE_PRESETS = [
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
  { label: "180D", days: 180 },
  { label: "1Y", days: 365 },
];

export default function StoreComparison() {
  const { locale } = useI18n();
  const { theme } = useThemeMode();
  const isDark = theme === "dark";

  const [allStores, setAllStores] = React.useState<Store[]>([]);
  const [storesLoading, setStoresLoading] = React.useState(true);
  const [selectedIds, setSelectedIds] = React.useState<number[]>([]);
  const [searchInput, setSearchInput] = React.useState("");

  const { from: defaultFrom, to: defaultTo } = rangePreset(90);
  const [dateFrom, setDateFrom] = React.useState(defaultFrom);
  const [dateTo, setDateTo] = React.useState(defaultTo);
  const [activePreset, setActivePreset] = React.useState<string>("90D");

  const [result, setResult] = React.useState<StoreComparisonMetrics[] | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    fetchStores()
      .then(setAllStores)
      .catch(() => {})
      .finally(() => setStoresLoading(false));
  }, []);

  function applyPreset(label: string, days: number) {
    const { from, to } = rangePreset(days);
    setDateFrom(from);
    setDateTo(to);
    setActivePreset(label);
  }

  function toggleStore(id: number) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 10) return prev;
      return [...prev, id];
    });
  }

  const filteredStores = React.useMemo(() => {
    const q = searchInput.trim().toLowerCase();
    if (!q) return allStores;
    return allStores.filter((s) =>
      String(s.store_id).includes(q) ||
      (s.store_type ?? "").toLowerCase().includes(q) ||
      (s.assortment ?? "").toLowerCase().includes(q)
    );
  }, [allStores, searchInput]);

  async function runComparison() {
    if (selectedIds.length < 2) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetchStoreComparison({ store_ids: selectedIds.join(","), date_from: dateFrom, date_to: dateTo });
      setResult(res.stores);
    } catch (err) {
      setError(extractApiError(err, locale === "ru" ? "Не удалось загрузить сравнение." : "Failed to load comparison."));
    } finally {
      setLoading(false);
    }
  }

  const chartData = React.useMemo(() => {
    if (!result) return [];
    return result.map((s) => ({
      name: `Store ${s.store_id}`,
      total_sales: Math.round(s.total_sales),
      avg_daily: Math.round(s.avg_daily_sales),
    }));
  }, [result]);

  const tableColumns: SmartColumn<Record<string, unknown>>[] = [
    { key: "store_id", label: locale === "ru" ? "Магазин" : "Store", sortable: true, render: (v) => <strong>#{String(v ?? "")}</strong> },
    { key: "store_type", label: locale === "ru" ? "Тип" : "Type", sortable: true, render: (v) => String(v ?? "-") },
    { key: "assortment", label: locale === "ru" ? "Ассортимент" : "Assortment", sortable: true, render: (v) => String(v ?? "-") },
    { key: "total_sales", label: locale === "ru" ? "Продажи" : "Total Sales", sortable: true, render: (v) => fmt(Number(v ?? 0)) },
    { key: "avg_daily_sales", label: locale === "ru" ? "Ср. в день" : "Avg/Day", sortable: true, render: (v) => fmt(Number(v ?? 0)) },
    { key: "total_customers", label: locale === "ru" ? "Покупатели" : "Customers", sortable: true, render: (v) => fmt(Number(v ?? 0)) },
    { key: "promo_days", label: locale === "ru" ? "Promo дни" : "Promo Days", sortable: true },
    { key: "open_days", label: locale === "ru" ? "Открыт дни" : "Open Days", sortable: true },
    {
      key: "promo_uplift_pct", label: locale === "ru" ? "Uplift промо" : "Promo Uplift",
      sortable: true,
      render: (v) => {
        if (v == null) return <span className="muted">—</span>;
        const val = Number(v);
        const color = val >= 0 ? "var(--color-success, #38a169)" : "var(--color-danger, #e53e3e)";
        return <span style={{ color, fontWeight: 600 }}>{val >= 0 ? "+" : ""}{val.toFixed(1)}%</span>;
      },
    },
  ];

  const gridColor = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.07)";
  const textColor = isDark ? "#9bb3ae" : "#6b8a83";

  return (
    <PageLayout
      title={locale === "ru" ? "Сравнение магазинов" : "Store Comparison"}
      subtitle={locale === "ru"
        ? "Выберите до 10 магазинов и сравните KPI за выбранный период."
        : "Select up to 10 stores and compare KPIs side-by-side."}
    >
      {/* Store selector + date range */}
      <Card title={locale === "ru" ? "Настройки сравнения" : "Comparison Setup"}>
        <div className="comparison-setup">
          <div className="comparison-store-picker">
            <div className="field">
              <label>{locale === "ru" ? "Поиск магазинов" : "Search stores"}</label>
              <input
                className="input"
                placeholder={locale === "ru" ? "ID, тип, ассортимент..." : "Store ID, type, assortment…"}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            {selectedIds.length > 0 && (
              <div className="comparison-selected-chips">
                {selectedIds.map((id) => (
                  <button key={id} className="chip chip-active" type="button" onClick={() => toggleStore(id)}>
                    #{id} ✕
                  </button>
                ))}
              </div>
            )}
            <p className="muted" style={{ fontSize: "0.8rem" }}>
              {locale === "ru" ? `Выбрано: ${selectedIds.length}/10` : `Selected: ${selectedIds.length}/10`}
            </p>
            <div className="comparison-store-list">
              {storesLoading ? <LoadingState lines={3} /> : filteredStores.slice(0, 50).map((s) => {
                const active = selectedIds.includes(s.store_id);
                const disabled = !active && selectedIds.length >= 10;
                return (
                  <button
                    key={s.store_id}
                    type="button"
                    className={`chip ${active ? "chip-active" : ""} ${disabled ? "chip-disabled" : ""}`}
                    onClick={() => !disabled && toggleStore(s.store_id)}
                    disabled={disabled}
                  >
                    #{s.store_id}
                    {s.store_type ? ` · ${s.store_type}` : ""}
                    {s.assortment ? ` · ${s.assortment}` : ""}
                  </button>
                );
              })}
              {filteredStores.length > 50 && (
                <p className="muted" style={{ fontSize: "0.78rem" }}>
                  {locale === "ru" ? `+${filteredStores.length - 50} ещё — уточните поиск` : `+${filteredStores.length - 50} more — refine search`}
                </p>
              )}
            </div>
          </div>

          <div className="comparison-date-controls">
            <div className="field">
              <label>{locale === "ru" ? "Дата от" : "Date from"}</label>
              <input type="date" className="input" value={dateFrom} max={dateTo} onChange={(e) => { setDateFrom(e.target.value); setActivePreset(""); }} />
            </div>
            <div className="field">
              <label>{locale === "ru" ? "Дата до" : "Date to"}</label>
              <input type="date" className="input" value={dateTo} min={dateFrom} onChange={(e) => { setDateTo(e.target.value); setActivePreset(""); }} />
            </div>
            <div className="preset-buttons">
              {DATE_PRESETS.map(({ label, days }) => (
                <button
                  key={label}
                  type="button"
                  className={`button ghost ${activePreset === label ? "button-active" : ""}`}
                  onClick={() => applyPreset(label, days)}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="button primary"
              disabled={selectedIds.length < 2 || !dateFrom || !dateTo || loading}
              onClick={runComparison}
            >
              {loading
                ? (locale === "ru" ? "Загрузка..." : "Loading…")
                : (locale === "ru" ? "Сравнить" : "Compare")}
            </button>
            {selectedIds.length < 2 && (
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                {locale === "ru" ? "Выберите минимум 2 магазина" : "Select at least 2 stores"}
              </p>
            )}
          </div>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={runComparison} />}
      {loading && <LoadingState lines={6} />}

      {!loading && result && result.length === 0 && (
        <EmptyState message={locale === "ru" ? "Нет данных для выбранных магазинов." : "No data for the selected stores and date range."} />
      )}

      {!loading && result && result.length > 0 && (
        <>
          {/* KPI metric cards */}
          <div className="comparison-metric-grid">
            {result.map((s, i) => (
              <Card key={s.store_id} title={`Store #${s.store_id}`} subtitle={[s.store_type, s.assortment].filter(Boolean).join(" · ") || undefined}>
                <div className="comparison-kpi-stack">
                  <MetricCard label={locale === "ru" ? "Продажи" : "Total Sales"} value={fmt(s.total_sales)} variant="teal" />
                  <MetricCard label={locale === "ru" ? "Ср./день" : "Avg/Day"} value={fmt(s.avg_daily_sales)} variant="slate" />
                  <MetricCard label={locale === "ru" ? "Покупатели" : "Customers"} value={fmt(s.total_customers)} />
                  {s.promo_uplift_pct != null && (
                    <MetricCard
                      label={locale === "ru" ? "Promo uplift" : "Promo Uplift"}
                      value={`${s.promo_uplift_pct >= 0 ? "+" : ""}${s.promo_uplift_pct.toFixed(1)}%`}
                      variant={s.promo_uplift_pct >= 0 ? "success" : "danger"}
                    />
                  )}
                </div>
              </Card>
            ))}
          </div>

          {/* Bar chart */}
          <Card title={locale === "ru" ? "Сравнение продаж" : "Sales Comparison"} subtitle={locale === "ru" ? "Общие и средние продажи по выбранным магазинам" : "Total and average daily sales per store"}>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: textColor }} />
                <YAxis tick={{ fontSize: 11, fill: textColor }} tickFormatter={(v) => v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : String(v)} />
                <Tooltip formatter={(v: number) => fmt(v)} contentStyle={{ background: isDark ? "#1a2b27" : "#fff", border: "1px solid var(--border)", borderRadius: 8 }} />
                <Legend />
                <Bar dataKey="total_sales" name={locale === "ru" ? "Всего продаж" : "Total Sales"} radius={[4, 4, 0, 0]}>
                  {chartData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Bar>
                <Bar dataKey="avg_daily" name={locale === "ru" ? "Ср. в день" : "Avg/Day"} radius={[4, 4, 0, 0]} fill="#47cca8" opacity={0.6} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Detail table */}
          <Card title={locale === "ru" ? "Детальное сравнение" : "Detailed Comparison"} subtitle={locale === "ru" ? "Полная таблица KPI для сравнения" : "Full KPI breakdown for all selected stores"}>
            <SmartTable
              columns={tableColumns}
              data={result as unknown as Record<string, unknown>[]}
              pageSize={20}
              rowKeyField="store_id"
              emptyMessage={locale === "ru" ? "Нет данных." : "No data."}
            />
          </Card>
        </>
      )}
    </PageLayout>
  );
}
