from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .preflight_registry import insert_preflight_run
from src.validation import (
    build_console_summary,
    build_semantic_console_summary,
    build_unification_console_summary,
    evaluate_quality_rules,
    load_input_contract,
    unify_validated_dataframe,
    validate_csv_file,
    write_json_report,
    write_unification_manifest,
    write_unified_csv,
)

PreflightMode = Literal["off", "report_only", "enforce"]
SUPPORTED_MODES = {"off", "report_only", "enforce"}
logger = logging.getLogger("preflight.runner")


@dataclass(frozen=True)
class PreflightResult:
    mode: str
    validation_status: str
    semantic_status: str
    raw_input_path: str
    etl_input_path: str
    artifact_dir: str | None
    validation_report_path: str | None
    semantic_report_path: str | None
    unification_manifest_path: str | None
    unified_output_path: str | None
    preflight_report_path: str | None
    console_summary: str | None = None
    unification_summary: str | None = None
    semantic_summary: str | None = None


class PreflightEnforcementError(RuntimeError):
    """Raised when preflight validation fails in enforce mode."""

    def __init__(self, message: str, result: PreflightResult):
        super().__init__(message)
        self.result = result


def _derive_final_status(validation_status: str, semantic_status: str) -> str:
    normalized_validation = str(validation_status).upper()
    normalized_semantic = str(semantic_status).upper()

    if normalized_validation == "FAIL" or normalized_semantic == "FAIL":
        return "FAIL"
    if normalized_validation == "WARN" or normalized_semantic == "WARN":
        return "WARN"
    if normalized_validation == "SKIPPED" and normalized_semantic == "SKIPPED":
        return "SKIPPED"
    return "PASS"


def _build_registry_summary(
    *,
    mode: str,
    validation_report: dict[str, object],
    semantic_report: dict[str, object] | None,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "mode": mode,
        "validation": {
            "status": validation_report.get("status"),
            "errors_count": len(validation_report.get("errors", [])) if isinstance(validation_report.get("errors"), list) else 0,
            "warnings_count": len(validation_report.get("warnings", [])) if isinstance(validation_report.get("warnings"), list) else 0,
        },
    }

    if semantic_report is None:
        summary["semantic"] = {"status": "SKIPPED", "counts": {"total": 0, "passed": 0, "warned": 0, "failed": 0}}
    else:
        summary["semantic"] = {
            "status": semantic_report.get("status"),
            "counts": semantic_report.get("counts", {"total": 0, "passed": 0, "warned": 0, "failed": 0}),
        }
    return summary


