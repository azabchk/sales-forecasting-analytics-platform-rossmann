from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import MLExperimentListItemResponse, MLExperimentsResponse
from app.services.ml_experiment_service import get_ml_experiment, list_ml_experiments

router = APIRouter()


@router.get("/ml/experiments", response_model=MLExperimentsResponse)
def get_experiments(
    limit: int = Query(default=100, ge=1, le=500),
    data_source_id: int | None = Query(default=None, gt=0),
) -> MLExperimentsResponse:
    try:
        rows = list_ml_experiments(limit=limit, data_source_id=data_source_id)
        return MLExperimentsResponse(
            items=[MLExperimentListItemResponse.model_validate(item) for item in rows],
            limit=limit,
            data_source_id=data_source_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ML experiment error: {exc}") from exc


@router.get("/ml/experiments/{experiment_id}", response_model=MLExperimentListItemResponse)
def get_experiment(experiment_id: str) -> MLExperimentListItemResponse:
    try:
        payload = get_ml_experiment(experiment_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_id}")
        return MLExperimentListItemResponse.model_validate(payload)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ML experiment error: {exc}") from exc
