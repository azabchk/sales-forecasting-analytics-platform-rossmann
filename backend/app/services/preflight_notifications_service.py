from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_notification_outbox_registry import (  # noqa: E402
    clone_outbox_item_for_replay,
    get_outbox_item,
    insert_outbox_event,
    list_due_outbox_items,
    list_outbox_history,
    mark_outbox_dead,
    mark_outbox_retry,
    mark_outbox_sent,
    query_outbox_items,
)
from src.etl.preflight_notification_attempt_registry import (  # noqa: E402
    complete_delivery_attempt,
    get_delivery_attempt,
    insert_delivery_attempt_started,
    query_delivery_attempts,
)

logger = logging.getLogger("preflight.notifications")

EVENT_ALERT_FIRING = "ALERT_FIRING"
EVENT_ALERT_RESOLVED = "ALERT_RESOLVED"
SUPPORTED_EVENT_TYPES = {EVENT_ALERT_FIRING, EVENT_ALERT_RESOLVED}
DEFAULT_CHANNELS_PATH = PROJECT_ROOT / "config" / "preflight_notification_channels.yaml"
REPLAYABLE_STATUSES = {"DEAD", "FAILED", "SENT"}
HEADER_DELIVERY_ID = "X-Preflight-Delivery-Id"
HEADER_EVENT_ID = "X-Preflight-Event-Id"
HEADER_TIMESTAMP = "X-Preflight-Timestamp"
HEADER_SIGNATURE = "X-Preflight-Signature"
DEFAULT_ANALYTICS_DAYS = 30
_PENDING_STATUSES = {"PENDING", "RETRYING"}
_SUPPORTED_NOTIFICATION_STATUSES = _PENDING_STATUSES | {"SENT", "DEAD", "FAILED"}
_ATTEMPT_STATUSES = {"STARTED", "SENT", "RETRY", "DEAD", "FAILED"}
_STATUS_TO_ATTEMPT_STATUSES: dict[str, tuple[str, ...]] = {
    "PENDING": ("STARTED",),
    "RETRYING": ("RETRY",),
    "SENT": ("SENT",),
    "DEAD": ("DEAD",),
    "FAILED": ("FAILED",),
}

_OBS_LOCK = threading.Lock()
_OBS_COUNTERS: dict[str, defaultdict[tuple[str, ...], int]] = {
    "enqueue_total": defaultdict(int),
    "dispatch_attempt_total": defaultdict(int),
    "dispatch_sent_total": defaultdict(int),
    "dispatch_retry_total": defaultdict(int),
    "dispatch_dead_total": defaultdict(int),
    "replay_total": defaultdict(int),
}
_OBS_LATENCIES_MS: dict[str, list[float]] = {
    "delivery_latency_ms": [],
    "end_to_end_latency_ms": [],
}


@dataclass(frozen=True)
class NotificationChannel:
    id: str
    channel_type: str
    enabled: bool
    target_url: str | None
    timeout_seconds: int
    max_attempts: int
    backoff_seconds: int
    signing_secret_env: str | None
    enabled_event_types: tuple[str, ...]

    def supports_event(self, event_type: str) -> bool:
        return str(event_type).strip().upper() in self.enabled_event_types


@dataclass(frozen=True)
class WebhookDeliveryResult:
    success: bool
    retryable: bool
    status_code: int | None
    error: str | None
    error_code: str | None = None


def _isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_iso_date_or_datetime(
    value: str | None,
    *,
    field_name: str,
    end_of_day_if_date: bool,
) -> datetime | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None

    if len(normalized) == 10 and normalized[4] == "-" and normalized[7] == "-":
        try:
            parsed_date = date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Invalid {field_name} '{value}'. Expected ISO date or datetime.") from exc
        parsed_time = time.max if end_of_day_if_date else time.min
        return datetime.combine(parsed_date, parsed_time, tzinfo=timezone.utc)

    candidate = normalized.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} '{value}'. Expected ISO date or datetime.") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolve_analytics_window(
    *,
    date_from: str | None,
    date_to: str | None,
    days: int | None,
    default_days: int = DEFAULT_ANALYTICS_DAYS,
) -> tuple[datetime | None, datetime | None, int | None]:
    parsed_from = _parse_iso_date_or_datetime(
        date_from,
        field_name="date_from",
        end_of_day_if_date=False,
    )
    parsed_to = _parse_iso_date_or_datetime(
        date_to,
        field_name="date_to",
        end_of_day_if_date=True,
    )

    normalized_days = int(days) if days is not None else None
    if parsed_from is not None or parsed_to is not None:
        if normalized_days is not None:
            raise ValueError("Use either days or explicit date_from/date_to filters, not both.")
    else:
        if normalized_days is None:
            normalized_days = default_days
        if normalized_days < 1 or normalized_days > 3650:
            raise ValueError("days must be between 1 and 3650.")
        parsed_to = datetime.now(timezone.utc)
        parsed_from = parsed_to - timedelta(days=normalized_days)

    if parsed_from is not None and parsed_to is not None and parsed_from > parsed_to:
        raise ValueError("date_from must be earlier than or equal to date_to.")

    return parsed_from, parsed_to, normalized_days


def _normalize_status_filter(status: str | None) -> str | None:
    normalized = _normalize_optional_text(status)
    if normalized is None:
        return None
    upper = normalized.upper()
    if upper not in _SUPPORTED_NOTIFICATION_STATUSES:
        raise ValueError(
            f"Unsupported status '{status}'. Expected one of {sorted(_SUPPORTED_NOTIFICATION_STATUSES)}."
        )
    return upper


def _normalize_attempt_status_filter(attempt_status: str | None) -> str | None:
    normalized = _normalize_optional_text(attempt_status)
    if normalized is None:
        return None
    upper = normalized.upper()
    if upper not in _ATTEMPT_STATUSES:
        raise ValueError(
            f"Unsupported attempt_status '{attempt_status}'. Expected one of {sorted(_ATTEMPT_STATUSES)}."
        )
    return upper


