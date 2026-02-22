from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from app.main import app
from backend.tests.diagnostics_auth_helpers import create_auth_headers
from src.etl.preflight_notification_outbox_registry import insert_outbox_event


def _prepare_env(monkeypatch, tmp_path: Path) -> str:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'diagnostics_auth_rbac.db').resolve()}"
    artifact_root = (tmp_path / "preflight_root").resolve()
    policy_path = (tmp_path / "preflight_alert_policies.yaml").resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PREFLIGHT_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("PREFLIGHT_ALERT_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("DIAGNOSTICS_AUTH_ENABLED", "1")
    monkeypatch.delenv("DIAGNOSTICS_AUTH_ALLOW_LEGACY_ACTOR", raising=False)

    with open(policy_path, "w", encoding="utf-8") as file:
        yaml.safe_dump({"version": "v1", "policies": []}, file, sort_keys=False)

    return database_url


def test_missing_api_key_returns_401(monkeypatch, tmp_path: Path):
    _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/api/v1/diagnostics/preflight/runs?limit=5")
    assert response.status_code == 401
    assert "x-api-key" in response.json()["detail"].lower()


def test_invalid_api_key_returns_401_without_key_echo(monkeypatch, tmp_path: Path):
    _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    invalid_key = "invalid-diagnostics-key"
    response = client.get(
        "/api/v1/diagnostics/preflight/runs?limit=5",
        headers={"X-API-Key": invalid_key},
    )
    assert response.status_code == 401
    assert invalid_key not in str(response.json())


def test_read_scope_works_and_mutation_requires_operate(monkeypatch, tmp_path: Path):
    database_url = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    read_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="rbac-read",
    )

    read_response = client.get("/api/v1/diagnostics/preflight/runs?limit=5", headers=read_headers)
    assert read_response.status_code == 200

    mutation_response = client.post(
        "/api/v1/diagnostics/preflight/alerts/silences",
        headers=read_headers,
        json={
            "ends_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "reason": "read-scope-should-not-mutate",
        },
    )
    assert mutation_response.status_code == 403


def test_operate_scope_can_mutate_and_audit_uses_authenticated_actor(monkeypatch, tmp_path: Path):
    database_url = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    operate_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read", "diagnostics:operate"],
        name="rbac-operator",
    )

    create_response = client.post(
        "/api/v1/diagnostics/preflight/alerts/silences",
        headers=operate_headers,
        json={
            "ends_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "reason": "operator-silence",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["created_by"] == "rbac-operator"

    audit_response = client.get("/api/v1/diagnostics/preflight/alerts/audit?limit=10", headers=operate_headers)
    assert audit_response.status_code == 200
    assert any(item["actor"] == "rbac-operator" for item in audit_response.json()["items"])


def test_manual_evaluate_requires_admin_scope(monkeypatch, tmp_path: Path):
    database_url = _prepare_env(monkeypatch, tmp_path)
    monkeypatch.setenv("PREFLIGHT_ALERTS_ALLOW_EVALUATE", "1")
    client = TestClient(app)

    operate_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read", "diagnostics:operate"],
        name="rbac-operator",
    )
    admin_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:admin"],
        name="rbac-admin",
    )

    forbidden_response = client.post("/api/v1/diagnostics/preflight/alerts/evaluate", headers=operate_headers)
    assert forbidden_response.status_code == 403

    success_response = client.post("/api/v1/diagnostics/preflight/alerts/evaluate", headers=admin_headers)
    assert success_response.status_code == 200


def test_notifications_endpoints_require_read_and_admin_scopes(monkeypatch, tmp_path: Path):
    database_url = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    read_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="rbac-read",
    )
    admin_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:admin"],
        name="rbac-admin",
    )
    dead_item = insert_outbox_event(
        {
            "event_type": "ALERT_FIRING",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "severity": "HIGH",
            "source_name": "train",
            "payload_json": {"event_id": "evt_test", "event_type": "ALERT_FIRING"},
            "channel_type": "webhook",
            "channel_target": "default_webhook",
            "status": "DEAD",
            "attempt_count": 2,
            "max_attempts": 3,
            "next_retry_at": datetime.now(timezone.utc),
            "last_error": "HTTP 500",
            "last_http_status": 500,
            "last_error_code": "HTTP_ERROR",
        },
        database_url=database_url,
    )

    outbox_response = client.get("/api/v1/diagnostics/preflight/notifications/outbox?limit=5", headers=read_headers)
    assert outbox_response.status_code == 200

    history_response = client.get("/api/v1/diagnostics/preflight/notifications/history?limit=5", headers=read_headers)
    assert history_response.status_code == 200

    stats_response = client.get("/api/v1/diagnostics/preflight/notifications/stats?days=30", headers=read_headers)
    assert stats_response.status_code == 200

    trends_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/trends?days=30&bucket=day",
        headers=read_headers,
    )
    assert trends_response.status_code == 200

    channels_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/channels?days=30",
        headers=read_headers,
    )
    assert channels_response.status_code == 200

    attempts_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/attempts?limit=5",
        headers=read_headers,
    )
    assert attempts_response.status_code == 200

    attempt_detail_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/attempts/nonexistent-attempt-id",
        headers=read_headers,
    )
    assert attempt_detail_response.status_code == 404

    forbidden_dispatch = client.post("/api/v1/diagnostics/preflight/notifications/dispatch", headers=read_headers)
    assert forbidden_dispatch.status_code == 403

    forbidden_replay = client.post(
        f"/api/v1/diagnostics/preflight/notifications/outbox/{dead_item['id']}/replay",
        headers=read_headers,
    )
    assert forbidden_replay.status_code == 403

    admin_dispatch = client.post(
        "/api/v1/diagnostics/preflight/notifications/dispatch?limit=5",
        headers=admin_headers,
    )
    assert admin_dispatch.status_code == 200

    admin_replay = client.post(
        f"/api/v1/diagnostics/preflight/notifications/outbox/{dead_item['id']}/replay",
        headers=admin_headers,
    )
    assert admin_replay.status_code == 200
    replay_payload = admin_replay.json()
    assert replay_payload["replayed_count"] == 1
    assert replay_payload["items"][0]["event_id"] == dead_item["event_id"]
    assert replay_payload["items"][0]["delivery_id"] != dead_item["delivery_id"]
