from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas import SalesTimeseriesPoint
from app.services.sales_service import get_sales_timeseries

router = APIRouter()


@router.get("/sales/timeseries", response_model=list[SalesTimeseriesPoint])
def sales_timeseries(
    granularity: Literal["daily", "monthly"] = Query(default="daily"),
    date_from: date = Query(...),
    date_to: date = Query(...),
    store_id: int | None = Query(default=None),
) -> list[SalesTimeseriesPoint]:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from не может быть больше date_to")

    return get_sales_timeseries(
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        store_id=store_id,
    )
