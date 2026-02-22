from fastapi.testclient import TestClient

import app.routers.diagnostics as diagnostics_router
from app.main import app


def _sample_record(source_name: str = "train") -> dict:
    return {
        "run_id": "20260221_190000",
        "created_at": "2026-02-21T19:00:00Z",
        "mode": "enforce",
        "source_name": source_name,
        "validation_status": "PASS",
        "semantic_status": "WARN",
        "final_status": "WARN",
        "blocked": False,
        "block_reason": None,
        "used_unified": True,
        "used_input_path": "/tmp/unified.csv",
        "artifact_dir": "/tmp/preflight/train",
        "validation_report_path": "/tmp/preflight/train/validation_report.json",
        "manifest_path": "/tmp/preflight/train/manifest.json",
    }


def test_diagnostics_list_endpoint(monkeypatch):
    client = TestClient(app)

    def fake_list(limit: int, source_name: str | None = None):
        assert limit == 20
        assert source_name == "train"
        return [_sample_record("train")]

    monkeypatch.setattr(diagnostics_router, "list_preflight_run_summaries", fake_list)
    response = client.get("/api/v1/diagnostics/preflight/runs?limit=20&source_name=train")

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 20
    assert payload["source_name"] == "train"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["run_id"] == "20260221_190000"


def test_diagnostics_details_endpoint(monkeypatch):
    client = TestClient(app)

    def fake_details(run_id: str):
        assert run_id == "20260221_190000"
        return {
            "run_id": "20260221_190000",
            "created_at": "2026-02-21T19:00:00Z",
            "mode": "enforce",
            "final_status": "WARN",
            "blocked": False,
            "records": [_sample_record("train"), _sample_record("store")],
        }

    monkeypatch.setattr(diagnostics_router, "get_preflight_run_details", fake_details)
    response = client.get("/api/v1/diagnostics/preflight/runs/20260221_190000")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "20260221_190000"
    assert payload["final_status"] == "WARN"
    assert len(payload["records"]) == 2


def test_diagnostics_latest_endpoint(monkeypatch):
    client = TestClient(app)

    def fake_latest():
        return {
            "run_id": "20260221_190100",
            "created_at": "2026-02-21T19:01:00Z",
            "mode": "report_only",
            "final_status": "PASS",
            "blocked": False,
            "records": [_sample_record("train")],
        }

    monkeypatch.setattr(diagnostics_router, "get_latest_preflight_run", fake_latest)
    response = client.get("/api/v1/diagnostics/preflight/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "20260221_190100"
    assert payload["final_status"] == "PASS"


def test_diagnostics_latest_source_endpoint(monkeypatch):
    client = TestClient(app)

    def fake_latest_source(source_name: str):
        assert source_name == "store"
        return _sample_record("store")

    monkeypatch.setattr(diagnostics_router, "get_latest_preflight_for_source", fake_latest_source)
    response = client.get("/api/v1/diagnostics/preflight/latest/store")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_name"] == "store"
