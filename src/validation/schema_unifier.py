from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .input_contract_models import InputContract, ProfileContract
from .input_validator import CHECK_FAIL, ValidationResult


@dataclass
class UnificationResult:
    unified_dataframe: pd.DataFrame
    manifest: dict[str, Any]


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _build_alias_map(profile: ProfileContract) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for column in profile.columns:
        canonical = _normalize_name(column.canonical_name)
        alias_map[canonical] = canonical
        for alias in column.aliases:
            alias_map[_normalize_name(alias)] = canonical
    return alias_map


def _coerce_bool(series: pd.Series) -> tuple[pd.Series, int]:
    true_values = {"1", "true", "t", "yes", "y"}
    false_values = {"0", "false", "f", "no", "n"}

    normalized = series.astype(str).str.strip().str.lower()
    out = pd.Series(pd.NA, index=series.index, dtype="boolean")

    out[normalized.isin(true_values)] = True
    out[normalized.isin(false_values)] = False
    out[series.isna()] = pd.NA

    invalid_mask = series.notna() & ~normalized.isin(true_values | false_values)
    return out, int(invalid_mask.sum())


def _coerce_for_output(series: pd.Series, dtype_name: str, null_on_coercion_error: bool) -> tuple[pd.Series, int]:
    dtype_name = dtype_name.lower().strip()

    if dtype_name == "string":
        converted = series.astype("string").str.strip()
        return converted, 0

    if dtype_name == "int":
        converted = pd.to_numeric(series, errors="coerce")
        invalid_mask = series.notna() & converted.isna()
        out = converted.astype("Int64") if null_on_coercion_error else series
        return out, int(invalid_mask.sum())

    if dtype_name == "float":
        converted = pd.to_numeric(series, errors="coerce")
        invalid_mask = series.notna() & converted.isna()
        out = converted.astype("float64") if null_on_coercion_error else series
        return out, int(invalid_mask.sum())

    if dtype_name == "date":
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        invalid_mask = series.notna() & converted.isna()
        out = converted if null_on_coercion_error else series
        return out, int(invalid_mask.sum())

    if dtype_name == "bool":
        converted, invalid = _coerce_bool(series)
        out = converted if null_on_coercion_error else series
        return out, invalid

    return series, 0


def unify_validated_dataframe(
    *,
    validation_result: ValidationResult,
    contract: InputContract,
    profile_name: str,
    source_file_name: str,
) -> UnificationResult:
    """Create canonical unified dataframe and manifest from a non-failing validation result."""

    validation_status = str(validation_result.report.get("status", "FAIL"))
    if validation_status == CHECK_FAIL:
        raise ValueError("Cannot unify dataset with FAIL validation status")

    if validation_result.dataframe is None:
        raise ValueError("Validation result has no dataframe to unify")

    if profile_name not in contract.profiles:
        raise ValueError(f"Profile '{profile_name}' is not defined in contract")

    profile = contract.profiles[profile_name]
    alias_map = _build_alias_map(profile)

    df = validation_result.dataframe.copy()

    renamed_columns: dict[str, str] = {}
    pre_renamed = validation_result.report.get("metadata", {}).get("renamed_columns", {})
    if isinstance(pre_renamed, dict):
        renamed_columns.update({str(k): str(v) for k, v in pre_renamed.items()})

    secondary_rename_map: dict[str, str] = {}
    for column_name in df.columns:
        normalized = _normalize_name(str(column_name))
        canonical = alias_map.get(normalized)
        if canonical and canonical != str(column_name):
            secondary_rename_map[str(column_name)] = canonical
            renamed_columns[str(column_name)] = canonical

    if secondary_rename_map:
        df = df.rename(columns=secondary_rename_map)

    canonical_columns = [_normalize_name(column) for column in profile.canonical_order]
    canonical_column_set = set(canonical_columns)

    # Ensure full canonical schema presence.
    for canonical in canonical_columns:
        if canonical not in df.columns:
            df[canonical] = pd.NA

    all_extra_columns = [column for column in df.columns if _normalize_name(str(column)) not in canonical_column_set]
    extra_columns_dropped: list[str] = []

    if contract.drop_unknown_columns and all_extra_columns:
        extra_columns_dropped = [str(column) for column in all_extra_columns]
        df = df.drop(columns=all_extra_columns)

    column_type_map = {
        _normalize_name(column.canonical_name): column.dtype
        for column in profile.columns
    }

    coercion_stats: dict[str, dict[str, Any]] = {}
    for canonical in canonical_columns:
        if canonical not in df.columns:
            continue

        expected_dtype = column_type_map.get(canonical, "string")
        converted, invalid_to_null = _coerce_for_output(
            df[canonical],
            expected_dtype,
            null_on_coercion_error=contract.null_on_coercion_error,
        )
        df[canonical] = converted
        coercion_stats[canonical] = {
            "expected_dtype": expected_dtype,
            "invalid_to_null": int(invalid_to_null),
            "null_count_after": int(pd.isna(df[canonical]).sum()),
        }

    retained_extras = [column for column in df.columns if _normalize_name(str(column)) not in canonical_column_set]
    final_columns = canonical_columns + [str(column) for column in retained_extras]
    df = df.reindex(columns=final_columns)

    manifest = {
        "source_file_name": source_file_name,
        "contract_version": contract.contract_version,
        "profile": profile_name,
        "validation_status": validation_status,
        "renamed_columns": renamed_columns,
        "extra_columns_dropped": extra_columns_dropped,
        "coercion_stats": coercion_stats,
        "output_row_count": int(len(df)),
        "output_column_count": int(len(df.columns)),
        "final_canonical_columns": canonical_columns,
        "retained_extra_columns": [str(column) for column in retained_extras],
    }

    return UnificationResult(unified_dataframe=df, manifest=manifest)


def write_unified_csv(dataframe: pd.DataFrame, output_path: str | Path) -> Path:
    """Write unified dataframe to CSV and return absolute path."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False)
    return path


def write_unification_manifest(manifest: dict[str, Any], output_path: str | Path) -> Path:
    """Write unification manifest as JSON and return absolute path."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
    return path
