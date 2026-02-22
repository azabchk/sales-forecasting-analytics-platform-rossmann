from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .quality_rule_models import QualityRuleSet

SUPPORTED_DTYPES = {"string", "int", "float", "date", "bool"}
SUPPORTED_FORMATS = {"csv"}


@dataclass
class ColumnContract:
    canonical_name: str
    required: bool
    dtype: str
    aliases: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ColumnContract":
        canonical_name = str(payload.get("canonical_name", "")).strip()
        if not canonical_name:
            raise ValueError("Column contract requires non-empty canonical_name")

        dtype = str(payload.get("dtype", "")).strip().lower()
        if dtype not in SUPPORTED_DTYPES:
            raise ValueError(
                f"Unsupported dtype '{dtype}' for column '{canonical_name}'. Supported: {sorted(SUPPORTED_DTYPES)}"
            )

        aliases_raw = payload.get("aliases", [])
        if aliases_raw is None:
            aliases_raw = []
        if not isinstance(aliases_raw, list):
            raise ValueError(f"aliases must be a list for column '{canonical_name}'")

        aliases = [str(alias).strip() for alias in aliases_raw if str(alias).strip()]
        return cls(
            canonical_name=canonical_name,
            required=bool(payload.get("required", False)),
            dtype=dtype,
            aliases=aliases,
        )


@dataclass
class ProfileContract:
    name: str
    description: str
    columns: list[ColumnContract]
    canonical_order: list[str]
    quality_rules: QualityRuleSet

    @classmethod
    def from_dict(cls, name: str, payload: dict[str, Any]) -> "ProfileContract":
        if not isinstance(payload, dict):
            raise ValueError(f"Profile '{name}' must be an object")

        columns_raw = payload.get("columns", [])
        if not isinstance(columns_raw, list) or not columns_raw:
            raise ValueError(f"Profile '{name}' must define a non-empty columns list")

        columns = [ColumnContract.from_dict(item) for item in columns_raw]
        canonical_order_raw = payload.get("canonical_order")
        if canonical_order_raw is None:
            canonical_order = [column.canonical_name for column in columns]
        else:
            if not isinstance(canonical_order_raw, list):
                raise ValueError(f"Profile '{name}' canonical_order must be a list")
            canonical_order = [str(column).strip() for column in canonical_order_raw if str(column).strip()]
            if not canonical_order:
                canonical_order = [column.canonical_name for column in columns]

        return cls(
            name=name,
            description=str(payload.get("description", "")).strip(),
            columns=columns,
            canonical_order=canonical_order,
            quality_rules=QualityRuleSet.from_dict(payload.get("quality_rules")),
        )


@dataclass
class InputContract:
    contract_version: str
    data_format: str
    max_rows: int
    max_file_size_mb: float
    allow_extra_columns: bool
    strict_types: bool
    drop_unknown_columns: bool
    null_on_coercion_error: bool
    profiles: dict[str, ProfileContract]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InputContract":
        if not isinstance(payload, dict):
            raise ValueError("Input contract root must be a mapping")

        contract_version = str(payload.get("contract_version", "")).strip()
        if not contract_version:
            raise ValueError("contract_version is required")

        data_format = str(payload.get("format", "")).strip().lower()
        if data_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{data_format}'. Supported: {sorted(SUPPORTED_FORMATS)}")

        limits = payload.get("limits", {})
        if not isinstance(limits, dict):
            raise ValueError("limits section must be an object")

        max_rows = int(limits.get("max_rows", 0))
        max_file_size_mb = float(limits.get("max_file_size_mb", 0))
        if max_rows <= 0:
            raise ValueError("limits.max_rows must be > 0")
        if max_file_size_mb <= 0:
            raise ValueError("limits.max_file_size_mb must be > 0")

        rules = payload.get("rules", {})
        if not isinstance(rules, dict):
            raise ValueError("rules section must be an object")

        profiles_raw = payload.get("profiles", {})
        if not isinstance(profiles_raw, dict) or not profiles_raw:
            raise ValueError("profiles section must be a non-empty object")

        profiles = {
            name: ProfileContract.from_dict(name, profile_payload)
            for name, profile_payload in profiles_raw.items()
        }

        return cls(
            contract_version=contract_version,
            data_format=data_format,
            max_rows=max_rows,
            max_file_size_mb=max_file_size_mb,
            allow_extra_columns=bool(rules.get("allow_extra_columns", True)),
            strict_types=bool(rules.get("strict_types", False)),
            drop_unknown_columns=bool(rules.get("drop_unknown_columns", False)),
            null_on_coercion_error=bool(rules.get("null_on_coercion_error", True)),
            profiles=profiles,
        )


def load_input_contract(contract_path: str | Path) -> InputContract:
    """Load and validate input contract from YAML file."""
    path = Path(contract_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input contract file not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        payload = yaml.safe_load(file)

    return InputContract.from_dict(payload)
