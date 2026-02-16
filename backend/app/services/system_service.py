from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

from app.config import get_settings
from app.db import fetch_one


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_model_metadata_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (_project_root() / candidate).resolve()


def _resolve_model_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (_project_root() / candidate).resolve()


def get_system_summary() -> dict:
    query = sa.text(
        """
        SELECT
            (SELECT COUNT(*) FROM dim_store)::bigint AS stores_count,
            (SELECT COUNT(*) FROM fact_sales_daily)::bigint AS sales_rows_count,
            (SELECT MIN(full_date) FROM dim_date d
                JOIN fact_sales_daily f ON f.date_id = d.date_id) AS date_from,
            (SELECT MAX(full_date) FROM dim_date d
                JOIN fact_sales_daily f ON f.date_id = d.date_id) AS date_to
        """
    )
    row = fetch_one(query)
    if row is None:
        raise ValueError("Failed to retrieve system summary from database")
    return row


def get_model_metadata() -> dict:
    settings = get_settings()
    metadata_path = _resolve_model_metadata_path(settings.model_metadata_path)
    model_path = _resolve_model_path(settings.model_path)

    if not metadata_path.exists():
        raise FileNotFoundError(f"Model metadata file not found: {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if not payload.get("trained_at"):
        source_path = model_path if model_path.exists() else metadata_path
        trained_at = source_path.stat().st_mtime
        payload["trained_at"] = datetime.fromtimestamp(trained_at, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    return payload