def _status_filter_to_attempt_statuses(status: str | None) -> tuple[str, ...] | None:
    normalized = _normalize_status_filter(status)
    if normalized is None:
        return None
    return _STATUS_TO_ATTEMPT_STATUSES.get(normalized)


def _normalize_event_type_filter(event_type: str | None) -> str | None:
    normalized = _normalize_optional_text(event_type)
    if normalized is None:
        return None
    upper = normalized.upper()
    if upper not in SUPPORTED_EVENT_TYPES:
        raise ValueError(f"Unsupported event_type '{event_type}'. Expected one of {sorted(SUPPORTED_EVENT_TYPES)}.")
    return upper


def _observe_counter(metric_name: str, labels: tuple[str, ...]) -> None:
    if metric_name not in _OBS_COUNTERS:
        return
    with _OBS_LOCK:
        _OBS_COUNTERS[metric_name][labels] += 1


def _observe_latency(metric_name: str, value_ms: float | None) -> None:
    if metric_name not in _OBS_LATENCIES_MS:
        return
    if value_ms is None:
        return
    if value_ms < 0:
        return
    with _OBS_LOCK:
        _OBS_LATENCIES_MS[metric_name].append(float(value_ms))


def reset_notification_observability_metrics() -> None:
    with _OBS_LOCK:
        for counter in _OBS_COUNTERS.values():
            counter.clear()
        for values in _OBS_LATENCIES_MS.values():
            values.clear()


def get_notification_observability_snapshot() -> dict[str, Any]:
    with _OBS_LOCK:
        counters: dict[str, dict[str, int]] = {}
        for metric_name, values in _OBS_COUNTERS.items():
            counters[metric_name] = {
                "|".join(label for label in labels if label): int(count)
                for labels, count in values.items()
            }
        latency = {
            metric_name: {
                "count": len(values),
                "avg_ms": (sum(values) / len(values)) if values else None,
                "p95_ms": _percentile(values, 95.0) if values else None,
            }
            for metric_name, values in _OBS_LATENCIES_MS.items()
        }
    return {"counters": counters, "latency": latency}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (max(0.0, min(percentile, 100.0)) / 100.0) * (len(ordered) - 1)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    weight = rank - lower_index
    return lower_value + (upper_value - lower_value) * weight


def _duration_ms(started_at: datetime, finished_at: datetime) -> float:
    return max(0.0, (finished_at - started_at).total_seconds() * 1000.0)


