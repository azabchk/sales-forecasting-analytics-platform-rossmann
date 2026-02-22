from __future__ import annotations

import logging
import math
import os
import sys
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_alert_registry import (  # noqa: E402
    count_active_silences,
    count_alert_audit_events_by_type,
    get_scheduler_lease,
    list_active_alert_states,
)
from src.etl.preflight_notification_attempt_registry import query_delivery_attempts  # noqa: E402
from src.etl.preflight_notification_outbox_registry import query_outbox_items  # noqa: E402
from src.etl.preflight_registry import query_preflight_runs  # noqa: E402

logger = logging.getLogger("preflight.metrics")

DEFAULT_SCHEDULER_LEASE_NAME = "preflight_alerts_scheduler"
_NOTIFICATION_LATENCY_BUCKETS_MS: tuple[float, ...] = (
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
    10000.0,
    30000.0,
    60000.0,
)

_METRICS_RENDER_ERRORS_TOTAL = 0
_METRICS_LOCK = threading.Lock()


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_status(value: Any, fallback: str = "UNKNOWN") -> str:
    text = _normalize_optional_text(value)
    if text is None:
        return fallback
    return text.upper()


def _normalize_source(value: Any, fallback: str = "unknown") -> str:
    text = _normalize_optional_text(value)
    if text is None:
        return fallback
    return text.lower()


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "t"}
    return False


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        if not candidate:
            return None
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _to_timestamp_seconds(value: datetime | None) -> int:
    if value is None:
        return 0
    return int(value.astimezone(timezone.utc).timestamp())


def _escape_label_value(value: Any) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("\n", "\\n")
    text = text.replace('"', '\\"')
    return text


def _format_number(value: int | float) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)

    numeric = float(value)
    if math.isnan(numeric) or math.isinf(numeric):
        return "0"

    rendered = f"{numeric:.6f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _render_metric(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if labels:
        serialized = ",".join(f'{key}="{_escape_label_value(labels[key])}"' for key in sorted(labels))
        return f"{name}{{{serialized}}} {_format_number(value)}"
    return f"{name} {_format_number(value)}"


def _get_scheduler_lease_base_name() -> str:
    configured = str(os.getenv("PREFLIGHT_ALERTS_SCHEDULER_LEASE_NAME", DEFAULT_SCHEDULER_LEASE_NAME)).strip()
    return configured or DEFAULT_SCHEDULER_LEASE_NAME


def _lease_last_tick_timestamp_seconds(lease_name: str) -> int:
    lease = get_scheduler_lease(lease_name=lease_name)
    if not isinstance(lease, dict):
        return 0
    for field in ("heartbeat_at", "updated_at", "acquired_at"):
        parsed = _parse_datetime(lease.get(field))
        if parsed is not None:
            return _to_timestamp_seconds(parsed)
    return 0


def _collect_preflight_lines() -> list[str]:
    rows = query_preflight_runs(limit=None)
    runs_counter: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    blocked_counter: defaultdict[str, int] = defaultdict(int)
    latest_by_source: dict[str, datetime] = {}

    for row in rows:
        source_name = _normalize_source(row.get("source_name"))
        final_status = _normalize_status(row.get("final_status"))
        mode = _normalize_source(row.get("mode"), fallback="unknown")

        runs_counter[(source_name, final_status, mode)] += 1
        if _coerce_bool(row.get("blocked")):
            blocked_counter[source_name] += 1

        created_at = _parse_datetime(row.get("created_at"))
        if created_at is not None:
            previous = latest_by_source.get(source_name)
            if previous is None or created_at > previous:
                latest_by_source[source_name] = created_at

    lines = [
        "# HELP preflight_runs_total Total persisted preflight runs grouped by source/final_status/mode.",
        "# TYPE preflight_runs_total counter",
    ]
    for (source_name, final_status, mode), count in sorted(runs_counter.items()):
        lines.append(
            _render_metric(
                "preflight_runs_total",
                count,
                {
                    "source_name": source_name,
                    "final_status": final_status,
                    "mode": mode,
                },
            )
        )

    lines.extend(
        [
            "# HELP preflight_blocked_total Total blocked preflight runs grouped by source.",
            "# TYPE preflight_blocked_total counter",
        ]
    )
    for source_name, count in sorted(blocked_counter.items()):
        lines.append(_render_metric("preflight_blocked_total", count, {"source_name": source_name}))

    lines.extend(
        [
            "# HELP preflight_latest_run_timestamp_seconds Latest preflight run timestamp by source (unix seconds).",
            "# TYPE preflight_latest_run_timestamp_seconds gauge",
        ]
    )
    for source_name, created_at in sorted(latest_by_source.items()):
        lines.append(
            _render_metric(
                "preflight_latest_run_timestamp_seconds",
                _to_timestamp_seconds(created_at),
                {"source_name": source_name},
            )
        )

    return lines


