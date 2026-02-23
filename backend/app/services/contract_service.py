from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.validation.input_contract_models import load_input_contract  # noqa: E402

DEFAULT_CONTRACT_REGISTRY_PATH = PROJECT_ROOT / "config" / "input_contract" / "contracts_registry.yaml"


def _registry_path() -> Path:
    configured = str(os.getenv("CONTRACTS_REGISTRY_PATH", str(DEFAULT_CONTRACT_REGISTRY_PATH))).strip()
    return Path(configured).expanduser().resolve()


def _load_registry_payload() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        raise FileNotFoundError(f"Contracts registry file not found: {path}")
    with open(path, encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    if not isinstance(payload, dict):
        raise ValueError("Contracts registry must be a top-level object")
    contracts = payload.get("contracts", [])
    if not isinstance(contracts, list):
        raise ValueError("Contracts registry field 'contracts' must be a list")
    return {"version": str(payload.get("version", "v1")), "path": str(path), "contracts": contracts}


def _resolve_schema_path(raw_path: str) -> Path:
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def _version_with_schema(version_item: dict[str, Any]) -> dict[str, Any]:
    schema_path = _resolve_schema_path(str(version_item.get("schema_path", "")))
    contract = load_input_contract(schema_path)

    profiles: dict[str, dict[str, Any]] = {}
    for profile_name, profile in contract.profiles.items():
        required_columns = [column.canonical_name for column in profile.columns if column.required]
        aliases = {column.canonical_name: column.aliases for column in profile.columns}
        dtypes = {column.canonical_name: column.dtype for column in profile.columns}
        profiles[profile_name] = {
            "required_columns": required_columns,
            "aliases": aliases,
            "dtypes": dtypes,
        }

    payload = dict(version_item)
    payload["schema_path"] = str(schema_path)
    payload["contract_version"] = contract.contract_version
    payload["profiles"] = profiles
    return payload


def list_contracts() -> list[dict[str, Any]]:
    payload = _load_registry_payload()
    contracts_raw = payload["contracts"]
    items: list[dict[str, Any]] = []
    for item in contracts_raw:
        if not isinstance(item, dict):
            continue
        versions = item.get("versions", [])
        latest_version = None
        if isinstance(versions, list) and versions:
            latest = versions[-1]
            if isinstance(latest, dict):
                latest_version = latest.get("version")
        items.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "is_active": bool(item.get("is_active", True)),
                "latest_version": latest_version,
                "versions_count": len(versions) if isinstance(versions, list) else 0,
            }
        )
    return items


def get_contract(contract_id: str) -> dict[str, Any] | None:
    contracts = _load_registry_payload()["contracts"]
    for item in contracts:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) == str(contract_id):
            payload = dict(item)
            payload["versions"] = item.get("versions", []) if isinstance(item.get("versions"), list) else []
            return payload
    return None


def list_contract_versions(contract_id: str) -> list[dict[str, Any]]:
    contract = get_contract(contract_id)
    if contract is None:
        return []
    versions = contract.get("versions", [])
    if not isinstance(versions, list):
        return []
    output: list[dict[str, Any]] = []
    for item in versions:
        if not isinstance(item, dict):
            continue
        output.append(
            {
                "version": item.get("version"),
                "created_at": item.get("created_at"),
                "changed_by": item.get("changed_by"),
                "changelog": item.get("changelog"),
                "schema_path": item.get("schema_path"),
            }
        )
    return output


def get_contract_version(contract_id: str, version: str) -> dict[str, Any] | None:
    contract = get_contract(contract_id)
    if contract is None:
        return None
    versions = contract.get("versions", [])
    if not isinstance(versions, list):
        return None
    for item in versions:
        if not isinstance(item, dict):
            continue
        if str(item.get("version")) == str(version):
            return _version_with_schema(item)
    return None

