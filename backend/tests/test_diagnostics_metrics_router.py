from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from backend.tests.diagnostics_auth_helpers import create_auth_headers
from src.etl.preflight_alert_registry import (
    acquire_scheduler_lease,
    create_silence,
    insert_alert_audit_event,
    upsert_alert_state,
)
from src.etl.preflight_notification_attempt_registry import (
    complete_delivery_attempt,
    insert_delivery_attempt_started,
)
from src.etl.preflight_notification_outbox_registry import insert_outbox_event
from src.etl.preflight_registry import insert_preflight_run


def _configure_env(monkeypatch, tmp_path: Path, *, db_name: str) -> str:
    database_path = (tmp_path / db_name).resolve()
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DIAGNOSTICS_AUTH_ENABLED", "1")
    monkeypatch.setenv("PREFLIGHT_ALERTS_SCHEDULER_LEASE_NAME", "preflight_alerts_scheduler")
    monkeypatch.delenv("DIAGNOSTICS_METRICS_AUTH_DISABLED", raising=False)
    return database_url


def _seed_metrics_data(database_url: str) -> None:
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)

    insert_preflight_run(
        {
            "run_id": "run_1",
            "source_name": "train",
            "created_at": datetime(2026, 2, 20, 8, 0, tzinfo=timezone.utc),
            "mode": "off",
            "validation_status": "PASS",
            "semantic_status": "PASS",
            "final_status": "PASS",
            "used_input_path": "/tmp/train.csv",
            "used_unified": False,
            "artifact_dir": None,
            "validation_report_path": None,
            "manifest_path": None,
            "summary_json": {},
            "blocked": False,
            "block_reason": None,
        },
        database_url=database_url,
    )
    insert_preflight_run(
        {
            "run_id": "run_1",
            "source_name": "store",
            "created_at": datetime(2026, 2, 20, 8, 0, tzinfo=timezone.utc),
            "mode": "enforce",
            "validation_status": "PASS",
            "semantic_status": "FAIL",
            "final_status": "FAIL",
            "used_input_path": "/tmp/store.csv",
            "used_unified": True,
            "artifact_dir": None,
            "validation_report_path": None,
            "manifest_path": None,
            "summary_json": {},
            "blocked": True,
            "block_reason": "semantic_fail",
        },
        database_url=database_url,
    )
    insert_preflight_run(
        {
            "run_id": "run_2",
            "source_name": "train",
            "created_at": datetime(2026, 2, 21, 10, 30, tzinfo=timezone.utc),
            "mode": "report_only",
            "validation_status": "PASS",
            "semantic_status": "WARN",
            "final_status": "WARN",
            "used_input_path": "/tmp/train_v2.csv",
            "used_unified": False,
            "artifact_dir": None,
            "validation_report_path": None,
            "manifest_path": None,
            "summary_json": {},
            "blocked": False,
            "block_reason": None,
        },
        database_url=database_url,
    )

    upsert_alert_state(
        {
            "policy_id": "blocked_runs_any",
            "status": "FIRING",
            "severity": "HIGH",
            "source_name": "train",
            "first_seen_at": now - timedelta(hours=4),
            "last_seen_at": now - timedelta(minutes=15),
            "consecutive_breaches": 2,
            "current_value": 2.0,
            "threshold": 1.0,
            "message": "Blocked runs detected",
            "evaluation_context_json": {},
            "policy_snapshot_json": {},
            "updated_at": now - timedelta(minutes=15),
        },
        database_url=database_url,
    )
    upsert_alert_state(
        {
            "policy_id": "warn_spike",
            "status": "PENDING",
            "severity": "MEDIUM",
            "source_name": "store",
            "first_seen_at": now - timedelta(hours=2),
            "last_seen_at": now - timedelta(minutes=5),
            "consecutive_breaches": 1,
            "current_value": 0.5,
            "threshold": 0.3,
            "message": "Warn spike",
            "evaluation_context_json": {},
            "policy_snapshot_json": {},
            "updated_at": now - timedelta(minutes=5),
        },
        database_url=database_url,
    )

    insert_alert_audit_event(
        {
            "alert_id": "blocked_runs_any",
            "event_type": "FIRING",
            "actor": "system:scheduler",
            "event_at": now - timedelta(minutes=15),
            "payload_json": {"status": "FIRING"},
        },
        database_url=database_url,
    )
    insert_alert_audit_event(
        {
            "alert_id": "blocked_runs_any",
            "event_type": "RESOLVED",
            "actor": "system:scheduler",
            "event_at": now - timedelta(minutes=1),
            "payload_json": {"status": "RESOLVED"},
        },
        database_url=database_url,
    )

    create_silence(
        {
            "policy_id": "blocked_runs_any",
            "source_name": "train",
            "severity": "HIGH",
            "rule_id": None,
            "starts_at": now - timedelta(hours=1),
            "ends_at": now + timedelta(hours=1),
            "reason": "maintenance",
            "created_by": "qa",
            "created_at": now - timedelta(hours=1),
        },
        database_url=database_url,
    )

    acquire_scheduler_lease(
        lease_name="preflight_alerts_scheduler:alerts",
        owner_id="scheduler-1",
        lease_ttl_seconds=120,
        now=now - timedelta(seconds=30),
        database_url=database_url,
    )
    acquire_scheduler_lease(
        lease_name="preflight_alerts_scheduler:notifications",
        owner_id="scheduler-1",
        lease_ttl_seconds=120,
        now=now - timedelta(seconds=10),
        database_url=database_url,
    )

    insert_outbox_event(
        {
            "id": "n1",
            "event_id": "evt_1",
            "delivery_id": "del_1",
            "event_type": "ALERT_FIRING",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "status": "SENT",
            "attempt_count": 1,
            "max_attempts": 5,
            "next_retry_at": now,
            "created_at": now - timedelta(minutes=30),
            "updated_at": now - timedelta(minutes=29),
            "sent_at": now - timedelta(minutes=29),
            "payload_json": {"authorization": "Bearer super-secret-token", "x-api-key": "top-secret-key"},
        },
        database_url=database_url,
    )
    insert_outbox_event(
        {
            "id": "n2",
            "event_id": "evt_2",
            "delivery_id": "del_2",
            "event_type": "ALERT_FIRING",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "status": "RETRYING",
            "attempt_count": 1,
            "max_attempts": 5,
            "next_retry_at": now + timedelta(minutes=5),
            "created_at": now - timedelta(minutes=15),
            "updated_at": now - timedelta(minutes=1),
            "payload_json": {},
        },
        database_url=database_url,
    )
    insert_outbox_event(
        {
            "id": "n3",
            "event_id": "evt_3",
            "delivery_id": "del_3",
            "replayed_from_id": "n1",
            "event_type": "ALERT_RESOLVED",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "channel_type": "webhook",
            "channel_target": "channel_b",
            "status": "SENT",
            "attempt_count": 1,
            "max_attempts": 5,
            "next_retry_at": now,
            "created_at": now - timedelta(minutes=5),
            "updated_at": now - timedelta(minutes=4),
            "sent_at": now - timedelta(minutes=4),
            "payload_json": {},
        },
        database_url=database_url,
    )

    attempt_1 = insert_delivery_attempt_started(
        {
            "attempt_id": "att_1",
            "outbox_item_id": "n1",
            "event_id": "evt_1",
            "delivery_id": "del_1a",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "event_type": "ALERT_FIRING",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "source_name": "train",
            "attempt_number": 1,
            "started_at": now - timedelta(minutes=30),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_1["attempt_id"]),
        attempt_status="SENT",
        duration_ms=1000,
        http_status=204,
        completed_at=now - timedelta(minutes=29, seconds=59),
        database_url=database_url,
    )

    attempt_2 = insert_delivery_attempt_started(
        {
            "attempt_id": "att_2",
            "outbox_item_id": "n2",
            "event_id": "evt_2",
            "delivery_id": "del_2a",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "event_type": "ALERT_FIRING",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "source_name": "train",
            "attempt_number": 1,
            "started_at": now - timedelta(minutes=14),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_2["attempt_id"]),
        attempt_status="RETRY",
        duration_ms=200,
        http_status=503,
        error_code="HTTP_ERROR",
        error_message_safe="HTTP 503",
        completed_at=now - timedelta(minutes=13, seconds=59),
        database_url=database_url,
    )

    attempt_3 = insert_delivery_attempt_started(
        {
            "attempt_id": "att_3",
            "outbox_item_id": "n2",
            "event_id": "evt_2",
            "delivery_id": "del_2b",
            "channel_type": "webhook",
            "channel_target": "channel_b",
            "event_type": "ALERT_RESOLVED",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "source_name": "store",
            "attempt_number": 2,
            "started_at": now - timedelta(minutes=10),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_3["attempt_id"]),
        attempt_status="DEAD",
        duration_ms=3000,
        http_status=503,
        error_code="HTTP_ERROR",
        error_message_safe="HTTP 503",
        completed_at=now - timedelta(minutes=9, seconds=57),
        database_url=database_url,
    )


