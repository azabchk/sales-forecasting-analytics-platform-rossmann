from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_console_summary(report: dict[str, Any]) -> str:
    """Build a readable console summary for a validation report."""
    lines = [
        "Input Validation Summary",
        f"- Status: {report.get('status')}",
        f"- Contract: {report.get('contract_version')}",
        f"- File: {report.get('file_name')}",
        f"- Profile: {report.get('profile')}",
        "- Checks:",
    ]

    checks = report.get("checks", {})
    for check_name in ["format", "file_size", "row_limit", "required_columns", "types", "extra_columns"]:
        if check_name in checks:
            lines.append(f"  - {check_name}: {checks[check_name]}")

    errors = report.get("errors", [])
    warnings = report.get("warnings", [])
    if errors:
        lines.append("- Errors:")
        lines.extend([f"  - {item}" for item in errors])

    if warnings:
        lines.append("- Warnings:")
        lines.extend([f"  - {item}" for item in warnings])

    summary = report.get("summary")
    if summary:
        lines.append(f"- Summary: {summary}")

    return "\n".join(lines)


def build_unification_console_summary(manifest: dict[str, Any]) -> str:
    """Build a readable console summary for unification manifest."""
    lines = [
        "Schema Unification Summary",
        f"- Source file: {manifest.get('source_file_name')}",
        f"- Contract: {manifest.get('contract_version')}",
        f"- Profile: {manifest.get('profile')}",
        f"- Validation status: {manifest.get('validation_status')}",
        f"- Output rows: {manifest.get('output_row_count')}",
        f"- Output columns: {manifest.get('output_column_count')}",
        f"- Canonical columns: {', '.join(manifest.get('final_canonical_columns', []))}",
    ]

    semantic_quality = manifest.get("semantic_quality", {})
    if isinstance(semantic_quality, dict) and semantic_quality:
        lines.append(f"- Semantic status: {semantic_quality.get('status')}")

    dropped = manifest.get("extra_columns_dropped", [])
    if dropped:
        lines.append(f"- Dropped extra columns: {dropped}")

    renamed = manifest.get("renamed_columns", {})
    if renamed:
        lines.append(f"- Renamed columns: {renamed}")

    return "\n".join(lines)


def build_semantic_console_summary(semantic_report: dict[str, Any]) -> str:
    """Build a readable console summary for semantic quality report."""
    counts = semantic_report.get("counts", {})
    lines = [
        "Semantic Quality Summary",
        f"- Status: {semantic_report.get('status')}",
        f"- Total rules: {counts.get('total', 0)}",
        f"- Passed: {counts.get('passed', 0)}",
        f"- Warned: {counts.get('warned', 0)}",
        f"- Failed: {counts.get('failed', 0)}",
    ]

    rules = semantic_report.get("rules", [])
    if rules:
        lines.append("- Rule results:")
        for rule in rules:
            lines.append(
                f"  - [{rule.get('status')}] {rule.get('rule_id')} "
                f"({rule.get('rule_type')}): {rule.get('message')}"
            )

    summary = semantic_report.get("summary")
    if summary:
        lines.append(f"- Summary: {summary}")

    return "\n".join(lines)


def write_json_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Persist report as JSON and return absolute path."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    return path
