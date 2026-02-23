import React from "react";

import { extractApiError } from "../api/client";
import {
  fetchStores,
  postScenarioRunV2,
  ScenarioRunResponseV2,
  Store,
} from "../api/endpoints";
import ScenarioChart from "../components/ScenarioChart";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { formatDecimal, formatInt, formatPercent } from "../lib/format";
import { useI18n } from "../lib/i18n";

type ScenarioMode = "store" | "segment";

export default function ScenarioLab() {
  const { locale, localeTag } = useI18n();
  const [stores, setStores] = React.useState<Store[]>([]);
  const [mode, setMode] = React.useState<ScenarioMode>("store");
  const [storeId, setStoreId] = React.useState<number | undefined>(undefined);

  const [segmentStoreType, setSegmentStoreType] = React.useState("");
  const [segmentAssortment, setSegmentAssortment] = React.useState("");
  const [segmentPromo2, setSegmentPromo2] = React.useState<"" | "0" | "1">("");

  const [horizon, setHorizon] = React.useState(30);
  const [promoMode, setPromoMode] = React.useState<"as_is" | "always_on" | "weekends_only" | "off">("as_is");
  const [weekendOpen, setWeekendOpen] = React.useState(true);
  const [schoolHoliday, setSchoolHoliday] = React.useState<0 | 1>(0);
  const [priceChangePct, setPriceChangePct] = React.useState(0);
  const [demandShiftPct, setDemandShiftPct] = React.useState(0);
  const [confidenceLevel, setConfidenceLevel] = React.useState(0.8);

  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [lastUpdated, setLastUpdated] = React.useState("-");
  const [result, setResult] = React.useState<ScenarioRunResponseV2 | null>(null);

  React.useEffect(() => {
    fetchStores()
      .then((rows) => {
        setStores(rows);
        if (!storeId && rows.length > 0) {
          setStoreId(rows[0].store_id);
        }
      })
      .catch((errorResponse) => {
        setError(
          extractApiError(
            errorResponse,
            locale === "ru" ? "Не удалось загрузить список магазинов." : "Failed to load stores list."
          )
        );
      });
  }, [locale, storeId]);

  async function runScenario() {
    if (mode === "store" && !storeId) {
      setError(locale === "ru" ? "Выберите магазин." : "Select a store.");
      return;
    }

    if (mode === "segment" && !segmentStoreType && !segmentAssortment && segmentPromo2 === "") {
      setError(
        locale === "ru"
          ? "Укажите хотя бы один фильтр сегмента."
          : "Provide at least one segment filter."
      );
      return;
    }

    setError("");
    setLoading(true);

    try {
      const response = await postScenarioRunV2({
        ...(mode === "store" ? { store_id: storeId } : {}),
        ...(mode === "segment"
          ? {
              segment: {
                ...(segmentStoreType ? { store_type: segmentStoreType } : {}),
                ...(segmentAssortment ? { assortment: segmentAssortment } : {}),
                ...(segmentPromo2 === "" ? {} : { promo2: Number(segmentPromo2) as 0 | 1 }),
              },
            }
          : {}),
        horizon_days: horizon,
        promo_mode: promoMode,
        weekend_open: weekendOpen,
        school_holiday: schoolHoliday,
        price_change_pct: priceChangePct,
        demand_shift_pct: demandShiftPct,
        confidence_level: confidenceLevel,
      });

      setResult(response);
      setLastUpdated(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru"
            ? "Ошибка расчета сценария. Проверьте параметры и backend."
            : "Scenario run failed. Verify request parameters and backend service."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const summary = result?.summary;

  return (
    <PageLayout
      title={locale === "ru" ? "Лаборатория сценариев" : "Scenario Lab"}
      subtitle={
        locale === "ru"
          ? "What-if прогнозирование для store/segment целей с учетом price/promo предпосылок."
          : "What-if forecasting for store and segment targets with explicit price/promo assumptions."
      }
      actions={
        <p className="meta-text">
          {locale === "ru" ? "Последнее обновление" : "Last update"}: {lastUpdated}
        </p>
      }
    >
      {error ? <ErrorState message={error} /> : null}

      <Card
        title={locale === "ru" ? "Параметры сценария" : "Scenario Inputs"}
        subtitle={locale === "ru" ? "Выберите target mode и бизнес-параметры." : "Choose target mode and business controls."}
      >
        <div className="controls">
          <div className="field">
            <label htmlFor="scenario-mode">{locale === "ru" ? "Режим" : "Mode"}</label>
            <select
              id="scenario-mode"
              className="select"
              value={mode}
              onChange={(event) => setMode(event.target.value as ScenarioMode)}
            >
              <option value="store">{locale === "ru" ? "Магазин" : "Store"}</option>
              <option value="segment">{locale === "ru" ? "Сегмент" : "Segment"}</option>
            </select>
          </div>

          {mode === "store" ? (
            <div className="field">
              <label htmlFor="scenario-store">{locale === "ru" ? "Магазин" : "Store"}</label>
              <select
                id="scenario-store"
                className="select"
                value={storeId ?? ""}
                onChange={(event) => setStoreId(Number(event.target.value))}
              >
                {stores.map((store) => (
                  <option key={store.store_id} value={store.store_id}>
                    #{store.store_id} · {store.store_type || "-"}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <>
              <div className="field">
                <label htmlFor="segment-store-type">store_type</label>
                <input
                  id="segment-store-type"
                  className="input"
                  placeholder="a"
                  value={segmentStoreType}
                  onChange={(event) => setSegmentStoreType(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="segment-assortment">assortment</label>
                <input
                  id="segment-assortment"
                  className="input"
                  placeholder="a"
                  value={segmentAssortment}
                  onChange={(event) => setSegmentAssortment(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="segment-promo2">promo2</label>
                <select
                  id="segment-promo2"
                  className="select"
                  value={segmentPromo2}
                  onChange={(event) => setSegmentPromo2(event.target.value as "" | "0" | "1")}
                >
                  <option value="">{locale === "ru" ? "Любой" : "Any"}</option>
                  <option value="1">1</option>
                  <option value="0">0</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div className="controls">
          <div className="field">
            <label htmlFor="scenario-horizon">{locale === "ru" ? "Горизонт (дни)" : "Horizon (days)"}</label>
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
            <label htmlFor="scenario-promo-mode">{locale === "ru" ? "Режим промо" : "Promo mode"}</label>
            <select
              id="scenario-promo-mode"
              className="select"
              value={promoMode}
              onChange={(event) => setPromoMode(event.target.value as "as_is" | "always_on" | "weekends_only" | "off")}
            >
              <option value="as_is">as_is</option>
              <option value="always_on">always_on</option>
              <option value="weekends_only">weekends_only</option>
              <option value="off">off</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="scenario-confidence">{locale === "ru" ? "Confidence" : "Confidence"}</label>
            <select
              id="scenario-confidence"
              className="select"
              value={confidenceLevel}
              onChange={(event) => setConfidenceLevel(Number(event.target.value))}
            >
              <option value={0.8}>0.80</option>
              <option value={0.9}>0.90</option>
              <option value={0.95}>0.95</option>
            </select>
          </div>
          <label className="toggle-field" htmlFor="scenario-weekend-open">
            <input
              id="scenario-weekend-open"
              type="checkbox"
              checked={weekendOpen}
              onChange={(event) => setWeekendOpen(event.target.checked)}
            />
            {locale === "ru" ? "Открыто в выходные" : "Weekend open"}
          </label>
          <label className="toggle-field" htmlFor="scenario-school-holiday">
            <input
              id="scenario-school-holiday"
              type="checkbox"
              checked={schoolHoliday === 1}
              onChange={(event) => setSchoolHoliday(event.target.checked ? 1 : 0)}
            />
            {locale === "ru" ? "School holiday" : "School holiday"}
          </label>
        </div>

        <div className="controls">
          <div className="field slider-field">
            <label htmlFor="scenario-price-change">
              {locale === "ru" ? "Изменение цены" : "Price change"} ({priceChangePct}%)
            </label>
            <input
              id="scenario-price-change"
              type="range"
              min={-30}
              max={30}
              step={1}
              value={priceChangePct}
              onChange={(event) => setPriceChangePct(Number(event.target.value))}
            />
          </div>
          <div className="field slider-field">
            <label htmlFor="scenario-demand-shift">
              {locale === "ru" ? "Сдвиг спроса" : "Demand shift"} ({demandShiftPct}%)
            </label>
            <input
              id="scenario-demand-shift"
              type="range"
              min={-50}
              max={50}
              step={1}
              value={demandShiftPct}
              onChange={(event) => setDemandShiftPct(Number(event.target.value))}
            />
          </div>
          <button className="button primary" type="button" onClick={runScenario} disabled={loading}>
            {loading ? (locale === "ru" ? "Расчет..." : "Running...") : locale === "ru" ? "Запустить сценарий" : "Run Scenario"}
          </button>
        </div>
      </Card>

      {loading && !result ? <LoadingState lines={4} /> : null}

      {summary ? (
        <div className="insight-grid">
          <MetricCard label={locale === "ru" ? "База" : "Baseline"} value={formatInt(summary.total_baseline_sales)} />
          <MetricCard label={locale === "ru" ? "Сценарий" : "Scenario"} value={formatInt(summary.total_scenario_sales)} />
          <MetricCard label={locale === "ru" ? "Дельта" : "Delta"} value={formatInt(summary.total_delta_sales)} />
          <MetricCard label={locale === "ru" ? "Uplift" : "Uplift"} value={formatPercent(summary.uplift_pct)} />
          <MetricCard label={locale === "ru" ? "Средн. дневная дельта" : "Avg Daily Delta"} value={formatInt(summary.avg_daily_delta)} />
        </div>
      ) : null}

      {result ? (
        <>
          <Card
            title={locale === "ru" ? "Предпосылки сценария" : "Scenario Assumptions"}
            subtitle={
              locale === "ru"
                ? "Price elasticity применяется как приближение: effective_demand_shift = demand_shift - elasticity*price_change"
                : "Price elasticity is an approximation: effective_demand_shift = demand_shift - elasticity*price_change"
            }
          >
            <div className="insight-grid">
              <MetricCard label="price_change_pct" value={formatPercent(result.assumptions.price_change_pct)} />
              <MetricCard label="price_elasticity" value={formatDecimal(result.assumptions.price_elasticity)} />
              <MetricCard label="price_effect_pct" value={formatPercent(result.assumptions.price_effect_pct)} />
              <MetricCard
                label="effective_demand_shift_pct"
                value={formatPercent(result.assumptions.effective_demand_shift_pct)}
              />
              <MetricCard
                label={locale === "ru" ? "Target" : "Target"}
                value={result.target.mode === "segment" ? `segment (${result.target.stores_count ?? 0})` : `store ${result.target.store_id ?? "-"}`}
              />
            </div>
          </Card>
          <ScenarioChart data={result.points} />
        </>
      ) : (
        !loading && <EmptyState message={locale === "ru" ? "Запустите сценарий для просмотра результатов." : "Run a scenario to see forecast comparisons."} />
      )}
    </PageLayout>
  );
}
