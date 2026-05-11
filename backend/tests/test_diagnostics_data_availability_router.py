from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from backend.tests.diagnostics_auth_helpers import configure_auth_database, create_auth_headers


def test_diagnostics_data_availability_response_shape(monkeypatch, tmp_path):
    database_url = configure_auth_database(monkeypatch, tmp_path, db_name="diagnostics_data_availability.db")
    headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="diagnostics-data-availability",
    )

    monkeypatch.setattr(
        "app.routers.diagnostics.get_data_availability",
        lambda: {
            "generated_at": datetime(2026, 2, 23, 18, 0, tzinfo=timezone.utc),
            "data_source_ids": [1],
            "datasets": [
                {
                    "table_name": "fact_sales_daily",
                    "rows": 10,
                    "min_date": datetime(2015, 7, 1, tzinfo=timezone.utc).date(),
                    "max_date": datetime(2015, 7, 31, tzinfo=timezone.utc).date(),
                }
            ],
        },
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/diagnostics/preflight/data-availability",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"].startswith("2026-02-23")
    assert payload["data_source_ids"] == [1]
    assert isinstance(payload["datasets"], list)
    assert payload["datasets"][0]["table_name"] == "fact_sales_daily"
    assert payload["datasets"][0]["rows"] == 10
