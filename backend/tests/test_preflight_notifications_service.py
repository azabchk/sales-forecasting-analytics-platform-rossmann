from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
import yaml

import app.services.preflight_notifications_service as notification_service
from app.services.preflight_notifications_service import (
    EVENT_ALERT_FIRING,
    EVENT_ALERT_RESOLVED,
    WebhookDeliveryResult,
    _sign_payload,
    dispatch_due_notifications,
    enqueue_alert_transition_notifications,
    get_notification_history,
    get_notification_outbox,
    replay_notification_outbox_item,
    verify_webhook_signature,
)
from src.etl.preflight_notification_attempt_registry import query_delivery_attempts
from src.etl.preflight_notification_outbox_registry import list_outbox_history


def _configure_env(monkeypatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "notifications.db"
    channels_path = tmp_path / "channels.yaml"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve()}")
    monkeypatch.setenv("PREFLIGHT_NOTIFICATION_CHANNELS_PATH", str(channels_path.resolve()))
    monkeypatch.setenv("PREFLIGHT_ALERTS_WEBHOOK_URL", "https://example.local/webhook")
    monkeypatch.setenv("PREFLIGHT_ALERTS_WEBHOOK_SIGNING_SECRET", "super-secret-token")
    return channels_path


def _write_channels(path: Path, *, max_attempts: int = 3, backoff_seconds: int = 10) -> None:
    with open(path, "w", encoding="utf-8") as file:
        yaml.safe_dump(
            {
                "version": "v1",
                "channels": [
                    {
                        "id": "default_webhook",
                        "type": "webhook",
                        "enabled": True,
                        "target_url_env": "PREFLIGHT_ALERTS_WEBHOOK_URL",
                        "timeout_seconds": 5,
                        "max_attempts": max_attempts,
                        "backoff_seconds": backoff_seconds,
                        "signing_secret_env": "PREFLIGHT_ALERTS_WEBHOOK_SIGNING_SECRET",
                        "enabled_event_types": ["ALERT_FIRING", "ALERT_RESOLVED"],
                    }
                ],
            },
            file,
            sort_keys=False,
        )


def test_enqueue_outbox_on_firing_transition(monkeypatch, tmp_path: Path):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path)

    result = enqueue_alert_transition_notifications(
        event_type=EVENT_ALERT_FIRING,
        alert_id="blocked_runs_any",
        policy_id="blocked_runs_any",
        severity="HIGH",
        source_name="train",
        message="Blocked runs detected.",
        current_value=2.0,
        threshold=1.0,
        previous_status="PENDING",
        current_status="FIRING",
        evaluated_at=datetime.now(timezone.utc),
        context={"window_days": 30},
    )

    assert result["enqueued_count"] == 1
    item = result["items"][0]
    assert item["event_type"] == EVENT_ALERT_FIRING
    assert item["status"] == "PENDING"
    assert item["channel_target"] == "default_webhook"

    outbox = get_notification_outbox(limit=10)
    assert outbox["items"][0]["event_type"] == EVENT_ALERT_FIRING
    assert "https://example.local/webhook" not in str(outbox)
    assert "super-secret-token" not in str(outbox)


def test_dispatch_webhook_success_marks_sent(monkeypatch, tmp_path: Path):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path)

    enqueue_alert_transition_notifications(
        event_type=EVENT_ALERT_FIRING,
        alert_id="blocked_runs_any",
        policy_id="blocked_runs_any",
        severity="HIGH",
        source_name="train",
        message="Blocked runs detected.",
        current_value=1.0,
        threshold=1.0,
        previous_status="PENDING",
        current_status="FIRING",
        evaluated_at=datetime.now(timezone.utc),
        context={},
    )

    summary = dispatch_due_notifications(
        webhook_sender=lambda _channel, _payload: WebhookDeliveryResult(
            success=True,
            retryable=False,
            status_code=204,
            error=None,
        )
    )
    assert summary["processed_count"] == 1
    assert summary["sent_count"] == 1
    assert summary["dead_count"] == 0

    history = get_notification_history(limit=10)
    assert history["items"][0]["status"] == "SENT"
    assert history["items"][0]["attempt_count"] == 1
    assert history["items"][0]["sent_at"] is not None

    attempts = query_delivery_attempts(limit=10)
    assert len(attempts) == 1
    assert attempts[0]["attempt_status"] == "SENT"
    assert attempts[0]["duration_ms"] is not None
    assert attempts[0]["duration_ms"] >= 0
    assert attempts[0]["http_status"] == 204


