from fastapi import APIRouter, HTTPException

from app.schemas import ForecastPoint, ForecastRequest
from app.services.forecast_service import forecast_for_store

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
        raise HTTPException(status_code=500, detail=f"Ошибка прогноза: {exc}") from exc
