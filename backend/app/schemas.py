from datetime import date

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class StoreItem(BaseModel):
    store_id: int
    store_type: str | None = None
    assortment: str | None = None


class KpiSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    store_id: int | None = None
    total_sales: float
    total_customers: float
    avg_daily_sales: float
    promo_days: int
    open_days: int


class SalesTimeseriesPoint(BaseModel):
    date: date
    store_id: int
    sales: float
    customers: float
    promo: int | None = None
    open: int | None = None


class PromoImpactPoint(BaseModel):
    store_id: int
    promo_flag: str
    avg_sales: float
    avg_customers: float
    num_days: int


class ForecastRequest(BaseModel):
    store_id: int = Field(..., gt=0)
    horizon_days: int = Field(30, ge=1, le=180)


class ForecastPoint(BaseModel):
    date: date
    predicted_sales: float
