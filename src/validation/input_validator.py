from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .input_contract_models import InputContract, ProfileContract


CHECK_PASS = "PASS"
CHECK_WARN = "WARN"
CHECK_FAIL = "FAIL"


@dataclass
class ValidationResult:
    report: dict[str, Any]
    dataframe: pd.DataFrame | None


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


def _read_csv_with_fallback(path: Path, encodings: list[str] | None = None) -> tuple[pd.DataFrame, str]:
    selected_encodings = encodings or ["utf-8", "utf-8-sig", "cp1251"]
    errors: list[str] = []

    for encoding in selected_encodings:
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False), encoding
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{encoding}: {exc}")

    raise ValueError(f"CSV parsing failed for {path}. Tried encodings {selected_encodings}. {errors}")


def _count_type_mismatches(series: pd.Series, dtype_name: str) -> int:
    dtype_name = dtype_name.lower()

    if dtype_name == "string":
        return 0

    if dtype_name == "int":
        converted = pd.to_numeric(series, errors="coerce")
        invalid = series.notna() & converted.isna()
        return int(invalid.sum())

    if dtype_name == "float":
        converted = pd.to_numeric(series, errors="coerce")
        invalid = series.notna() & converted.isna()
        return int(invalid.sum())

    if dtype_name == "date":
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        invalid = series.notna() & converted.isna()
        return int(invalid.sum())

    if dtype_name == "bool":
        normalized = series.astype(str).str.strip().str.lower()
        allowed = {"1", "0", "true", "false", "t", "f", "yes", "no", "y", "n"}
        invalid = series.notna() & ~normalized.isin(allowed)
        return int(invalid.sum())

    return 0


def _status_from_checks(checks: dict[str, str]) -> str:
    if any(value == CHECK_FAIL for value in checks.values()):
        return CHECK_FAIL
    if any(value == CHECK_WARN for value in checks.values()):
        return CHECK_WARN
    return CHECK_PASS