def _emit_structured_delivery_log(
    *,
    status: str,
    event_id: str | None,
    delivery_id: str | None,
    outbox_item_id: str | None,
    channel_target: str | None,
    event_type: str | None,
    http_status: int | None,
    attempt_count: int | None,
    attempt_id: str | None = None,
    replayed_from_id: str | None = None,
    error_code: str | None = None,
) -> None:
    payload = {
        "kind": "preflight_notification_delivery",
        "status": str(status).upper(),
        "event_id": _normalize_optional_text(event_id),
        "delivery_id": _normalize_optional_text(delivery_id),
        "outbox_item_id": _normalize_optional_text(outbox_item_id),
        "channel_target": _normalize_optional_text(channel_target),
        "event_type": _normalize_optional_text(event_type),
        "http_status": int(http_status) if http_status is not None else None,
        "attempt_count": int(attempt_count) if attempt_count is not None else None,
        "attempt_id": _normalize_optional_text(attempt_id),
        "replayed_from_id": _normalize_optional_text(replayed_from_id),
        "error_code": _normalize_optional_text(error_code),
        "logged_at": _isoformat_utc(datetime.now(timezone.utc)),
    }
    logger.info("notification_delivery_event %s", json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


def _current_unix_timestamp() -> str:
    return str(int(datetime.now(timezone.utc).timestamp()))


def _normalize_event_id(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized or uuid.uuid4().hex


def _normalize_delivery_id(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized or uuid.uuid4().hex


def _channels_config_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    env_path = str(os.getenv("PREFLIGHT_NOTIFICATION_CHANNELS_PATH", str(DEFAULT_CHANNELS_PATH)))
    return Path(env_path).expanduser().resolve()


def _resolve_env_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.startswith("${") and normalized.endswith("}"):
        env_name = normalized[2:-1].strip()
        return str(os.getenv(env_name, "")).strip() or None
    return normalized


def _normalize_event_types(raw_value: Any) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        return tuple(sorted(SUPPORTED_EVENT_TYPES))
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_value:
        event_type = str(item).strip().upper()
        if not event_type or event_type not in SUPPORTED_EVENT_TYPES or event_type in seen:
            continue
        seen.add(event_type)
        normalized.append(event_type)
    if not normalized:
        return tuple(sorted(SUPPORTED_EVENT_TYPES))
    return tuple(normalized)


def _resolve_target_url(payload: dict[str, Any]) -> str | None:
    target_url = _resolve_env_reference(str(payload.get("target_url", "")).strip() or None)
    if target_url:
        return target_url

    target_url_env = str(payload.get("target_url_env", "")).strip()
    if target_url_env:
        return str(os.getenv(target_url_env, "")).strip() or None
    return None


def _normalize_channel(payload: dict[str, Any]) -> NotificationChannel:
    channel_id = str(payload.get("id", "")).strip()
    if not channel_id:
        raise ValueError("Notification channel requires non-empty 'id'.")

    channel_type = str(payload.get("type", "webhook")).strip().lower() or "webhook"
    if channel_type != "webhook":
        raise ValueError(f"Unsupported notification channel type '{channel_type}' for '{channel_id}'.")

    timeout_seconds = max(1, int(payload.get("timeout_seconds", 5)))
    max_attempts = max(1, int(payload.get("max_attempts", 5)))
    backoff_seconds = max(1, int(payload.get("backoff_seconds", 30)))
    signing_secret_env = str(payload.get("signing_secret_env", "")).strip() or None

    return NotificationChannel(
        id=channel_id,
        channel_type=channel_type,
        enabled=bool(payload.get("enabled", False)),
        target_url=_resolve_target_url(payload),
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        signing_secret_env=signing_secret_env,
        enabled_event_types=_normalize_event_types(payload.get("enabled_event_types")),
    )


def load_notification_channels(path: str | Path | None = None) -> dict[str, Any]:
    resolved_path = _channels_config_path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Notification channels file not found: {resolved_path}")

    with open(resolved_path, encoding="utf-8") as file:
        raw_payload = yaml.safe_load(file) or {}

    if not isinstance(raw_payload, dict):
        raise ValueError("Notification channels YAML must define a top-level object.")

    channels_raw = raw_payload.get("channels", [])
    if not isinstance(channels_raw, list):
        raise ValueError("Notification channels field 'channels' must be a list.")

    channels: list[NotificationChannel] = []
    seen: set[str] = set()
    for item in channels_raw:
        if not isinstance(item, dict):
            raise ValueError("Each notification channel must be an object.")
        channel = _normalize_channel(item)
        if channel.id in seen:
            raise ValueError(f"Duplicate notification channel id '{channel.id}' is not allowed.")
        seen.add(channel.id)
        channels.append(channel)

    return {
        "version": str(raw_payload.get("version", "v1")),
        "path": str(resolved_path),
        "channels": channels,
    }


def _safe_load_channels(path: str | Path | None = None) -> list[NotificationChannel]:
    try:
        payload = load_notification_channels(path)
    except FileNotFoundError:
        logger.warning("Notification channels file not found; outbox dispatch is disabled.")
        return []
    except (yaml.YAMLError, OSError, ValueError) as exc:
        logger.warning("Notification channels config is invalid; outbox dispatch skipped: %s", exc)
        return []

    return payload["channels"]


def _build_webhook_payload(
    *,
    event_id: str,
    event_type: str,
    alert_id: str,
    policy_id: str,
    severity: str | None,
    source_name: str | None,
    message: str,
    current_value: float | None,
    threshold: float | None,
    evaluated_at: datetime | None,
    previous_status: str | None,
    current_status: str | None,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "version": "v1",
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": _isoformat_utc(evaluated_at or datetime.now(timezone.utc)),
        "alert": {
            "alert_id": alert_id,
            "policy_id": policy_id,
            "severity": severity,
            "source_name": source_name,
            "previous_status": previous_status,
            "status": current_status,
            "current_value": current_value,
            "threshold": threshold,
            "message": message,
        },
        "context": context or {},
    }


def enqueue_alert_transition_notifications(
    *,
    event_type: str,
    alert_id: str,
    policy_id: str,
    severity: str | None,
    source_name: str | None,
    message: str,
    current_value: float | None,
    threshold: float | None,
    previous_status: str | None,
    current_status: str | None,
    evaluated_at: datetime | None,
    context: dict[str, Any] | None = None,
    channels_path: str | Path | None = None,
) -> dict[str, Any]:
    normalized_event_type = str(event_type).strip().upper()
    if normalized_event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(f"Unsupported notification event type '{event_type}'.")

    channels = _safe_load_channels(channels_path)
    if not channels:
        return {"event_type": normalized_event_type, "enqueued_count": 0, "items": []}

    transition_event_id = uuid.uuid4().hex
    payload_json = _build_webhook_payload(
        event_id=transition_event_id,
        event_type=normalized_event_type,
        alert_id=str(alert_id),
        policy_id=str(policy_id),
        severity=str(severity).strip().upper() if severity is not None else None,
        source_name=str(source_name).strip().lower() if source_name is not None else None,
        message=str(message),
        current_value=current_value,
        threshold=threshold,
        previous_status=str(previous_status).strip().upper() if previous_status else None,
        current_status=str(current_status).strip().upper() if current_status else None,
        evaluated_at=evaluated_at,
        context=context,
    )

    inserted: list[dict[str, Any]] = []
    for channel in channels:
        if not channel.enabled:
            continue
        if not channel.supports_event(normalized_event_type):
            continue
        if not channel.target_url:
            logger.warning(
                "Skipping notification enqueue for channel=%s event_type=%s because target URL is not configured.",
                channel.id,
                normalized_event_type,
            )
            continue

        created_row = insert_outbox_event(
            {
                "event_type": normalized_event_type,
                "event_id": transition_event_id,
                "delivery_id": uuid.uuid4().hex,
                "alert_id": str(alert_id),
                "policy_id": str(policy_id),
                "severity": str(severity).strip().upper() if severity is not None else None,
                "source_name": str(source_name).strip().lower() if source_name is not None else None,
                "payload_json": payload_json,
                "channel_type": "webhook",
                "channel_target": channel.id,
                "status": "PENDING",
                "attempt_count": 0,
                "max_attempts": channel.max_attempts,
                "next_retry_at": datetime.now(timezone.utc),
            }
        )
        _observe_counter("enqueue_total", (normalized_event_type, channel.id))
        _emit_structured_delivery_log(
            status="ENQUEUED",
            event_id=str(created_row.get("event_id")),
            delivery_id=str(created_row.get("delivery_id")),
            outbox_item_id=str(created_row.get("id")),
            channel_target=channel.id,
            event_type=normalized_event_type,
            http_status=None,
            attempt_count=int(created_row.get("attempt_count", 0)),
            replayed_from_id=str(created_row.get("replayed_from_id", "")).strip() or None,
            error_code=None,
        )
        inserted.append(created_row)

    return {
        "event_type": normalized_event_type,
        "enqueued_count": len(inserted),
        "items": inserted,
    }


def _sign_payload(timestamp: str, body_bytes: bytes, secret: str) -> str:
    message = f"{timestamp}.".encode("utf-8") + body_bytes
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(
    *,
    timestamp: str,
    body_bytes: bytes,
    signature: str,
    secret: str,
) -> bool:
    expected = _sign_payload(timestamp, body_bytes, secret)
    return hmac.compare_digest(expected, str(signature).strip())


def _build_delivery_payload(
    *,
    base_payload: dict[str, Any],
    event_id: str,
    delivery_id: str,
    replayed_from_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(base_payload)
    payload["event_id"] = event_id
    delivery_meta = {"delivery_id": delivery_id}
    if replayed_from_id:
        delivery_meta["replayed_from_id"] = str(replayed_from_id)
    payload["delivery"] = delivery_meta
    return payload


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 429} or status_code >= 500


def _sanitize_error(status_code: int | None, error_text: str | None = None) -> str:
    if status_code is not None:
        return f"HTTP {status_code}"
    if error_text:
        return str(error_text).split("\n")[0][:240]
    return "Delivery failed"


def _send_webhook_request(channel: NotificationChannel, payload: dict[str, Any]) -> WebhookDeliveryResult:
    if not channel.target_url:
        return WebhookDeliveryResult(
            success=False,
            retryable=False,
            status_code=None,
            error="Channel target URL is not configured.",
            error_code="CHANNEL_TARGET_MISSING",
        )

    event_id = _normalize_event_id(str(payload.get("event_id", "")).strip() or None)
    delivery_meta = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
    delivery_id = _normalize_delivery_id(str(delivery_meta.get("delivery_id", "")).strip() or None)
    replayed_from_id = str(delivery_meta.get("replayed_from_id", "")).strip() or None
    timestamp = _current_unix_timestamp()

    payload_with_delivery = _build_delivery_payload(
        base_payload=payload,
        event_id=event_id,
        delivery_id=delivery_id,
        replayed_from_id=replayed_from_id,
    )
    body_bytes = json.dumps(payload_with_delivery, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        HEADER_DELIVERY_ID: delivery_id,
        HEADER_EVENT_ID: event_id,
        HEADER_TIMESTAMP: timestamp,
    }

    if channel.signing_secret_env:
        signing_secret = str(os.getenv(channel.signing_secret_env, "")).strip()
        if signing_secret:
            headers[HEADER_SIGNATURE] = _sign_payload(timestamp, body_bytes, signing_secret)
        else:
            logger.warning(
                "Webhook signing secret is not configured for channel=%s (env=%s); dispatching unsigned.",
                channel.id,
                channel.signing_secret_env,
            )
    else:
        logger.warning("Webhook signing secret env is not set for channel=%s; dispatching unsigned.", channel.id)

    request = urllib.request.Request(
        url=channel.target_url,
        data=body_bytes,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=channel.timeout_seconds) as response:  # noqa: S310
            status_code = int(getattr(response, "status", 0) or response.getcode())
    except urllib.error.HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0) or None
        return WebhookDeliveryResult(
            success=False,
            retryable=_is_retryable_status(status_code) if status_code is not None else True,
            status_code=status_code,
            error=_sanitize_error(status_code, str(exc.reason) if hasattr(exc, "reason") else str(exc)),
            error_code="HTTP_ERROR",
        )
    except urllib.error.URLError as exc:
        return WebhookDeliveryResult(
            success=False,
            retryable=True,
            status_code=None,
            error=_sanitize_error(None, str(getattr(exc, "reason", "network_error"))),
            error_code="NETWORK_ERROR",
        )
    except TimeoutError:
        return WebhookDeliveryResult(
            success=False,
            retryable=True,
            status_code=None,
            error="Network timeout",
            error_code="TIMEOUT",
        )
    except Exception as exc:  # noqa: BLE001
        return WebhookDeliveryResult(
            success=False,
            retryable=True,
            status_code=None,
            error=_sanitize_error(None, str(exc)),
            error_code="UNEXPECTED_ERROR",
        )

    if 200 <= status_code < 300:
        return WebhookDeliveryResult(success=True, retryable=False, status_code=status_code, error=None, error_code=None)

    return WebhookDeliveryResult(
        success=False,
        retryable=_is_retryable_status(status_code),
        status_code=status_code,
        error=_sanitize_error(status_code),
        error_code="HTTP_ERROR",
    )


def _compute_retry_delay_seconds(base_backoff_seconds: int, attempt_count: int) -> int:
    normalized_base = max(1, int(base_backoff_seconds))
    normalized_attempt = max(1, int(attempt_count))
    return min(normalized_base * (2 ** (normalized_attempt - 1)), 24 * 3600)


def dispatch_due_notifications(
    *,
    limit: int = 50,
    due_at: datetime | None = None,
    channels_path: str | Path | None = None,
    actor: str = "system:scheduler",
    webhook_sender: Callable[[NotificationChannel, dict[str, Any]], WebhookDeliveryResult] | None = None,
) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 1000))
    now = _parse_datetime(due_at) or datetime.now(timezone.utc)
    sender = webhook_sender or _send_webhook_request

    channels = _safe_load_channels(channels_path)
    channel_map = {channel.id: channel for channel in channels}

    due_items = list_due_outbox_items(limit=normalized_limit, due_at=now)
    summary = {
        "actor": str(actor).strip() or "system:scheduler",
        "dispatched_at": _isoformat_utc(now),
        "processed_count": 0,
        "sent_count": 0,
        "retrying_count": 0,
        "dead_count": 0,
        "failed_count": 0,
    }

    for item in due_items:
        summary["processed_count"] += 1
        item_id = str(item.get("id"))
        channel_target = str(item.get("channel_target", "")).strip()
        event_type = str(item.get("event_type", "")).strip().upper() or "UNKNOWN"
        max_attempts = max(1, int(item.get("max_attempts", 5)))
        previous_attempts = max(0, int(item.get("attempt_count", 0)))
        attempt_count = previous_attempts + 1
        event_id = _normalize_event_id(str(item.get("event_id", "")).strip() or None)
        delivery_id = uuid.uuid4().hex
        replayed_from_id = str(item.get("replayed_from_id", "")).strip() or None
        attempt_started_at = datetime.now(timezone.utc)
        _observe_counter("dispatch_attempt_total", (event_type, channel_target))

        attempt_row = insert_delivery_attempt_started(
            {
                "outbox_item_id": item_id,
                "event_id": event_id,
                "delivery_id": delivery_id,
                "replayed_from_id": replayed_from_id,
                "channel_type": str(item.get("channel_type", "webhook")).strip().lower() or "webhook",
                "channel_target": channel_target,
                "event_type": event_type,
                "alert_id": str(item.get("alert_id", "")).strip(),
                "policy_id": str(item.get("policy_id", "")).strip(),
                "source_name": str(item.get("source_name", "")).strip().lower() or None,
                "attempt_number": attempt_count,
                "started_at": attempt_started_at,
            }
        )
        attempt_id = str(attempt_row.get("attempt_id"))
        final_attempt_status = "FAILED"
        final_http_status: int | None = None
        final_error_code: str | None = "UNEXPECTED_ERROR"
        final_error_message: str | None = "Unexpected dispatch flow termination."
        attempt_finished_at: datetime | None = None

        try:
            channel = channel_map.get(channel_target)
            if channel is None or not channel.enabled or channel.channel_type != "webhook":
                mark_outbox_dead(
                    item_id,
                    attempt_count=attempt_count,
                    last_error="Channel is missing or disabled.",
                    event_id=event_id,
                    delivery_id=delivery_id,
                    last_error_code="CHANNEL_UNAVAILABLE",
                )
                final_attempt_status = "DEAD"
                final_error_code = "CHANNEL_UNAVAILABLE"
                final_error_message = "Channel is missing or disabled."
                _observe_counter("dispatch_dead_total", (event_type, channel_target, "CHANNEL_UNAVAILABLE"))
                _emit_structured_delivery_log(
                    status="DEAD",
                    event_id=event_id,
                    delivery_id=delivery_id,
                    outbox_item_id=item_id,
                    channel_target=channel_target,
                    event_type=event_type,
                    http_status=None,
                    attempt_count=attempt_count,
                    attempt_id=attempt_id,
                    replayed_from_id=replayed_from_id,
                    error_code="CHANNEL_UNAVAILABLE",
                )
                summary["dead_count"] += 1
                summary["failed_count"] += 1
                continue

            if not channel.target_url:
                mark_outbox_dead(
                    item_id,
                    attempt_count=attempt_count,
                    last_error="Channel target URL is not configured.",
                    event_id=event_id,
                    delivery_id=delivery_id,
                    last_error_code="CHANNEL_TARGET_MISSING",
                )
                final_attempt_status = "DEAD"
                final_error_code = "CHANNEL_TARGET_MISSING"
                final_error_message = "Channel target URL is not configured."
                _observe_counter("dispatch_dead_total", (event_type, channel_target, "CHANNEL_TARGET_MISSING"))
                _emit_structured_delivery_log(
                    status="DEAD",
                    event_id=event_id,
                    delivery_id=delivery_id,
                    outbox_item_id=item_id,
                    channel_target=channel_target,
                    event_type=event_type,
                    http_status=None,
                    attempt_count=attempt_count,
                    attempt_id=attempt_id,
                    replayed_from_id=replayed_from_id,
                    error_code="CHANNEL_TARGET_MISSING",
                )
                summary["dead_count"] += 1
                summary["failed_count"] += 1
                continue

            payload_json = item.get("payload_json") if isinstance(item.get("payload_json"), dict) else {}
            payload_with_delivery = _build_delivery_payload(
                base_payload=payload_json,
                event_id=event_id,
                delivery_id=delivery_id,
                replayed_from_id=replayed_from_id,
            )

            try:
                result = sender(channel, payload_with_delivery)
            except Exception as exc:  # noqa: BLE001
                result = WebhookDeliveryResult(
                    success=False,
                    retryable=True,
                    status_code=None,
                    error=_sanitize_error(None, str(exc)),
                    error_code="UNEXPECTED_ERROR",
                )

            final_http_status = result.status_code
            attempt_finished_at = datetime.now(timezone.utc)
            _observe_latency("delivery_latency_ms", _duration_ms(attempt_started_at, attempt_finished_at))

            if result.success:
                mark_outbox_sent(
                    item_id,
                    sent_at=now,
                    attempt_count=attempt_count,
                    event_id=event_id,
                    delivery_id=delivery_id,
                    last_http_status=result.status_code,
                )
                created_at = _parse_datetime(item.get("created_at"))
                if created_at is not None:
                    _observe_latency("end_to_end_latency_ms", _duration_ms(created_at, now))
                final_attempt_status = "SENT"
                final_error_code = None
                final_error_message = None
                _observe_counter("dispatch_sent_total", (event_type, channel_target))
                _emit_structured_delivery_log(
                    status="SENT",
                    event_id=event_id,
                    delivery_id=delivery_id,
                    outbox_item_id=item_id,
                    channel_target=channel_target,
                    event_type=event_type,
                    http_status=result.status_code,
                    attempt_count=attempt_count,
                    attempt_id=attempt_id,
                    replayed_from_id=replayed_from_id,
                    error_code=None,
                )
                summary["sent_count"] += 1
                continue

            summary["failed_count"] += 1
            if result.retryable and attempt_count < max_attempts:
                retry_delay = _compute_retry_delay_seconds(channel.backoff_seconds, attempt_count)
                next_retry_at = now + timedelta(seconds=retry_delay)
                mark_outbox_retry(
                    item_id,
                    attempt_count=attempt_count,
                    next_retry_at=next_retry_at,
                    last_error=result.error,
                    event_id=event_id,
                    delivery_id=delivery_id,
                    last_http_status=result.status_code,
                    last_error_code=result.error_code,
                )
                final_attempt_status = "RETRY"
                final_error_code = str(result.error_code or "UNKNOWN").upper()
                final_error_message = result.error
                _observe_counter(
                    "dispatch_retry_total",
                    (event_type, channel_target, str(result.error_code or "UNKNOWN").upper()),
                )
                _emit_structured_delivery_log(
                    status="RETRYING",
                    event_id=event_id,
                    delivery_id=delivery_id,
                    outbox_item_id=item_id,
                    channel_target=channel_target,
                    event_type=event_type,
                    http_status=result.status_code,
                    attempt_count=attempt_count,
                    attempt_id=attempt_id,
                    replayed_from_id=replayed_from_id,
                    error_code=result.error_code,
                )
                summary["retrying_count"] += 1
                continue

            mark_outbox_dead(
                item_id,
                attempt_count=attempt_count,
                last_error=result.error,
                event_id=event_id,
                delivery_id=delivery_id,
                last_http_status=result.status_code,
                last_error_code=result.error_code,
            )
            final_attempt_status = "DEAD"
            final_error_code = str(result.error_code or "UNKNOWN").upper()
            final_error_message = result.error
            _observe_counter(
                "dispatch_dead_total",
                (event_type, channel_target, str(result.error_code or "UNKNOWN").upper()),
            )
            _emit_structured_delivery_log(
                status="DEAD",
                event_id=event_id,
                delivery_id=delivery_id,
                outbox_item_id=item_id,
                channel_target=channel_target,
                event_type=event_type,
                http_status=result.status_code,
                attempt_count=attempt_count,
                attempt_id=attempt_id,
                replayed_from_id=replayed_from_id,
                error_code=result.error_code,
            )
            summary["dead_count"] += 1
        finally:
            if attempt_finished_at is None:
                attempt_finished_at = datetime.now(timezone.utc)
                _observe_latency("delivery_latency_ms", _duration_ms(attempt_started_at, attempt_finished_at))
            complete_delivery_attempt(
                attempt_id,
                attempt_status=final_attempt_status,
                completed_at=attempt_finished_at,
                http_status=final_http_status,
                error_code=final_error_code,
                error_message_safe=final_error_message,
            )

    return summary


