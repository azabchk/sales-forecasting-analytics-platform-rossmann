from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_ATTEMPT_TABLE_NAME = "preflight_notification_delivery_attempt"
_METADATA = sa.MetaData()

_ATTEMPT_TABLE = sa.Table(
    _ATTEMPT_TABLE_NAME,
    _METADATA,
    sa.Column("attempt_id", sa.String(64), primary_key=True),
    sa.Column("outbox_item_id", sa.String(64), nullable=False),
    sa.Column("event_id", sa.String(64), nullable=True),
    sa.Column("delivery_id", sa.String(64), nullable=True),
    sa.Column("replayed_from_id", sa.String(64), nullable=True),
    sa.Column("channel_type", sa.String(32), nullable=False, default="webhook"),
    sa.Column("channel_target", sa.String(128), nullable=False),
    sa.Column("event_type", sa.String(64), nullable=False),
    sa.Column("alert_id", sa.String(160), nullable=False),
    sa.Column("policy_id", sa.String(128), nullable=False),
    sa.Column("source_name", sa.String(16), nullable=True),
    sa.Column("attempt_number", sa.Integer, nullable=False),
    sa.Column("attempt_status", sa.String(16), nullable=False, default="STARTED"),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("duration_ms", sa.Integer, nullable=True),
    sa.Column("http_status", sa.Integer, nullable=True),
    sa.Column("error_code", sa.String(64), nullable=True),
    sa.Column("error_message_safe", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_preflight_notification_attempt_outbox_item", "outbox_item_id"),
    sa.Index("ix_preflight_notification_attempt_event_id", "event_id"),
    sa.Index("ix_preflight_notification_attempt_delivery_id", "delivery_id"),
    sa.Index("ix_preflight_notification_attempt_channel_target", "channel_target"),
    sa.Index("ix_preflight_notification_attempt_event_type", "event_type"),
    sa.Index("ix_preflight_notification_attempt_status", "attempt_status"),
    sa.Index("ix_preflight_notification_attempt_started_at", "started_at"),
    sa.Index("ix_preflight_notification_attempt_completed_at", "completed_at"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for preflight notification attempt persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_datetime(value: datetime | str | None, *, default_now: bool = False) -> datetime | None:
    if value is None:
        return datetime.now(timezone.utc) if default_now else None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            return datetime.now(timezone.utc) if default_now else None
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError(f"Unsupported datetime value: {value!r}")


def _sanitize_error_message(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return None
    return text[:512]


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    for key, value in list(payload.items()):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            payload[key] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def _ensure_attempt_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_ATTEMPT_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def insert_delivery_attempt_started(record: dict[str, Any], database_url: str | None = None) -> dict[str, Any]:
    engine = _ensure_attempt_table(database_url)
    payload = dict(record)
    started_at = _ensure_datetime(payload.get("started_at"), default_now=True)
    assert started_at is not None

    payload["attempt_id"] = str(payload.get("attempt_id") or uuid.uuid4().hex)
    payload["outbox_item_id"] = str(payload.get("outbox_item_id", "")).strip()
    payload["event_id"] = str(payload.get("event_id", "")).strip() or None
    payload["delivery_id"] = str(payload.get("delivery_id", "")).strip() or None
    payload["replayed_from_id"] = str(payload.get("replayed_from_id", "")).strip() or None
    payload["channel_type"] = str(payload.get("channel_type", "webhook")).strip().lower() or "webhook"
    payload["channel_target"] = str(payload.get("channel_target", "")).strip()
    payload["event_type"] = str(payload.get("event_type", "")).strip().upper()
    payload["alert_id"] = str(payload.get("alert_id", "")).strip()
    payload["policy_id"] = str(payload.get("policy_id", "")).strip()
    payload["source_name"] = str(payload.get("source_name", "")).strip().lower() or None
    payload["attempt_number"] = max(1, int(payload.get("attempt_number", 1)))
    payload["attempt_status"] = "STARTED"
    payload["started_at"] = started_at
    payload["completed_at"] = None
    payload["duration_ms"] = None
    payload["http_status"] = None
    payload["error_code"] = None
    payload["error_message_safe"] = None
    payload["created_at"] = _ensure_datetime(payload.get("created_at"), default_now=True)

    if not payload["outbox_item_id"]:
        raise ValueError("Delivery attempt requires outbox_item_id")
    if not payload["channel_target"]:
        raise ValueError("Delivery attempt requires channel_target")
    if not payload["event_type"]:
        raise ValueError("Delivery attempt requires event_type")
    if not payload["alert_id"]:
        raise ValueError("Delivery attempt requires alert_id")
    if not payload["policy_id"]:
        raise ValueError("Delivery attempt requires policy_id")

    with engine.begin() as conn:
        conn.execute(_ATTEMPT_TABLE.insert().values(**payload))
    return _serialize_row(payload)


def complete_delivery_attempt(
    attempt_id: str,
    *,
    attempt_status: str,
    completed_at: datetime | None = None,
    duration_ms: int | float | None = None,
    http_status: int | None = None,
    error_code: str | None = None,
    error_message_safe: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    engine = _ensure_attempt_table(database_url)
    normalized_attempt_id = str(attempt_id).strip()
    if not normalized_attempt_id:
        raise ValueError("attempt_id is required")

    normalized_status = str(attempt_status).strip().upper()
    if not normalized_status:
        raise ValueError("attempt_status is required")

    with engine.begin() as conn:
        existing = conn.execute(
            sa.select(_ATTEMPT_TABLE).where(_ATTEMPT_TABLE.c.attempt_id == normalized_attempt_id)
        ).mappings().first()
        if existing is None:
            return None

        resolved_completed_at = _ensure_datetime(completed_at, default_now=True)
        assert resolved_completed_at is not None
        started_at = _ensure_datetime(existing.get("started_at"), default_now=False)

        if duration_ms is not None:
            resolved_duration = max(0, int(float(duration_ms)))
        elif started_at is not None:
            resolved_duration = max(0, int((resolved_completed_at - started_at).total_seconds() * 1000.0))
        else:
            resolved_duration = None

        values: dict[str, Any] = {
            "attempt_status": normalized_status,
            "completed_at": resolved_completed_at,
            "duration_ms": resolved_duration,
            "http_status": int(http_status) if http_status is not None else None,
            "error_code": str(error_code).strip().upper() if error_code is not None and str(error_code).strip() else None,
            "error_message_safe": _sanitize_error_message(error_message_safe),
        }
        conn.execute(
            _ATTEMPT_TABLE.update()
            .where(_ATTEMPT_TABLE.c.attempt_id == normalized_attempt_id)
            .values(**values)
        )
        updated = conn.execute(
            sa.select(_ATTEMPT_TABLE).where(_ATTEMPT_TABLE.c.attempt_id == normalized_attempt_id)
        ).mappings().first()

    return _serialize_row(dict(updated)) if updated else None


def get_delivery_attempt(attempt_id: str, database_url: str | None = None) -> dict[str, Any] | None:
    engine = _ensure_attempt_table(database_url)
    normalized_attempt_id = str(attempt_id).strip()
    if not normalized_attempt_id:
        raise ValueError("attempt_id is required")

    query = sa.select(_ATTEMPT_TABLE).where(_ATTEMPT_TABLE.c.attempt_id == normalized_attempt_id)
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None:
        return None
    return _serialize_row(dict(row))


def query_delivery_attempts(
    *,
    attempt_statuses: tuple[str, ...] | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    alert_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    date_field: str = "started_at",
    limit: int | None = None,
    descending: bool = True,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_attempt_table(database_url)

    date_column_map = {
        "started_at": _ATTEMPT_TABLE.c.started_at,
        "completed_at": _ATTEMPT_TABLE.c.completed_at,
        "created_at": _ATTEMPT_TABLE.c.created_at,
    }
    if date_field not in date_column_map:
        raise ValueError(f"Unsupported date_field '{date_field}'. Use one of {sorted(date_column_map)}.")

    query = sa.select(_ATTEMPT_TABLE)
    if attempt_statuses:
        normalized_statuses = tuple(
            str(status).strip().upper()
            for status in attempt_statuses
            if str(status).strip()
        )
        if normalized_statuses:
            query = query.where(sa.func.upper(_ATTEMPT_TABLE.c.attempt_status).in_(normalized_statuses))
    if event_type:
        query = query.where(sa.func.upper(_ATTEMPT_TABLE.c.event_type) == str(event_type).strip().upper())
    if channel_target:
        query = query.where(_ATTEMPT_TABLE.c.channel_target == str(channel_target).strip())
    if alert_id:
        query = query.where(_ATTEMPT_TABLE.c.alert_id == str(alert_id).strip())

    selected_date_column = date_column_map[date_field]
    if date_from is not None:
        normalized_from = _ensure_datetime(date_from, default_now=False)
        query = query.where(selected_date_column >= normalized_from)
    if date_to is not None:
        normalized_to = _ensure_datetime(date_to, default_now=False)
        query = query.where(selected_date_column <= normalized_to)

    query = query.order_by(selected_date_column.desc() if descending else selected_date_column.asc())
    if limit is not None:
        query = query.limit(max(1, min(int(limit), 100000)))

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [_serialize_row(dict(row)) for row in rows]


def list_delivery_attempts(
    *,
    limit: int = 100,
    attempt_statuses: tuple[str, ...] | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    alert_id: str | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    normalized_limit = max(1, min(int(limit), 1000))
    return query_delivery_attempts(
        limit=normalized_limit,
        attempt_statuses=attempt_statuses,
        event_type=event_type,
        channel_target=channel_target,
        alert_id=alert_id,
        descending=True,
        database_url=database_url,
    )
