from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_has_security_and_request_headers():
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"


def test_contract_by_id_returns_404_on_file_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.services.contract_service.get_contract",
        lambda _: (_ for _ in ()).throw(FileNotFoundError("not found")),
    )
    client = TestClient(app)
    resp = client.get("/api/v1/contracts/missing_contract")
    assert resp.status_code == 404


def test_contract_versions_returns_404_when_contract_missing(monkeypatch):
    monkeypatch.setattr(
        "app.services.contract_service.get_contract",
        lambda _: None,
    )
    client = TestClient(app)
    resp = client.get("/api/v1/contracts/no_such/versions")
    assert resp.status_code == 404
