from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from app.services.diagnostics_service import (
    DiagnosticsNotFoundError,
    DiagnosticsPayloadError,
    _load_semantic_payload_with_fallback,
    _normalize_semantic_payload,
)
from app.services.preflight_notifications_service import (
    EVENT_ALERT_FIRING,
    EVENT_ALERT_RESOLVED,
    enqueue_alert_transition_notifications,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_alert_registry import (  # noqa: E402
    acknowledge_alert as save_alert_acknowledgement,
    create_silence as save_alert_silence,
    delete_alert_state,
    expire_elapsed_silences,
    expire_silence as mark_silence_expired,
    get_alert_state,
    get_silence,
    insert_alert_audit_event,
    insert_alert_history,
    list_active_acknowledgements,
    list_active_alert_states,
    list_alert_audit_events,
    list_alert_history,
    list_silences as fetch_silences,
    unacknowledge_alert as clear_alert_acknowledgement,
    upsert_alert_state,
)
from src.etl.preflight_registry import query_preflight_runs  # noqa: E402

logger = logging.getLogger("preflight.alerts")

ALERT_STATUS_OK = "OK"
ALERT_STATUS_PENDING = "PENDING"
ALERT_STATUS_FIRING = "FIRING"
ALERT_STATUS_RESOLVED = "RESOLVED"

AUDIT_ACTOR_SYSTEM = "system"
AUDIT_ACTOR_SCHEDULER = "system:scheduler"

SUPPORTED_SOURCES = {"train", "store"}
SUPPORTED_SEVERITIES = {"LOW", "MEDIUM", "HIGH"}
SUPPORTED_METRICS = {
    "fail_rate",
    "blocked_count",
    "top_rule_fail_count",
    "semantic_rule_fail_count",
    "unified_usage_rate",
    "fail_count",
}
SUPPORTED_OPERATORS = {">", ">=", "<", "<=", "==", "!="}
_OPERATOR_MAP: dict[str, Callable[[float, float], bool]] = {
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


@dataclass(frozen=True)
class AlertPolicy:
    id: str
    enabled: bool
    severity: str
    source_name: str | None
    window_days: int
    metric_type: str
    operator: str
    threshold: float
    pending_evaluations: int
    description: str
    rule_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "enabled": self.enabled,
            "severity": self.severity,
            "source_name": self.source_name,
            "window_days": self.window_days,
            "metric_type": self.metric_type,
            "operator": self.operator,
            "threshold": self.threshold,
            "pending_evaluations": self.pending_evaluations,
            "description": self.description,
            "rule_id": self.rule_id,
        }


def _policy_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()

    from_env = Path(
        str(
            os.getenv(
                "PREFLIGHT_ALERT_POLICY_PATH",
                str(PROJECT_ROOT / "config" / "preflight_alert_policies.yaml"),
            )
        )
    )
    return from_env.expanduser().resolve()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        normalized = normalized.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _require_datetime(value: Any, *, field_name: str) -> datetime:
    parsed = _parse_datetime(value)
    if parsed is None:
        raise DiagnosticsPayloadError(f"Field '{field_name}' requires a valid ISO date/datetime value.")
    return parsed


def _isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _normalize_source(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized not in SUPPORTED_SOURCES:
        raise DiagnosticsPayloadError(
            f"Unsupported source_name '{value}' in alert policy. Expected one of {sorted(SUPPORTED_SOURCES)}."
        )
    return normalized


def _normalize_severity(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized:
        return None
    if normalized not in SUPPORTED_SEVERITIES:
        raise DiagnosticsPayloadError(
            f"Unsupported severity '{value}'. Expected one of {sorted(SUPPORTED_SEVERITIES)}."
        )
    return normalized


def _normalize_policy(payload: dict[str, Any]) -> AlertPolicy:
    if not isinstance(payload, dict):
        raise DiagnosticsPayloadError("Each alert policy must be an object.")

    policy_id = str(payload.get("id", "")).strip()
    if not policy_id:
        raise DiagnosticsPayloadError("Alert policy requires non-empty 'id'.")

    enabled = bool(payload.get("enabled", True))
    severity = str(payload.get("severity", "MEDIUM")).strip().upper()
    if severity not in SUPPORTED_SEVERITIES:
        raise DiagnosticsPayloadError(
            f"Alert policy '{policy_id}' has invalid severity '{severity}'. Expected one of {sorted(SUPPORTED_SEVERITIES)}."
        )

    source_name = _normalize_source(payload.get("source_name"))
    window_days = int(payload.get("window_days", 7))
    if window_days < 1 or window_days > 3650:
        raise DiagnosticsPayloadError(f"Alert policy '{policy_id}' window_days must be between 1 and 3650.")

    metric_type = str(payload.get("metric_type", "")).strip().lower()
    if metric_type not in SUPPORTED_METRICS:
        raise DiagnosticsPayloadError(
            f"Alert policy '{policy_id}' metric_type '{metric_type}' is not supported. "
            f"Supported: {sorted(SUPPORTED_METRICS)}."
        )

    operator = str(payload.get("operator", "")).strip()
    if operator not in SUPPORTED_OPERATORS:
        raise DiagnosticsPayloadError(
            f"Alert policy '{policy_id}' operator '{operator}' is not supported. "
            f"Supported: {sorted(SUPPORTED_OPERATORS)}."
        )

    try:
        threshold = float(payload.get("threshold"))
    except (TypeError, ValueError) as exc:
        raise DiagnosticsPayloadError(f"Alert policy '{policy_id}' requires numeric threshold.") from exc

    pending_evaluations = int(payload.get("pending_evaluations", 1))
    if pending_evaluations < 1:
        raise DiagnosticsPayloadError(f"Alert policy '{policy_id}' pending_evaluations must be >= 1.")

    description = str(payload.get("description", "")).strip() or policy_id
    rule_id = payload.get("rule_id")
    normalized_rule_id = str(rule_id).strip() if rule_id is not None else None

    if metric_type == "semantic_rule_fail_count" and not normalized_rule_id:
        raise DiagnosticsPayloadError(
            f"Alert policy '{policy_id}' with metric_type=semantic_rule_fail_count requires non-empty rule_id."
        )

    return AlertPolicy(
        id=policy_id,
        enabled=enabled,
        severity=severity,
        source_name=source_name,
        window_days=window_days,
        metric_type=metric_type,
        operator=operator,
        threshold=threshold,
        pending_evaluations=pending_evaluations,
        description=description,
        rule_id=normalized_rule_id,
    )


def load_alert_policies(path: str | Path | None = None) -> dict[str, Any]:
    resolved_path = _policy_path(path)
    if not resolved_path.exists():
        raise DiagnosticsNotFoundError(f"Alert policy file not found: {resolved_path}")

    try:
        with open(resolved_path, encoding="utf-8") as file:
            raw_payload = yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        raise DiagnosticsPayloadError(f"Failed to parse alert policies YAML at {resolved_path}: {exc}") from exc
    except OSError as exc:
        raise DiagnosticsPayloadError(f"Failed to read alert policies file {resolved_path}: {exc}") from exc

    if not isinstance(raw_payload, dict):
        raise DiagnosticsPayloadError("Alert policy file must define a top-level object.")

    policies_raw = raw_payload.get("policies", [])
    if not isinstance(policies_raw, list):
        raise DiagnosticsPayloadError("Alert policy file field 'policies' must be a list.")

    policies: list[AlertPolicy] = []
    seen_ids: set[str] = set()
    for item in policies_raw:
        policy = _normalize_policy(item)
        if policy.id in seen_ids:
            raise DiagnosticsPayloadError(f"Duplicate alert policy id '{policy.id}' is not allowed.")
        seen_ids.add(policy.id)
        policies.append(policy)

    return {
        "version": str(raw_payload.get("version", "v1")),
        "path": str(resolved_path),
        "policies": policies,
    }


def _normalize_status(value: Any) -> str:
    return str(value).strip().upper()


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "t"}
    return False


def _collect_rule_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for record in records:
        created_at = _parse_datetime(record.get("created_at"))
        try:
            semantic_payload, _ = _load_semantic_payload_with_fallback(record)
        except DiagnosticsNotFoundError:
            continue

        normalized_payload = _normalize_semantic_payload(semantic_payload)
        rules = normalized_payload.get("rules", [])
        if not isinstance(rules, list):
            continue

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            status = _normalize_status(rule.get("status"))
            if status not in {"WARN", "FAIL"}:
                continue

            rule_id = str(rule.get("rule_id", "unknown_rule"))
            entry = counts.setdefault(
                rule_id,
                {
                    "rule_id": rule_id,
                    "rule_type": str(rule.get("rule_type", "unknown")),
                    "severity": _normalize_status(rule.get("severity")) or "WARN",
                    "warn_count": 0,
                    "fail_count": 0,
                    "last_seen_at": None,
                    "sample_message": str(rule.get("message", "")) or None,
                },
            )

            if status == "WARN":
                entry["warn_count"] += 1
            else:
                entry["fail_count"] += 1

            if not entry.get("sample_message"):
                entry["sample_message"] = str(rule.get("message", "")) or None

            current_last_seen = _parse_datetime(entry.get("last_seen_at"))
            if created_at is not None and (current_last_seen is None or created_at > current_last_seen):
                entry["last_seen_at"] = _isoformat_utc(created_at)
    return counts


def _count_status(records: list[dict[str, Any]], status: str) -> int:
    normalized_status = status.upper()
    return sum(1 for record in records if _normalize_status(record.get("final_status")) == normalized_status)


def _compute_metric(policy: AlertPolicy, records: list[dict[str, Any]], rule_counts: dict[str, dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    total_runs = len(records)
    fail_count = _count_status(records, "FAIL")
    blocked_count = sum(1 for record in records if _coerce_bool(record.get("blocked")))
    used_unified_count = sum(1 for record in records if _coerce_bool(record.get("used_unified")))

    context: dict[str, Any] = {
        "window_days": policy.window_days,
        "total_runs": total_runs,
        "fail_count": fail_count,
        "blocked_count": blocked_count,
        "used_unified_count": used_unified_count,
    }

    if policy.metric_type == "fail_rate":
        value = float(fail_count / total_runs) if total_runs > 0 else 0.0
        context["metric_details"] = {"numerator": fail_count, "denominator": total_runs}
        return value, context

    if policy.metric_type == "blocked_count":
        return float(blocked_count), context

    if policy.metric_type == "unified_usage_rate":
        value = float(used_unified_count / total_runs) if total_runs > 0 else 0.0
        context["metric_details"] = {"numerator": used_unified_count, "denominator": total_runs}
        return value, context

    if policy.metric_type == "fail_count":
        return float(fail_count), context

    if policy.metric_type == "top_rule_fail_count":
        top_entry = max(rule_counts.values(), key=lambda item: int(item.get("fail_count", 0)), default=None)
        value = float(int(top_entry.get("fail_count", 0))) if top_entry else 0.0
        context["rule"] = top_entry
        return value, context

    if policy.metric_type == "semantic_rule_fail_count":
        entry = rule_counts.get(policy.rule_id or "")
        value = float(int(entry.get("fail_count", 0))) if entry else 0.0
        context["rule"] = entry
        context["rule_id"] = policy.rule_id
        return value, context

    raise DiagnosticsPayloadError(f"Unsupported metric_type '{policy.metric_type}' for policy '{policy.id}'.")


def _compare_value(current: float, operator: str, threshold: float) -> bool:
    comparator = _OPERATOR_MAP.get(operator)
    if comparator is None:
        raise DiagnosticsPayloadError(f"Unsupported operator '{operator}'.")
    return bool(comparator(current, threshold))


def _build_message(policy: AlertPolicy, *, current_value: float, status: str) -> str:
    return (
        f"{policy.description} "
        f"(metric={policy.metric_type}, current={current_value:.6f}, "
        f"operator='{policy.operator}', threshold={policy.threshold:.6f}, status={status})"
    )


def _policy_records(policy: AlertPolicy, *, evaluated_at: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    window_end = evaluated_at
    window_start = evaluated_at - timedelta(days=policy.window_days)
    records = query_preflight_runs(
        source_name=policy.source_name,
        date_from=window_start,
        date_to=window_end,
        limit=None,
    )
    context = {
        "window_start": _isoformat_utc(window_start),
        "window_end": _isoformat_utc(window_end),
        "source_name": policy.source_name,
    }
    return records, context


def _emit_audit_event(
    *,
    alert_id: str,
    event_type: str,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        insert_alert_audit_event(
            {
                "alert_id": str(alert_id),
                "event_type": str(event_type).strip().upper(),
                "actor": str(actor).strip() or AUDIT_ACTOR_SYSTEM,
                "event_at": datetime.now(timezone.utc),
                "payload_json": payload or {},
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write alert audit event alert_id=%s event_type=%s: %s", alert_id, event_type, exc)


def _transition_to_history(
    *,
    policy: AlertPolicy,
    status: str,
    first_seen_at: datetime | None,
    last_seen_at: datetime | None,
    resolved_at: datetime | None,
    current_value: float,
    message: str,
    context: dict[str, Any],
    actor: str = AUDIT_ACTOR_SYSTEM,
) -> None:
    insert_alert_history(
        {
            "policy_id": policy.id,
            "status": status,
            "severity": policy.severity,
            "source_name": policy.source_name,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
            "resolved_at": resolved_at,
            "current_value": current_value,
            "threshold": policy.threshold,
            "message": message,
            "evaluation_context_json": context,
            "policy_snapshot_json": policy.to_dict(),
        }
    )
    _emit_audit_event(
        alert_id=policy.id,
        event_type=status,
        actor=actor,
        payload={
            "status": status,
            "first_seen_at": _isoformat_utc(first_seen_at),
            "last_seen_at": _isoformat_utc(last_seen_at),
            "resolved_at": _isoformat_utc(resolved_at),
            "current_value": current_value,
            "threshold": policy.threshold,
            "message": message,
            "context": context,
        },
    )


def _is_silence_match(silence: dict[str, Any], alert_item: dict[str, Any]) -> bool:
    silence_policy = silence.get("policy_id")
    silence_source = silence.get("source_name")
    silence_severity = silence.get("severity")
    silence_rule = silence.get("rule_id")

    policy = alert_item.get("policy") if isinstance(alert_item.get("policy"), dict) else {}
    alert_rule = policy.get("rule_id")

    if silence_policy is not None and str(silence_policy).strip():
        if str(silence_policy).strip() != str(alert_item.get("policy_id", "")).strip():
            return False

    if silence_source is not None and str(silence_source).strip():
        if str(silence_source).strip().lower() != str(alert_item.get("source_name", "")).strip().lower():
            return False

    if silence_severity is not None and str(silence_severity).strip():
        if str(silence_severity).strip().upper() != str(alert_item.get("severity", "")).strip().upper():
            return False

    if silence_rule is not None and str(silence_rule).strip():
        if str(silence_rule).strip() != str(alert_rule or "").strip():
            return False

    return True


def _decorate_alert_items_with_overlays(items: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    resolved_now = now or datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=timezone.utc)
    resolved_now = resolved_now.astimezone(timezone.utc)

    expire_elapsed_silences(at_time=resolved_now)
    active_silences = fetch_silences(active_only=True, at_time=resolved_now, limit=1000)
    for silence in active_silences:
        silence["is_active"] = True
    acknowledgements = {
        str(row.get("alert_id")): row for row in list_active_acknowledgements(limit=5000)
    }

    for item in items:
        alert_id = str(item.get("alert_id", "")).strip()
        matching_silence = next((silence for silence in active_silences if _is_silence_match(silence, item)), None)
        acknowledgement = acknowledgements.get(alert_id)

        item["is_silenced"] = matching_silence is not None
        item["silence"] = matching_silence
        item["is_acknowledged"] = acknowledgement is not None
        item["acknowledgement"] = acknowledgement

    return items


def evaluate_alert_policies(
    *,
    policy_path: str | Path | None = None,
    evaluated_at: datetime | None = None,
    audit_actor: str = AUDIT_ACTOR_SYSTEM,
) -> dict[str, Any]:
    payload = load_alert_policies(policy_path)
    policies: list[AlertPolicy] = payload["policies"]
    normalized_audit_actor = str(audit_actor).strip() or AUDIT_ACTOR_SYSTEM
    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    results: list[dict[str, Any]] = []
    for policy in policies:
        if not policy.enabled:
            continue

        records, window_context = _policy_records(policy, evaluated_at=now)
        rule_counts = _collect_rule_counts(records)
        current_value, metric_context = _compute_metric(policy, records, rule_counts)
        condition_met = _compare_value(current_value, policy.operator, policy.threshold)

        existing_state = get_alert_state(policy.id)
        existing_status = _normalize_status(existing_state.get("status")) if existing_state else ""
        existing_first_seen = _parse_datetime(existing_state.get("first_seen_at")) if existing_state else None
        existing_consecutive = int(existing_state.get("consecutive_breaches", 0)) if existing_state else 0

        base_context = {
            **window_context,
            **metric_context,
            "condition_met": condition_met,
            "pending_evaluations": policy.pending_evaluations,
            "operator": policy.operator,
            "threshold": policy.threshold,
            "current_value": current_value,
        }

        _emit_audit_event(
            alert_id=policy.id,
            event_type="EVALUATED",
            actor=normalized_audit_actor,
            payload=base_context,
        )

        if condition_met:
            consecutive = existing_consecutive + 1 if existing_status in {ALERT_STATUS_PENDING, ALERT_STATUS_FIRING} else 1
            first_seen_at = existing_first_seen or now
            status = ALERT_STATUS_FIRING if consecutive >= policy.pending_evaluations else ALERT_STATUS_PENDING
            message = _build_message(policy, current_value=current_value, status=status)

            upsert_alert_state(
                {
                    "policy_id": policy.id,
                    "status": status,
                    "severity": policy.severity,
                    "source_name": policy.source_name,
                    "first_seen_at": first_seen_at,
                    "last_seen_at": now,
                    "consecutive_breaches": consecutive,
                    "current_value": current_value,
                    "threshold": policy.threshold,
                    "message": message,
                    "evaluation_context_json": base_context,
                    "policy_snapshot_json": policy.to_dict(),
                    "updated_at": now,
                }
            )

            if existing_status != status:
                _transition_to_history(
                    policy=policy,
                    status=status,
                    first_seen_at=first_seen_at,
                    last_seen_at=now,
                    resolved_at=None,
                    current_value=current_value,
                    message=message,
                    context=base_context,
                    actor=normalized_audit_actor,
                )

                if status == ALERT_STATUS_FIRING:
                    try:
                        enqueue_alert_transition_notifications(
                            event_type=EVENT_ALERT_FIRING,
                            alert_id=policy.id,
                            policy_id=policy.id,
                            severity=policy.severity,
                            source_name=policy.source_name,
                            message=message,
                            current_value=current_value,
                            threshold=policy.threshold,
                            previous_status=existing_status or None,
                            current_status=status,
                            evaluated_at=now,
                            context=base_context,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Failed to enqueue firing notification for policy_id=%s: %s",
                            policy.id,
                            exc,
                        )

            results.append(
                {
                    "alert_id": policy.id,
                    "policy_id": policy.id,
                    "status": status,
                    "severity": policy.severity,
                    "source_name": policy.source_name,
                    "first_seen_at": _isoformat_utc(first_seen_at),
                    "last_seen_at": _isoformat_utc(now),
                    "resolved_at": None,
                    "current_value": current_value,
                    "threshold": policy.threshold,
                    "message": message,
                    "evaluation_context_json": base_context,
                    "policy": policy.to_dict(),
                    "evaluated_at": _isoformat_utc(now),
                }
            )
            continue

        if existing_status in {ALERT_STATUS_PENDING, ALERT_STATUS_FIRING}:
            message = _build_message(policy, current_value=current_value, status=ALERT_STATUS_RESOLVED)
            _transition_to_history(
                policy=policy,
                status=ALERT_STATUS_RESOLVED,
                first_seen_at=existing_first_seen,
                last_seen_at=now,
                resolved_at=now,
                current_value=current_value,
                message=message,
                context=base_context,
                actor=normalized_audit_actor,
            )

            if existing_status == ALERT_STATUS_FIRING:
                try:
                    enqueue_alert_transition_notifications(
                        event_type=EVENT_ALERT_RESOLVED,
                        alert_id=policy.id,
                        policy_id=policy.id,
                        severity=policy.severity,
                        source_name=policy.source_name,
                        message=message,
                        current_value=current_value,
                        threshold=policy.threshold,
                        previous_status=existing_status,
                        current_status=ALERT_STATUS_RESOLVED,
                        evaluated_at=now,
                        context=base_context,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to enqueue resolved notification for policy_id=%s: %s",
                        policy.id,
                        exc,
                    )
            delete_alert_state(policy.id)

        results.append(
            {
                "alert_id": policy.id,
                "policy_id": policy.id,
                "status": ALERT_STATUS_OK,
                "severity": policy.severity,
                "source_name": policy.source_name,
                "first_seen_at": _isoformat_utc(existing_first_seen),
                "last_seen_at": _isoformat_utc(now),
                "resolved_at": _isoformat_utc(now) if existing_status in {ALERT_STATUS_PENDING, ALERT_STATUS_FIRING} else None,
                "current_value": current_value,
                "threshold": policy.threshold,
                "message": _build_message(policy, current_value=current_value, status=ALERT_STATUS_OK),
                "evaluation_context_json": base_context,
                "policy": policy.to_dict(),
                "evaluated_at": _isoformat_utc(now),
            }
        )

    _decorate_alert_items_with_overlays(results, now=now)
    active_count = sum(1 for item in results if item["status"] in {ALERT_STATUS_PENDING, ALERT_STATUS_FIRING})
    return {
        "evaluated_at": _isoformat_utc(now),
        "total_policies": len([policy for policy in policies if policy.enabled]),
        "active_count": active_count,
        "items": results,
        "policy_path": payload["path"],
        "version": payload["version"],
    }


def run_alert_evaluation(
    *,
    policy_path: str | Path | None = None,
    evaluated_at: datetime | None = None,
    audit_actor: str = AUDIT_ACTOR_SYSTEM,
) -> dict[str, Any]:
    """Single alert-evaluation entrypoint used by scheduler, manual API, and optional read-triggered refresh."""

    return evaluate_alert_policies(
        policy_path=policy_path,
        evaluated_at=evaluated_at,
        audit_actor=audit_actor,
    )


def list_alert_policies(*, policy_path: str | Path | None = None) -> dict[str, Any]:
    payload = load_alert_policies(policy_path)
    policies: list[AlertPolicy] = payload["policies"]
    return {
        "path": payload["path"],
        "version": payload["version"],
        "items": [policy.to_dict() for policy in policies],
    }


def create_silence(
    *,
    actor: str,
    starts_at: str | datetime | None,
    ends_at: str | datetime,
    reason: str,
    policy_id: str | None = None,
    source_name: str | None = None,
    severity: str | None = None,
    rule_id: str | None = None,
) -> dict[str, Any]:
    created_by = str(actor).strip()
    if not created_by:
        raise DiagnosticsPayloadError("Actor is required for silence creation.")

    normalized_source = _normalize_source(source_name) if source_name is not None else None
    normalized_severity = _normalize_severity(severity) if severity is not None else None
    normalized_policy_id = str(policy_id).strip() if policy_id is not None and str(policy_id).strip() else None
    normalized_rule_id = str(rule_id).strip() if rule_id is not None and str(rule_id).strip() else None

    resolved_starts_at = _parse_datetime(starts_at) or datetime.now(timezone.utc)
    resolved_ends_at = _require_datetime(ends_at, field_name="ends_at")
    if resolved_ends_at <= resolved_starts_at:
        raise DiagnosticsPayloadError("Silence ends_at must be later than starts_at.")

    silence = save_alert_silence(
        {
            "policy_id": normalized_policy_id,
            "source_name": normalized_source,
            "severity": normalized_severity,
            "rule_id": normalized_rule_id,
            "starts_at": resolved_starts_at,
            "ends_at": resolved_ends_at,
            "reason": str(reason or "").strip(),
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
    )

    _emit_audit_event(
        alert_id=normalized_policy_id or f"silence:{silence['silence_id']}",
        event_type="SILENCED",
        actor=created_by,
        payload={"silence": silence},
    )

    now = datetime.now(timezone.utc)
    silence_starts = _parse_datetime(silence.get("starts_at"))
    silence_ends = _parse_datetime(silence.get("ends_at"))
    silence["is_active"] = bool(
        silence.get("expired_at") is None
        and silence_starts is not None
        and silence_ends is not None
        and silence_starts <= now < silence_ends
    )
    return silence


def expire_silence_by_id(*, silence_id: str, actor: str) -> dict[str, Any]:
    normalized_actor = str(actor).strip()
    if not normalized_actor:
        raise DiagnosticsPayloadError("Actor is required for silence expiry.")

    existing = get_silence(silence_id)
    if existing is None:
        raise DiagnosticsNotFoundError(f"Silence not found: {silence_id}")

    updated = mark_silence_expired(silence_id)
    if updated is None:
        raise DiagnosticsNotFoundError(f"Silence not found: {silence_id}")

    _emit_audit_event(
        alert_id=str(updated.get("policy_id") or f"silence:{silence_id}"),
        event_type="UNSILENCED",
        actor=normalized_actor,
        payload={"silence": updated},
    )

    return updated


def list_silences(
    *,
    limit: int = 100,
    include_expired: bool = False,
) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 1000))
    now = datetime.now(timezone.utc)
    expire_elapsed_silences(at_time=now)

    rows = fetch_silences(limit=normalized_limit, include_expired=include_expired, active_only=False, at_time=now)
    for row in rows:
        starts = _parse_datetime(row.get("starts_at"))
        ends = _parse_datetime(row.get("ends_at"))
        row["is_active"] = bool(
            row.get("expired_at") is None
            and starts is not None
            and ends is not None
            and starts <= now < ends
        )

    return {
        "limit": normalized_limit,
        "include_expired": include_expired,
        "items": rows,
    }


def acknowledge_alert(
    *,
    alert_id: str,
    actor: str,
    note: str | None = None,
) -> dict[str, Any]:
    normalized_alert_id = str(alert_id).strip()
    if not normalized_alert_id:
        raise DiagnosticsPayloadError("alert_id is required.")

    normalized_actor = str(actor).strip()
    if not normalized_actor:
        raise DiagnosticsPayloadError("Actor is required for alert acknowledgement.")

    state = get_alert_state(normalized_alert_id)
    if state is None:
        raise DiagnosticsNotFoundError(f"Active alert not found for alert_id '{normalized_alert_id}'.")

    acknowledgement = save_alert_acknowledgement(
        normalized_alert_id,
        acknowledged_by=normalized_actor,
        note=note,
        acknowledged_at=datetime.now(timezone.utc),
    )

    _emit_audit_event(
        alert_id=normalized_alert_id,
        event_type="ACKED",
        actor=normalized_actor,
        payload={"acknowledgement": acknowledgement},
    )

    return acknowledgement


def unacknowledge_alert(
    *,
    alert_id: str,
    actor: str,
) -> dict[str, Any]:
    normalized_alert_id = str(alert_id).strip()
    if not normalized_alert_id:
        raise DiagnosticsPayloadError("alert_id is required.")

    normalized_actor = str(actor).strip()
    if not normalized_actor:
        raise DiagnosticsPayloadError("Actor is required for unacknowledge.")

    acknowledgement = clear_alert_acknowledgement(normalized_alert_id, cleared_at=datetime.now(timezone.utc))
    if acknowledgement is None:
        raise DiagnosticsNotFoundError(f"Acknowledgement not found for alert_id '{normalized_alert_id}'.")

    _emit_audit_event(
        alert_id=normalized_alert_id,
        event_type="UNACKED",
        actor=normalized_actor,
        payload={"acknowledgement": acknowledgement},
    )

    return acknowledgement


def get_active_alerts(
    *,
    policy_path: str | Path | None = None,
    auto_evaluate: bool = False,
    evaluation_actor: str = AUDIT_ACTOR_SYSTEM,
) -> dict[str, Any]:
    evaluation_summary: dict[str, Any] | None = None
    if auto_evaluate:
        evaluation_summary = run_alert_evaluation(policy_path=policy_path, audit_actor=evaluation_actor)

    policies = {item["id"]: item for item in list_alert_policies(policy_path=policy_path)["items"]}
    rows = list_active_alert_states()
    items: list[dict[str, Any]] = []

    for row in rows:
        policy_id = str(row.get("policy_id"))
        item = {
            "alert_id": policy_id,
            "policy_id": policy_id,
            "status": _normalize_status(row.get("status")),
            "severity": _normalize_status(row.get("severity")),
            "source_name": row.get("source_name"),
            "first_seen_at": row.get("first_seen_at"),
            "last_seen_at": row.get("last_seen_at"),
            "resolved_at": None,
            "current_value": row.get("current_value"),
            "threshold": row.get("threshold"),
            "message": row.get("message"),
            "evaluation_context_json": row.get("evaluation_context_json") or {},
            "policy": policies.get(policy_id),
            "evaluated_at": evaluation_summary.get("evaluated_at") if evaluation_summary else row.get("updated_at"),
        }
        items.append(item)

    _decorate_alert_items_with_overlays(items)

    evaluated_at = evaluation_summary.get("evaluated_at") if evaluation_summary else _isoformat_utc(datetime.now(timezone.utc))
    return {
        "evaluated_at": evaluated_at,
        "total_active": len(items),
        "items": items,
    }


def get_alert_history(*, limit: int = 50, policy_path: str | Path | None = None) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 500))
    policies = {item["id"]: item for item in list_alert_policies(policy_path=policy_path)["items"]}
    rows = list_alert_history(limit=normalized_limit)

    items: list[dict[str, Any]] = []
    for row in rows:
        policy_id = str(row.get("policy_id"))
        items.append(
            {
                "alert_id": f"{policy_id}:{row.get('id')}",
                "policy_id": policy_id,
                "status": _normalize_status(row.get("status")),
                "severity": _normalize_status(row.get("severity")),
                "source_name": row.get("source_name"),
                "first_seen_at": row.get("first_seen_at"),
                "last_seen_at": row.get("last_seen_at"),
                "resolved_at": row.get("resolved_at"),
                "current_value": row.get("current_value"),
                "threshold": row.get("threshold"),
                "message": row.get("message"),
                "evaluation_context_json": row.get("evaluation_context_json") or {},
                "policy": policies.get(policy_id),
                "evaluated_at": row.get("created_at"),
            }
        )

    return {
        "limit": normalized_limit,
        "items": items,
    }


def list_alert_audit(*, limit: int = 50) -> dict[str, Any]:
    normalized_limit = max(1, min(int(limit), 500))
    rows = list_alert_audit_events(limit=normalized_limit)

    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "event_id": row.get("event_id"),
                "alert_id": row.get("alert_id"),
                "event_type": str(row.get("event_type", "")).upper(),
                "actor": row.get("actor"),
                "event_at": row.get("event_at"),
                "payload_json": row.get("payload_json") if isinstance(row.get("payload_json"), dict) else {},
            }
        )

    return {
        "limit": normalized_limit,
        "items": items,
    }
