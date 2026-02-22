from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_OUTBOX_TABLE_NAME = "preflight_notification_outbox"
_METADATA = sa.MetaData()

_OUTBOX_TABLE = sa.Table(
    _OUTBOX_TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("event_id", sa.String(64), nullable=True),
    sa.Column("delivery_id", sa.String(64), nullable=True),
    sa.Column("replayed_from_id", sa.String(64), nullable=True),
    sa.Column("event_type", sa.String(64), nullable=False),
    sa.Column("alert_id", sa.String(160), nullable=False),
    sa.Column("policy_id", sa.String(128), nullable=False),
    sa.Column("severity", sa.String(16), nullable=True),
    sa.Column("source_name", sa.String(16), nullable=True),
    sa.Column("payload_json", sa.JSON, nullable=False, default=dict),
    sa.Column("channel_type", sa.String(32), nullable=False, default="webhook"),
    sa.Column("channel_target", sa.String(128), nullable=False),
    sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
    sa.Column("attempt_count", sa.Integer, nullable=False, default=0),
    sa.Column("max_attempts", sa.Integer, nullable=False, default=5),
    sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_error", sa.Text, nullable=True),
    sa.Column("last_http_status", sa.Integer, nullable=True),
    sa.Column("last_error_code", sa.String(64), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    sa.Index("ix_preflight_notification_outbox_status", "status"),
    sa.Index("ix_preflight_notification_outbox_next_retry_at", "next_retry_at"),
    sa.Index("ix_preflight_notification_outbox_created_at", "created_at"),
    sa.Index("ix_preflight_notification_outbox_event_type", "event_type"),
    sa.Index("ix_preflight_notification_outbox_policy_id", "policy_id"),
    sa.Index("ix_preflight_notification_outbox_event_id", "event_id"),
    sa.Index("ix_preflight_notification_outbox_delivery_id", "delivery_id"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()

_BACKWARD_COMPAT_COLUMNS: dict[str, str] = {
    "event_id": "VARCHAR(64)",
    "delivery_id": "VARCHAR(64)",
    "replayed_from_id": "VARCHAR(64)",
    "last_http_status": "INTEGER",
    "last_error_code": "VARCHAR(64)",
}


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for preflight notification outbox persistence")
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


def _add_missing_columns(engine: sa.Engine) -> None:
    inspector = sa.inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(_OUTBOX_TABLE_NAME)}
    missing = [(name, ddl) for name, ddl in _BACKWARD_COMPAT_COLUMNS.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as conn:
        for column_name, ddl in missing:
            conn.execute(sa.text(f"ALTER TABLE {_OUTBOX_TABLE_NAME} ADD COLUMN {column_name} {ddl}"))


def _ensure_indexes(engine: sa.Engine) -> None:
    for index in _OUTBOX_TABLE.indexes:
        index.create(bind=engine, checkfirst=True)


def _ensure_outbox_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_OUTBOX_TABLE], checkfirst=True)
        _add_missing_columns(engine)
        _ensure_indexes(engine)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    for key, value in list(payload.items()):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            payload[key] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def insert_outbox_event(record: dict[str, Any], database_url: str | None = None) -> dict[str, Any]:
    engine = _ensure_outbox_table(database_url)
    payload = dict(record)
    now = _ensure_datetime(payload.get("created_at"), default_now=True)
    assert now is not None

    payload["id"] = str(payload.get("id") or uuid.uuid4().hex)
    payload["event_id"] = str(payload.get("event_id") or uuid.uuid4().hex)
    payload["delivery_id"] = str(payload.get("delivery_id") or uuid.uuid4().hex)
    payload["replayed_from_id"] = str(payload.get("replayed_from_id", "")).strip() or None
    payload["event_type"] = str(payload.get("event_type", "")).strip().upper()
    payload["alert_id"] = str(payload.get("alert_id", "")).strip()
    payload["policy_id"] = str(payload.get("policy_id", "")).strip()
    payload["severity"] = str(payload.get("severity", "")).strip().upper() or None
    payload["source_name"] = str(payload.get("source_name", "")).strip().lower() or None
    payload["payload_json"] = payload.get("payload_json") if isinstance(payload.get("payload_json"), dict) else {}
    payload["channel_type"] = str(payload.get("channel_type", "webhook")).strip().lower() or "webhook"
    payload["channel_target"] = str(payload.get("channel_target", "")).strip()
    payload["status"] = str(payload.get("status", "PENDING")).strip().upper() or "PENDING"
    payload["attempt_count"] = int(payload.get("attempt_count", 0))
    payload["max_attempts"] = max(1, int(payload.get("max_attempts", 5)))
    payload["next_retry_at"] = _ensure_datetime(payload.get("next_retry_at"), default_now=True)
    payload["last_error"] = str(payload.get("last_error", "")).strip() or None
    payload["last_http_status"] = int(payload.get("last_http_status")) if payload.get("last_http_status") is not None else None
    payload["last_error_code"] = str(payload.get("last_error_code", "")).strip().upper() or None
    payload["created_at"] = now
    payload["updated_at"] = _ensure_datetime(payload.get("updated_at"), default_now=True)
    payload["sent_at"] = _ensure_datetime(payload.get("sent_at"), default_now=False)

    if not payload["event_type"]:
        raise ValueError("Outbox event requires event_type")
    if not payload["alert_id"]:
        raise ValueError("Outbox event requires alert_id")
    if not payload["policy_id"]:
        raise ValueError("Outbox event requires policy_id")
    if not payload["channel_target"]:
        raise ValueError("Outbox event requires channel_target")

    with engine.begin() as conn:
        conn.execute(_OUTBOX_TABLE.insert().values(**payload))
    return _serialize_row(payload)


def clone_outbox_item_for_replay(
    item_id: str,
    *,
    replayed_at: datetime | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    source_row = get_outbox_item(item_id=item_id, database_url=database_url)
    if source_row is None:
        return None

    now = _ensure_datetime(replayed_at, default_now=True)
    assert now is not None
    event_id = str(source_row.get("event_id") or uuid.uuid4().hex)

    replay_payload = {
        "id": uuid.uuid4().hex,
        "event_id": event_id,
        "delivery_id": uuid.uuid4().hex,
        "replayed_from_id": str(source_row.get("id")),
        "event_type": source_row.get("event_type"),
        "alert_id": source_row.get("alert_id"),
        "policy_id": source_row.get("policy_id"),
        "severity": source_row.get("severity"),
        "source_name": source_row.get("source_name"),
        "payload_json": source_row.get("payload_json") if isinstance(source_row.get("payload_json"), dict) else {},
        "channel_type": source_row.get("channel_type") or "webhook",
        "channel_target": source_row.get("channel_target"),
        "status": "PENDING",
        "attempt_count": 0,
        "max_attempts": max(1, int(source_row.get("max_attempts", 5))),
        "next_retry_at": now,
        "last_error": None,
        "last_http_status": None,
        "last_error_code": None,
        "created_at": now,
        "updated_at": now,
        "sent_at": None,
    }
    return insert_outbox_event(replay_payload, database_url=database_url)


def list_due_outbox_items(
    *,
    limit: int = 50,
    statuses: tuple[str, ...] = ("PENDING", "RETRYING"),
    due_at: datetime | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_outbox_table(database_url)
    normalized_limit = max(1, min(int(limit), 1000))
    normalized_statuses = tuple(str(status).strip().upper() for status in statuses if str(status).strip())
    now = _ensure_datetime(due_at, default_now=True)
    assert now is not None

    query = (
        sa.select(_OUTBOX_TABLE)
        .where(sa.func.upper(_OUTBOX_TABLE.c.status).in_(normalized_statuses))
        .where(_OUTBOX_TABLE.c.next_retry_at <= now)
        .order_by(_OUTBOX_TABLE.c.next_retry_at.asc(), _OUTBOX_TABLE.c.created_at.asc())
        .limit(normalized_limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [_serialize_row(dict(row)) for row in rows]


def get_outbox_item(item_id: str, database_url: str | None = None) -> dict[str, Any] | None:
    engine = _ensure_outbox_table(database_url)
    query = sa.select(_OUTBOX_TABLE).where(_OUTBOX_TABLE.c.id == str(item_id).strip())
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None:
        return None
    return _serialize_row(dict(row))


def mark_outbox_sent(
    item_id: str,
    *,
    sent_at: datetime | None = None,
    attempt_count: int | None = None,
    event_id: str | None = None,
    delivery_id: str | None = None,
    last_http_status: int | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    engine = _ensure_outbox_table(database_url)
    now = _ensure_datetime(sent_at, default_now=True)
    assert now is not None
    values: dict[str, Any] = {
        "status": "SENT",
        "sent_at": now,
        "updated_at": now,
        "last_error": None,
        "last_error_code": None,
        "last_http_status": int(last_http_status) if last_http_status is not None else None,
    }
    if attempt_count is not None:
        values["attempt_count"] = max(0, int(attempt_count))
    if event_id is not None and str(event_id).strip():
        values["event_id"] = str(event_id).strip()
    if delivery_id is not None and str(delivery_id).strip():
        values["delivery_id"] = str(delivery_id).strip()

    with engine.begin() as conn:
        result = conn.execute(
            _OUTBOX_TABLE.update()
            .where(_OUTBOX_TABLE.c.id == str(item_id).strip())
            .values(**values)
        )
        if result.rowcount == 0:
            return None
        row = conn.execute(sa.select(_OUTBOX_TABLE).where(_OUTBOX_TABLE.c.id == str(item_id).strip())).mappings().first()

    return _serialize_row(dict(row)) if row else None


def mark_outbox_retry(
    item_id: str,
    *,
    next_retry_at: datetime,
    last_error: str | None = None,
    attempt_count: int | None = None,
    event_id: str | None = None,
    delivery_id: str | None = None,
    last_http_status: int | None = None,
    last_error_code: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    engine = _ensure_outbox_table(database_url)
    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "status": "RETRYING",
        "next_retry_at": _ensure_datetime(next_retry_at, default_now=False),
        "last_error": str(last_error).strip() if last_error is not None and str(last_error).strip() else None,
        "last_http_status": int(last_http_status) if last_http_status is not None else None,
        "last_error_code": str(last_error_code).strip().upper() if last_error_code is not None and str(last_error_code).strip() else None,
        "updated_at": now,
    }
    if attempt_count is not None:
        values["attempt_count"] = max(0, int(attempt_count))
    if event_id is not None and str(event_id).strip():
        values["event_id"] = str(event_id).strip()
    if delivery_id is not None and str(delivery_id).strip():
        values["delivery_id"] = str(delivery_id).strip()

    with engine.begin() as conn:
        result = conn.execute(
            _OUTBOX_TABLE.update()
            .where(_OUTBOX_TABLE.c.id == str(item_id).strip())
            .values(**values)
        )
        if result.rowcount == 0:
            return None
        row = conn.execute(sa.select(_OUTBOX_TABLE).where(_OUTBOX_TABLE.c.id == str(item_id).strip())).mappings().first()

    return _serialize_row(dict(row)) if row else None


def mark_outbox_dead(
    item_id: str,
    *,
    last_error: str | None = None,
    attempt_count: int | None = None,
    event_id: str | None = None,
    delivery_id: str | None = None,
    last_http_status: int | None = None,
    last_error_code: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    engine = _ensure_outbox_table(database_url)
    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "status": "DEAD",
        "last_error": str(last_error).strip() if last_error is not None and str(last_error).strip() else None,
        "last_http_status": int(last_http_status) if last_http_status is not None else None,
        "last_error_code": str(last_error_code).strip().upper() if last_error_code is not None and str(last_error_code).strip() else None,
        "updated_at": now,
    }
    if attempt_count is not None:
        values["attempt_count"] = max(0, int(attempt_count))
    if event_id is not None and str(event_id).strip():
        values["event_id"] = str(event_id).strip()
    if delivery_id is not None and str(delivery_id).strip():
        values["delivery_id"] = str(delivery_id).strip()

    with engine.begin() as conn:
        result = conn.execute(
            _OUTBOX_TABLE.update()
            .where(_OUTBOX_TABLE.c.id == str(item_id).strip())
            .values(**values)
        )
        if result.rowcount == 0:
            return None
        row = conn.execute(sa.select(_OUTBOX_TABLE).where(_OUTBOX_TABLE.c.id == str(item_id).strip())).mappings().first()

    return _serialize_row(dict(row)) if row else None


def list_outbox_history(
    *,
    limit: int = 100,
    statuses: tuple[str, ...] | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_outbox_table(database_url)
    normalized_limit = max(1, min(int(limit), 1000))

    query = sa.select(_OUTBOX_TABLE)
    if statuses:
        normalized_statuses = tuple(str(status).strip().upper() for status in statuses if str(status).strip())
        query = query.where(sa.func.upper(_OUTBOX_TABLE.c.status).in_(normalized_statuses))
    if event_type:
        query = query.where(sa.func.upper(_OUTBOX_TABLE.c.event_type) == str(event_type).strip().upper())
    if channel_target:
        query = query.where(_OUTBOX_TABLE.c.channel_target == str(channel_target).strip())

    query = query.order_by(_OUTBOX_TABLE.c.created_at.desc()).limit(normalized_limit)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [_serialize_row(dict(row)) for row in rows]


def query_outbox_items(
    *,
    statuses: tuple[str, ...] | None = None,
    event_type: str | None = None,
    channel_target: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    date_field: str = "created_at",
    limit: int | None = None,
    descending: bool = True,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_outbox_table(database_url)

    date_column_map = {
        "created_at": _OUTBOX_TABLE.c.created_at,
        "updated_at": _OUTBOX_TABLE.c.updated_at,
        "sent_at": _OUTBOX_TABLE.c.sent_at,
    }
    if date_field not in date_column_map:
        raise ValueError(f"Unsupported date_field '{date_field}'. Use one of {sorted(date_column_map)}.")

    query = sa.select(_OUTBOX_TABLE)
    if statuses:
        normalized_statuses = tuple(str(status).strip().upper() for status in statuses if str(status).strip())
        if normalized_statuses:
            query = query.where(sa.func.upper(_OUTBOX_TABLE.c.status).in_(normalized_statuses))
    if event_type:
        query = query.where(sa.func.upper(_OUTBOX_TABLE.c.event_type) == str(event_type).strip().upper())
    if channel_target:
        query = query.where(_OUTBOX_TABLE.c.channel_target == str(channel_target).strip())

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
