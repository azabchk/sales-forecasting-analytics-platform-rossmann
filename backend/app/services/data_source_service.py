from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.data_source_registry import (
    create_data_source,
    get_data_source,
    list_data_sources,
    resolve_data_source_id,
)
from src.etl.preflight_registry import list_preflight_runs


def _parse_created_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _latest_preflight_by_data_source(limit: int = 2000) -> dict[int, dict[str, Any]]:
    rows = list_preflight_runs(limit=limit)
    latest_by_source: dict[int, dict[str, Any]] = {}
    for row in rows:
        ds_id_raw = row.get("data_source_id")
        if ds_id_raw is None:
            continue
        try:
            ds_id = int(ds_id_raw)
        except (TypeError, ValueError):
            continue

        created_at = _parse_created_at(row.get("created_at"))
        existing = latest_by_source.get(ds_id)
        if existing is None:
            latest_by_source[ds_id] = row
            continue
        existing_created_at = _parse_created_at(existing.get("created_at"))
        if created_at is not None and (existing_created_at is None or created_at > existing_created_at):
            latest_by_source[ds_id] = row
    return latest_by_source


def list_data_sources_with_health(*, include_inactive: bool = True) -> list[dict[str, Any]]:
    sources = list_data_sources(include_inactive=include_inactive)
    latest_map = _latest_preflight_by_data_source()
    items: list[dict[str, Any]] = []
    for source in sources:
        ds_id = int(source["id"])
        latest = latest_map.get(ds_id)
        payload = dict(source)
        payload["last_preflight_status"] = latest.get("final_status") if latest else None
        payload["last_preflight_at"] = latest.get("created_at") if latest else None
        payload["last_preflight_run_id"] = latest.get("run_id") if latest else None
        items.append(payload)
    return items


def get_data_source_by_id(data_source_id: int) -> dict[str, Any]:
    try:
        resolved_id = resolve_data_source_id(data_source_id, allow_inactive=True)
    except ValueError as exc:
        raise LookupError(str(exc)) from exc
    row = get_data_source(resolved_id)
    if row is None:
        raise LookupError(f"data source not found: {data_source_id}")
    return row


def create_data_source_entry(
    *,
    name: str,
    description: str | None = None,
    source_type: str = "cms",
    related_contract_id: str | None = None,
    related_contract_version: str | None = None,
    is_active: bool = True,
    is_default: bool = False,
) -> dict[str, Any]:
    return create_data_source(
        name=name,
        description=description,
        source_type=source_type,
        related_contract_id=related_contract_id,
        related_contract_version=related_contract_version,
        is_active=is_active,
        is_default=is_default,
    )


def list_data_source_preflight_runs(data_source_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    try:
        resolved_id = resolve_data_source_id(data_source_id, allow_inactive=True)
    except ValueError as exc:
        raise LookupError(str(exc)) from exc
    return list_preflight_runs(limit=limit, data_source_id=resolved_id)
