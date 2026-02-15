import React, { useMemo, useState } from "react";

import { fetchPromoImpact, fetchSalesTimeseries, fetchStores, PromoImpactPoint, SalesPoint, Store } from "../api/endpoints";
import SalesChart from "../components/SalesChart";
import StoreSelector from "../components/StoreSelector";

function getDefaultRange() {
  const dateTo = new Date();
  const dateFrom = new Date();
  dateFrom.setMonth(dateFrom.getMonth() - 2);

  return {
    from: dateFrom.toISOString().slice(0, 10),
    to: dateTo.toISOString().slice(0, 10),
  };
}

export default function StoreAnalytics() {
  const defaults = useMemo(() => getDefaultRange(), []);

  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);

  const [series, setSeries] = useState<SalesPoint[]>([]);
  const [promoImpact, setPromoImpact] = useState<PromoImpactPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  React.useEffect(() => {
    fetchStores().then(setStores).catch(() => setError("Failed to load stores list."));
  }, []);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [seriesData, promoData] = await Promise.all([
        fetchSalesTimeseries({
          granularity: "daily",
          date_from: dateFrom,
          date_to: dateTo,
          store_id: storeId,
        }),
        fetchPromoImpact(storeId),
      ]);

      setSeries(seriesData);
      setPromoImpact(promoData);
    } catch {
      setError("Failed to load store analytics. Check backend connectivity.");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, storeId]);

  React.useEffect(() => {
    load();
  }, [load]);

  const chartData = series.map((row) => ({
    date: row.date,
    sales: row.sales,
    customers: row.customers,
  }));

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Store Analytics</h2>
          <p className="page-note">Compare daily demand and promo impact per store.</p>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label="Store" includeAllOption />
          <div className="field">
            <label htmlFor="store-date-from">Date from</label>
            <input
              id="store-date-from"
              className="input"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="store-date-to">Date to</label>
            <input
              id="store-date-to"
              className="input"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <button className="button primary" onClick={load} disabled={loading || dateFrom > dateTo}>
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {dateFrom > dateTo && <p className="error">Date from cannot be greater than Date to.</p>}
      {error && <p className="error">{error}</p>}

      {chartData.length > 0 ? (
        <SalesChart data={chartData} title="Daily Sales and Customers" showCustomers />
      ) : (
        !loading && <p className="muted">No daily observations for current filters.</p>
      )}

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Promo Impact</h3>
        {promoImpact.length === 0 ? (
          <p className="muted">No promo effect rows returned by API.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Store</th>
                  <th>Promo Status</th>
                  <th>Avg Sales</th>
                  <th>Avg Customers</th>
                  <th>Days</th>
                </tr>
              </thead>
              <tbody>
                {promoImpact.map((row) => (
                  <tr key={`${row.store_id}-${row.promo_flag}`}>
                    <td>{row.store_id}</td>
                    <td>
                      <span className={`badge ${row.promo_flag === "promo" ? "promo" : "no-promo"}`}>
                        {row.promo_flag}
                      </span>
                    </td>
                    <td>{row.avg_sales.toLocaleString("en-US", { maximumFractionDigits: 2 })}</td>
                    <td>{row.avg_customers.toLocaleString("en-US", { maximumFractionDigits: 2 })}</td>
                    <td>{row.num_days.toLocaleString("en-US")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