def run_notification_dispatch(
    *,
    limit: int = 50,
    actor: str = "system:scheduler",
) -> dict[str, Any]:
    return dispatch_due_notifications(limit=limit, actor=actor)


def replay_notification_outbox_item(
    *,
    item_id: str,
    actor: str,
) -> dict[str, Any]:
    normalized_item_id = str(item_id).strip()
    if not normalized_item_id:
        raise ValueError("outbox item id is required")

    normalized_actor = str(actor).strip() or "system:admin"
    item = get_outbox_item(normalized_item_id)
    if item is None:
        raise LookupError(f"Outbox item not found: {normalized_item_id}")

    status = str(item.get("status", "")).strip().upper()
    if status not in REPLAYABLE_STATUSES:
        raise ValueError(
            f"Outbox item '{normalized_item_id}' with status '{status}' is not replayable. "
            f"Allowed statuses: {', '.join(sorted(REPLAYABLE_STATUSES))}."
        )

    replayed = clone_outbox_item_for_replay(normalized_item_id)
    if replayed is None:
        raise LookupError(f"Failed to replay outbox item: {normalized_item_id}")

    event_type = str(replayed.get("event_type", "")).strip().upper() or "UNKNOWN"
    channel_target = str(replayed.get("channel_target", "")).strip()
    _observe_counter("replay_total", (event_type, channel_target))
    _emit_structured_delivery_log(
        status="REPLAYED",
        event_id=str(replayed.get("event_id")),
        delivery_id=str(replayed.get("delivery_id")),
        outbox_item_id=str(replayed.get("id")),
        channel_target=channel_target,
        event_type=event_type,
        http_status=None,
        attempt_count=int(replayed.get("attempt_count", 0)),
        replayed_from_id=str(replayed.get("replayed_from_id", "")).strip() or None,
        error_code=None,
    )

    return {
        "actor": normalized_actor,
        "replayed_count": 1,
        "items": [replayed],
    }


