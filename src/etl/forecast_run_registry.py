from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_TABLE_NAME = "forecast_run_registry"
_METADATA = sa.MetaData()

_FORECAST_RUN_TABLE = sa.Table(
    _TABLE_NAME,
    _METADATA,
    sa.Column("run_id", sa.String(64), primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("run_type", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("data_source_id", sa.Integer, nullable=True),
    sa.Column("store_id", sa.Integer, nullable=True),
    sa.Column("request_json", sa.JSON, nullable=False, default=dict),
    sa.Column("summary_json", sa.JSON, nullable=False, default=dict),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Index("ix_forecast_run_registry_created_at", "created_at"),
    sa.Index("ix_forecast_run_registry_run_type", "run_type"),
    sa.Index("ix_forecast_run_registry_status", "status"),
    sa.Index("ix_forecast_run_registry_data_source", "data_source_id"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for forecast run persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_FORECAST_RUN_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def upsert_forecast_run(record: dict[str, Any], database_url: str | None = None) -> None:
    engine = _ensure_table(database_url)
    payload = dict(record)

    created_at = payload.get("created_at")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = created_at.astimezone(timezone.utc)
    else:
        created_at = datetime.now(timezone.utc)

    payload["created_at"] = created_at
    payload["run_type"] = str(payload.get("run_type", "forecast")).strip().lower() or "forecast"
    payload["status"] = str(payload.get("status", "UNKNOWN")).strip().upper() or "UNKNOWN"
    payload["request_json"] = payload.get("request_json") if isinstance(payload.get("request_json"), dict) else {}
    payload["summary_json"] = payload.get("summary_json") if isinstance(payload.get("summary_json"), dict) else {}
    payload["data_source_id"] = int(payload["data_source_id"]) if payload.get("data_source_id") is not None else None
    payload["store_id"] = int(payload["store_id"]) if payload.get("store_id") is not None else None

    with engine.begin() as conn:
        updated_rows = conn.execute(
            _FORECAST_RUN_TABLE.update()
            .where(_FORECAST_RUN_TABLE.c.run_id == payload["run_id"])
            .values(**payload)
        ).rowcount
        if not updated_rows:
            conn.execute(_FORECAST_RUN_TABLE.insert().values(**payload))
