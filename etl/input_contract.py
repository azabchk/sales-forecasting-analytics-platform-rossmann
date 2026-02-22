from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


class InputValidationError(Exception):
    """Raised when input contract validation fails."""


@dataclass
class FileValidationResult:
    dataframe: pd.DataFrame
    summary: dict[str, Any]
    coercion_summary: dict[str, int]
    duplicates_summary: dict[str, Any]
    null_summary: dict[str, Any]
    schema_mapping_used: dict[str, str]
    errors: list[str]
    warnings: list[str]


def _normalize_col_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _build_alias_lookup(profile: dict[str, Any]) -> dict[str, str]:
    aliases_cfg = profile.get("aliases", {})
    lookup: dict[str, str] = {}

    for canonical, aliases in aliases_cfg.items():
        canonical_norm = _normalize_col_name(str(canonical))
        lookup[canonical_norm] = canonical_norm
        if isinstance(aliases, list):
            for alias in aliases:
                lookup[_normalize_col_name(str(alias))] = canonical_norm
        elif isinstance(aliases, str):
            lookup[_normalize_col_name(aliases)] = canonical_norm

    for col in profile.get("required_columns", []):
        lookup[_normalize_col_name(str(col))] = _normalize_col_name(str(col))
    for col in profile.get("optional_columns", []):
        lookup[_normalize_col_name(str(col))] = _normalize_col_name(str(col))

    return lookup


def _safe_read_csv(path: Path, encodings: list[str]) -> tuple[pd.DataFrame, str]:
    parse_errors: list[str] = []
    for encoding in encodings:
        try:
            df = pd.read_csv(path, encoding=encoding, low_memory=False)
            return df, encoding
        except Exception as exc:  # noqa: BLE001
            parse_errors.append(f"{encoding}: {exc}")

    raise InputValidationError(
        f"Unable to parse CSV file '{path}'. Tried encodings: {', '.join(encodings)}. "
        f"Errors: {' | '.join(parse_errors)}"
    )


def _coerce_bool(series: pd.Series) -> tuple[pd.Series, int]:
    true_values = {"1", "true", "t", "yes", "y"}
    false_values = {"0", "false", "f", "no", "n"}

    normalized = series.astype(str).str.strip().str.lower()
    parsed = pd.Series(index=series.index, dtype="float64")

    parsed[normalized.isin(true_values)] = 1.0
    parsed[normalized.isin(false_values)] = 0.0
    parsed[series.isna()] = pd.NA

    invalid_mask = series.notna() & ~normalized.isin(true_values | false_values)
    return parsed, int(invalid_mask.sum())


def _coerce_dtype(series: pd.Series, dtype_name: str) -> tuple[pd.Series, int]:
    dtype_name = dtype_name.lower().strip()

    if dtype_name in {"int", "integer", "float", "numeric"}:
        converted = pd.to_numeric(series, errors="coerce")
        invalid_mask = series.notna() & converted.isna()
        return converted, int(invalid_mask.sum())

    if dtype_name in {"bool", "boolean"}:
        return _coerce_bool(series)

    if dtype_name in {"date", "datetime"}:
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        invalid_mask = series.notna() & converted.isna()
        return converted, int(invalid_mask.sum())

    if dtype_name in {"str", "string"}:
        converted = series.astype("string").str.strip()
        invalid_mask = pd.Series(False, index=series.index)
        return converted, int(invalid_mask.sum())

    return series, 0


