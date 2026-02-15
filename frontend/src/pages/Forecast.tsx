import React, { useEffect, useState } from "react";

import { fetchStores, ForecastPoint, postForecast, Store } from "../api/endpoints";
import ForecastChart from "../components/ForecastChart";
import StoreSelector from "../components/StoreSelector";

export default function ForecastPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [horizon, setHorizon] = useState<number>(30);
  const [data, setData] = useState<ForecastPoint[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStores().then((rows) => {
      setStores(rows);
      if (rows.length > 0) {
        setStoreId(rows[0].store_id);
      }
    });
  }, []);

  async function generateForecast() {
    if (!storeId) {
      setError("Выберите магазин");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const result = await postForecast({ store_id: storeId, horizon_days: horizon });
      setData(result);
    } catch (e) {
      setError("Не удалось получить прогноз. Проверьте backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h2>Forecast</h2>
      <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
        <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label="Магазин" />
        <label>
          <span style={{ display: "block", marginBottom: 4 }}>Горизонт (дни)</span>
          <input
            type="number"
            min={1}
            max={180}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #c8d4f1", width: 140 }}
          />
        </label>
        <button
          onClick={generateForecast}
          disabled={loading}
          style={{
            padding: "10px 16px",
            borderRadius: 8,
            border: "none",
            background: "#1f6feb",
            color: "white",
            cursor: "pointer"
          }}
        >
          {loading ? "Расчет..." : "Построить прогноз"}
        </button>
      </div>

      {error && <p style={{ color: "#b3261e" }}>{error}</p>}
      {data.length > 0 && <ForecastChart data={data} />}
    </div>
  );
}
