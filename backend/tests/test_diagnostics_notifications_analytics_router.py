from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from backend.tests.diagnostics_auth_helpers import create_auth_headers
from src.etl.preflight_notification_attempt_registry import (
    complete_delivery_attempt,
    insert_delivery_attempt_started,
)
from src.etl.preflight_notification_outbox_registry import insert_outbox_event


def _seed_notification_data(monkeypatch, tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    db_path = tmp_path / "diagnostics_notifications_analytics.db"
    database_url = f"sqlite+pysqlite:///{db_path.resolve()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DIAGNOSTICS_AUTH_ENABLED", "1")

    headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="notifications-analytics-reader",
    )

    # Outbox state for backlog/pending view.
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
            "next_retry_at": datetime(2026, 2, 20, 10, 1, tzinfo=timezone.utc),
            "created_at": datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 20, 10, 5, tzinfo=timezone.utc),
            "sent_at": datetime(2026, 2, 20, 10, 5, tzinfo=timezone.utc),
            "payload_json": {"event_id": "evt_1"},
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
            "status": "DEAD",
            "attempt_count": 2,
            "max_attempts": 5,
            "next_retry_at": datetime(2026, 2, 20, 12, 1, tzinfo=timezone.utc),
            "created_at": datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 20, 12, 2, tzinfo=timezone.utc),
            "last_http_status": 503,
            "last_error_code": "HTTP_ERROR",
            "last_error": "HTTP 503",
            "payload_json": {"event_id": "evt_2"},
        },
        database_url=database_url,
    )
    insert_outbox_event(
        {
            "id": "n3",
            "event_id": "evt_3",
            "delivery_id": "del_3",
            "event_type": "ALERT_RESOLVED",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "channel_type": "webhook",
            "channel_target": "channel_b",
            "status": "RETRYING",
            "attempt_count": 1,
            "max_attempts": 5,
            "next_retry_at": datetime(2026, 2, 21, 9, 5, tzinfo=timezone.utc),
            "created_at": datetime(2026, 2, 21, 9, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 21, 9, 1, tzinfo=timezone.utc),
            "last_error_code": "NETWORK_ERROR",
            "last_error": "network_error",
            "payload_json": {"event_id": "evt_3"},
        },
        database_url=database_url,
    )
    insert_outbox_event(
        {
            "id": "n4",
            "event_id": "evt_4",
            "delivery_id": "del_4",
            "replayed_from_id": "n2",
            "event_type": "ALERT_RESOLVED",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "status": "SENT",
            "attempt_count": 3,
            "max_attempts": 5,
            "next_retry_at": datetime(2026, 2, 22, 9, 1, tzinfo=timezone.utc),
            "created_at": datetime(2026, 2, 22, 9, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 22, 9, 1, tzinfo=timezone.utc),
            "sent_at": datetime(2026, 2, 22, 9, 1, tzinfo=timezone.utc),
            "payload_json": {"event_id": "evt_4"},
        },
        database_url=database_url,
    )

    # Attempt-level telemetry (exact source for retry/latency analytics).
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
            "started_at": datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_1["attempt_id"]),
        attempt_status="SENT",
        completed_at=datetime(2026, 2, 20, 10, 0, 5, tzinfo=timezone.utc),
        duration_ms=5000,
        http_status=204,
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
            "started_at": datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_2["attempt_id"]),
        attempt_status="RETRY",
        completed_at=datetime(2026, 2, 20, 12, 0, 1, 500000, tzinfo=timezone.utc),
        duration_ms=1500,
        http_status=503,
        error_code="HTTP_ERROR",
        error_message_safe="HTTP 503",
        database_url=database_url,
    )

    attempt_3 = insert_delivery_attempt_started(
        {
            "attempt_id": "att_3",
            "outbox_item_id": "n2",
            "event_id": "evt_2",
            "delivery_id": "del_2b",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "event_type": "ALERT_FIRING",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "source_name": "train",
            "attempt_number": 2,
            "started_at": datetime(2026, 2, 20, 12, 2, tzinfo=timezone.utc),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_3["attempt_id"]),
        attempt_status="DEAD",
        completed_at=datetime(2026, 2, 20, 12, 2, 1, tzinfo=timezone.utc),
        duration_ms=1000,
        http_status=503,
        error_code="HTTP_ERROR",
        error_message_safe="HTTP 503",
        database_url=database_url,
    )

    attempt_4 = insert_delivery_attempt_started(
        {
            "attempt_id": "att_4",
            "outbox_item_id": "n3",
            "event_id": "evt_3",
            "delivery_id": "del_3a",
            "channel_type": "webhook",
            "channel_target": "channel_b",
            "event_type": "ALERT_RESOLVED",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "source_name": "store",
            "attempt_number": 1,
            "started_at": datetime(2026, 2, 21, 9, 0, tzinfo=timezone.utc),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_4["attempt_id"]),
        attempt_status="RETRY",
        completed_at=datetime(2026, 2, 21, 9, 0, 2, tzinfo=timezone.utc),
        duration_ms=2000,
        error_code="NETWORK_ERROR",
        error_message_safe="network_error",
        database_url=database_url,
    )

    attempt_5 = insert_delivery_attempt_started(
        {
            "attempt_id": "att_5",
            "outbox_item_id": "n4",
            "event_id": "evt_4",
            "delivery_id": "del_4a",
            "replayed_from_id": "n2",
            "channel_type": "webhook",
            "channel_target": "channel_a",
            "event_type": "ALERT_RESOLVED",
            "alert_id": "blocked_runs_any",
            "policy_id": "blocked_runs_any",
            "source_name": "train",
            "attempt_number": 1,
            "started_at": datetime(2026, 2, 22, 9, 0, tzinfo=timezone.utc),
        },
        database_url=database_url,
    )
    complete_delivery_attempt(
        str(attempt_5["attempt_id"]),
        attempt_status="SENT",
        completed_at=datetime(2026, 2, 22, 9, 0, 1, tzinfo=timezone.utc),
        duration_ms=1000,
        http_status=204,
        database_url=database_url,
    )

    return TestClient(app), headers


