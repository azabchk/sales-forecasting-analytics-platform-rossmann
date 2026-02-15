import React, { useMemo, useState } from "react";

import { fetchStores, ForecastPoint, postForecast, Store } from "../api/endpoints";
import ForecastChart from "../components/ForecastChart";
import StoreSelector from "../components/StoreSelector";

function summarizeForecast(rows: ForecastPoint[]) {
  if (rows.length === 0) {
    return {
      total: 0,
      avg: 0,
      peak: 0,
      peakDate: "-",
    };
  }

  const total = rows.reduce((acc, row) => acc + row.predicted_sales, 0);
  const avg = total / rows.length;
  const peakRow = rows.reduce((maxRow, row) => (row.predicted_sales > maxRow.predicted_sales ? row : maxRow), rows[0]);

  return {
    total,
    avg,
    peak: peakRow.predicted_sales,
    peakDate: peakRow.date,
  };
}

export default function ForecastPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<number | undefined>(undefined);
  const [horizon, setHorizon] = useState<number>(30);
  const [data, setData] = useState<ForecastPoint[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    fetchStores()
      .then((rows) => {
        setStores(rows);
        if (rows.length > 0) {
          setStoreId(rows[0].store_id);
        }
      })
      .catch(() => setError("Failed to load stores list."));
  }, []);

  async function generateForecast() {
    if (!storeId) {
      setError("Select a store to run forecast.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const result = await postForecast({ store_id: storeId, horizon_days: horizon });
      setData(result);
    } catch {
      setError("Unable to generate forecast. Ensure backend and trained model are available.");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => summarizeForecast(data), [data]);

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Forecast Studio</h2>
          <p className="page-note">Recursive multi-day forecasting with confidence interval bands.</p>
        </div>
      </div>

      <div className="panel">
        <div className="controls">
          <StoreSelector stores={stores} value={storeId} onChange={setStoreId} label="Store" includeAllOption={false} />
          <div className="field">
            <label htmlFor="forecast-horizon">Horizon (days)</label>
            <input
              id="forecast-horizon"
              className="input"
              type="number"
              min={1}
              max={180}
              value={horizon}
              onChange={(e) => setHorizon(Math.max(1, Math.min(180, Number(e.target.value) || 1)))}
            />
          </div>
          <button onClick={generateForecast} className="button primary" disabled={loading || !storeId}>
            {loading ? "Running..." : "Generate forecast"}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {data.length > 0 && (
        <>
          <div className="forecast-summary">
            <div className="summary-box">
              <p className="label">Total forecast</p>
              <p className="value">{summary.total.toLocaleString("en-US", { maximumFractionDigits: 0 })}</p>
            </div>
            <div className="summary-box">
              <p className="label">Average per day</p>
              <p className="value">{summary.avg.toLocaleString("en-US", { maximumFractionDigits: 2 })}</p>
            </div>
            <div className="summary-box">
              <p className="label">Peak day</p>
              <p className="value">
                {summary.peak.toLocaleString("en-US", { maximumFractionDigits: 0 })} ({summary.peakDate})
              </p>
            </div>
          </div>
          <ForecastChart data={data} />
        </>
      )}

      {!loading && data.length === 0 && !error && (
        <p className="muted">Select forecast settings and run the model to display results.</p>
      )}
    </section>
  );
}
