from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from typing import Literal
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_registry import get_latest_preflight, get_preflight_run, list_preflight_runs

PreflightArtifactType = Literal["validation", "semantic", "manifest", "preflight", "unified_csv"]
ARTIFACT_TYPES: tuple[PreflightArtifactType, ...] = ("validation", "semantic", "manifest", "preflight", "unified_csv")
ARTIFACT_CONTENT_TYPES: dict[PreflightArtifactType, str] = {
    "validation": "application/json",
    "semantic": "application/json",
    "manifest": "application/json",
    "preflight": "application/json",
    "unified_csv": "text/csv; charset=utf-8",
}


class DiagnosticsNotFoundError(LookupError):
    """Raised when a diagnostics resource does not exist."""


class DiagnosticsAccessError(PermissionError):
    """Raised when artifact access escapes the allowed diagnostics directory."""


class DiagnosticsPayloadError(ValueError):
    """Raised when artifact payload cannot be parsed as expected."""


def _compact_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": payload.get("run_id"),
        "created_at": payload.get("created_at"),
        "mode": payload.get("mode"),
        "source_name": payload.get("source_name"),
        "validation_status": payload.get("validation_status"),
        "semantic_status": payload.get("semantic_status"),
        "final_status": payload.get("final_status"),
        "blocked": bool(payload.get("blocked", False)),
        "block_reason": payload.get("block_reason"),
        "used_unified": bool(payload.get("used_unified", False)),
        "used_input_path": payload.get("used_input_path"),
        "artifact_dir": payload.get("artifact_dir"),
        "validation_report_path": payload.get("validation_report_path"),
        "manifest_path": payload.get("manifest_path"),
    }


