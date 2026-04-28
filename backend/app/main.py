import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any ETL/registry modules so os.getenv("DATABASE_URL") resolves.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.routers import (
    auth,
    chat,
    contracts,
    data_sources,
    diagnostics,
    forecast,
    health,
    kpi,
    ml,
    sales,
    scenario,
    stores,
    system,
)
from app.security.jwt import get_current_user
from app.services.preflight_alerts_scheduler import PreflightAlertsScheduler

settings = get_settings()

# ── Rate limiter (in-memory, keyed by client IP) ──────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app.api")

_preflight_alerts_scheduler: PreflightAlertsScheduler | None = None


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global _preflight_alerts_scheduler
    _preflight_alerts_scheduler = PreflightAlertsScheduler.from_env()
    _preflight_alerts_scheduler.start()
    try:
        yield
    finally:
        if _preflight_alerts_scheduler is not None:
            _preflight_alerts_scheduler.shutdown()
            _preflight_alerts_scheduler = None


app = FastAPI(
    title="Rossmann Sales Forecast API",
    description="API for KPI analytics, timeseries exploration, and sales forecasting",
    version="2.0.0",
    lifespan=app_lifespan,
)

# Attach rate limiter state and handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Unhandled error: method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    duration_ms = (time.perf_counter() - started) * 1000.0
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    logger.info(
        "Request completed: method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response

_protected = [Depends(get_current_user)]

# Public — no auth required
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router,   prefix="/api/v1", tags=["auth"])

# Protected — valid JWT required
app.include_router(stores.router,       prefix="/api/v1", tags=["stores"],       dependencies=_protected)
app.include_router(kpi.router,          prefix="/api/v1", tags=["kpi"],          dependencies=_protected)
app.include_router(sales.router,        prefix="/api/v1", tags=["sales"],        dependencies=_protected)
app.include_router(forecast.router,     prefix="/api/v1", tags=["forecast"],     dependencies=_protected)
app.include_router(scenario.router,     prefix="/api/v1", tags=["scenario"],     dependencies=_protected)
app.include_router(system.router,       prefix="/api/v1", tags=["system"],       dependencies=_protected)
app.include_router(data_sources.router, prefix="/api/v1", tags=["data_sources"], dependencies=_protected)
app.include_router(contracts.router,    prefix="/api/v1", tags=["contracts"],    dependencies=_protected)
app.include_router(ml.router,           prefix="/api/v1", tags=["ml"],           dependencies=_protected)
app.include_router(chat.router,         prefix="/api/v1", tags=["chat"],         dependencies=_protected)
app.include_router(diagnostics.router,  prefix="/api/v1", tags=["diagnostics"],  dependencies=_protected)
