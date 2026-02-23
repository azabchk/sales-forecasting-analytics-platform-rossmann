from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import DataSourceCreateRequest, DataSourceResponse, PreflightRunSummary
from app.services.data_source_service import (
    create_data_source_entry,
    get_data_source_by_id,
    list_data_source_preflight_runs,
    list_data_sources_with_health,
)

router = APIRouter()


@router.get("/data-sources", response_model=list[DataSourceResponse])
def get_data_sources(
    include_inactive: bool = Query(default=True),
) -> list[DataSourceResponse]:
    try:
        payload = list_data_sources_with_health(include_inactive=include_inactive)
        return [DataSourceResponse.model_validate(item) for item in payload]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Data source error: {exc}") from exc


@router.post("/data-sources", response_model=DataSourceResponse, status_code=201)
def post_data_source(payload: DataSourceCreateRequest) -> DataSourceResponse:
    try:
        created = create_data_source_entry(
            name=payload.name,
            description=payload.description,
            source_type=payload.source_type,
            related_contract_id=payload.related_contract_id,
            related_contract_version=payload.related_contract_version,
            is_active=payload.is_active,
            is_default=payload.is_default,
        )
        return DataSourceResponse.model_validate(created)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Data source error: {exc}") from exc


@router.get("/data-sources/{data_source_id}", response_model=DataSourceResponse)
def get_data_source(data_source_id: int) -> DataSourceResponse:
    try:
        payload = get_data_source_by_id(data_source_id)
        return DataSourceResponse.model_validate(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Data source error: {exc}") from exc


@router.get("/data-sources/{data_source_id}/preflight-runs", response_model=list[PreflightRunSummary])
def get_data_source_preflight_runs(
    data_source_id: int,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PreflightRunSummary]:
    try:
        rows = list_data_source_preflight_runs(data_source_id=data_source_id, limit=limit)
        return [PreflightRunSummary.model_validate(item) for item in rows]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Data source error: {exc}") from exc