def _persist_registry_record(
    *,
    run_id: str,
    source_name: str,
    result: PreflightResult,
    validation_report: dict[str, object],
    semantic_report: dict[str, object] | None,
    blocked: bool,
    block_reason: str | None,
    data_source_id: int | None,
    contract_id: str | None,
    contract_version: str | None,
) -> None:
    final_status = _derive_final_status(result.validation_status, result.semantic_status)
    summary_json = _build_registry_summary(
        mode=result.mode,
        validation_report=validation_report,
        semantic_report=semantic_report,
    )

    record = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc),
        "mode": result.mode,
        "source_name": source_name,
        "validation_status": result.validation_status,
        "semantic_status": result.semantic_status,
        "final_status": final_status,
        "used_input_path": result.etl_input_path,
        "used_unified": bool(result.unified_output_path and result.unified_output_path == result.etl_input_path),
        "artifact_dir": result.artifact_dir,
        "validation_report_path": result.validation_report_path,
        "manifest_path": result.unification_manifest_path,
        "summary_json": summary_json,
        "blocked": blocked,
        "block_reason": block_reason,
        "data_source_id": data_source_id,
        "contract_id": contract_id,
        "contract_version": contract_version,
    }

    try:
        insert_preflight_run(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preflight registry persistence failed for run_id=%s source=%s: %s", run_id, source_name, exc)


def _resolve_mode(mode: str) -> PreflightMode:
    normalized = str(mode).strip().lower()
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported preflight mode '{mode}'. Expected one of {sorted(SUPPORTED_MODES)}")
    return normalized  # type: ignore[return-value]


def run_preflight(
    *,
    raw_input_path: str | Path,
    profile_name: str,
    contract_path: str | Path,
    mode: str,
    artifact_root: str | Path,
    source_name: str,
    run_id: str | None = None,
    data_source_id: int | None = None,
    contract_id: str | None = None,
) -> PreflightResult:
    """Run preflight validation/unification for one input file.

    Modes:
    - off: skip preflight and return raw input path
    - report_only: run validation+unification artifacts; ETL still uses raw input
    - enforce: FAIL blocks ETL; PASS/WARN use unified canonical CSV
    """

    resolved_mode = _resolve_mode(mode)
    raw_path = Path(raw_input_path).resolve()

    if resolved_mode == "off":
        return PreflightResult(
            mode=resolved_mode,
            validation_status="SKIPPED",
            semantic_status="SKIPPED",
            raw_input_path=str(raw_path),
            etl_input_path=str(raw_path),
            artifact_dir=None,
            validation_report_path=None,
            semantic_report_path=None,
            unification_manifest_path=None,
            unified_output_path=None,
            preflight_report_path=None,
            console_summary="Preflight skipped (mode=off).",
            unification_summary=None,
            semantic_summary=None,
        )

    contract = load_input_contract(contract_path)
    validation_result = validate_csv_file(
        file_path=raw_path,
        contract=contract,
        profile_name=profile_name,
    )

    resolved_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = Path(artifact_root).resolve() / resolved_run_id / source_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    validation_report_path = write_json_report(validation_result.report, artifact_dir / "validation_report.json")
    validation_status = str(validation_result.report.get("status", "FAIL"))
    validation_summary = build_console_summary(validation_result.report)

    if validation_status == "FAIL":
        preflight_payload = {
            "mode": resolved_mode,
            "source_name": source_name,
            "raw_input_path": str(raw_path),
            "etl_input_path": str(raw_path),
            "validation": validation_result.report,
            "semantic": {
                "status": "SKIPPED",
                "summary": "Semantic quality checks were skipped because validation failed.",
                "counts": {"total": 0, "passed": 0, "warned": 0, "failed": 0},
                "rules": [],
            },
        }
        preflight_report_path = write_json_report(preflight_payload, artifact_dir / "preflight_report.json")
        result = PreflightResult(
            mode=resolved_mode,
            validation_status=validation_status,
            semantic_status="SKIPPED",
            raw_input_path=str(raw_path),
            etl_input_path=str(raw_path),
            artifact_dir=str(artifact_dir),
            validation_report_path=str(validation_report_path),
            semantic_report_path=None,
            unification_manifest_path=None,
            unified_output_path=None,
            preflight_report_path=str(preflight_report_path),
            console_summary=validation_summary,
            unification_summary=None,
            semantic_summary=None,
        )
        blocked = resolved_mode == "enforce"
        block_reason = "validation_fail" if blocked else None
        _persist_registry_record(
            run_id=resolved_run_id,
            source_name=source_name,
            result=result,
            validation_report=validation_result.report,
            semantic_report=None,
            blocked=blocked,
            block_reason=block_reason,
            data_source_id=data_source_id,
            contract_id=contract_id,
            contract_version=contract.contract_version,
        )
        if resolved_mode == "enforce":
            raise PreflightEnforcementError(
                f"Preflight validation failed for '{source_name}' with profile '{profile_name}'",
                result,
            )
        return result

    unification_result = unify_validated_dataframe(
        validation_result=validation_result,
        contract=contract,
        profile_name=profile_name,
        source_file_name=raw_path.name,
    )
    unified_output_path = write_unified_csv(unification_result.unified_dataframe, artifact_dir / "unified.csv")
    semantic_evaluation = evaluate_quality_rules(
        dataframe=unification_result.unified_dataframe,
        profile=contract.profiles[profile_name],
    )
    semantic_report = semantic_evaluation.to_dict()
    semantic_report_path = write_json_report(semantic_report, artifact_dir / "semantic_report.json")
    semantic_summary = build_semantic_console_summary(semantic_report)

    semantic_status = str(semantic_report.get("status", "FAIL"))
    manifest_payload = dict(unification_result.manifest)
    manifest_payload["semantic_quality"] = semantic_report

    unification_manifest_path = write_unification_manifest(manifest_payload, artifact_dir / "manifest.json")
    unification_summary = build_unification_console_summary(manifest_payload)

    etl_input_path = str(unified_output_path if resolved_mode == "enforce" else raw_path)
    preflight_payload = {
        "mode": resolved_mode,
        "source_name": source_name,
        "raw_input_path": str(raw_path),
        "etl_input_path": etl_input_path,
        "validation": validation_result.report,
        "unification": manifest_payload,
        "semantic": semantic_report,
    }
    preflight_report_path = write_json_report(preflight_payload, artifact_dir / "preflight_report.json")

    result = PreflightResult(
        mode=resolved_mode,
        validation_status=validation_status,
        semantic_status=semantic_status,
        raw_input_path=str(raw_path),
        etl_input_path=etl_input_path,
        artifact_dir=str(artifact_dir),
        validation_report_path=str(validation_report_path),
        semantic_report_path=str(semantic_report_path),
        unification_manifest_path=str(unification_manifest_path),
        unified_output_path=str(unified_output_path),
        preflight_report_path=str(preflight_report_path),
        console_summary=validation_summary,
        unification_summary=unification_summary,
        semantic_summary=semantic_summary,
    )

    blocked = semantic_status == "FAIL" and resolved_mode == "enforce"
    block_reason = "semantic_fail" if blocked else None
    _persist_registry_record(
        run_id=resolved_run_id,
        source_name=source_name,
        result=result,
        validation_report=validation_result.report,
        semantic_report=semantic_report,
        blocked=blocked,
        block_reason=block_reason,
        data_source_id=data_source_id,
        contract_id=contract_id,
        contract_version=contract.contract_version,
    )

    if blocked:
        raise PreflightEnforcementError(
            f"Semantic quality rules failed for '{source_name}' with profile '{profile_name}'",
            result,
        )

    return result
