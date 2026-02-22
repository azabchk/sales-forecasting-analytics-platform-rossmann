from __future__ import annotations

from typing import Any

import pandas as pd

from .input_contract_models import ProfileContract
from .quality_rule_models import (
    ColumnQualityRule,
    QualityEvaluationReport,
    QualityRuleResult,
    TableQualityRule,
)


def _normalize_name(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _rule_status(violation: bool, severity: str) -> str:
    if not violation:
        return "PASS"
    return "FAIL" if severity.upper() == "FAIL" else "WARN"


def _format_columns(columns: list[str]) -> list[str]:
    return [_normalize_name(column) for column in columns]


def _evaluate_between_rule(dataframe: pd.DataFrame, rule: ColumnQualityRule) -> QualityRuleResult:
    column = _normalize_name(rule.column)
    if column not in dataframe.columns:
        return QualityRuleResult(
            rule_id=rule.id,
            rule_type=rule.rule_type,
            target=[column],
            severity=rule.severity,
            status=_rule_status(True, rule.severity),
            observed={"missing_column": True},
            message=f"Column '{column}' is missing.",
        )

    series = dataframe[column]
    converted = pd.to_numeric(series, errors="coerce")
    null_or_invalid_count = int(converted.isna().sum())

    out_of_range_mask = pd.Series(False, index=dataframe.index)
    if rule.min_value is not None:
        out_of_range_mask |= converted < float(rule.min_value)
    if rule.max_value is not None:
        out_of_range_mask |= converted > float(rule.max_value)

    out_of_range_count = int(out_of_range_mask.fillna(False).sum())
    violation_count = int(null_or_invalid_count + out_of_range_count)
    status = _rule_status(violation_count > 0, rule.severity)

    observed = {
        "row_count": int(len(dataframe)),
        "null_or_invalid_count": null_or_invalid_count,
        "out_of_range_count": out_of_range_count,
        "violation_count": violation_count,
        "min_allowed": rule.min_value,
        "max_allowed": rule.max_value,
        "min_observed": float(converted.min()) if converted.notna().any() else None,
        "max_observed": float(converted.max()) if converted.notna().any() else None,
    }

    if status == "PASS":
        message = f"Column '{column}' is within configured range."
    else:
        message = (
            f"Column '{column}' has {violation_count} violating rows "
            f"(null/invalid={null_or_invalid_count}, out_of_range={out_of_range_count})."
        )

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=[column],
        severity=rule.severity,
        status=status,
        observed=observed,
        message=message,
    )


def _evaluate_accepted_values_rule(dataframe: pd.DataFrame, rule: ColumnQualityRule) -> QualityRuleResult:
    column = _normalize_name(rule.column)
    if column not in dataframe.columns:
        return QualityRuleResult(
            rule_id=rule.id,
            rule_type=rule.rule_type,
            target=[column],
            severity=rule.severity,
            status=_rule_status(True, rule.severity),
            observed={"missing_column": True},
            message=f"Column '{column}' is missing.",
        )

    series = dataframe[column]
    allowed_values = list(rule.values)
    invalid_mask = series.isna() | ~series.isin(allowed_values)
    invalid_count = int(invalid_mask.sum())
    status = _rule_status(invalid_count > 0, rule.severity)

    invalid_values_sample = series[invalid_mask].dropna().unique().tolist()[:5]
    observed = {
        "row_count": int(len(dataframe)),
        "invalid_count": invalid_count,
        "allowed_values": allowed_values,
        "invalid_values_sample": invalid_values_sample,
    }

    if status == "PASS":
        message = f"Column '{column}' only contains accepted values."
    else:
        message = f"Column '{column}' has {invalid_count} rows outside accepted values."

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=[column],
        severity=rule.severity,
        status=status,
        observed=observed,
        message=message,
    )


def _evaluate_max_null_ratio_rule(dataframe: pd.DataFrame, rule: ColumnQualityRule) -> QualityRuleResult:
    column = _normalize_name(rule.column)
    if column not in dataframe.columns:
        return QualityRuleResult(
            rule_id=rule.id,
            rule_type=rule.rule_type,
            target=[column],
            severity=rule.severity,
            status=_rule_status(True, rule.severity),
            observed={"missing_column": True},
            message=f"Column '{column}' is missing.",
        )

    series = dataframe[column]
    null_count = int(series.isna().sum())
    row_count = int(len(dataframe))
    null_ratio = float(null_count / row_count) if row_count > 0 else 1.0
    threshold = float(rule.value or 0.0)

    status = _rule_status(null_ratio > threshold, rule.severity)
    observed = {
        "row_count": row_count,
        "null_count": null_count,
        "null_ratio": null_ratio,
        "max_null_ratio": threshold,
    }

    if status == "PASS":
        message = f"Column '{column}' null ratio is within threshold."
    else:
        message = (
            f"Column '{column}' null ratio {null_ratio:.4f} exceeds allowed threshold {threshold:.4f}."
        )

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=[column],
        severity=rule.severity,
        status=status,
        observed=observed,
        message=message,
    )


