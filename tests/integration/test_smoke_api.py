from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PREFLIGHT_ALERTS_SCHEDULER_ENABLED", "0")
os.environ.setdefault("PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED", "0")

if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = str(os.getenv("TEST_DATABASE_URL"))
else:
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.main import app  # noqa: E402


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload.get("status") == "ok"


def test_contracts_endpoint() -> None:
    response = client.get("/api/v1/contracts")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_data_sources_endpoint() -> None:
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("Set TEST_DATABASE_URL to run DB-backed smoke endpoint assertions.")

    response = client.get("/api/v1/data-sources")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