def test_notification_stats_aggregation(monkeypatch, tmp_path: Path):
    client, headers = _seed_notification_data(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/notifications/stats?date_from=2026-02-20&date_to=2026-02-22",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_events"] == 5
    assert payload["sent_count"] == 2
    assert payload["dead_count"] == 1
    assert payload["retry_count"] == 2
    assert payload["pending_count"] == 1
    assert payload["replay_count"] == 1
    assert abs(payload["success_rate"] - (2 / 3)) < 1e-6
    assert abs(payload["avg_delivery_latency_ms"] - 2100.0) < 1e-6
    assert abs(payload["p95_delivery_latency_ms"] - 4400.0) < 1e-6


def test_notification_trends_bucket_by_day(monkeypatch, tmp_path: Path):
    client, headers = _seed_notification_data(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/notifications/trends?date_from=2026-02-20&date_to=2026-02-22&bucket=day",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["bucket"] == "day"

    by_day = {item["bucket_start"][:10]: item for item in payload["items"]}
    assert by_day["2026-02-20"]["sent_count"] == 1
    assert by_day["2026-02-20"]["dead_count"] == 1
    assert by_day["2026-02-20"]["retry_count"] == 1
    assert by_day["2026-02-21"]["retry_count"] == 1
    assert by_day["2026-02-22"]["sent_count"] == 1
    assert by_day["2026-02-22"]["retry_count"] == 0
    assert by_day["2026-02-22"]["replay_count"] == 1


def test_notification_channels_summary(monkeypatch, tmp_path: Path):
    client, headers = _seed_notification_data(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/notifications/channels?date_from=2026-02-20&date_to=2026-02-22",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()

    by_channel = {item["channel_target"]: item for item in payload["items"]}
    channel_a = by_channel["channel_a"]
    assert channel_a["sent_count"] == 2
    assert channel_a["dead_count"] == 1
    assert channel_a["pending_count"] == 0
    assert channel_a["retry_count"] == 1
    assert channel_a["replay_count"] == 1
    assert abs(channel_a["success_rate"] - (2 / 3)) < 1e-6
    assert abs(channel_a["avg_delivery_latency_ms"] - 2125.0) < 1e-6
    assert channel_a["last_sent_at"].startswith("2026-02-22")
    assert channel_a["top_error_codes"][0]["error_code"] == "HTTP_ERROR"
    assert channel_a["top_error_codes"][0]["count"] == 2

    channel_b = by_channel["channel_b"]
    assert channel_b["sent_count"] == 0
    assert channel_b["dead_count"] == 0
    assert channel_b["pending_count"] == 1
    assert channel_b["retry_count"] == 1
    assert channel_b["top_error_codes"][0]["error_code"] == "NETWORK_ERROR"


def test_notification_attempts_endpoints(monkeypatch, tmp_path: Path):
    client, headers = _seed_notification_data(monkeypatch, tmp_path)

    attempts_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/attempts?date_from=2026-02-20&date_to=2026-02-22&limit=10",
        headers=headers,
    )
    assert attempts_response.status_code == 200
    attempts_payload = attempts_response.json()
    assert attempts_payload["limit"] == 10
    assert len(attempts_payload["items"]) == 5
    first_attempt = attempts_payload["items"][0]
    assert first_attempt["attempt_id"]

    detail_response = client.get(
        f"/api/v1/diagnostics/preflight/notifications/attempts/{first_attempt['attempt_id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["attempt_id"] == first_attempt["attempt_id"]
    assert detail_payload["duration_ms"] is not None
    assert detail_payload["duration_ms"] >= 0


def test_notification_stats_empty_window_and_invalid_filters(monkeypatch, tmp_path: Path):
    client, headers = _seed_notification_data(monkeypatch, tmp_path)

    empty_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/stats?date_from=2020-01-01&date_to=2020-01-02",
        headers=headers,
    )
    assert empty_response.status_code == 200
    empty_payload = empty_response.json()
    assert empty_payload["total_events"] == 0
    assert empty_payload["avg_delivery_latency_ms"] is None
    assert empty_payload["p95_delivery_latency_ms"] is None

    invalid_response = client.get(
        "/api/v1/diagnostics/preflight/notifications/stats?status=INVALID",
        headers=headers,
    )
    assert invalid_response.status_code == 400

    invalid_attempt_status = client.get(
        "/api/v1/diagnostics/preflight/notifications/attempts?attempt_status=NOT_A_STATUS",
        headers=headers,
    )
    assert invalid_attempt_status.status_code == 400