def _evaluate_column_rule(dataframe: pd.DataFrame, rule: ColumnQualityRule) -> QualityRuleResult:
    if rule.rule_type == "between":
        return _evaluate_between_rule(dataframe, rule)
    if rule.rule_type == "accepted_values":
        return _evaluate_accepted_values_rule(dataframe, rule)
    if rule.rule_type == "max_null_ratio":
        return _evaluate_max_null_ratio_rule(dataframe, rule)

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=[_normalize_name(rule.column)],
        severity=rule.severity,
        status=_rule_status(True, rule.severity),
        observed={"unsupported_rule": rule.rule_type},
        message=f"Unsupported column rule type '{rule.rule_type}'.",
    )


def _evaluate_composite_unique_rule(dataframe: pd.DataFrame, rule: TableQualityRule) -> QualityRuleResult:
    columns = _format_columns(rule.columns)
    missing_columns = [column for column in columns if column not in dataframe.columns]
    if missing_columns:
        return QualityRuleResult(
            rule_id=rule.id,
            rule_type=rule.rule_type,
            target=columns,
            severity=rule.severity,
            status=_rule_status(True, rule.severity),
            observed={"missing_columns": missing_columns},
            message=f"Columns missing for composite uniqueness check: {missing_columns}",
        )

    duplicate_rows = int(dataframe.duplicated(subset=columns, keep=False).sum())
    status = _rule_status(duplicate_rows > 0, rule.severity)
    observed = {
        "row_count": int(len(dataframe)),
        "columns": columns,
        "duplicate_row_count": duplicate_rows,
    }

    if status == "PASS":
        message = f"Composite key {columns} is unique."
    else:
        message = f"Composite key {columns} has {duplicate_rows} duplicate rows."

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=columns,
        severity=rule.severity,
        status=status,
        observed=observed,
        message=message,
    )


def _evaluate_row_count_between_rule(dataframe: pd.DataFrame, rule: TableQualityRule) -> QualityRuleResult:
    row_count = int(len(dataframe))
    min_value = int(rule.min_value) if rule.min_value is not None else None
    max_value = int(rule.max_value) if rule.max_value is not None else None

    violation = False
    if min_value is not None and row_count < min_value:
        violation = True
    if max_value is not None and row_count > max_value:
        violation = True

    status = _rule_status(violation, rule.severity)
    observed = {
        "row_count": row_count,
        "min_allowed": min_value,
        "max_allowed": max_value,
    }

    if status == "PASS":
        message = "Row count is within configured bounds."
    else:
        message = f"Row count {row_count} is outside configured bounds."

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=[],
        severity=rule.severity,
        status=status,
        observed=observed,
        message=message,
    )


def _evaluate_table_rule(dataframe: pd.DataFrame, rule: TableQualityRule) -> QualityRuleResult:
    if rule.rule_type == "composite_unique":
        return _evaluate_composite_unique_rule(dataframe, rule)
    if rule.rule_type == "row_count_between":
        return _evaluate_row_count_between_rule(dataframe, rule)

    return QualityRuleResult(
        rule_id=rule.id,
        rule_type=rule.rule_type,
        target=[],
        severity=rule.severity,
        status=_rule_status(True, rule.severity),
        observed={"unsupported_rule": rule.rule_type},
        message=f"Unsupported table rule type '{rule.rule_type}'.",
    )


def _aggregate_status(results: list[QualityRuleResult]) -> str:
    if any(result.status == "FAIL" for result in results):
        return "FAIL"
    if any(result.status == "WARN" for result in results):
        return "WARN"
    return "PASS"


def evaluate_quality_rules(dataframe: pd.DataFrame, profile: ProfileContract) -> QualityEvaluationReport:
    """Evaluate semantic quality rules on unified canonical dataframe."""

    if not profile.quality_rules.has_rules:
        return QualityEvaluationReport(
            status="PASS",
            passed_rules=0,
            warned_rules=0,
            failed_rules=0,
            total_rules=0,
            results=[],
            summary="No semantic quality rules configured.",
        )

    df = dataframe.copy()
    df.columns = [_normalize_name(str(column)) for column in df.columns]

    results: list[QualityRuleResult] = []
    for column_rule in profile.quality_rules.columns:
        results.append(_evaluate_column_rule(df, column_rule))
    for table_rule in profile.quality_rules.table:
        results.append(_evaluate_table_rule(df, table_rule))

    status = _aggregate_status(results)
    passed_rules = sum(1 for result in results if result.status == "PASS")
    warned_rules = sum(1 for result in results if result.status == "WARN")
    failed_rules = sum(1 for result in results if result.status == "FAIL")

    if status == "PASS":
        summary = "All semantic quality rules passed."
    elif status == "WARN":
        summary = "Semantic quality checks completed with warnings."
    else:
        summary = "Semantic quality checks failed."

    return QualityEvaluationReport(
        status=status,
        passed_rules=int(passed_rules),
        warned_rules=int(warned_rules),
        failed_rules=int(failed_rules),
        total_rules=int(len(results)),
        results=results,
        summary=summary,
    )
