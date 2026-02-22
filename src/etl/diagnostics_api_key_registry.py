from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_TABLE_NAME = "diagnostics_api_client"
_METADATA = sa.MetaData()

_CLIENT_TABLE = sa.Table(
    _TABLE_NAME,
    _METADATA,
    sa.Column("client_id", sa.String(64), primary_key=True),
    sa.Column("name", sa.String(128), nullable=False),
    sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
    sa.Column("scopes", sa.JSON, nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, default=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.String(128), nullable=False),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_used_ip", sa.String(64), nullable=True),
    sa.Column("notes", sa.Text, nullable=True),
    sa.Index("ix_diag_api_client_key_hash", "key_hash"),
    sa.Index("ix_diag_api_client_active", "is_active"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for diagnostics API key persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_CLIENT_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_row(row: dict[str, Any], *, include_sensitive: bool = False) -> dict[str, Any]:
    payload = dict(row)
    for key in ("created_at", "last_used_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            payload[key] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    scopes = payload.get("scopes")
    if isinstance(scopes, list):
        payload["scopes"] = [str(scope).strip() for scope in scopes if str(scope).strip()]
    else:
        payload["scopes"] = []

    if not include_sensitive:
        payload.pop("key_hash", None)
    return payload


def _normalize_scopes(scopes: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if scopes is None:
        return []

    values: list[str]
    if isinstance(scopes, str):
        values = [scope.strip() for scope in scopes.split(",")]
    else:
        values = [str(scope).strip() for scope in scopes]

    normalized: list[str] = []
    seen: set[str] = set()
    for scope in values:
        if not scope:
            continue
        if scope in seen:
            continue
        seen.add(scope)
        normalized.append(scope)
    return normalized


def _api_key_salt(salt: str | None = None) -> str:
    if salt is not None:
        return str(salt)
    return str(os.getenv("DIAGNOSTICS_API_KEY_SALT", ""))


def hash_api_key(raw_key: str, *, salt: str | None = None) -> str:
    key = str(raw_key).strip()
    if not key:
        raise ValueError("API key cannot be empty")
    salted = f"{_api_key_salt(salt)}:{key}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def create_api_client_key(
    *,
    name: str,
    scopes: list[str] | tuple[str, ...] | str,
    created_by: str,
    notes: str | None = None,
    is_active: bool = True,
    client_id: str | None = None,
    raw_key: str | None = None,
    database_url: str | None = None,
) -> tuple[dict[str, Any], str]:
    normalized_name = str(name).strip()
    if not normalized_name:
        raise ValueError("name is required")

    normalized_created_by = str(created_by).strip()
    if not normalized_created_by:
        raise ValueError("created_by is required")

    normalized_scopes = _normalize_scopes(scopes)
    if not normalized_scopes:
        raise ValueError("At least one scope is required")

    generated_key = str(raw_key).strip() if raw_key is not None else secrets.token_urlsafe(32)
    if not generated_key:
        raise ValueError("Generated API key is empty")

    record = {
        "client_id": str(client_id or uuid.uuid4().hex),
        "name": normalized_name,
        "key_hash": hash_api_key(generated_key),
        "scopes": normalized_scopes,
        "is_active": bool(is_active),
        "created_at": _now_utc(),
        "created_by": normalized_created_by,
        "last_used_at": None,
        "last_used_ip": None,
        "notes": str(notes).strip() if notes is not None and str(notes).strip() else None,
    }

    engine = _ensure_table(database_url)
    with engine.begin() as conn:
        conn.execute(_CLIENT_TABLE.insert().values(**record))

    return _serialize_row(record), generated_key


def authenticate_api_key(
    raw_key: str,
    *,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    candidate_hash = hash_api_key(raw_key)
    engine = _ensure_table(database_url)
    query = (
        sa.select(_CLIENT_TABLE)
        .where(_CLIENT_TABLE.c.key_hash == candidate_hash)
        .where(_CLIENT_TABLE.c.is_active.is_(True))
        .limit(1)
    )

    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()

    if row is None:
        return None
    return _serialize_row(dict(row))


def touch_api_client_usage(
    client_id: str,
    *,
    last_used_ip: str | None = None,
    last_used_at: datetime | None = None,
    database_url: str | None = None,
) -> None:
    normalized_client_id = str(client_id).strip()
    if not normalized_client_id:
        raise ValueError("client_id is required")

    engine = _ensure_table(database_url)
    resolved_used_at = last_used_at or _now_utc()
    if resolved_used_at.tzinfo is None:
        resolved_used_at = resolved_used_at.replace(tzinfo=timezone.utc)
    else:
        resolved_used_at = resolved_used_at.astimezone(timezone.utc)

    with engine.begin() as conn:
        conn.execute(
            _CLIENT_TABLE.update()
            .where(_CLIENT_TABLE.c.client_id == normalized_client_id)
            .values(
                last_used_at=resolved_used_at,
                last_used_ip=str(last_used_ip).strip() if last_used_ip is not None and str(last_used_ip).strip() else None,
            )
        )


def list_api_clients(
    *,
    limit: int = 100,
    include_inactive: bool = False,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_table(database_url)
    normalized_limit = max(1, min(int(limit), 1000))

    query = sa.select(_CLIENT_TABLE)
    if not include_inactive:
        query = query.where(_CLIENT_TABLE.c.is_active.is_(True))

    query = query.order_by(_CLIENT_TABLE.c.created_at.desc()).limit(normalized_limit)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [_serialize_row(dict(row)) for row in rows]


def set_api_client_active(
    client_id: str,
    *,
    is_active: bool,
    database_url: str | None = None,
) -> None:
    normalized_client_id = str(client_id).strip()
    if not normalized_client_id:
        raise ValueError("client_id is required")

    engine = _ensure_table(database_url)
    with engine.begin() as conn:
        conn.execute(
            _CLIENT_TABLE.update()
            .where(_CLIENT_TABLE.c.client_id == normalized_client_id)
            .values(is_active=bool(is_active))
        )