def _collect_alert_lines() -> list[str]:
    active_alert_rows = list_active_alert_states(statuses=("PENDING", "FIRING"), limit=5000)
    active_counter: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in active_alert_rows:
        severity = _normalize_status(row.get("severity"))
        status = _normalize_status(row.get("status"))
        active_counter[(severity, status)] += 1

    transitions_counter = count_alert_audit_events_by_type()
    active_silences = count_active_silences()

    lease_base = _get_scheduler_lease_base_name()
    alerts_tick_ts = _lease_last_tick_timestamp_seconds(f"{lease_base}:alerts")

    lines = [
        "# HELP preflight_alerts_active Current active alerts grouped by severity/status.",
        "# TYPE preflight_alerts_active gauge",
    ]
    for (severity, status), count in sorted(active_counter.items()):
        lines.append(
            _render_metric(
                "preflight_alerts_active",
                count,
                {
                    "severity": severity,
                    "status": status,
                },
            )
        )

    lines.extend(
        [
            "# HELP preflight_alert_transitions_total Total alert transition/audit events grouped by event_type.",
            "# TYPE preflight_alert_transitions_total counter",
        ]
    )
    for event_type, count in sorted(transitions_counter.items()):
        lines.append(_render_metric("preflight_alert_transitions_total", count, {"event_type": event_type}))

    lines.extend(
        [
            "# HELP preflight_alert_silences_active Current number of active alert silences.",
            "# TYPE preflight_alert_silences_active gauge",
            _render_metric("preflight_alert_silences_active", active_silences),
            "# HELP preflight_alerts_scheduler_last_tick_timestamp_seconds Last alerts scheduler tick timestamp (unix seconds).",
            "# TYPE preflight_alerts_scheduler_last_tick_timestamp_seconds gauge",
            _render_metric("preflight_alerts_scheduler_last_tick_timestamp_seconds", alerts_tick_ts),
        ]
    )

    return lines


