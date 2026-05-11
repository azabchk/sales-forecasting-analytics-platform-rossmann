"""Tests for the /stores endpoints: pagination, filtering, detail, and comparison."""

from fastapi.testclient import TestClient

import app.routers.stores as stores_router
from app.main import app
from app.schemas import StoreComparisonMetrics, StoreItem


def _fake_paginated(*, page=1, page_size=100, store_type=None, assortment=None):
    stores = [
        StoreItem(store_id=1, store_type="a", assortment="a"),
        StoreItem(store_id=2, store_type="b", assortment="b"),
        StoreItem(store_id=3, store_type="a", assortment="c"),
    ]
    filtered = [s for s in stores if (store_type is None or s.store_type == store_type)]
    return {"items": filtered, "total": len(filtered), "page": page, "page_size": page_size}


def test_get_stores_returns_paginated_shape(monkeypatch):
    monkeypatch.setattr(stores_router, "list_stores_paginated", _fake_paginated)
    client = TestClient(app)
    resp = client.get("/api/v1/stores?page=1&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body


def test_get_stores_filter_by_store_type(monkeypatch):
    monkeypatch.setattr(stores_router, "list_stores_paginated", _fake_paginated)
    client = TestClient(app)
    resp = client.get("/api/v1/stores?store_type=a")
    assert resp.status_code == 200
    body = resp.json()
    assert all(s["store_type"] == "a" for s in body["items"])


def test_get_store_by_id_returns_item(monkeypatch):
    monkeypatch.setattr(stores_router, "get_store_by_id", lambda sid: StoreItem(store_id=sid, store_type="c", assortment="a"))
    client = TestClient(app)
    resp = client.get("/api/v1/stores/42")
    assert resp.status_code == 200
    assert resp.json()["store_id"] == 42


def test_get_store_by_id_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(stores_router, "get_store_by_id", lambda _: None)
    client = TestClient(app)
    resp = client.get("/api/v1/stores/99999")
    assert resp.status_code == 404


def test_get_store_comparison_rejects_more_than_10():
    client = TestClient(app)
    ids = ",".join(str(i) for i in range(1, 12))
    resp = client.get(f"/api/v1/stores/comparison?store_ids={ids}&date_from=2015-01-01&date_to=2015-07-31")
    assert resp.status_code == 400


def test_get_store_comparison_rejects_invalid_date_range(monkeypatch):
    monkeypatch.setattr(stores_router, "get_store_comparison", lambda **_: [])
    client = TestClient(app)
    resp = client.get("/api/v1/stores/comparison?store_ids=1,2&date_from=2015-07-31&date_to=2015-01-01")
    assert resp.status_code == 400


def test_get_store_comparison_returns_valid_shape(monkeypatch):
    fake_stores = [
        StoreComparisonMetrics(store_id=1, store_type="a", assortment="a", competition_distance=100.0,
                               total_sales=50000.0, avg_daily_sales=600.0, total_customers=5000.0,
                               avg_daily_customers=60.0, promo_days=30, open_days=80, promo_uplift_pct=12.5),
        StoreComparisonMetrics(store_id=2, store_type="b", assortment="b", competition_distance=200.0,
                               total_sales=40000.0, avg_daily_sales=480.0, total_customers=4000.0,
                               avg_daily_customers=48.0, promo_days=20, open_days=80, promo_uplift_pct=8.0),
    ]
    monkeypatch.setattr(stores_router, "get_store_comparison", lambda **_: fake_stores)
    client = TestClient(app)
    resp = client.get("/api/v1/stores/comparison?store_ids=1,2&date_from=2015-01-01&date_to=2015-07-31")
    assert resp.status_code == 200
    body = resp.json()
    assert "stores" in body
    assert len(body["stores"]) == 2
    assert body["stores"][0]["store_id"] == 1
