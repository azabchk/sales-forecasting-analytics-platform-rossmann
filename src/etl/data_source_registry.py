from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_TABLE_NAME = "data_source"
_METADATA = sa.MetaData()

_DATA_SOURCE_TABLE = sa.Table(
    _TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("name", sa.String(128), nullable=False, unique=True),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("source_type", sa.String(64), nullable=False, default="cms"),
    sa.Column("related_contract_id", sa.String(128), nullable=True),
    sa.Column("related_contract_version", sa.String(64), nullable=True),
    sa.Column("is_active", sa.Boolean, nullable=False, default=True),
    sa.Column("is_default", sa.Boolean, nullable=False, default=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_data_source_active", "is_active"),
    sa.Index("ix_data_source_default", "is_default"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()

_DEFAULT_SOURCE_NAME = "Rossmann Default"
_DEFAULT_SOURCE_DESCRIPTION = "Default data source used for backward-compatible runs."
_DEFAULT_SOURCE_TYPE = "cms"
_DEFAULT_CONTRACT_ID = "rossmann_input_contract"
_DEFAULT_CONTRACT_VERSION = "v1"


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for data source persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_DATA_SOURCE_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    for key in ("created_at", "updated_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            payload[key] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def ensure_default_data_source(database_url: str | None = None) -> dict[str, Any]:
    engine = _ensure_table(database_url)
    with engine.begin() as conn:
        default_row = conn.execute(
            sa.select(_DATA_SOURCE_TABLE).where(_DATA_SOURCE_TABLE.c.is_default.is_(True)).limit(1)
        ).mappings().first()
        if default_row is not None:
            return _serialize_row(dict(default_row))

        now = _now_utc()
        payload = {
            "name": _DEFAULT_SOURCE_NAME,
            "description": _DEFAULT_SOURCE_DESCRIPTION,
            "source_type": _DEFAULT_SOURCE_TYPE,
            "related_contract_id": _DEFAULT_CONTRACT_ID,
            "related_contract_version": _DEFAULT_CONTRACT_VERSION,
            "is_active": True,
            "is_default": True,
            "created_at": now,
            "updated_at": now,
        }
        result = conn.execute(_DATA_SOURCE_TABLE.insert().values(**payload))
        inserted_id = int(result.inserted_primary_key[0])
        row = conn.execute(
            sa.select(_DATA_SOURCE_TABLE).where(_DATA_SOURCE_TABLE.c.id == inserted_id)
        ).mappings().first()

    if row is None:
        raise RuntimeError("Failed to create default data source")
    return _serialize_row(dict(row))


def resolve_data_source_id(
    data_source_id: int | None = None,
    *,
    allow_inactive: bool = False,
    database_url: str | None = None,
) -> int:
    if data_source_id is None:
        default_row = ensure_default_data_source(database_url=database_url)
        return int(default_row["id"])

    row = get_data_source(data_source_id, database_url=database_url)
    if row is None:
        raise ValueError(f"data_source_id={data_source_id} does not exist")
    if not allow_inactive and not bool(row.get("is_active", False)):
        raise ValueError(f"data_source_id={data_source_id} is inactive")
    return int(row["id"])


def list_data_sources(
    *,
    include_inactive: bool = True,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    ensure_default_data_source(database_url=database_url)
    engine = _ensure_table(database_url)

    query = sa.select(_DATA_SOURCE_TABLE)
    if not include_inactive:
        query = query.where(_DATA_SOURCE_TABLE.c.is_active.is_(True))
    query = query.order_by(_DATA_SOURCE_TABLE.c.is_default.desc(), _DATA_SOURCE_TABLE.c.id.asc())

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [_serialize_row(dict(row)) for row in rows]


def get_data_source(data_source_id: int, database_url: str | None = None) -> dict[str, Any] | None:
    ensure_default_data_source(database_url=database_url)
    engine = _ensure_table(database_url)
    query = sa.select(_DATA_SOURCE_TABLE).where(_DATA_SOURCE_TABLE.c.id == int(data_source_id)).limit(1)
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None:
        return None
    return _serialize_row(dict(row))


def create_data_source(
    *,
    name: str,
    description: str | None = None,
    source_type: str = "cms",
    related_contract_id: str | None = None,
    related_contract_version: str | None = None,
    is_active: bool = True,
    is_default: bool = False,
    database_url: str | None = None,
) -> dict[str, Any]:
    normalized_name = str(name).strip()
    if not normalized_name:
        raise ValueError("name is required")

    normalized_source_type = str(source_type).strip() or "cms"
    now = _now_utc()
    payload = {
        "name": normalized_name,
        "description": str(description).strip() if description is not None and str(description).strip() else None,
        "source_type": normalized_source_type,
        "related_contract_id": str(related_contract_id).strip()
        if related_contract_id is not None and str(related_contract_id).strip()
        else None,
        "related_contract_version": str(related_contract_version).strip()
        if related_contract_version is not None and str(related_contract_version).strip()
        else None,
        "is_active": bool(is_active),
        "is_default": bool(is_default),
        "created_at": now,
        "updated_at": now,
    }

    engine = _ensure_table(database_url)
    with engine.begin() as conn:
        if payload["is_default"]:
            conn.execute(_DATA_SOURCE_TABLE.update().values(is_default=False, updated_at=now))

        try:
            result = conn.execute(_DATA_SOURCE_TABLE.insert().values(**payload))
        except sa.exc.IntegrityError as exc:
            raise ValueError(f"data source name already exists: '{normalized_name}'") from exc

        inserted_id = int(result.inserted_primary_key[0])
        row = conn.execute(
            sa.select(_DATA_SOURCE_TABLE).where(_DATA_SOURCE_TABLE.c.id == inserted_id)
        ).mappings().first()

    if row is None:
        raise RuntimeError("Failed to create data source")
    return _serialize_row(dict(row))