def test_dispatch_webhook_failure_retries_then_dead(monkeypatch, tmp_path: Path):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path, max_attempts=2, backoff_seconds=1)

    enqueue_alert_transition_notifications(
        event_type=EVENT_ALERT_RESOLVED,
        alert_id="blocked_runs_any",
        policy_id="blocked_runs_any",
        severity="HIGH",
        source_name="train",
        message="Condition resolved.",
        current_value=0.0,
        threshold=1.0,
        previous_status="FIRING",
        current_status="RESOLVED",
        evaluated_at=datetime.now(timezone.utc),
        context={},
    )

    first_summary = dispatch_due_notifications(
        due_at=datetime.now(timezone.utc),
        webhook_sender=lambda _channel, _payload: WebhookDeliveryResult(
            success=False,
            retryable=True,
            status_code=503,
            error="HTTP 503",
            error_code="HTTP_ERROR",
        ),
    )
    assert first_summary["processed_count"] == 1
    assert first_summary["retrying_count"] == 1
    assert first_summary["dead_count"] == 0

    outbox_rows = list_outbox_history(limit=10)
    assert outbox_rows[0]["status"] == "RETRYING"
    assert outbox_rows[0]["attempt_count"] == 1

    attempts_after_first = query_delivery_attempts(limit=10)
    assert len(attempts_after_first) == 1
    assert attempts_after_first[0]["attempt_status"] == "RETRY"
    assert attempts_after_first[0]["error_code"] == "HTTP_ERROR"
    assert attempts_after_first[0]["duration_ms"] is not None
    assert attempts_after_first[0]["duration_ms"] >= 0

    second_summary = dispatch_due_notifications(
        due_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        webhook_sender=lambda _channel, _payload: WebhookDeliveryResult(
            success=False,
            retryable=True,
            status_code=503,
            error="HTTP 503",
            error_code="HTTP_ERROR",
        ),
    )
    assert second_summary["processed_count"] == 1
    assert second_summary["dead_count"] == 1

    history = get_notification_history(limit=10)
    assert history["items"][0]["status"] == "DEAD"
    assert history["items"][0]["attempt_count"] == 2

    attempts = query_delivery_attempts(limit=10)
    statuses = [item["attempt_status"] for item in attempts]
    assert statuses.count("RETRY") == 1
    assert statuses.count("DEAD") == 1


def test_signed_headers_present_and_signature_is_verifiable(monkeypatch, tmp_path: Path):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path)

    captured: dict[str, object] = {}

    class _Response:
        status = 204

        def getcode(self):
            return self.status

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["body"] = request.data
        return _Response()

    monkeypatch.setattr(notification_service.urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(notification_service, "_current_unix_timestamp", lambda: "1700000000")

    channel = notification_service.NotificationChannel(
        id="default_webhook",
        channel_type="webhook",
        enabled=True,
        target_url="https://example.local/webhook",
        timeout_seconds=5,
        max_attempts=5,
        backoff_seconds=10,
        signing_secret_env="PREFLIGHT_ALERTS_WEBHOOK_SIGNING_SECRET",
        enabled_event_types=(EVENT_ALERT_FIRING, EVENT_ALERT_RESOLVED),
    )
    payload = {
        "version": "v1",
        "event_id": "evt_123",
        "event_type": EVENT_ALERT_FIRING,
        "alert": {"policy_id": "blocked_runs_any"},
        "delivery": {"delivery_id": "del_123"},
    }
    result = notification_service._send_webhook_request(channel, payload)
    assert result.success is True
    assert result.status_code == 204

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["x-preflight-delivery-id"] == "del_123"
    assert headers["x-preflight-event-id"] == "evt_123"
    assert headers["x-preflight-timestamp"] == "1700000000"
    assert headers["x-preflight-signature"].startswith("sha256=")

    body = captured["body"]
    assert isinstance(body, bytes)
    assert verify_webhook_signature(
        timestamp="1700000000",
        body_bytes=body,
        signature=headers["x-preflight-signature"],
        secret="super-secret-token",
    )


def test_hmac_signature_is_deterministic_for_same_payload_and_timestamp():
    payload = json.dumps({"a": 1, "b": "x"}, separators=(",", ":")).encode("utf-8")
    sig1 = _sign_payload("1700000000", payload, "super-secret-token")
    sig2 = _sign_payload("1700000000", payload, "super-secret-token")
    assert sig1 == sig2
    assert verify_webhook_signature(
        timestamp="1700000000",
        body_bytes=payload,
        signature=sig1,
        secret="super-secret-token",
    )


def test_replay_clones_delivery_with_same_event_id_and_new_delivery_id(monkeypatch, tmp_path: Path):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path)

    enqueue_result = enqueue_alert_transition_notifications(
        event_type=EVENT_ALERT_FIRING,
        alert_id="blocked_runs_any",
        policy_id="blocked_runs_any",
        severity="HIGH",
        source_name="train",
        message="Blocked runs detected.",
        current_value=3.0,
        threshold=1.0,
        previous_status="PENDING",
        current_status="FIRING",
        evaluated_at=datetime.now(timezone.utc),
        context={},
    )
    original_item = enqueue_result["items"][0]
    dispatch_due_notifications(
        webhook_sender=lambda _channel, _payload: WebhookDeliveryResult(
            success=True,
            retryable=False,
            status_code=204,
            error=None,
        )
    )
    sent_item = get_notification_history(limit=1)["items"][0]
    assert sent_item["status"] == "SENT"

    replay_result = replay_notification_outbox_item(
        item_id=sent_item["id"],
        actor="diag-admin",
    )
    assert replay_result["replayed_count"] == 1
    replayed_item = replay_result["items"][0]

    assert replayed_item["event_id"] == sent_item["event_id"]
    assert replayed_item["delivery_id"] != sent_item["delivery_id"]
    assert replayed_item["replayed_from_id"] == sent_item["id"]
    assert replayed_item["status"] == "PENDING"
    assert replayed_item["attempt_count"] == 0


