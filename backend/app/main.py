from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import forecast, health, kpi, sales, stores

settings = get_settings()

app = FastAPI(
    title="Rossmann Sales Forecast API",
    description="API для KPI, таймсерий и прогноза продаж",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(stores.router, prefix="/api/v1", tags=["stores"])
app.include_router(kpi.router, prefix="/api/v1", tags=["kpi"])
app.include_router(sales.router, prefix="/api/v1", tags=["sales"])
app.include_router(forecast.router, prefix="/api/v1", tags=["forecast"])