def validate_csv_file(
    *,
    file_path: str | Path,
    contract: InputContract,
    profile_name: str,
    encodings: list[str] | None = None,
) -> ValidationResult:
    """Validate CSV file against a profile in the input contract.

    Returns validation report and unified dataframe (renamed to canonical columns) when parsing succeeds.
    """

    path = Path(file_path).resolve()
    checks = {
        "format": CHECK_PASS,
        "file_size": CHECK_PASS,
        "row_limit": CHECK_PASS,
        "required_columns": CHECK_PASS,
        "types": CHECK_PASS,
        "extra_columns": CHECK_PASS,
    }
    errors: list[str] = []
    warnings: list[str] = []
    dataframe: pd.DataFrame | None = None
    encoding_used: str | None = None
    file_size_bytes = 0
    renamed_columns: dict[str, str] = {}

    if profile_name not in contract.profiles:
        raise ValueError(f"Profile '{profile_name}' is not defined in contract")

    profile = contract.profiles[profile_name]

    if not path.exists():
        checks["format"] = CHECK_FAIL
        errors.append(f"File does not exist: {path}")
        report = _build_report(
            contract=contract,
            profile_name=profile_name,
            file_path=path,
            checks=checks,
            errors=errors,
            warnings=warnings,
            encoding_used=encoding_used,
            file_size_bytes=file_size_bytes,
            row_count=0,
            mapped_columns=[],
            extra_columns=[],
            type_mismatches={},
            renamed_columns=renamed_columns,
        )
        return ValidationResult(report=report, dataframe=None)

    file_size_bytes = path.stat().st_size
    max_size_bytes = int(contract.max_file_size_mb * 1024 * 1024)
    if file_size_bytes > max_size_bytes:
        checks["file_size"] = CHECK_FAIL
        errors.append(
            f"File size {file_size_bytes} bytes exceeds max_file_size_mb={contract.max_file_size_mb} ({max_size_bytes} bytes)"
        )

    if path.suffix.lower() != ".csv":
        checks["format"] = CHECK_FAIL
        errors.append(f"Unsupported extension '{path.suffix}'. Expected .csv")

    if checks["format"] == CHECK_FAIL or checks["file_size"] == CHECK_FAIL:
        report = _build_report(
            contract=contract,
            profile_name=profile_name,
            file_path=path,
            checks=checks,
            errors=errors,
            warnings=warnings,
            encoding_used=encoding_used,
            file_size_bytes=file_size_bytes,
            row_count=0,
            mapped_columns=[],
            extra_columns=[],
            type_mismatches={},
            renamed_columns=renamed_columns,
        )
        return ValidationResult(report=report, dataframe=None)

    try:
        raw_df, encoding_used = _read_csv_with_fallback(path, encodings=encodings)
    except ValueError as exc:
        checks["format"] = CHECK_FAIL
        errors.append(str(exc))
        report = _build_report(
            contract=contract,
            profile_name=profile_name,
            file_path=path,
            checks=checks,
            errors=errors,
            warnings=warnings,
            encoding_used=encoding_used,
            file_size_bytes=file_size_bytes,
            row_count=0,
            mapped_columns=[],
            extra_columns=[],
            type_mismatches={},
            renamed_columns=renamed_columns,
        )
        return ValidationResult(report=report, dataframe=None)

    if raw_df.empty:
        checks["required_columns"] = CHECK_FAIL
        errors.append("CSV file is empty")

    row_count = int(len(raw_df))
    if row_count > contract.max_rows:
        checks["row_limit"] = CHECK_FAIL
        errors.append(f"Row count {row_count} exceeds max_rows={contract.max_rows}")

    alias_map = _build_alias_map(profile)
    rename_map: dict[str, str] = {}
    mapped_columns: list[str] = []

    for column_name in raw_df.columns:
        normalized = _normalize_name(str(column_name))
        canonical = alias_map.get(normalized)
        if canonical:
            rename_map[column_name] = canonical
            mapped_columns.append(canonical)
            if str(column_name) != canonical:
                renamed_columns[str(column_name)] = canonical

    dataframe = raw_df.rename(columns=rename_map)

    required_columns = {
        _normalize_name(column.canonical_name)
        for column in profile.columns
        if column.required
    }
    present_columns = {_normalize_name(str(column)) for column in dataframe.columns}

    missing_required = sorted(required_columns - present_columns)
    if missing_required:
        checks["required_columns"] = CHECK_FAIL
        errors.append(f"Missing required columns: {missing_required}")

    known_columns = {
        _normalize_name(column.canonical_name)
        for column in profile.columns
    }
    extra_columns = sorted([str(column) for column in dataframe.columns if _normalize_name(str(column)) not in known_columns])
    if extra_columns:
        if contract.allow_extra_columns:
            checks["extra_columns"] = CHECK_WARN
            warnings.append(f"Extra columns detected: {extra_columns}")
        else:
            checks["extra_columns"] = CHECK_FAIL
            errors.append(f"Extra columns are not allowed: {extra_columns}")

    type_mismatches: dict[str, int] = {}
    total_type_mismatches = 0
    for column in profile.columns:
        canonical = _normalize_name(column.canonical_name)
        if canonical not in dataframe.columns:
            continue
        mismatch_count = _count_type_mismatches(dataframe[canonical], column.dtype)
        type_mismatches[canonical] = mismatch_count
        total_type_mismatches += mismatch_count

    if total_type_mismatches > 0:
        if contract.strict_types:
            checks["types"] = CHECK_FAIL
            errors.append(f"Type mismatches detected: {total_type_mismatches} values")
        else:
            checks["types"] = CHECK_WARN
            warnings.append(f"Type mismatches detected: {total_type_mismatches} values")

    report = _build_report(
        contract=contract,
        profile_name=profile_name,
        file_path=path,
        checks=checks,
        errors=errors,
        warnings=warnings,
        encoding_used=encoding_used,
        file_size_bytes=file_size_bytes,
        row_count=row_count,
        mapped_columns=sorted(set(mapped_columns)),
        extra_columns=extra_columns,
        type_mismatches=type_mismatches,
        renamed_columns=renamed_columns,
    )
    return ValidationResult(report=report, dataframe=dataframe)


def _build_report(
    *,
    contract: InputContract,
    profile_name: str,
    file_path: Path,
    checks: dict[str, str],
    errors: list[str],
    warnings: list[str],
    encoding_used: str | None,
    file_size_bytes: int,
    row_count: int,
    mapped_columns: list[str],
    extra_columns: list[str],
    type_mismatches: dict[str, int],
    renamed_columns: dict[str, str],
) -> dict[str, Any]:
    status = _status_from_checks(checks)
    summary = (
        "Validation passed."
        if status == CHECK_PASS
        else "Validation completed with warnings."
        if status == CHECK_WARN
        else "Validation failed."
    )

    return {
        "status": status,
        "contract_version": contract.contract_version,
        "file_name": file_path.name,
        "file_path": str(file_path),
        "profile": profile_name,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "metadata": {
            "format": contract.data_format,
            "encoding": encoding_used,
            "rows": row_count,
            "file_size_bytes": file_size_bytes,
            "max_rows": contract.max_rows,
            "max_file_size_mb": contract.max_file_size_mb,
            "allow_extra_columns": contract.allow_extra_columns,
            "strict_types": contract.strict_types,
            "mapped_columns": mapped_columns,
            "renamed_columns": renamed_columns,
            "extra_columns": extra_columns,
            "type_mismatches": type_mismatches,
        },
    }
