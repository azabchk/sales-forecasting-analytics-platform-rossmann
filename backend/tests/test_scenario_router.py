"""Tests for /scenario/run — XOR validation and success path."""
import app.routers.scenario as scenario_router
from fastapi.testclient import TestClient
from app.main import app


def test_scenario_rejects_both_store_and_segment():
    client = TestClient(app)
    resp = client.post("/api/v1/scenario/run", json={
        "store_id": 1,
        "segment": {"store_type": "a"},
        "horizon_days": 7,
    })
    assert resp.status_code == 400
    assert "both" in resp.json()["detail"].lower()


def test_scenario_rejects_neither_store_nor_segment():
    client = TestClient(app)
    resp = client.post("/api/v1/scenario/run", json={"horizon_days": 7})
    assert resp.status_code == 400


def test_scenario_store_mode_succeeds(monkeypatch):
    fake_response = {
        "run_id": "test_run_1",
        "target": {"mode": "store", "store_id": 1, "stores_count": 1, "store_ids": [1]},
        "assumptions": {
            "price_change_pct": 0.0,
            "price_elasticity": 1.0,
            "price_effect_pct": 0.0,
            "effective_demand_shift_pct": 0.0,
        },
        "request": {"store_id": 1, "horizon_days": 7},
        "summary": {
            "total_baseline_sales": 20000.0,
            "total_scenario_sales": 20000.0,
            "total_delta_sales": 0.0,
            "uplift_pct": 0.0,
            "avg_daily_delta": 0.0,
            "max_delta_date": None,
            "max_delta_value": 0.0,
        },
        "points": [],
    }
    monkeypatch.setattr(scenario_router, "run_scenario_v2", lambda **_: fake_response)
    client = TestClient(app)
    resp = client.post("/api/v1/scenario/run", json={"store_id": 1, "horizon_days": 7})
    assert resp.status_code == 200
    assert resp.json()["target"]["store_id"] == 1