def _normalize_status(value: Any, fallback: str = "UNKNOWN") -> str:
    text = str(value).strip().upper()
    return text if text else fallback


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_allowed_artifact_root() -> Path:
    configured = os.getenv("PREFLIGHT_ARTIFACT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (PROJECT_ROOT / "etl" / "reports" / "preflight").resolve()


def _resolve_source_record(run_id: str, source_name: str) -> dict[str, Any]:
    payload = get_preflight_run(run_id)
    if payload is None:
        raise DiagnosticsNotFoundError(f"Preflight run not found: {run_id}")

    records = payload.get("records", [])
    if not isinstance(records, list):
        raise DiagnosticsPayloadError(f"Malformed records payload for run '{run_id}'")

    for record in records:
        if isinstance(record, dict) and str(record.get("source_name")) == source_name:
            return record
    raise DiagnosticsNotFoundError(f"Source '{source_name}' not found for run '{run_id}'")


def _resolve_artifact_dir(record: dict[str, Any]) -> tuple[Path, Path]:
    raw_artifact_dir = record.get("artifact_dir")
    if raw_artifact_dir is None or not str(raw_artifact_dir).strip():
        raise DiagnosticsNotFoundError("Artifact directory is not registered for this run/source")

    artifact_dir = Path(str(raw_artifact_dir)).expanduser().resolve()
    allowed_root = _resolve_allowed_artifact_root()
    if not _is_within(artifact_dir, allowed_root):
        raise DiagnosticsAccessError(
            f"Artifact directory '{artifact_dir}' is outside allowed root '{allowed_root}'"
        )
    return artifact_dir, allowed_root


def _coerce_candidate_path(value: Any, artifact_dir: Path) -> Path | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    path = Path(text).expanduser()
    if not path.is_absolute():
        path = artifact_dir / path
    return path.resolve()


def _summary_paths(record: dict[str, Any]) -> dict[str, str]:
    summary_json = record.get("summary_json")
    if not isinstance(summary_json, dict):
        return {}

    paths_payload = summary_json.get("paths")
    if not isinstance(paths_payload, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, value in paths_payload.items():
        if isinstance(value, str) and value.strip():
            normalized[str(key)] = value
    return normalized


def _artifact_candidates(
    *,
    record: dict[str, Any],
    artifact_type: PreflightArtifactType,
    artifact_dir: Path,
) -> list[Path]:
    summary_paths = _summary_paths(record)

    raw_candidates: list[Any]
    if artifact_type == "validation":
        raw_candidates = [
            record.get("validation_report_path"),
            summary_paths.get("validation_report_path"),
            artifact_dir / "validation_report.json",
        ]
    elif artifact_type == "semantic":
        raw_candidates = [
            summary_paths.get("semantic_report_path"),
            artifact_dir / "semantic_report.json",
        ]
    elif artifact_type == "manifest":
        raw_candidates = [
            record.get("manifest_path"),
            summary_paths.get("manifest_path"),
            artifact_dir / "manifest.json",
        ]
    elif artifact_type == "preflight":
        raw_candidates = [
            summary_paths.get("preflight_report_path"),
            artifact_dir / "preflight_report.json",
        ]
    else:
        raw_candidates = [
            summary_paths.get("unified_output_path"),
            record.get("used_input_path") if bool(record.get("used_unified", False)) else None,
            artifact_dir / "unified.csv",
        ]

    paths: list[Path] = []
    seen: set[str] = set()
    for raw_candidate in raw_candidates:
        resolved = _coerce_candidate_path(raw_candidate, artifact_dir)
        if resolved is None:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        paths.append(resolved)
    return paths


def _assert_path_allowed(path: Path, *, artifact_dir: Path, allowed_root: Path) -> None:
    if not _is_within(path, artifact_dir):
        raise DiagnosticsAccessError(
            f"Artifact path '{path}' is outside registered artifact directory '{artifact_dir}'"
        )
    if not _is_within(path, allowed_root):
        raise DiagnosticsAccessError(
            f"Artifact path '{path}' is outside allowed root '{allowed_root}'"
        )


def _resolve_artifact_descriptor(
    *,
    record: dict[str, Any],
    artifact_type: PreflightArtifactType,
) -> dict[str, Any]:
    artifact_dir, allowed_root = _resolve_artifact_dir(record)
    candidate_paths = _artifact_candidates(record=record, artifact_type=artifact_type, artifact_dir=artifact_dir)
    if not candidate_paths:
        return {"artifact_type": artifact_type, "path": None, "available": False}

    for candidate in candidate_paths:
        _assert_path_allowed(candidate, artifact_dir=artifact_dir, allowed_root=allowed_root)

    for candidate in candidate_paths:
        if candidate.exists() and candidate.is_file():
            return {"artifact_type": artifact_type, "path": candidate, "available": True}

    return {"artifact_type": artifact_type, "path": candidate_paths[0], "available": False}


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as exc:
        raise DiagnosticsNotFoundError(f"Artifact file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DiagnosticsPayloadError(f"Artifact file is not valid JSON: {path}") from exc
    except OSError as exc:
        raise DiagnosticsPayloadError(f"Unable to read artifact file: {path}") from exc

    if not isinstance(payload, dict):
        raise DiagnosticsPayloadError(f"Artifact JSON must be an object: {path}")
    return payload


def _load_artifact_json(
    *,
    record: dict[str, Any],
    artifact_type: PreflightArtifactType,
) -> tuple[dict[str, Any], Path]:
    descriptor = _resolve_artifact_descriptor(record=record, artifact_type=artifact_type)
    path = descriptor.get("path")
    available = bool(descriptor.get("available"))
    if not available or not isinstance(path, Path):
        raise DiagnosticsNotFoundError(
            f"{artifact_type} artifact is not available for source '{record.get('source_name')}'"
        )
    return _load_json_file(path), path


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_of_strings(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_semantic_rules(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "rule_id": str(item.get("rule_id", "unknown_rule")),
                "rule_type": str(item.get("rule_type", "unknown")),
                "severity": _normalize_status(item.get("severity"), fallback="WARN"),
                "status": _normalize_status(item.get("status"), fallback="UNKNOWN"),
                "message": str(item.get("message", "")),
                "target": _list_of_strings(item.get("target")),
                "observed": item.get("observed") if isinstance(item.get("observed"), dict) else {},
            }
        )
    return normalized


def _semantic_counts_from_rules(rules: list[dict[str, Any]]) -> dict[str, int]:
    total = len(rules)
    passed = sum(1 for rule in rules if str(rule.get("status")).upper() == "PASS")
    warned = sum(1 for rule in rules if str(rule.get("status")).upper() == "WARN")
    failed = sum(1 for rule in rules if str(rule.get("status")).upper() == "FAIL")
    return {"total": int(total), "passed": int(passed), "warned": int(warned), "failed": int(failed)}


def _normalize_semantic_counts(value: Any, *, fallback_rules: list[dict[str, Any]]) -> dict[str, int]:
    fallback = _semantic_counts_from_rules(fallback_rules)
    if not isinstance(value, dict):
        return fallback

    normalized: dict[str, int] = {}
    for key in ("total", "passed", "warned", "failed"):
        raw = value.get(key, fallback[key])
        try:
            normalized[key] = int(raw)
        except (TypeError, ValueError):
            normalized[key] = fallback[key]
    return normalized


def _normalize_validation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    checks_raw = payload.get("checks")
    checks: dict[str, str] = {}
    if isinstance(checks_raw, dict):
        checks = {str(name): _normalize_status(status, fallback="UNKNOWN") for name, status in checks_raw.items()}

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "status": _normalize_status(payload.get("status")),
        "contract_version": payload.get("contract_version"),
        "profile": payload.get("profile"),
        "checks": checks,
        "errors": _list_of_strings(payload.get("errors")),
        "warnings": _list_of_strings(payload.get("warnings")),
        "summary": payload.get("summary"),
        "metadata": metadata,
    }


def _normalize_semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rules = _normalize_semantic_rules(payload.get("rules"))
    counts = _normalize_semantic_counts(payload.get("counts"), fallback_rules=rules)

    status = _normalize_status(payload.get("status"), fallback="")
    if not status:
        if counts.get("failed", 0) > 0:
            status = "FAIL"
        elif counts.get("warned", 0) > 0:
            status = "WARN"
        else:
            status = "PASS"

    summary = payload.get("summary")
    if summary is None:
        summary = "Semantic quality results loaded."

    return {
        "status": status,
        "summary": str(summary),
        "counts": counts,
        "rules": rules,
    }


def _normalize_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": payload.get("contract_version"),
        "profile": payload.get("profile"),
        "validation_status": _normalize_status(payload.get("validation_status")),
        "renamed_columns": _dict_of_strings(payload.get("renamed_columns")),
        "extra_columns_dropped": _list_of_strings(payload.get("extra_columns_dropped")),
        "coercion_stats": payload.get("coercion_stats") if isinstance(payload.get("coercion_stats"), dict) else {},
        "final_canonical_columns": _list_of_strings(payload.get("final_canonical_columns")),
        "retained_extra_columns": _list_of_strings(payload.get("retained_extra_columns")),
        "output_row_count": _safe_int(payload.get("output_row_count")),
        "output_column_count": _safe_int(payload.get("output_column_count")),
        "semantic_quality": payload.get("semantic_quality") if isinstance(payload.get("semantic_quality"), dict) else None,
    }


def _build_download_url(*, run_id: str, source_name: str, artifact_type: PreflightArtifactType) -> str:
    return (
        "/api/v1/diagnostics/preflight/runs/"
        f"{quote(run_id, safe='')}/sources/{quote(source_name, safe='')}/download/{artifact_type}"
    )


def _load_semantic_payload_with_fallback(record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        semantic_payload, semantic_path = _load_artifact_json(record=record, artifact_type="semantic")
        return semantic_payload, str(semantic_path)
    except DiagnosticsNotFoundError:
        pass

    for container_type, key in (("manifest", "semantic_quality"), ("preflight", "semantic")):
        try:
            container_payload, container_path = _load_artifact_json(record=record, artifact_type=container_type)
        except DiagnosticsNotFoundError:
            continue
        nested = container_payload.get(key)
        if isinstance(nested, dict):
            return nested, str(container_path)

    raise DiagnosticsNotFoundError(
        f"semantic artifact is not available for source '{record.get('source_name')}'"
    )


def list_preflight_run_summaries(limit: int = 20, source_name: str | None = None) -> list[dict[str, Any]]:
    records = list_preflight_runs(limit=limit, source_name=source_name)
    return [_compact_record(record) for record in records]


def get_preflight_run_details(run_id: str) -> dict[str, Any] | None:
    payload = get_preflight_run(run_id)
    if payload is None:
        return None

    records = [_compact_record(record) for record in payload.get("records", [])]
    return {
        "run_id": payload.get("run_id"),
        "created_at": payload.get("created_at"),
        "mode": payload.get("mode"),
        "final_status": payload.get("final_status"),
        "blocked": bool(payload.get("blocked", False)),
        "records": records,
    }


def get_latest_preflight_run() -> dict[str, Any] | None:
    payload = get_latest_preflight(source_name=None)
    if payload is None:
        return None
    run_id = payload.get("run_id")
    if not run_id:
        return None
    return get_preflight_run_details(str(run_id))


def get_latest_preflight_for_source(source_name: str) -> dict[str, Any] | None:
    payload = get_latest_preflight(source_name=source_name)
    if payload is None:
        return None
    return _compact_record(payload)


def get_preflight_source_artifacts(run_id: str, source_name: str) -> dict[str, Any]:
    record = _resolve_source_record(run_id, source_name)
    artifact_items: list[dict[str, Any]] = []

    for artifact_type in ARTIFACT_TYPES:
        descriptor = _resolve_artifact_descriptor(record=record, artifact_type=artifact_type)
        resolved_path = descriptor.get("path")
        available = bool(descriptor.get("available"))
        file_size = None
        if available and isinstance(resolved_path, Path):
            file_size = int(resolved_path.stat().st_size)

        artifact_items.append(
            {
                "artifact_type": artifact_type,
                "available": available,
                "file_name": resolved_path.name if isinstance(resolved_path, Path) else None,
                "path": str(resolved_path) if isinstance(resolved_path, Path) else None,
                "size_bytes": file_size,
                "content_type": ARTIFACT_CONTENT_TYPES[artifact_type],
                "download_url": _build_download_url(
                    run_id=run_id,
                    source_name=source_name,
                    artifact_type=artifact_type,
                )
                if available
                else None,
            }
        )

    return {
        "run_id": run_id,
        "source_name": source_name,
        "artifact_dir": record.get("artifact_dir"),
        "artifacts": artifact_items,
    }


def get_preflight_source_validation(run_id: str, source_name: str) -> dict[str, Any]:
    record = _resolve_source_record(run_id, source_name)
    payload, artifact_path = _load_artifact_json(record=record, artifact_type="validation")
    normalized = _normalize_validation_payload(payload)
    return {
        "run_id": run_id,
        "source_name": source_name,
        **normalized,
        "artifact_path": str(artifact_path),
    }


def get_preflight_source_semantic(run_id: str, source_name: str) -> dict[str, Any]:
    record = _resolve_source_record(run_id, source_name)
    payload, artifact_path = _load_semantic_payload_with_fallback(record)
    normalized = _normalize_semantic_payload(payload)
    return {
        "run_id": run_id,
        "source_name": source_name,
        **normalized,
        "artifact_path": artifact_path,
    }


def get_preflight_source_manifest(run_id: str, source_name: str) -> dict[str, Any]:
    record = _resolve_source_record(run_id, source_name)
    payload, artifact_path = _load_artifact_json(record=record, artifact_type="manifest")
    normalized = _normalize_manifest_payload(payload)
    return {
        "run_id": run_id,
        "source_name": source_name,
        **normalized,
        "artifact_path": str(artifact_path),
    }


def get_preflight_source_artifact_download(
    run_id: str,
    source_name: str,
    artifact_type: PreflightArtifactType,
) -> dict[str, str]:
    if artifact_type not in ARTIFACT_TYPES:
        raise DiagnosticsPayloadError(f"Unsupported artifact type '{artifact_type}'")

    record = _resolve_source_record(run_id, source_name)
    descriptor = _resolve_artifact_descriptor(record=record, artifact_type=artifact_type)
    path = descriptor.get("path")
    available = bool(descriptor.get("available"))
    if not available or not isinstance(path, Path):
        raise DiagnosticsNotFoundError(
            f"{artifact_type} artifact is not available for source '{source_name}' in run '{run_id}'"
        )

    return {
        "path": str(path),
        "file_name": path.name,
        "content_type": ARTIFACT_CONTENT_TYPES[artifact_type],
    }
