from fastapi import APIRouter, HTTPException

from app.schemas import ModelMetadataResponse, SystemSummaryResponse
from app.services.system_service import get_model_metadata, get_system_summary

router = APIRouter()


@router.get("/system/summary", response_model=SystemSummaryResponse)
def system_summary() -> SystemSummaryResponse:
    try:
        return SystemSummaryResponse.model_validate(get_system_summary())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"System summary error: {exc}") from exc


@router.get("/model/metadata", response_model=ModelMetadataResponse)
def model_metadata() -> ModelMetadataResponse:
    try:
        return ModelMetadataResponse.model_validate(get_model_metadata())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Model metadata error: {exc}") from exc