def _collect_notification_lines(*, now: datetime) -> list[str]:
    attempt_rows = query_delivery_attempts(limit=None, descending=False)

    attempts_counter: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    delivery_latencies_ms: list[float] = []
    dispatch_errors_total = 0

    for row in attempt_rows:
        channel_target = _normalize_optional_text(row.get("channel_target")) or "unknown"
        event_type = _normalize_status(row.get("event_type"))
        attempt_status = _normalize_status(row.get("attempt_status"))
        attempts_counter[(channel_target, event_type, attempt_status)] += 1

        duration_ms = row.get("duration_ms")
        if duration_ms is not None:
            try:
                parsed_duration = float(duration_ms)
            except (TypeError, ValueError):
                parsed_duration = None
            if parsed_duration is not None and parsed_duration >= 0:
                delivery_latencies_ms.append(parsed_duration)

        if attempt_status in {"RETRY", "DEAD", "FAILED"}:
            dispatch_errors_total += 1

    pending_rows = query_outbox_items(statuses=("PENDING", "RETRYING"), limit=None, descending=False)
    dead_rows = query_outbox_items(statuses=("DEAD",), limit=None, descending=False)
    all_outbox_rows = query_outbox_items(limit=None, descending=False)

    pending_count = len(pending_rows)
    dead_count = len(dead_rows)
    replay_count = sum(1 for row in all_outbox_rows if _normalize_optional_text(row.get("replayed_from_id")) is not None)

    oldest_pending_age_seconds = 0
    if pending_rows:
        oldest_created_at: datetime | None = None
        for row in pending_rows:
            created_at = _parse_datetime(row.get("created_at"))
            if created_at is None:
                continue
            if oldest_created_at is None or created_at < oldest_created_at:
                oldest_created_at = created_at
        if oldest_created_at is not None:
            oldest_pending_age_seconds = max(0, int((now - oldest_created_at).total_seconds()))

    lease_base = _get_scheduler_lease_base_name()
    notifications_tick_ts = _lease_last_tick_timestamp_seconds(f"{lease_base}:notifications")

    lines = [
        "# HELP preflight_notifications_attempts_total Total notification delivery attempts grouped by channel/event/status.",
        "# TYPE preflight_notifications_attempts_total counter",
    ]
    for (channel_target, event_type, attempt_status), count in sorted(attempts_counter.items()):
        lines.append(
            _render_metric(
                "preflight_notifications_attempts_total",
                count,
                {
                    "channel_target": channel_target,
                    "event_type": event_type,
                    "attempt_status": attempt_status,
                },
            )
        )

    lines.extend(
        [
            "# HELP preflight_notifications_delivery_latency_ms Delivery latency histogram from attempt ledger (milliseconds).",
            "# TYPE preflight_notifications_delivery_latency_ms histogram",
        ]
    )

    sorted_latencies = sorted(delivery_latencies_ms)
    cumulative = 0
    for bucket in _NOTIFICATION_LATENCY_BUCKETS_MS:
        while cumulative < len(sorted_latencies) and sorted_latencies[cumulative] <= bucket:
            cumulative += 1
        lines.append(
            _render_metric(
                "preflight_notifications_delivery_latency_ms_bucket",
                cumulative,
                {"le": _format_number(bucket)},
            )
        )

    lines.append(
        _render_metric(
            "preflight_notifications_delivery_latency_ms_bucket",
            len(sorted_latencies),
            {"le": "+Inf"},
        )
    )
    lines.append(_render_metric("preflight_notifications_delivery_latency_ms_sum", sum(sorted_latencies)))
    lines.append(_render_metric("preflight_notifications_delivery_latency_ms_count", len(sorted_latencies)))

    lines.extend(
        [
            "# HELP preflight_notifications_outbox_pending Current number of pending/retrying outbox items.",
            "# TYPE preflight_notifications_outbox_pending gauge",
            _render_metric("preflight_notifications_outbox_pending", pending_count),
            "# HELP preflight_notifications_outbox_dead Current number of dead outbox items.",
            "# TYPE preflight_notifications_outbox_dead gauge",
            _render_metric("preflight_notifications_outbox_dead", dead_count),
            "# HELP preflight_notifications_outbox_oldest_pending_age_seconds Age of oldest pending outbox item in seconds.",
            "# TYPE preflight_notifications_outbox_oldest_pending_age_seconds gauge",
            _render_metric("preflight_notifications_outbox_oldest_pending_age_seconds", oldest_pending_age_seconds),
            "# HELP preflight_notifications_replays_total Total replayed notification outbox items.",
            "# TYPE preflight_notifications_replays_total counter",
            _render_metric("preflight_notifications_replays_total", replay_count),
            "# HELP preflight_notifications_scheduler_last_tick_timestamp_seconds Last notifications scheduler tick timestamp (unix seconds).",
            "# TYPE preflight_notifications_scheduler_last_tick_timestamp_seconds gauge",
            _render_metric("preflight_notifications_scheduler_last_tick_timestamp_seconds", notifications_tick_ts),
            "# HELP preflight_notifications_dispatch_errors_total Total notification attempt outcomes with RETRY/DEAD/FAILED status.",
            "# TYPE preflight_notifications_dispatch_errors_total counter",
            _render_metric("preflight_notifications_dispatch_errors_total", dispatch_errors_total),
        ]
    )

    return lines


def _render_metrics(now: datetime) -> str:
    lines: list[str] = []
    lines.extend(_collect_preflight_lines())
    lines.append("")
    lines.extend(_collect_alert_lines())
    lines.append("")
    lines.extend(_collect_notification_lines(now=now))
    lines.append("")
    lines.append("# HELP preflight_metrics_render_errors_total Total diagnostics metrics render failures.")
    lines.append("# TYPE preflight_metrics_render_errors_total counter")
    lines.append(_render_metric("preflight_metrics_render_errors_total", _METRICS_RENDER_ERRORS_TOTAL))
    lines.append("")
    return "\n".join(lines)


def _increment_render_errors() -> int:
    global _METRICS_RENDER_ERRORS_TOTAL
    with _METRICS_LOCK:
        _METRICS_RENDER_ERRORS_TOTAL += 1
        return _METRICS_RENDER_ERRORS_TOTAL


def render_prometheus_metrics(*, now: datetime | None = None) -> str:
    """Render Prometheus/OpenMetrics-compatible text exposition payload."""

    resolved_now = now or datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=timezone.utc)
    resolved_now = resolved_now.astimezone(timezone.utc)

    try:
        return _render_metrics(resolved_now)
    except Exception as exc:  # noqa: BLE001
        failures = _increment_render_errors()
        logger.exception("Failed to render diagnostics metrics payload: %s", exc)
        return "\n".join(
            [
                "# HELP preflight_metrics_render_errors_total Total diagnostics metrics render failures.",
                "# TYPE preflight_metrics_render_errors_total counter",
                _render_metric("preflight_metrics_render_errors_total", failures),
                "",
            ]
        )
