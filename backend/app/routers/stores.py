from fastapi import APIRouter

from app.schemas import StoreItem
from app.services.sales_service import list_stores

router = APIRouter()


@router.get("/stores", response_model=list[StoreItem])
def get_stores() -> list[StoreItem]:
    return list_stores()
