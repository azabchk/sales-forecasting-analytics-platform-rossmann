from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import ScenarioRunRequestV2, ScenarioRunResponseV2
from app.services.scenario_service import run_scenario_v2

router = APIRouter()


@router.post("/scenario/run", response_model=ScenarioRunResponseV2)
def run_scenario(payload: ScenarioRunRequestV2) -> ScenarioRunResponseV2:
    if payload.store_id is not None and payload.segment is not None:
        raise HTTPException(status_code=400, detail="Use either store_id or segment, not both")
    if payload.store_id is None and payload.segment is None:
        raise HTTPException(status_code=400, detail="Either store_id or segment is required")
    try:
        response = run_scenario_v2(
            store_id=payload.store_id,
            segment=payload.segment.model_dump(exclude_none=True) if payload.segment else None,
            price_change_pct=payload.price_change_pct,
            promo_mode=payload.promo_mode,
            weekend_open=payload.weekend_open,
            school_holiday=payload.school_holiday,
            demand_shift_pct=payload.demand_shift_pct,
            confidence_level=payload.confidence_level,
            horizon_days=payload.horizon_days,
            data_source_id=payload.data_source_id,
        )
        return ScenarioRunResponseV2.model_validate(response)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Scenario v2 error: {exc}") from exc