def test_backward_compatibility_when_legacy_outbox_rows_miss_event_and_delivery_ids(monkeypatch, tmp_path: Path):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path)

    enqueue_result = enqueue_alert_transition_notifications(
        event_type=EVENT_ALERT_FIRING,
        alert_id="blocked_runs_any",
        policy_id="blocked_runs_any",
        severity="HIGH",
        source_name="train",
        message="Blocked runs detected.",
        current_value=1.0,
        threshold=1.0,
        previous_status="PENDING",
        current_status="FIRING",
        evaluated_at=datetime.now(timezone.utc),
        context={},
    )
    item_id = enqueue_result["items"][0]["id"]

    engine = sa.create_engine(str(os.environ["DATABASE_URL"]), future=True)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE preflight_notification_outbox "
                "SET event_id = NULL, delivery_id = NULL "
                "WHERE id = :item_id"
            ),
            {"item_id": item_id},
        )

    summary = dispatch_due_notifications(
        webhook_sender=lambda _channel, _payload: WebhookDeliveryResult(
            success=True,
            retryable=False,
            status_code=204,
            error=None,
        ),
    )
    assert summary["processed_count"] == 1
    assert summary["sent_count"] == 1

    history = get_notification_history(limit=10)
    assert history["items"][0]["event_id"]
    assert history["items"][0]["delivery_id"]


def test_structured_dispatch_logging_has_required_fields_and_masks_secrets(monkeypatch, tmp_path: Path, caplog):
    channels_path = _configure_env(monkeypatch, tmp_path)
    _write_channels(channels_path)

    with caplog.at_level("INFO", logger="preflight.notifications"):
        enqueue_alert_transition_notifications(
            event_type=EVENT_ALERT_FIRING,
            alert_id="blocked_runs_any",
            policy_id="blocked_runs_any",
            severity="HIGH",
            source_name="train",
            message="Blocked runs detected.",
            current_value=1.0,
            threshold=1.0,
            previous_status="PENDING",
            current_status="FIRING",
            evaluated_at=datetime.now(timezone.utc),
            context={},
        )
        dispatch_due_notifications(
            webhook_sender=lambda _channel, _payload: WebhookDeliveryResult(
                success=True,
                retryable=False,
                status_code=204,
                error=None,
            )
        )

    structured_lines = [
        record.message
        for record in caplog.records
        if "notification_delivery_event " in record.message
    ]
    assert structured_lines, "Expected structured notification logs."
    parsed = []
    for line in structured_lines:
        payload = json.loads(line.split("notification_delivery_event ", 1)[1])
        parsed.append(payload)

    assert any(item["status"] == "ENQUEUED" for item in parsed)
    sent_items = [item for item in parsed if item["status"] == "SENT"]
    assert sent_items, "Expected SENT delivery structured log."
    sent = sent_items[0]
    assert sent["event_id"]
    assert sent["delivery_id"]
    assert sent["outbox_item_id"]
    assert sent["channel_target"] == "default_webhook"
    assert sent["event_type"] == EVENT_ALERT_FIRING
    assert sent["http_status"] == 204
    assert sent["attempt_count"] == 1
    assert sent["attempt_id"]
    assert "super-secret-token" not in str(parsed)
    assert "x-api-key" not in str(parsed).lower()

    attempts = query_delivery_attempts(limit=10)
    assert attempts
    assert attempts[0]["error_message_safe"] in {None, ""}
    serialized_attempts = str(attempts).lower()
    assert "super-secret-token" not in serialized_attempts
    assert "authorization" not in serialized_attempts
    assert "x-api-key" not in serialized_attempts
