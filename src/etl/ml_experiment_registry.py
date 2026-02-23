from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa

_TABLE_NAME = "ml_experiment_registry"
_METADATA = sa.MetaData()

_ML_EXPERIMENT_TABLE = sa.Table(
    _TABLE_NAME,
    _METADATA,
    sa.Column("experiment_id", sa.String(64), primary_key=True),
    sa.Column("data_source_id", sa.Integer, nullable=True),
    sa.Column("model_type", sa.String(64), nullable=False),
    sa.Column("hyperparameters_json", sa.JSON, nullable=False, default=dict),
    sa.Column("train_period_start", sa.Date, nullable=True),
    sa.Column("train_period_end", sa.Date, nullable=True),
    sa.Column("validation_period_start", sa.Date, nullable=True),
    sa.Column("validation_period_end", sa.Date, nullable=True),
    sa.Column("metrics_json", sa.JSON, nullable=False, default=dict),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("artifact_path", sa.Text, nullable=True),
    sa.Column("metadata_path", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_ml_experiment_registry_created_at", "created_at"),
    sa.Index("ix_ml_experiment_registry_model_type", "model_type"),
    sa.Index("ix_ml_experiment_registry_status", "status"),
    sa.Index("ix_ml_experiment_registry_data_source", "data_source_id"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for ML experiment persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_ML_EXPERIMENT_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def _parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def upsert_experiment(record: dict[str, Any], database_url: str | None = None) -> None:
    engine = _ensure_table(database_url)
    payload = dict(record)

    now = _ensure_utc(payload.get("updated_at"))
    payload["updated_at"] = now
    payload["created_at"] = _ensure_utc(payload.get("created_at")) if payload.get("created_at") else now
    payload["status"] = str(payload.get("status", "UNKNOWN")).strip().upper() or "UNKNOWN"
    payload["model_type"] = str(payload.get("model_type", "unknown")).strip()
    payload["hyperparameters_json"] = (
        payload.get("hyperparameters_json") if isinstance(payload.get("hyperparameters_json"), dict) else {}
    )
    payload["metrics_json"] = payload.get("metrics_json") if isinstance(payload.get("metrics_json"), dict) else {}
    payload["data_source_id"] = int(payload["data_source_id"]) if payload.get("data_source_id") is not None else None
    payload["train_period_start"] = _parse_iso_date(payload.get("train_period_start"))
    payload["train_period_end"] = _parse_iso_date(payload.get("train_period_end"))
    payload["validation_period_start"] = _parse_iso_date(payload.get("validation_period_start"))
    payload["validation_period_end"] = _parse_iso_date(payload.get("validation_period_end"))

    with engine.begin() as conn:
        updated_rows = conn.execute(
            _ML_EXPERIMENT_TABLE.update()
            .where(_ML_EXPERIMENT_TABLE.c.experiment_id == payload["experiment_id"])
            .values(**payload)
        ).rowcount
        if not updated_rows:
            conn.execute(_ML_EXPERIMENT_TABLE.insert().values(**payload))


def list_experiments(
    *,
    limit: int = 100,
    data_source_id: int | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    engine = _ensure_table(database_url)
    normalized_limit = max(1, min(int(limit), 1000))
    query = sa.select(_ML_EXPERIMENT_TABLE)
    if data_source_id is not None:
        query = query.where(_ML_EXPERIMENT_TABLE.c.data_source_id == int(data_source_id))
    query = query.order_by(_ML_EXPERIMENT_TABLE.c.created_at.desc()).limit(normalized_limit)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(row) for row in rows]


def get_experiment(experiment_id: str, database_url: str | None = None) -> dict[str, Any] | None:
    engine = _ensure_table(database_url)
    query = sa.select(_ML_EXPERIMENT_TABLE).where(_ML_EXPERIMENT_TABLE.c.experiment_id == str(experiment_id)).limit(1)
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    return dict(row) if row else None
