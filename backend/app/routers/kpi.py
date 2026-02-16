from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas import KpiSummaryResponse, PromoImpactPoint
from app.services.kpi_service import get_kpi_summary, get_promo_impact

router = APIRouter()


@router.get("/kpi/summary", response_model=KpiSummaryResponse)
def kpi_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    store_id: int | None = Query(default=None),
) -> KpiSummaryResponse:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from cannot be greater than date_to")

    return get_kpi_summary(date_from=date_from, date_to=date_to, store_id=store_id)


@router.get("/kpi/promo-impact", response_model=list[PromoImpactPoint])
def kpi_promo_impact(store_id: int | None = Query(default=None)) -> list[PromoImpactPoint]:
    return get_promo_impact(store_id=store_id)
