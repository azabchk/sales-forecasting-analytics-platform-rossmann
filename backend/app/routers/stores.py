from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas import StoreComparisonResponse, StoreItem, StoreListResponse
from app.services.sales_service import get_store_by_id, get_store_comparison, list_stores_paginated

router = APIRouter()


@router.get("/stores", response_model=StoreListResponse)
def get_stores(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    store_type: str | None = Query(default=None),
    assortment: str | None = Query(default=None),
) -> StoreListResponse:
    result = list_stores_paginated(page=page, page_size=page_size, store_type=store_type, assortment=assortment)
    return StoreListResponse.model_validate(result)


@router.get("/stores/comparison", response_model=StoreComparisonResponse)
def get_store_comparison_endpoint(
    store_ids: str = Query(..., description="Comma-separated store IDs (1–10)"),
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> StoreComparisonResponse:
    ids = [int(x.strip()) for x in store_ids.split(",") if x.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="Provide at least one valid store_id")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 stores allowed for comparison")
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from cannot exceed date_to")
    stores = get_store_comparison(store_ids=ids, date_from=date_from, date_to=date_to)
    return StoreComparisonResponse(date_from=date_from, date_to=date_to, stores=stores)


@router.get("/stores/{store_id}", response_model=StoreItem)
def get_store(store_id: int) -> StoreItem:
    item = get_store_by_id(store_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Store not found: {store_id}")
    return item
