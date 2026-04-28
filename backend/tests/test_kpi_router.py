"""Tests for /kpi/summary and /kpi/promo-impact endpoints."""
import app.routers.kpi as kpi_router
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import KpiSummaryResponse, PromoImpactPoint


def test_kpi_summary_returns_valid_shape(monkeypatch):
    def fake_kpi(date_from, date_to, store_id=None):
        return KpiSummaryResponse(
            date_from=date_from,
            date_to=date_to,
            store_id=store_id,
            total_sales=1_000_000.0,
            total_customers=50_000.0,
            avg_daily_sales=5_000.0,
            promo_days=30,
            open_days=180,
        )

    monkeypatch.setattr(kpi_router, "get_kpi_summary", fake_kpi)
    client = TestClient(app)
    resp = client.get("/api/v1/kpi/summary?date_from=2015-01-01&date_to=2015-07-31")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_sales"] == 1_000_000.0
    assert body["promo_days"] == 30
    assert body["date_from"] == "2015-01-01"


def test_kpi_summary_rejects_invalid_date_range():
    client = TestClient(app)
    resp = client.get("/api/v1/kpi/summary?date_from=2015-07-31&date_to=2015-01-01")
    assert resp.status_code == 400


def test_promo_impact_returns_list(monkeypatch):
    def fake_promo(store_id=None):
        return [
            PromoImpactPoint(store_id=1, promo_flag="promo", avg_sales=5000.0, avg_customers=500.0, num_days=90),
            PromoImpactPoint(store_id=1, promo_flag="no_promo", avg_sales=3000.0, avg_customers=300.0, num_days=90),
        ]

    monkeypatch.setattr(kpi_router, "get_promo_impact", fake_promo)
    client = TestClient(app)
    resp = client.get("/api/v1/kpi/promo-impact?store_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["promo_flag"] == "promo"
