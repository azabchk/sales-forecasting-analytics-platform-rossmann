import React, { useEffect, useMemo, useState } from "react";

import { fetchPromoImpact, fetchSalesTimeseries, fetchStores, PromoImpactPoint, SalesPoint, Store } from "../api/endpoints";
import SalesChart from "../components/SalesChart";
import StoreSelector from "../components/StoreSelector";

function getDefaultRange() {
  const dateTo = new Date();
  const dateFrom = new Date();
  dateFrom.setMonth(dateFrom.getMonth() - 2);

  return {
    from: dateFrom.toISOString().slice(0, 10),
    to: dateTo.toISOString().slice(0, 10)
  };
}

export default function StoreAnalytics() {
  const range = useMemo(() => getDefaultRange(), []);
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [series, setSeries] = useState<SalesPoint[]>([]);
  const [promoImpact, setPromoImpact] = useState<PromoImpactPoint[]>([]);

  useEffect(() => {
    fetchStores().then(setStores);
  }, []);

  useEffect(() => {
    fetchSalesTimeseries({
      granularity: "daily",
      date_from: range.from,
      date_to: range.to,
      store_id: storeId
    }).then(setSeries);

    fetchPromoImpact(storeId).then(setPromoImpact);
  }, [range.from, range.to, storeId]);

  const chartData = series.map((row) => ({ date: row.date, sales: row.sales }));

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h2>Store Analytics</h2>
      <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label="Выбор магазина" />
      <SalesChart data={chartData} title="Ежедневные продажи" />

      <div style={{ background: "#fff", border: "1px solid #dbe3f5", borderRadius: 12, padding: 12 }}>
        <h3 style={{ marginTop: 0 }}>Promo Impact</h3>
        {promoImpact.length === 0 && <p>Нет данных.</p>}
        {promoImpact.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid #dbe3f5", padding: 8 }}>Store</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #dbe3f5", padding: 8 }}>Promo</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #dbe3f5", padding: 8 }}>Avg Sales</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #dbe3f5", padding: 8 }}>Avg Customers</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #dbe3f5", padding: 8 }}>Days</th>
              </tr>
            </thead>
            <tbody>
              {promoImpact.map((row) => (
                <tr key={`${row.store_id}-${row.promo_flag}`}>
                  <td style={{ borderBottom: "1px solid #eef2fb", padding: 8 }}>{row.store_id}</td>
                  <td style={{ borderBottom: "1px solid #eef2fb", padding: 8 }}>{row.promo_flag}</td>
                  <td style={{ borderBottom: "1px solid #eef2fb", padding: 8 }}>{row.avg_sales.toFixed(2)}</td>
                  <td style={{ borderBottom: "1px solid #eef2fb", padding: 8 }}>{row.avg_customers.toFixed(2)}</td>
                  <td style={{ borderBottom: "1px solid #eef2fb", padding: 8 }}>{row.num_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