def test_metrics_endpoint_auth_and_rbac(monkeypatch, tmp_path: Path):
    database_url = _configure_env(monkeypatch, tmp_path, db_name="diagnostics_metrics_auth.db")
    client = TestClient(app)

    unauthorized = client.get("/api/v1/diagnostics/metrics")
    assert unauthorized.status_code == 401

    operate_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:operate"],
        name="diag-operator",
    )
    forbidden = client.get("/api/v1/diagnostics/metrics", headers=operate_headers)
    assert forbidden.status_code == 403

    read_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="diag-reader",
    )
    allowed = client.get("/api/v1/diagnostics/metrics", headers=read_headers)
    assert allowed.status_code == 200
    assert allowed.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in allowed.headers["content-type"]


def test_metrics_endpoint_can_disable_auth_for_local_demo(monkeypatch, tmp_path: Path):
    _configure_env(monkeypatch, tmp_path, db_name="diagnostics_metrics_noauth.db")
    monkeypatch.setenv("DIAGNOSTICS_METRICS_AUTH_DISABLED", "1")

    client = TestClient(app)
    response = client.get("/api/v1/diagnostics/metrics")
    assert response.status_code == 200
    assert "preflight_runs_total" in response.text


def test_metrics_endpoint_outputs_expected_series(monkeypatch, tmp_path: Path):
    database_url = _configure_env(monkeypatch, tmp_path, db_name="diagnostics_metrics_data.db")
    _seed_metrics_data(database_url)

    headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="diag-reader",
    )

    client = TestClient(app)
    response = client.get("/api/v1/diagnostics/metrics", headers=headers)
    assert response.status_code == 200
    payload = response.text

    assert "# HELP preflight_runs_total" in payload
    assert 'preflight_runs_total{final_status="PASS",mode="off",source_name="train"} 1' in payload
    assert 'preflight_runs_total{final_status="FAIL",mode="enforce",source_name="store"} 1' in payload
    assert 'preflight_runs_total{final_status="WARN",mode="report_only",source_name="train"} 1' in payload

    assert 'preflight_blocked_total{source_name="store"} 1' in payload
    assert 'preflight_alerts_active{severity="HIGH",status="FIRING"} 1' in payload
    assert 'preflight_alerts_active{severity="MEDIUM",status="PENDING"} 1' in payload
    assert 'preflight_alert_transitions_total{event_type="FIRING"} 1' in payload
    assert 'preflight_alert_transitions_total{event_type="RESOLVED"} 1' in payload
    assert "preflight_alert_silences_active 1" in payload

    # Attempt telemetry must come from immutable attempt ledger.
    assert (
        'preflight_notifications_attempts_total{attempt_status="DEAD",channel_target="channel_b",event_type="ALERT_RESOLVED"} 1'
        in payload
    )
    assert (
        'preflight_notifications_attempts_total{attempt_status="RETRY",channel_target="channel_a",event_type="ALERT_FIRING"} 1'
        in payload
    )
    assert "preflight_notifications_outbox_dead 0" in payload

    assert "preflight_notifications_delivery_latency_ms_count 3" in payload
    assert "preflight_notifications_delivery_latency_ms_sum 4200" in payload
    assert 'preflight_notifications_delivery_latency_ms_bucket{le="+Inf"} 3' in payload

    assert "preflight_notifications_outbox_pending 1" in payload
    assert "preflight_notifications_replays_total 1" in payload
    assert "preflight_notifications_dispatch_errors_total 2" in payload
    assert "preflight_metrics_render_errors_total" in payload

    # Metrics text must not expose secrets from payloads/headers.
    lowered = payload.lower()
    assert "super-secret-token" not in lowered
    assert "top-secret-key" not in lowered
    assert "x-api-key" not in lowered
    assert "authorization" not in lowered


def test_metrics_endpoint_empty_state_is_valid(monkeypatch, tmp_path: Path):
    database_url = _configure_env(monkeypatch, tmp_path, db_name="diagnostics_metrics_empty.db")
    headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="diag-reader",
    )

    client = TestClient(app)
    response = client.get("/api/v1/diagnostics/metrics", headers=headers)
    assert response.status_code == 200
    payload = response.text

    assert "# HELP preflight_runs_total" in payload
    assert "# HELP preflight_notifications_attempts_total" in payload
    assert "preflight_notifications_outbox_pending 0" in payload
    assert "preflight_notifications_outbox_dead 0" in payload
    assert "preflight_notifications_delivery_latency_ms_count 0" in payload
