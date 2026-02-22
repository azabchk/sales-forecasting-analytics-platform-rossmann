from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas import (
    PreflightArtifactType,
    PreflightManifestArtifactResponse,
    PreflightRunDetailResponse,
    PreflightRunsListResponse,
    PreflightRunSummary,
    PreflightSemanticArtifactResponse,
    PreflightSourceArtifactsResponse,
    PreflightValidationArtifactResponse,
)
from app.services.diagnostics_service import (
    DiagnosticsAccessError,
    DiagnosticsNotFoundError,
    DiagnosticsPayloadError,
    get_latest_preflight_for_source,
    get_latest_preflight_run,
    get_preflight_source_artifact_download,
    get_preflight_source_artifacts,
    get_preflight_source_manifest,
    get_preflight_source_semantic,
    get_preflight_source_validation,
    get_preflight_run_details,
    list_preflight_run_summaries,
)

router = APIRouter()


@router.get("/diagnostics/preflight/runs", response_model=PreflightRunsListResponse)
def diagnostics_preflight_runs(
    limit: int = Query(20, ge=1, le=100),
    source_name: Literal["train", "store"] | None = Query(default=None),
) -> PreflightRunsListResponse:
    try:
        items = list_preflight_run_summaries(limit=limit, source_name=source_name)
        return PreflightRunsListResponse(items=items, limit=limit, source_name=source_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc


@router.get("/diagnostics/preflight/runs/{run_id}", response_model=PreflightRunDetailResponse)
def diagnostics_preflight_run_details(run_id: str) -> PreflightRunDetailResponse:
    try:
        payload = get_preflight_run_details(run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail=f"Preflight run not found: {run_id}")
    return PreflightRunDetailResponse.model_validate(payload)


@router.get("/diagnostics/preflight/latest", response_model=PreflightRunDetailResponse)
def diagnostics_preflight_latest() -> PreflightRunDetailResponse:
    try:
        payload = get_latest_preflight_run()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail="No preflight runs found")
    return PreflightRunDetailResponse.model_validate(payload)


@router.get("/diagnostics/preflight/latest/{source_name}", response_model=PreflightRunSummary)
def diagnostics_preflight_latest_by_source(source_name: Literal["train", "store"]) -> PreflightRunSummary:
    try:
        payload = get_latest_preflight_for_source(source_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail=f"No preflight runs found for source '{source_name}'")
    return PreflightRunSummary.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts",
    response_model=PreflightSourceArtifactsResponse,
)
def diagnostics_preflight_source_artifacts(run_id: str, source_name: Literal["train", "store"]) -> PreflightSourceArtifactsResponse:
    try:
        payload = get_preflight_source_artifacts(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightSourceArtifactsResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation",
    response_model=PreflightValidationArtifactResponse,
)
def diagnostics_preflight_source_validation(
    run_id: str,
    source_name: Literal["train", "store"],
) -> PreflightValidationArtifactResponse:
    try:
        payload = get_preflight_source_validation(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightValidationArtifactResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic",
    response_model=PreflightSemanticArtifactResponse,
)
def diagnostics_preflight_source_semantic(
    run_id: str,
    source_name: Literal["train", "store"],
) -> PreflightSemanticArtifactResponse:
    try:
        payload = get_preflight_source_semantic(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightSemanticArtifactResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest",
    response_model=PreflightManifestArtifactResponse,
)
def diagnostics_preflight_source_manifest(
    run_id: str,
    source_name: Literal["train", "store"],
) -> PreflightManifestArtifactResponse:
    try:
        payload = get_preflight_source_manifest(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightManifestArtifactResponse.model_validate(payload)


@router.get("/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}")
def diagnostics_preflight_source_download(
    run_id: str,
    source_name: Literal["train", "store"],
    artifact_type: PreflightArtifactType,
) -> FileResponse:
    try:
        payload = get_preflight_source_artifact_download(
            run_id=run_id,
            source_name=source_name,
            artifact_type=artifact_type,
        )
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    return FileResponse(
        path=payload["path"],
        media_type=payload["content_type"],
        filename=payload["file_name"],
    )