def _apply_ranges(
    df: pd.DataFrame,
    ranges_cfg: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    for col, rules in ranges_cfg.items():
        col_norm = _normalize_col_name(str(col))
        if col_norm not in df.columns:
            continue

        series = df[col_norm]
        if not isinstance(rules, dict):
            continue

        if "allowed" in rules:
            allowed = set(rules["allowed"])
            invalid = series.dropna()[~series.dropna().isin(allowed)]
            if not invalid.empty:
                errors.append(
                    f"Column '{col_norm}' contains {len(invalid)} values outside allowed set {sorted(allowed)}"
                )

        if "min" in rules:
            invalid = series.dropna()[series.dropna() < rules["min"]]
            if not invalid.empty:
                errors.append(f"Column '{col_norm}' contains {len(invalid)} values below min={rules['min']}")

        if "max" in rules:
            invalid = series.dropna()[series.dropna() > rules["max"]]
            if not invalid.empty:
                errors.append(f"Column '{col_norm}' contains {len(invalid)} values above max={rules['max']}")

        if "min_date" in rules:
            min_date = pd.to_datetime(rules["min_date"], errors="coerce")
            invalid = series.dropna()[series.dropna() < min_date]
            if not invalid.empty:
                errors.append(f"Column '{col_norm}' contains {len(invalid)} values before {rules['min_date']}")

        if "max_date" in rules:
            max_date = pd.to_datetime(rules["max_date"], errors="coerce")
            invalid = series.dropna()[series.dropna() > max_date]
            if not invalid.empty:
                errors.append(f"Column '{col_norm}' contains {len(invalid)} values after {rules['max_date']}")


def _validate_single_file(
    *,
    file_key: str,
    file_path: str,
    profile_name: str,
    profiles: dict[str, Any],
    file_limits: dict[str, Any],
    policy: dict[str, Any],
    encodings: list[str],
) -> FileValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    path = Path(file_path).resolve()
    if not path.exists():
        raise InputValidationError(f"{file_key}: file not found: {path}")

    if path.suffix.lower() != ".csv":
        raise InputValidationError(f"{file_key}: unsupported file extension '{path.suffix}'. Only .csv is supported")

    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and "csv" not in mime_type and "text" not in mime_type:
        warnings.append(f"{file_key}: MIME hint is '{mime_type}', expected text/csv")

    size_bytes = path.stat().st_size
    max_file_size_mb = float(file_limits.get("max_file_size_mb", 100.0))
    max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
    if size_bytes > max_file_size_bytes:
        raise InputValidationError(
            f"{file_key}: file size {size_bytes} bytes exceeds limit {max_file_size_bytes} bytes ({max_file_size_mb} MB)"
        )

    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise InputValidationError(f"{file_key}: source profile '{profile_name}' not found in validation config")

    df, selected_encoding = _safe_read_csv(path, encodings=encodings)
    if df.empty:
        raise InputValidationError(f"{file_key}: CSV file has no rows: {path}")

    max_rows = int(file_limits.get("max_rows", 5_000_000))
    if len(df) > max_rows:
        raise InputValidationError(f"{file_key}: row count {len(df)} exceeds max_rows={max_rows}")

    alias_lookup = _build_alias_lookup(profile)
    rename_map: dict[str, str] = {}
    schema_mapping_used: dict[str, str] = {}

    for col in df.columns:
        col_norm = _normalize_col_name(col)
        canonical = alias_lookup.get(col_norm)
        if canonical:
            rename_map[col] = canonical
            if canonical != col_norm:
                schema_mapping_used[col] = canonical

    df = df.rename(columns=rename_map)

    required = {_normalize_col_name(str(c)) for c in profile.get("required_columns", [])}
    optional = {_normalize_col_name(str(c)) for c in profile.get("optional_columns", [])}
    known = required | optional

    missing_required = sorted([c for c in required if c not in df.columns])
    if missing_required:
        errors.append(f"{file_key}: missing required columns: {missing_required}")

    unknown_columns = sorted([c for c in df.columns if c not in known])
    on_unknown = str(policy.get("on_unknown_columns", "warn")).lower()
    if unknown_columns:
        message = f"{file_key}: unknown columns detected: {unknown_columns}"
        if on_unknown == "fail":
            errors.append(message)
        elif on_unknown == "warn":
            warnings.append(message)

    dtypes_cfg = profile.get("dtypes", {})
    coercion_summary: dict[str, int] = {}
    total_coercion_errors = 0

    for col, dtype_name in dtypes_cfg.items():
        col_norm = _normalize_col_name(str(col))
        if col_norm not in df.columns:
            continue

        converted, invalid_count = _coerce_dtype(df[col_norm], str(dtype_name))
        df[col_norm] = converted
        coercion_summary[col_norm] = int(invalid_count)
        total_coercion_errors += int(invalid_count)

    coercion_threshold = int(policy.get("type_coercion_fail_threshold", 0))
    if total_coercion_errors > coercion_threshold:
        errors.append(
            f"{file_key}: type coercion errors={total_coercion_errors} exceed threshold={coercion_threshold}"
        )
    elif total_coercion_errors > 0:
        warnings.append(
            f"{file_key}: type coercion errors detected={total_coercion_errors} (within threshold={coercion_threshold})"
        )

    on_invalid_dates = str(policy.get("on_invalid_dates", "fail")).lower()
    for col, dtype_name in dtypes_cfg.items():
        if str(dtype_name).lower() not in {"date", "datetime"}:
            continue
        col_norm = _normalize_col_name(str(col))
        if col_norm not in df.columns:
            continue

        invalid_count = int(df[col_norm].isna().sum())
        if invalid_count == 0:
            continue

        if on_invalid_dates == "drop":
            before = len(df)
            df = df[df[col_norm].notna()].copy()
            dropped = before - len(df)
            warnings.append(f"{file_key}: dropped {dropped} rows with invalid dates in '{col_norm}'")
        else:
            errors.append(f"{file_key}: invalid date values detected in '{col_norm}' (count={invalid_count})")

    null_threshold = float(policy.get("null_threshold_required", 0.0))
    null_summary: dict[str, Any] = {"required_columns": {}}
    for col in sorted(required):
        if col not in df.columns:
            continue
        null_count = int(df[col].isna().sum())
        ratio = float(null_count / len(df)) if len(df) > 0 else 0.0
        null_summary["required_columns"][col] = {
            "null_count": null_count,
            "null_ratio": ratio,
        }
        if ratio > null_threshold:
            errors.append(
                f"{file_key}: required column '{col}' null_ratio={ratio:.4f} exceeds threshold={null_threshold:.4f}"
            )

    duplicate_subset = [
        _normalize_col_name(str(c))
        for c in profile.get("duplicate_subset", [])
        if _normalize_col_name(str(c)) in df.columns
    ]
    duplicates_count = int(df.duplicated(subset=duplicate_subset or None).sum())
    on_duplicates = str(policy.get("on_duplicates", "warn")).lower()

    if duplicates_count > 0:
        if on_duplicates == "fail":
            errors.append(f"{file_key}: duplicate rows detected={duplicates_count}")
        elif on_duplicates == "drop":
            before = len(df)
            df = df.drop_duplicates(subset=duplicate_subset or None).copy()
            dropped = before - len(df)
            warnings.append(f"{file_key}: dropped duplicate rows={dropped}")
        else:
            warnings.append(f"{file_key}: duplicate rows detected={duplicates_count}")

    duplicates_summary = {
        "policy": on_duplicates,
        "subset": duplicate_subset,
        "duplicates_detected": duplicates_count,
        "rows_after_policy": int(len(df)),
    }

    ranges_cfg = profile.get("ranges", {})
    _apply_ranges(df, ranges_cfg, errors, warnings)

    summary = {
        "file_key": file_key,
        "path": str(path),
        "profile": profile_name,
        "encoding": selected_encoding,
        "mime_hint": mime_type,
        "size_bytes": size_bytes,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": list(df.columns),
    }

    return FileValidationResult(
        dataframe=df,
        summary=summary,
        coercion_summary=coercion_summary,
        duplicates_summary=duplicates_summary,
        null_summary=null_summary,
        schema_mapping_used=schema_mapping_used,
        errors=errors,
        warnings=warnings,
    )


def validate_and_unify_inputs(
    *,
    train_csv: str,
    store_csv: str,
    validation_config: dict[str, Any],
) -> dict[str, Any]:
    """Validate and unify source CSV inputs using config-driven source profiles.

    Returns a dict with unified dataframes and a structured validation report.
    """

    if not validation_config:
        raise InputValidationError("Validation config is empty")

    profile_mapping = validation_config.get("profile_mapping", {})
    train_profile = str(profile_mapping.get("train", "rossmann_train"))
    store_profile = str(profile_mapping.get("store", "rossmann_store"))

    file_limits = validation_config.get("file_limits", {})
    policy = validation_config.get("policy", {})
    profiles = validation_config.get("source_profiles", {})
    encodings = validation_config.get("encodings", ["utf-8", "utf-8-sig", "cp1251"])

    train_result = _validate_single_file(
        file_key="train",
        file_path=train_csv,
        profile_name=train_profile,
        profiles=profiles,
        file_limits=file_limits,
        policy=policy,
        encodings=list(encodings),
    )

    store_result = _validate_single_file(
        file_key="store",
        file_path=store_csv,
        profile_name=store_profile,
        profiles=profiles,
        file_limits=file_limits,
        policy=policy,
        encodings=list(encodings),
    )

    errors = [*train_result.errors, *store_result.errors]
    warnings = [*train_result.warnings, *store_result.warnings]

    status = "PASS"
    if errors:
        status = "FAIL"
    elif warnings:
        status = "PASS_WITH_WARNINGS"

    report = {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "files": {
            "train": train_result.summary,
            "store": store_result.summary,
        },
        "coercion_summary": {
            "train": train_result.coercion_summary,
            "store": store_result.coercion_summary,
        },
        "duplicates_summary": {
            "train": train_result.duplicates_summary,
            "store": store_result.duplicates_summary,
        },
        "null_summary": {
            "train": train_result.null_summary,
            "store": store_result.null_summary,
        },
        "schema_mapping_used": {
            "train": train_result.schema_mapping_used,
            "store": store_result.schema_mapping_used,
        },
    }

    return {
        "dataframes": {
            "train": train_result.dataframe,
            "store": store_result.dataframe,
        },
        "report": report,
    }


def write_validation_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Persist validation report as JSON and return absolute path."""
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2, default=str)
    return out_path
