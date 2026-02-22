from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa

_STATE_TABLE_NAME = "preflight_alert_state"
_HISTORY_TABLE_NAME = "preflight_alert_history"
_SILENCE_TABLE_NAME = "preflight_alert_silence"
_ACK_TABLE_NAME = "preflight_alert_acknowledgement"
_AUDIT_TABLE_NAME = "preflight_alert_audit_event"
_SCHEDULER_LEASE_TABLE_NAME = "preflight_alert_scheduler_lease"

_METADATA = sa.MetaData()

_ALERT_STATE_TABLE = sa.Table(
    _STATE_TABLE_NAME,
    _METADATA,
    sa.Column("policy_id", sa.String(128), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("severity", sa.String(16), nullable=False),
    sa.Column("source_name", sa.String(16), nullable=True),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("consecutive_breaches", sa.Integer, nullable=False, default=0),
    sa.Column("current_value", sa.Float, nullable=True),
    sa.Column("threshold", sa.Float, nullable=True),
    sa.Column("message", sa.Text, nullable=False, default=""),
    sa.Column("evaluation_context_json", sa.JSON, nullable=False, default=dict),
    sa.Column("policy_snapshot_json", sa.JSON, nullable=False, default=dict),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("policy_id", name="pk_preflight_alert_state"),
    sa.Index("ix_preflight_alert_state_status", "status"),
    sa.Index("ix_preflight_alert_state_last_seen", "last_seen_at"),
)

_ALERT_HISTORY_TABLE = sa.Table(
    _HISTORY_TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("policy_id", sa.String(128), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("severity", sa.String(16), nullable=False),
    sa.Column("source_name", sa.String(16), nullable=True),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("current_value", sa.Float, nullable=True),
    sa.Column("threshold", sa.Float, nullable=True),
    sa.Column("message", sa.Text, nullable=False, default=""),
    sa.Column("evaluation_context_json", sa.JSON, nullable=False, default=dict),
    sa.Column("policy_snapshot_json", sa.JSON, nullable=False, default=dict),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_preflight_alert_history_policy_id", "policy_id"),
    sa.Index("ix_preflight_alert_history_status", "status"),
    sa.Index("ix_preflight_alert_history_created_at", "created_at"),
)

_ALERT_SILENCE_TABLE = sa.Table(
    _SILENCE_TABLE_NAME,
    _METADATA,
    sa.Column("silence_id", sa.String(64), primary_key=True),
    sa.Column("policy_id", sa.String(128), nullable=True),
    sa.Column("source_name", sa.String(16), nullable=True),
    sa.Column("severity", sa.String(16), nullable=True),
    sa.Column("rule_id", sa.String(128), nullable=True),
    sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reason", sa.Text, nullable=False, default=""),
    sa.Column("created_by", sa.String(128), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    sa.Index("ix_preflight_alert_silence_ends_at", "ends_at"),
    sa.Index("ix_preflight_alert_silence_expired_at", "expired_at"),
    sa.Index("ix_preflight_alert_silence_policy_id", "policy_id"),
    sa.Index("ix_preflight_alert_silence_source_name", "source_name"),
)

_ALERT_ACK_TABLE = sa.Table(
    _ACK_TABLE_NAME,
    _METADATA,
    sa.Column("alert_id", sa.String(160), primary_key=True),
    sa.Column("acknowledged_by", sa.String(128), nullable=False),
    sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("note", sa.Text, nullable=True),
    sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_preflight_alert_ack_cleared_at", "cleared_at"),
    sa.Index("ix_preflight_alert_ack_updated_at", "updated_at"),
)

_ALERT_AUDIT_TABLE = sa.Table(
    _AUDIT_TABLE_NAME,
    _METADATA,
    sa.Column("event_id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("alert_id", sa.String(160), nullable=False),
    sa.Column("event_type", sa.String(32), nullable=False),
    sa.Column("actor", sa.String(128), nullable=False),
    sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload_json", sa.JSON, nullable=False, default=dict),
    sa.Index("ix_preflight_alert_audit_event_at", "event_at"),
    sa.Index("ix_preflight_alert_audit_alert_id", "alert_id"),
    sa.Index("ix_preflight_alert_audit_event_type", "event_type"),
)

_SCHEDULER_LEASE_TABLE = sa.Table(
    _SCHEDULER_LEASE_TABLE_NAME,
    _METADATA,
    sa.Column("lease_name", sa.String(128), primary_key=True),
    sa.Column("owner_id", sa.String(128), nullable=False),
    sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_preflight_alert_scheduler_lease_expires_at", "expires_at"),
    sa.Index("ix_preflight_alert_scheduler_lease_owner_id", "owner_id"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for preflight alert registry persistence")
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


def _ensure_alert_tables(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(
            engine,
            tables=[
                _ALERT_STATE_TABLE,
                _ALERT_HISTORY_TABLE,
                _ALERT_SILENCE_TABLE,
                _ALERT_ACK_TABLE,
                _ALERT_AUDIT_TABLE,
                _SCHEDULER_LEASE_TABLE,
            ],
            checkfirst=True,
        )
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


def upsert_alert_state(record: dict[str, Any], database_url: str | None = None) -> None:
    """Insert or update current alert state for one policy."""

    engine = _ensure_alert_tables(database_url)
    payload = dict(record)
    payload["updated_at"] = _ensure_datetime(payload.get("updated_at"), default_now=True)
    payload["evaluation_context_json"] = payload.get("evaluation_context_json") or {}
    payload["policy_snapshot_json"] = payload.get("policy_snapshot_json") or {}
    payload["consecutive_breaches"] = int(payload.get("consecutive_breaches", 0))

    with engine.begin() as conn:
        try:
            conn.execute(_ALERT_STATE_TABLE.insert().values(**payload))
        except sa.exc.IntegrityError:
            conn.execute(
                _ALERT_STATE_TABLE.update()
                .where(_ALERT_STATE_TABLE.c.policy_id == payload["policy_id"])
                .values(**payload)
            )


def get_alert_state(policy_id: str, database_url: str | None = None) -> dict[str, Any] | None:
    engine = _ensure_alert_tables(database_url)
    query = sa.select(_ALERT_STATE_TABLE).where(_ALERT_STATE_TABLE.c.policy_id == policy_id)

    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()

    if row is None:
        return None
    return _serialize_row(dict(row))


def delete_alert_state(policy_id: str, database_url: str | None = None) -> None:
    engine = _ensure_alert_tables(database_url)
    query = _ALERT_STATE_TABLE.delete().where(_ALERT_STATE_TABLE.c.policy_id == policy_id)
    with engine.begin() as conn:
        conn.execute(query)


def list_active_alert_states(
    *,
    statuses: tuple[str, ...] = ("PENDING", "FIRING"),
    limit: int = 200,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_alert_tables(database_url)
    normalized_limit = max(1, min(int(limit), 1000))
    normalized_statuses = tuple(str(status).strip().upper() for status in statuses if str(status).strip())

    query = (
        sa.select(_ALERT_STATE_TABLE)
        .where(sa.func.upper(_ALERT_STATE_TABLE.c.status).in_(normalized_statuses))
        .order_by(_ALERT_STATE_TABLE.c.severity.desc(), _ALERT_STATE_TABLE.c.last_seen_at.desc())
        .limit(normalized_limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [_serialize_row(dict(row)) for row in rows]


def insert_alert_history(record: dict[str, Any], database_url: str | None = None) -> None:
    """Insert one alert transition history event."""

    engine = _ensure_alert_tables(database_url)
    payload = dict(record)
    payload["created_at"] = _ensure_datetime(payload.get("created_at"), default_now=True)
    payload["evaluation_context_json"] = payload.get("evaluation_context_json") or {}
    payload["policy_snapshot_json"] = payload.get("policy_snapshot_json") or {}

    with engine.begin() as conn:
        conn.execute(_ALERT_HISTORY_TABLE.insert().values(**payload))


def list_alert_history(
    *,
    limit: int = 50,
    policy_id: str | None = None,
    status: str | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_alert_tables(database_url)
    normalized_limit = max(1, min(int(limit), 1000))

    query = sa.select(_ALERT_HISTORY_TABLE).order_by(_ALERT_HISTORY_TABLE.c.created_at.desc()).limit(normalized_limit)
    if policy_id:
        query = query.where(_ALERT_HISTORY_TABLE.c.policy_id == policy_id)
    if status:
        query = query.where(sa.func.upper(_ALERT_HISTORY_TABLE.c.status) == str(status).strip().upper())

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [_serialize_row(dict(row)) for row in rows]


def create_silence(record: dict[str, Any], database_url: str | None = None) -> dict[str, Any]:
    engine = _ensure_alert_tables(database_url)
    payload = dict(record)
    payload["silence_id"] = str(payload.get("silence_id") or uuid.uuid4().hex)
    payload["starts_at"] = _ensure_datetime(payload.get("starts_at"), default_now=True)
    payload["ends_at"] = _ensure_datetime(payload.get("ends_at"), default_now=False)
    payload["created_at"] = _ensure_datetime(payload.get("created_at"), default_now=True)
    payload["expired_at"] = _ensure_datetime(payload.get("expired_at"), default_now=False)
    payload["reason"] = str(payload.get("reason", "") or "")
    payload["created_by"] = str(payload.get("created_by", "") or "")

    if payload["ends_at"] is None:
        raise ValueError("Silence requires ends_at")
    if payload["starts_at"] is None:
        raise ValueError("Silence requires starts_at")
    if payload["ends_at"] <= payload["starts_at"]:
        raise ValueError("Silence ends_at must be later than starts_at")
    if not payload["created_by"].strip():
        raise ValueError("Silence requires created_by")

    with engine.begin() as conn:
        conn.execute(_ALERT_SILENCE_TABLE.insert().values(**payload))

    return _serialize_row(payload)


def get_silence(silence_id: str, database_url: str | None = None) -> dict[str, Any] | None:
    engine = _ensure_alert_tables(database_url)
    query = sa.select(_ALERT_SILENCE_TABLE).where(_ALERT_SILENCE_TABLE.c.silence_id == silence_id)
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None:
        return None
    return _serialize_row(dict(row))


def expire_silence(
    silence_id: str,
    *,
    expired_at: datetime | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    engine = _ensure_alert_tables(database_url)
    resolved_expired_at = _ensure_datetime(expired_at, default_now=True)

    with engine.begin() as conn:
        result = conn.execute(
            _ALERT_SILENCE_TABLE.update()
            .where(_ALERT_SILENCE_TABLE.c.silence_id == silence_id)
            .where(_ALERT_SILENCE_TABLE.c.expired_at.is_(None))
            .values(expired_at=resolved_expired_at)
        )
        if result.rowcount == 0:
            existing = conn.execute(
                sa.select(_ALERT_SILENCE_TABLE).where(_ALERT_SILENCE_TABLE.c.silence_id == silence_id)
            ).mappings().first()
            if existing is None:
                return None
            return _serialize_row(dict(existing))

        row = conn.execute(
            sa.select(_ALERT_SILENCE_TABLE).where(_ALERT_SILENCE_TABLE.c.silence_id == silence_id)
        ).mappings().first()

    return _serialize_row(dict(row)) if row else None


def expire_elapsed_silences(
    *,
    at_time: datetime | None = None,
    database_url: str | None = None,
) -> int:
    engine = _ensure_alert_tables(database_url)
    now = _ensure_datetime(at_time, default_now=True)
    assert now is not None

    with engine.begin() as conn:
        result = conn.execute(
            _ALERT_SILENCE_TABLE.update()
            .where(_ALERT_SILENCE_TABLE.c.expired_at.is_(None))
            .where(_ALERT_SILENCE_TABLE.c.ends_at <= now)
            .values(expired_at=now)
        )
    return int(result.rowcount or 0)


def list_silences(
    *,
    limit: int = 100,
    include_expired: bool = False,
    active_only: bool = False,
    at_time: datetime | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_alert_tables(database_url)
    normalized_limit = max(1, min(int(limit), 1000))
    now = _ensure_datetime(at_time, default_now=True)
    assert now is not None

    query = sa.select(_ALERT_SILENCE_TABLE)
    if active_only:
        query = (
            query.where(_ALERT_SILENCE_TABLE.c.expired_at.is_(None))
            .where(_ALERT_SILENCE_TABLE.c.starts_at <= now)
            .where(_ALERT_SILENCE_TABLE.c.ends_at > now)
        )
    elif not include_expired:
        query = query.where(
            sa.or_(
                _ALERT_SILENCE_TABLE.c.expired_at.is_(None),
                _ALERT_SILENCE_TABLE.c.expired_at > now,
            )
        )

    query = query.order_by(_ALERT_SILENCE_TABLE.c.created_at.desc()).limit(normalized_limit)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [_serialize_row(dict(row)) for row in rows]


def acknowledge_alert(
    alert_id: str,
    *,
    acknowledged_by: str,
    note: str | None = None,
    acknowledged_at: datetime | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    if not str(alert_id).strip():
        raise ValueError("alert_id is required")
    if not str(acknowledged_by).strip():
        raise ValueError("acknowledged_by is required")

    engine = _ensure_alert_tables(database_url)
    now = _ensure_datetime(acknowledged_at, default_now=True)
    assert now is not None

    payload = {
        "alert_id": str(alert_id),
        "acknowledged_by": str(acknowledged_by).strip(),
        "acknowledged_at": now,
        "note": str(note).strip() if note is not None and str(note).strip() else None,
        "cleared_at": None,
        "updated_at": now,
    }

    with engine.begin() as conn:
        try:
            conn.execute(_ALERT_ACK_TABLE.insert().values(**payload))
        except sa.exc.IntegrityError:
            conn.execute(
                _ALERT_ACK_TABLE.update()
                .where(_ALERT_ACK_TABLE.c.alert_id == payload["alert_id"])
                .values(**payload)
            )

        row = conn.execute(
            sa.select(_ALERT_ACK_TABLE).where(_ALERT_ACK_TABLE.c.alert_id == payload["alert_id"])
        ).mappings().first()

    return _serialize_row(dict(row)) if row else _serialize_row(payload)


def unacknowledge_alert(
    alert_id: str,
    *,
    cleared_at: datetime | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    if not str(alert_id).strip():
        raise ValueError("alert_id is required")

    engine = _ensure_alert_tables(database_url)
    now = _ensure_datetime(cleared_at, default_now=True)
    assert now is not None

    with engine.begin() as conn:
        result = conn.execute(
            _ALERT_ACK_TABLE.update()
            .where(_ALERT_ACK_TABLE.c.alert_id == str(alert_id))
            .where(_ALERT_ACK_TABLE.c.cleared_at.is_(None))
            .values(cleared_at=now, updated_at=now)
        )

        row = conn.execute(
            sa.select(_ALERT_ACK_TABLE).where(_ALERT_ACK_TABLE.c.alert_id == str(alert_id))
        ).mappings().first()

    if result.rowcount == 0 and row is None:
        return None
    return _serialize_row(dict(row)) if row else None


def get_alert_acknowledgement(
    alert_id: str,
    *,
    include_cleared: bool = False,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    engine = _ensure_alert_tables(database_url)
    query = sa.select(_ALERT_ACK_TABLE).where(_ALERT_ACK_TABLE.c.alert_id == str(alert_id))
    if not include_cleared:
        query = query.where(_ALERT_ACK_TABLE.c.cleared_at.is_(None))

    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()

    if row is None:
        return None
    return _serialize_row(dict(row))


def list_active_acknowledgements(
    *,
    limit: int = 500,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_alert_tables(database_url)
    normalized_limit = max(1, min(int(limit), 5000))
    query = (
        sa.select(_ALERT_ACK_TABLE)
        .where(_ALERT_ACK_TABLE.c.cleared_at.is_(None))
        .order_by(_ALERT_ACK_TABLE.c.updated_at.desc())
        .limit(normalized_limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [_serialize_row(dict(row)) for row in rows]


def insert_alert_audit_event(record: dict[str, Any], database_url: str | None = None) -> dict[str, Any]:
    engine = _ensure_alert_tables(database_url)
    payload = dict(record)
    payload["alert_id"] = str(payload.get("alert_id", "") or "")
    payload["event_type"] = str(payload.get("event_type", "") or "").strip().upper()
    payload["actor"] = str(payload.get("actor", "") or "").strip()
    payload["event_at"] = _ensure_datetime(payload.get("event_at"), default_now=True)
    payload["payload_json"] = payload.get("payload_json") or {}

    if not payload["alert_id"]:
        raise ValueError("Audit event requires alert_id")
    if not payload["event_type"]:
        raise ValueError("Audit event requires event_type")
    if not payload["actor"]:
        raise ValueError("Audit event requires actor")

    with engine.begin() as conn:
        result = conn.execute(_ALERT_AUDIT_TABLE.insert().values(**payload))
        event_id = result.inserted_primary_key[0] if result.inserted_primary_key else None

        row = None
        if event_id is not None:
            row = conn.execute(
                sa.select(_ALERT_AUDIT_TABLE).where(_ALERT_AUDIT_TABLE.c.event_id == event_id)
            ).mappings().first()

    return _serialize_row(dict(row)) if row else _serialize_row(payload)


def list_alert_audit_events(
    *,
    limit: int = 50,
    alert_id: str | None = None,
    event_type: str | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_alert_tables(database_url)
    normalized_limit = max(1, min(int(limit), 1000))

    query = sa.select(_ALERT_AUDIT_TABLE)
    if alert_id:
        query = query.where(_ALERT_AUDIT_TABLE.c.alert_id == str(alert_id))
    if event_type:
        query = query.where(sa.func.upper(_ALERT_AUDIT_TABLE.c.event_type) == str(event_type).strip().upper())

    query = query.order_by(_ALERT_AUDIT_TABLE.c.event_at.desc()).limit(normalized_limit)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [_serialize_row(dict(row)) for row in rows]


def count_alert_audit_events_by_type(database_url: str | None = None) -> dict[str, int]:
    """Return alert audit event counters grouped by event_type."""

    engine = _ensure_alert_tables(database_url)
    query = sa.select(
        sa.func.upper(_ALERT_AUDIT_TABLE.c.event_type).label("event_type"),
        sa.func.count().label("count"),
    ).group_by(sa.func.upper(_ALERT_AUDIT_TABLE.c.event_type))

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    counters: dict[str, int] = {}
    for row in rows:
        event_type = str(row.get("event_type", "")).strip().upper() or "UNKNOWN"
        counters[event_type] = int(row.get("count", 0) or 0)
    return counters


def count_active_silences(
    *,
    at_time: datetime | None = None,
    database_url: str | None = None,
) -> int:
    """Count currently active silences."""

    engine = _ensure_alert_tables(database_url)
    now = _ensure_datetime(at_time, default_now=True)
    assert now is not None

    query = sa.select(sa.func.count()).where(
        sa.and_(
            _ALERT_SILENCE_TABLE.c.expired_at.is_(None),
            _ALERT_SILENCE_TABLE.c.starts_at <= now,
            _ALERT_SILENCE_TABLE.c.ends_at > now,
        )
    )
    with engine.connect() as conn:
        count = conn.execute(query).scalar_one()
    return int(count or 0)


def acquire_scheduler_lease(
    *,
    lease_name: str,
    owner_id: str,
    lease_ttl_seconds: int,
    now: datetime | None = None,
    database_url: str | None = None,
) -> bool:
    """Acquire or renew a scheduler lease.

    Returns True when the caller owns the lease after this call.
    Returns False when the lease is currently held by another owner and not expired.
    """

    normalized_lease_name = str(lease_name).strip()
    normalized_owner_id = str(owner_id).strip()
    if not normalized_lease_name:
        raise ValueError("lease_name is required")
    if not normalized_owner_id:
        raise ValueError("owner_id is required")

    ttl_seconds = int(lease_ttl_seconds)
    if ttl_seconds < 1:
        raise ValueError("lease_ttl_seconds must be >= 1")

    engine = _ensure_alert_tables(database_url)
    acquired_at = _ensure_datetime(now, default_now=True)
    assert acquired_at is not None
    expires_at = acquired_at + timedelta(seconds=ttl_seconds)

    payload = {
        "lease_name": normalized_lease_name,
        "owner_id": normalized_owner_id,
        "acquired_at": acquired_at,
        "heartbeat_at": acquired_at,
        "expires_at": expires_at,
        "updated_at": acquired_at,
    }

    with engine.begin() as conn:
        try:
            conn.execute(_SCHEDULER_LEASE_TABLE.insert().values(**payload))
            return True
        except sa.exc.IntegrityError:
            result = conn.execute(
                _SCHEDULER_LEASE_TABLE.update()
                .where(_SCHEDULER_LEASE_TABLE.c.lease_name == normalized_lease_name)
                .where(
                    sa.or_(
                        _SCHEDULER_LEASE_TABLE.c.owner_id == normalized_owner_id,
                        _SCHEDULER_LEASE_TABLE.c.expires_at <= acquired_at,
                    )
                )
                .values(
                    owner_id=normalized_owner_id,
                    acquired_at=acquired_at,
                    heartbeat_at=acquired_at,
                    expires_at=expires_at,
                    updated_at=acquired_at,
                )
            )
            return bool(result.rowcount and result.rowcount > 0)


def get_scheduler_lease(
    *,
    lease_name: str,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    normalized_lease_name = str(lease_name).strip()
    if not normalized_lease_name:
        raise ValueError("lease_name is required")

    engine = _ensure_alert_tables(database_url)
    query = sa.select(_SCHEDULER_LEASE_TABLE).where(_SCHEDULER_LEASE_TABLE.c.lease_name == normalized_lease_name)
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None:
        return None
    return _serialize_row(dict(row))


def release_scheduler_lease(
    *,
    lease_name: str,
    owner_id: str,
    released_at: datetime | None = None,
    database_url: str | None = None,
) -> bool:
    normalized_lease_name = str(lease_name).strip()
    normalized_owner_id = str(owner_id).strip()
    if not normalized_lease_name:
        raise ValueError("lease_name is required")
    if not normalized_owner_id:
        raise ValueError("owner_id is required")

    engine = _ensure_alert_tables(database_url)
    now = _ensure_datetime(released_at, default_now=True)
    assert now is not None

    with engine.begin() as conn:
        result = conn.execute(
            _SCHEDULER_LEASE_TABLE.update()
            .where(_SCHEDULER_LEASE_TABLE.c.lease_name == normalized_lease_name)
            .where(_SCHEDULER_LEASE_TABLE.c.owner_id == normalized_owner_id)
            .values(
                expires_at=now,
                heartbeat_at=now,
                updated_at=now,
            )
        )
    return bool(result.rowcount and result.rowcount > 0)