def replay_dead_notification_outbox(
    *,
    limit: int = 50,
    actor: str,
) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 1000))
    normalized_actor = str(actor).strip() or "system:admin"

    dead_items = list_outbox_history(limit=normalized_limit, statuses=("DEAD",))
    replayed_items: list[dict[str, Any]] = []
    for item in dead_items:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        replayed = clone_outbox_item_for_replay(item_id)
        if replayed is not None:
            event_type = str(replayed.get("event_type", "")).strip().upper() or "UNKNOWN"
            channel_target = str(replayed.get("channel_target", "")).strip()
            _observe_counter("replay_total", (event_type, channel_target))
            _emit_structured_delivery_log(
                status="REPLAYED",
                event_id=str(replayed.get("event_id")),
                delivery_id=str(replayed.get("delivery_id")),
                outbox_item_id=str(replayed.get("id")),
                channel_target=channel_target,
                event_type=event_type,
                http_status=None,
                attempt_count=int(replayed.get("attempt_count", 0)),
                replayed_from_id=str(replayed.get("replayed_from_id", "")).strip() or None,
                error_code=None,
            )
            replayed_items.append(replayed)

    return {
        "actor": normalized_actor,
        "replayed_count": len(replayed_items),
        "items": replayed_items,
    }


def get_notification_outbox(
    *,
    limit: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 1000))
    statuses = (str(status).strip().upper(),) if status else ("PENDING", "RETRYING")
    items = list_outbox_history(limit=normalized_limit, statuses=statuses)
    return {"limit": normalized_limit, "items": items}


