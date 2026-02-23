from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_TABLE_NAME = "etl_run_registry"
_METADATA = sa.MetaData()

_ETL_RUN_TABLE = sa.Table(
    _TABLE_NAME,
    _METADATA,
    sa.Column("run_id", sa.String(64), primary_key=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("data_source_id", sa.Integer, nullable=True),
    sa.Column("preflight_mode", sa.String(32), nullable=True),
    sa.Column("train_input_path", sa.Text, nullable=True),
    sa.Column("store_input_path", sa.Text, nullable=True),
    sa.Column("summary_json", sa.JSON, nullable=False, default=dict),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Index("ix_etl_run_registry_started_at", "started_at"),
    sa.Index("ix_etl_run_registry_status", "status"),
    sa.Index("ix_etl_run_registry_data_source", "data_source_id"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for ETL run persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_ETL_RUN_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def upsert_etl_run(record: dict[str, Any], database_url: str | None = None) -> None:
    engine = _ensure_table(database_url)
    payload = dict(record)
    payload["started_at"] = _ensure_utc(payload.get("started_at")) or datetime.now(timezone.utc)
    payload["finished_at"] = _ensure_utc(payload.get("finished_at"))
    payload["status"] = str(payload.get("status", "UNKNOWN")).strip().upper() or "UNKNOWN"
    payload["summary_json"] = payload.get("summary_json") if isinstance(payload.get("summary_json"), dict) else {}
    payload["data_source_id"] = int(payload["data_source_id"]) if payload.get("data_source_id") is not None else None

    with engine.begin() as conn:
        updated_rows = conn.execute(
            _ETL_RUN_TABLE.update().where(_ETL_RUN_TABLE.c.run_id == payload["run_id"]).values(**payload)
        ).rowcount
        if not updated_rows:
            conn.execute(_ETL_RUN_TABLE.insert().values(**payload))


def list_etl_runs(limit: int = 50, database_url: str | None = None) -> list[dict[str, Any]]:
    engine = _ensure_table(database_url)
    normalized_limit = max(1, min(int(limit), 1000))
    query = sa.select(_ETL_RUN_TABLE).order_by(_ETL_RUN_TABLE.c.started_at.desc()).limit(normalized_limit)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(row) for row in rows]
