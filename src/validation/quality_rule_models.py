from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RULE_SEVERITIES = {"WARN", "FAIL"}
COLUMN_RULE_TYPES = {"between", "accepted_values", "max_null_ratio"}
TABLE_RULE_TYPES = {"composite_unique", "row_count_between"}
RULE_STATUSES = {"PASS", "WARN", "FAIL"}


def _normalize_name(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")


@dataclass(frozen=True)
class ColumnQualityRule:
    id: str
    column: str
    rule_type: str
    severity: str
    min_value: float | None = None
    max_value: float | None = None
    values: list[Any] = field(default_factory=list)
    value: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ColumnQualityRule":
        if not isinstance(payload, dict):
            raise ValueError("Column quality rule must be an object")

        rule_id = str(payload.get("id", "")).strip()
        if not rule_id:
            raise ValueError("Column quality rule requires non-empty id")

        column = _normalize_name(payload.get("column", ""))
        if not column:
            raise ValueError(f"Column quality rule '{rule_id}' requires non-empty column")

        rule_type = str(payload.get("type", "")).strip().lower()
        if rule_type not in COLUMN_RULE_TYPES:
            raise ValueError(
                f"Unsupported column quality rule type '{rule_type}' for rule '{rule_id}'. "
                f"Supported: {sorted(COLUMN_RULE_TYPES)}"
            )

        severity = str(payload.get("severity", "FAIL")).strip().upper()
        if severity not in RULE_SEVERITIES:
            raise ValueError(
                f"Unsupported severity '{severity}' for rule '{rule_id}'. Supported: {sorted(RULE_SEVERITIES)}"
            )

        min_value = payload.get("min_value")
        max_value = payload.get("max_value")
        values = payload.get("values", [])
        value = payload.get("value")

        if rule_type == "between":
            if min_value is None and max_value is None:
                raise ValueError(f"Rule '{rule_id}' (between) requires min_value and/or max_value")
            min_value = float(min_value) if min_value is not None else None
            max_value = float(max_value) if max_value is not None else None

        if rule_type == "accepted_values":
            if not isinstance(values, list) or not values:
                raise ValueError(f"Rule '{rule_id}' (accepted_values) requires non-empty values list")

        if rule_type == "max_null_ratio":
            if value is None:
                raise ValueError(f"Rule '{rule_id}' (max_null_ratio) requires value")
            value = float(value)
            if value < 0 or value > 1:
                raise ValueError(f"Rule '{rule_id}' (max_null_ratio) value must be between 0 and 1")

        return cls(
            id=rule_id,
            column=column,
            rule_type=rule_type,
            severity=severity,
            min_value=min_value if isinstance(min_value, float) or min_value is None else float(min_value),
            max_value=max_value if isinstance(max_value, float) or max_value is None else float(max_value),
            values=list(values) if isinstance(values, list) else [],
            value=float(value) if isinstance(value, (int, float)) else (value if value is None else float(value)),
        )


@dataclass(frozen=True)
class TableQualityRule:
    id: str
    rule_type: str
    severity: str
    columns: list[str] = field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableQualityRule":
        if not isinstance(payload, dict):
            raise ValueError("Table quality rule must be an object")

        rule_id = str(payload.get("id", "")).strip()
        if not rule_id:
            raise ValueError("Table quality rule requires non-empty id")

        rule_type = str(payload.get("type", "")).strip().lower()
        if rule_type not in TABLE_RULE_TYPES:
            raise ValueError(
                f"Unsupported table quality rule type '{rule_type}' for rule '{rule_id}'. "
                f"Supported: {sorted(TABLE_RULE_TYPES)}"
            )

        severity = str(payload.get("severity", "FAIL")).strip().upper()
        if severity not in RULE_SEVERITIES:
            raise ValueError(
                f"Unsupported severity '{severity}' for rule '{rule_id}'. Supported: {sorted(RULE_SEVERITIES)}"
            )

        columns_raw = payload.get("columns", [])
        min_value = payload.get("min_value")
        max_value = payload.get("max_value")

        if rule_type == "composite_unique":
            if not isinstance(columns_raw, list) or not columns_raw:
                raise ValueError(f"Rule '{rule_id}' (composite_unique) requires non-empty columns list")
            columns = [_normalize_name(column) for column in columns_raw if str(column).strip()]
            if not columns:
                raise ValueError(f"Rule '{rule_id}' (composite_unique) requires valid columns")
        else:
            columns = []

        if rule_type == "row_count_between":
            if min_value is None and max_value is None:
                raise ValueError(f"Rule '{rule_id}' (row_count_between) requires min_value and/or max_value")
            min_value = float(min_value) if min_value is not None else None
            max_value = float(max_value) if max_value is not None else None

        return cls(
            id=rule_id,
            rule_type=rule_type,
            severity=severity,
            columns=columns,
            min_value=min_value if isinstance(min_value, float) or min_value is None else float(min_value),
            max_value=max_value if isinstance(max_value, float) or max_value is None else float(max_value),
        )


@dataclass(frozen=True)
class QualityRuleSet:
    columns: list[ColumnQualityRule]
    table: list[TableQualityRule]

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "QualityRuleSet":
        if payload is None:
            return cls(columns=[], table=[])
        if not isinstance(payload, dict):
            raise ValueError("quality_rules must be an object when provided")

        column_rules_raw = payload.get("columns", [])
        table_rules_raw = payload.get("table", [])

        if not isinstance(column_rules_raw, list):
            raise ValueError("quality_rules.columns must be a list")
        if not isinstance(table_rules_raw, list):
            raise ValueError("quality_rules.table must be a list")

        return cls(
            columns=[ColumnQualityRule.from_dict(item) for item in column_rules_raw],
            table=[TableQualityRule.from_dict(item) for item in table_rules_raw],
        )

    @property
    def has_rules(self) -> bool:
        return bool(self.columns or self.table)


@dataclass(frozen=True)
class QualityRuleResult:
    rule_id: str
    rule_type: str
    target: list[str]
    severity: str
    status: str
    observed: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        if self.status not in RULE_STATUSES:
            raise ValueError(f"Invalid rule status '{self.status}'")
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type,
            "target": self.target,
            "severity": self.severity,
            "status": self.status,
            "observed": self.observed,
            "message": self.message,
        }


@dataclass(frozen=True)
class QualityEvaluationReport:
    status: str
    passed_rules: int
    warned_rules: int
    failed_rules: int
    total_rules: int
    results: list[QualityRuleResult]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        if self.status not in RULE_STATUSES:
            raise ValueError(f"Invalid evaluation status '{self.status}'")
        return {
            "status": self.status,
            "summary": self.summary,
            "counts": {
                "total": self.total_rules,
                "passed": self.passed_rules,
                "warned": self.warned_rules,
                "failed": self.failed_rules,
            },
            "rules": [result.to_dict() for result in self.results],
        }
