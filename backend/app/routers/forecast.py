from fastapi import APIRouter, HTTPException

from app.schemas import (
    ForecastBatchRequest,
    ForecastBatchResponse,
    ForecastPoint,
    ForecastRequest,
    ForecastScenarioRequest,
    ForecastScenarioResponse,
)
from app.services.forecast_service import forecast_batch_for_stores, forecast_for_store, forecast_scenario_for_store

router = APIRouter()


@router.post("/forecast", response_model=list[ForecastPoint])
def forecast_sales(payload: ForecastRequest) -> list[ForecastPoint]:
    try:
        return forecast_for_store(store_id=payload.store_id, horizon_days=payload.horizon_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Forecast error: {exc}") from exc


@router.post("/forecast/scenario", response_model=ForecastScenarioResponse)
def forecast_sales_scenario(payload: ForecastScenarioRequest) -> ForecastScenarioResponse:
    try:
        result = forecast_scenario_for_store(
            store_id=payload.store_id,
            horizon_days=payload.horizon_days,
            promo_mode=payload.promo_mode,
            weekend_open=payload.weekend_open,
            school_holiday=payload.school_holiday,
            demand_shift_pct=payload.demand_shift_pct,
            confidence_level=payload.confidence_level,
        )
        return ForecastScenarioResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Scenario forecast error: {exc}") from exc


@router.post("/forecast/batch", response_model=ForecastBatchResponse)
def forecast_sales_batch(payload: ForecastBatchRequest) -> ForecastBatchResponse:
    try:
        result = forecast_batch_for_stores(store_ids=payload.store_ids, horizon_days=payload.horizon_days)
        return ForecastBatchResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Batch forecast error: {exc}") from exc