def get_notification_history(
    *,
    limit: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 1000))
    statuses = (str(status).strip().upper(),) if status else ("SENT", "FAILED", "DEAD")
    items = list_outbox_history(limit=normalized_limit, statuses=statuses)
    return {"limit": normalized_limit, "items": items}


def _parse_row_datetime(value: Any) -> datetime | None:
    return _parse_datetime(value)


def _parse_duration_ms(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _end_to_end_latency_ms(row: dict[str, Any]) -> float | None:
    created_at = _parse_row_datetime(row.get("created_at"))
    sent_at = _parse_row_datetime(row.get("sent_at"))
    if created_at is None or sent_at is None:
        return None
    return _duration_ms(created_at, sent_at)


def _bucket_datetime(dt: datetime, *, bucket: str) -> datetime:
    utc_dt = dt.astimezone(timezone.utc)
    if bucket == "hour":
        return utc_dt.replace(minute=0, second=0, microsecond=0)
    return utc_dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _query_notification_attempt_rows(
    *,
    days: int | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    status: str | None = None,
    attempt_status: str | None = None,
    alert_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_event_type = _normalize_event_type_filter(event_type)
    normalized_channel_target = _normalize_optional_text(channel_target)
    normalized_alert_id = _normalize_optional_text(alert_id)
    explicit_attempt_status = _normalize_attempt_status_filter(attempt_status)
    mapped_statuses = _status_filter_to_attempt_statuses(status)

    if explicit_attempt_status is not None and mapped_statuses is not None:
        raise ValueError("Use either status or attempt_status filter, not both.")

    attempt_statuses = (explicit_attempt_status,) if explicit_attempt_status is not None else mapped_statuses
    parsed_from, parsed_to, normalized_days = _resolve_analytics_window(
        date_from=date_from,
        date_to=date_to,
        days=days,
    )

    rows = query_delivery_attempts(
        attempt_statuses=attempt_statuses,
        event_type=normalized_event_type,
        channel_target=normalized_channel_target,
        alert_id=normalized_alert_id,
        date_from=parsed_from,
        date_to=parsed_to,
        date_field="started_at",
        limit=None,
        descending=False,
    )

    filters = {
        "days": normalized_days,
        "event_type": normalized_event_type,
        "channel_target": normalized_channel_target,
        "status": _normalize_status_filter(status),
        "attempt_status": explicit_attempt_status,
        "alert_id": normalized_alert_id,
        "date_from": _isoformat_utc(parsed_from) if parsed_from else None,
        "date_to": _isoformat_utc(parsed_to) if parsed_to else None,
    }
    return rows, filters


def _query_pending_outbox_rows(
    *,
    event_type: str | None,
    channel_target: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    status: str | None,
) -> list[dict[str, Any]]:
    normalized_status = _normalize_status_filter(status)
    if normalized_status in {"SENT", "DEAD", "FAILED"}:
        return []
    pending_statuses = (normalized_status,) if normalized_status in _PENDING_STATUSES else tuple(sorted(_PENDING_STATUSES))
    return query_outbox_items(
        statuses=pending_statuses,
        event_type=event_type,
        channel_target=channel_target,
        date_from=date_from,
        date_to=date_to,
        date_field="created_at",
        limit=None,
        descending=False,
    )


def get_notification_stats(
    *,
    days: int | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    attempt_rows, filters = _query_notification_attempt_rows(
        days=days,
        event_type=event_type,
        channel_target=channel_target,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    now = datetime.now(timezone.utc)

    sent_count = sum(1 for row in attempt_rows if str(row.get("attempt_status", "")).upper() == "SENT")
    retry_count = sum(1 for row in attempt_rows if str(row.get("attempt_status", "")).upper() == "RETRY")
    dead_count = sum(1 for row in attempt_rows if str(row.get("attempt_status", "")).upper() == "DEAD")
    failed_count = sum(1 for row in attempt_rows if str(row.get("attempt_status", "")).upper() == "FAILED")
    replay_count = sum(1 for row in attempt_rows if _normalize_optional_text(row.get("replayed_from_id")) is not None)
    total_events = len(attempt_rows)

    completed = sent_count + dead_count + failed_count
    success_rate = float(sent_count / completed) if completed > 0 else 0.0

    delivery_latencies = [value for value in (_parse_duration_ms(row.get("duration_ms")) for row in attempt_rows) if value is not None]
    avg_delivery_latency_ms = float(sum(delivery_latencies) / len(delivery_latencies)) if delivery_latencies else None
    p95_delivery_latency_ms = _percentile(delivery_latencies, 95.0) if delivery_latencies else None

    parsed_from = _parse_datetime(filters.get("date_from"))
    parsed_to = _parse_datetime(filters.get("date_to"))
    pending_rows = _query_pending_outbox_rows(
        event_type=filters.get("event_type"),
        channel_target=filters.get("channel_target"),
        date_from=parsed_from,
        date_to=parsed_to,
        status=filters.get("status"),
    )
    pending_count = len(pending_rows)
    pending_ages_seconds = []
    for row in pending_rows:
        created_at = _parse_row_datetime(row.get("created_at"))
        if created_at is None:
            continue
        pending_ages_seconds.append(max(0, int((now - created_at).total_seconds())))
    oldest_pending_age_seconds = max(pending_ages_seconds) if pending_ages_seconds else None

    return {
        "filters": filters,
        "total_events": int(total_events),
        "sent_count": int(sent_count),
        "retry_count": int(retry_count),
        "dead_count": int(dead_count),
        "replay_count": int(replay_count),
        "pending_count": int(pending_count),
        "success_rate": success_rate,
        "avg_delivery_latency_ms": avg_delivery_latency_ms,
        "p95_delivery_latency_ms": p95_delivery_latency_ms,
        "oldest_pending_age_seconds": oldest_pending_age_seconds,
        "runtime_observability": get_notification_observability_snapshot(),
    }


def get_notification_trends(
    *,
    days: int | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    bucket: str = "day",
) -> dict[str, Any]:
    normalized_bucket = str(bucket).strip().lower() or "day"
    if normalized_bucket not in {"day", "hour"}:
        raise ValueError("bucket must be one of: day, hour")

    attempt_rows, filters = _query_notification_attempt_rows(
        days=days,
        event_type=event_type,
        channel_target=channel_target,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )

    bucketed: dict[datetime, dict[str, Any]] = {}
    for row in attempt_rows:
        started_at = _parse_row_datetime(row.get("started_at"))
        if started_at is None:
            continue
        bucket_start = _bucket_datetime(started_at, bucket=normalized_bucket)
        if bucket_start not in bucketed:
            bucketed[bucket_start] = {
                "bucket_start": bucket_start,
                "sent_count": 0,
                "retry_count": 0,
                "dead_count": 0,
                "replay_count": 0,
                "latencies": [],
            }

        payload = bucketed[bucket_start]
        row_status = str(row.get("attempt_status", "")).upper()
        if row_status == "SENT":
            payload["sent_count"] += 1
        elif row_status == "RETRY":
            payload["retry_count"] += 1
        elif row_status == "DEAD":
            payload["dead_count"] += 1

        if _normalize_optional_text(row.get("replayed_from_id")) is not None:
            payload["replay_count"] += 1

        duration = _parse_duration_ms(row.get("duration_ms"))
        if duration is not None:
            payload["latencies"].append(duration)

    items: list[dict[str, Any]] = []
    for bucket_start in sorted(bucketed):
        payload = bucketed[bucket_start]
        latencies = payload.pop("latencies")
        payload["avg_delivery_latency_ms"] = (sum(latencies) / len(latencies)) if latencies else None
        items.append(payload)

    return {
        "bucket": normalized_bucket,
        "filters": filters,
        "items": items,
    }


def get_notification_channels(
    *,
    days: int | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    attempt_rows, filters = _query_notification_attempt_rows(
        days=days,
        event_type=event_type,
        channel_target=channel_target,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )

    parsed_from = _parse_datetime(filters.get("date_from"))
    parsed_to = _parse_datetime(filters.get("date_to"))
    pending_rows = _query_pending_outbox_rows(
        event_type=filters.get("event_type"),
        channel_target=filters.get("channel_target"),
        date_from=parsed_from,
        date_to=parsed_to,
        status=filters.get("status"),
    )
    pending_by_channel: dict[str, int] = defaultdict(int)
    for row in pending_rows:
        target = str(row.get("channel_target", "")).strip() or "unknown"
        pending_by_channel[target] += 1

    channel_stats: dict[str, dict[str, Any]] = {}
    for row in attempt_rows:
        target = str(row.get("channel_target", "")).strip() or "unknown"
        if target not in channel_stats:
            channel_stats[target] = {
                "channel_target": target,
                "sent_count": 0,
                "retry_count": 0,
                "dead_count": 0,
                "pending_count": 0,
                "replay_count": 0,
                "latencies": [],
                "last_sent_at": None,
                "last_error_at": None,
                "error_counts": defaultdict(int),
            }

        payload = channel_stats[target]
        row_status = str(row.get("attempt_status", "")).upper()
        if row_status == "SENT":
            payload["sent_count"] += 1
        elif row_status == "RETRY":
            payload["retry_count"] += 1
        elif row_status == "DEAD":
            payload["dead_count"] += 1

        if _normalize_optional_text(row.get("replayed_from_id")) is not None:
            payload["replay_count"] += 1

        duration = _parse_duration_ms(row.get("duration_ms"))
        if duration is not None:
            payload["latencies"].append(duration)

        completed_at = _parse_row_datetime(row.get("completed_at"))
        if row_status == "SENT" and completed_at is not None:
            last_sent_at = _parse_row_datetime(payload.get("last_sent_at"))
            if last_sent_at is None or completed_at > last_sent_at:
                payload["last_sent_at"] = completed_at

        error_code = _normalize_optional_text(row.get("error_code"))
        if error_code is not None:
            payload["error_counts"][error_code.upper()] += 1
            if completed_at is not None:
                last_error_at = _parse_row_datetime(payload.get("last_error_at"))
                if last_error_at is None or completed_at > last_error_at:
                    payload["last_error_at"] = completed_at

    for target, count in pending_by_channel.items():
        if target not in channel_stats:
            channel_stats[target] = {
                "channel_target": target,
                "sent_count": 0,
                "retry_count": 0,
                "dead_count": 0,
                "pending_count": count,
                "replay_count": 0,
                "latencies": [],
                "last_sent_at": None,
                "last_error_at": None,
                "error_counts": defaultdict(int),
            }
        else:
            channel_stats[target]["pending_count"] = count

    items: list[dict[str, Any]] = []
    for target in sorted(channel_stats):
        payload = channel_stats[target]
        latencies = payload.pop("latencies")
        error_counts = payload.pop("error_counts")
        completed = payload["sent_count"] + payload["dead_count"]
        payload["success_rate"] = (payload["sent_count"] / completed) if completed > 0 else 0.0
        payload["avg_delivery_latency_ms"] = (sum(latencies) / len(latencies)) if latencies else None
        payload["top_error_codes"] = [
            {"error_code": code, "count": count}
            for code, count in sorted(error_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        items.append(payload)

    return {
        "filters": filters,
        "items": items,
    }


def get_notification_attempts(
    *,
    limit: int = 100,
    days: int | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    attempt_status: str | None = None,
    alert_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 1000))
    rows, filters = _query_notification_attempt_rows(
        days=days,
        event_type=event_type,
        channel_target=channel_target,
        attempt_status=attempt_status,
        alert_id=alert_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "limit": normalized_limit,
        "filters": filters,
        "items": list(rows)[-normalized_limit:][::-1],
    }


def get_notification_attempt_details(attempt_id: str) -> dict[str, Any] | None:
    normalized_attempt_id = str(attempt_id).strip()
    if not normalized_attempt_id:
        raise ValueError("attempt_id is required")
    return get_delivery_attempt(normalized_attempt_id)
