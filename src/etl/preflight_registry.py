from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_TABLE_NAME = "preflight_run_registry"
_METADATA = sa.MetaData()
_REGISTRY_TABLE = sa.Table(
    _TABLE_NAME,
    _METADATA,
    sa.Column("run_id", sa.String(64), nullable=False),
    sa.Column("source_name", sa.String(16), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("mode", sa.String(32), nullable=False),
    sa.Column("validation_status", sa.String(32), nullable=False),
    sa.Column("semantic_status", sa.String(32), nullable=False),
    sa.Column("final_status", sa.String(32), nullable=False),
    sa.Column("used_input_path", sa.Text, nullable=False),
    sa.Column("used_unified", sa.Boolean, nullable=False),
    sa.Column("artifact_dir", sa.Text, nullable=True),
    sa.Column("validation_report_path", sa.Text, nullable=True),
    sa.Column("manifest_path", sa.Text, nullable=True),
    sa.Column("summary_json", sa.JSON, nullable=False),
    sa.Column("blocked", sa.Boolean, nullable=False),
    sa.Column("block_reason", sa.Text, nullable=True),
    sa.PrimaryKeyConstraint("run_id", "source_name", name="pk_preflight_run_registry"),
)

_ENGINES: dict[str, sa.Engine] = {}
_INITIALIZED_DATABASE_URLS: set[str] = set()


def _resolve_database_url(database_url: str | None = None) -> str:
    db_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for preflight registry persistence")
    return db_url


def _get_engine(database_url: str) -> sa.Engine:
    if database_url not in _ENGINES:
        _ENGINES[database_url] = sa.create_engine(database_url, future=True, pool_pre_ping=True)
    return _ENGINES[database_url]


def _ensure_registry_table(database_url: str | None = None) -> sa.Engine:
    resolved_url = _resolve_database_url(database_url)
    engine = _get_engine(resolved_url)
    if resolved_url not in _INITIALIZED_DATABASE_URLS:
        _METADATA.create_all(engine, tables=[_REGISTRY_TABLE], checkfirst=True)
        _INITIALIZED_DATABASE_URLS.add(resolved_url)
    return engine


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    created_at = payload.get("created_at")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        payload["created_at"] = created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def insert_preflight_run(record: dict[str, Any], database_url: str | None = None) -> None:
    """Insert or update a preflight registry record."""

    engine = _ensure_registry_table(database_url)
    payload = dict(record)
    payload["created_at"] = payload.get("created_at") or datetime.now(timezone.utc)
    payload["summary_json"] = payload.get("summary_json") or {}
    payload["blocked"] = bool(payload.get("blocked", False))
    payload["used_unified"] = bool(payload.get("used_unified", False))

    with engine.begin() as conn:
        try:
            conn.execute(_REGISTRY_TABLE.insert().values(**payload))
        except sa.exc.IntegrityError:
            conn.execute(
                _REGISTRY_TABLE.update()
                .where(
                    sa.and_(
                        _REGISTRY_TABLE.c.run_id == payload["run_id"],
                        _REGISTRY_TABLE.c.source_name == payload["source_name"],
                    )
                )
                .values(**payload)
            )


def list_preflight_runs(
    limit: int = 20,
    source_name: str | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    """List preflight run records ordered by latest first."""

    engine = _ensure_registry_table(database_url)
    normalized_limit = max(1, min(int(limit), 200))

    query = sa.select(_REGISTRY_TABLE).order_by(_REGISTRY_TABLE.c.created_at.desc()).limit(normalized_limit)
    if source_name:
        query = query.where(_REGISTRY_TABLE.c.source_name == source_name)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [_serialize_row(dict(row)) for row in rows]


def get_preflight_run(run_id: str, database_url: str | None = None) -> dict[str, Any] | None:
    """Get all source records for a specific run_id."""

    engine = _ensure_registry_table(database_url)
    query = (
        sa.select(_REGISTRY_TABLE)
        .where(_REGISTRY_TABLE.c.run_id == run_id)
        .order_by(_REGISTRY_TABLE.c.source_name.asc())
    )

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    if not rows:
        return None

    records = [_serialize_row(dict(row)) for row in rows]
    first = records[0]
    final_statuses = [str(record.get("final_status", "PASS")).upper() for record in records]

    if "FAIL" in final_statuses:
        aggregate_status = "FAIL"
    elif "WARN" in final_statuses:
        aggregate_status = "WARN"
    elif "PASS" in final_statuses:
        aggregate_status = "PASS"
    else:
        aggregate_status = "SKIPPED"

    return {
        "run_id": run_id,
        "created_at": first.get("created_at"),
        "mode": first.get("mode"),
        "final_status": aggregate_status,
        "blocked": bool(any(bool(record.get("blocked")) for record in records)),
        "records": records,
    }


def get_latest_preflight(
    source_name: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    """Get latest preflight (grouped run when source_name is None, source record otherwise)."""

    if source_name:
        rows = list_preflight_runs(limit=1, source_name=source_name, database_url=database_url)
        return rows[0] if rows else None

    rows = list_preflight_runs(limit=1, source_name=None, database_url=database_url)
    if not rows:
        return None
    return get_preflight_run(str(rows[0]["run_id"]), database_url=database_url)
