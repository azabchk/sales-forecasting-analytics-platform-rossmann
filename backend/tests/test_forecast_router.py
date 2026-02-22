from fastapi.testclient import TestClient

import app.routers.forecast as forecast_router
from app.main import app


def test_forecast_batch_route_returns_expected_shape(monkeypatch):
    client = TestClient(app)

    def fake_batch(store_ids: list[int], horizon_days: int) -> dict:
        assert store_ids == [1, 2]
        assert horizon_days == 7
        return {
            "request": {"store_ids": [1, 2], "horizon_days": 7},
            "store_summaries": [
                {
                    "store_id": 1,
                    "total_predicted_sales": 100.0,
                    "avg_daily_sales": 14.2,
                    "peak_date": "2025-01-03",
                    "peak_sales": 20.0,
                    "avg_interval_width": 4.0,
                }
            ],
            "portfolio_summary": {
                "stores_count": 2,
                "horizon_days": 7,
                "total_predicted_sales": 250.0,
                "avg_daily_sales": 35.7,
                "peak_date": "2025-01-04",
                "peak_sales": 42.0,
                "avg_interval_width": 8.0,
            },
            "portfolio_series": [
                {
                    "date": "2025-01-01",
                    "predicted_sales": 35.0,
                    "predicted_lower": 30.0,
                    "predicted_upper": 40.0,
                }
            ],
        }

    monkeypatch.setattr(forecast_router, "forecast_batch_for_stores", fake_batch)
    response = client.post("/api/v1/forecast/batch", json={"store_ids": [1, 2], "horizon_days": 7})

    assert response.status_code == 200
    payload = response.json()
    assert payload["request"] == {"store_ids": [1, 2], "horizon_days": 7}
    assert payload["portfolio_summary"]["stores_count"] == 2
    assert len(payload["portfolio_series"]) == 1


def test_forecast_batch_route_validates_payload():
    client = TestClient(app)
    response = client.post("/api/v1/forecast/batch", json={"store_ids": [], "horizon_days": 7})

    assert response.status_code == 422
