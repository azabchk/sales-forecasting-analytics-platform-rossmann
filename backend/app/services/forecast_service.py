from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any
import uuid
import sys

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa

from app.config import get_settings
from app.db import engine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.data_source_registry import resolve_data_source_id
from src.etl.forecast_run_registry import upsert_forecast_run

settings = get_settings()

# ── In-memory model artifact cache (invalidates on file mtime change) ─────────
_ARTIFACT_CACHE: dict[str, object] = {
    "path": None,
    "mtime": None,
    "payload": None,
}

# ── Short-lived forecast cache (keyed by (store_id, horizon, date)) ──────────
# LRU OrderedDict: most-recently-used at the end; evicts from the front at 500 entries.
_FORECAST_CACHE: OrderedDict[tuple, tuple[datetime, list[dict]]] = OrderedDict()
_FORECAST_CACHE_TTL_SECONDS = 300  # 5-minute TTL


@dataclass(frozen=True)
class ForecastControls:
    promo_mode: str = "as_is"
    weekend_open: bool = True
    school_holiday: int = 0
    demand_shift_pct: float = 0.0
    confidence_level: float = 0.8


def _resolve_model_path() -> Path:
    candidate = Path(settings.model_path)
    if candidate.is_absolute():
        return candidate

    repo_root = Path(__file__).resolve().parents[3]
    backend_root = Path(__file__).resolve().parents[2]

    from_repo = (repo_root / candidate).resolve()
    if from_repo.exists():
        return from_repo

    from_backend = (backend_root / candidate).resolve()
    if from_backend.exists():
        return from_backend

    return from_repo


def _validate_horizon(horizon_days: int) -> None:
    if horizon_days < 1 or horizon_days > 180:
        raise ValueError("horizon_days must be between 1 and 180")


def _validate_store_ids(store_ids: list[int]) -> list[int]:
    if not store_ids:
        raise ValueError("store_ids cannot be empty")
    unique_store_ids: list[int] = []
    seen: set[int] = set()
    for raw in store_ids:
        if raw <= 0:
            raise ValueError("store_ids must contain only positive integers")
        if raw in seen:
            continue
        seen.add(raw)
        unique_store_ids.append(raw)
    if len(unique_store_ids) > 50:
        raise ValueError("store_ids cannot contain more than 50 stores")
    return unique_store_ids


def _fetch_history(engine_ref: sa.Engine, store_id: int, history_days: int = 400) -> pd.DataFrame:
    """
    Fetch the last `history_days` rows for a store.
    400 days (default) is required so lag_364 (yearly seasonality feature)
    is available from the very first forecast step.
    """
    query = sa.text(
        """
        SELECT
            d.full_date,
            f.sales,
            COALESCE(f.promo, 0) AS promo,
            COALESCE(f.school_holiday, 0) AS school_holiday,
            COALESCE(f.open, 1) AS open,
            COALESCE(f.state_holiday, '0') AS state_holiday
        FROM fact_sales_daily f
        JOIN dim_date d ON d.date_id = f.date_id
        WHERE f.store_id = :store_id
        ORDER BY d.full_date DESC
        LIMIT :history_days;
        """
    )
    df = pd.read_sql(query, engine_ref, params={"store_id": store_id, "history_days": history_days})
    if df.empty:
        raise ValueError(f"No data found for store_id={store_id}")
    df["full_date"] = pd.to_datetime(df["full_date"])
    return df.sort_values("full_date").reset_index(drop=True)


def _fetch_store_meta(engine_ref: sa.Engine, store_id: int) -> pd.Series:
    query = sa.text(
        """
        SELECT
            store_id,
            COALESCE(store_type, 'unknown') AS store_type,
            COALESCE(assortment, 'unknown') AS assortment,
            COALESCE(competition_distance, 0) AS competition_distance,
            COALESCE(promo2, 0) AS promo2
        FROM dim_store
        WHERE store_id = :store_id;
        """
    )
    df = pd.read_sql(query, engine_ref, params={"store_id": store_id})
    if df.empty:
        raise ValueError(f"store_id={store_id} not found in dim_store")
    return df.iloc[0]


# ── History helper utilities ──────────────────────────────────────────────────

def _safe_lag(values: list[float], offset: int) -> float:
    if len(values) >= offset:
        return float(values[-offset])
    return float(values[-1])


def _safe_mean(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    return float(np.mean(values[-window:] if len(values) >= window else values))


def _safe_std(values: list[float], window: int) -> float:
    if len(values) < 2:
        return 0.0
    slice_v = values[-window:] if len(values) >= window else values
    return float(np.std(slice_v, ddof=0))


def _safe_density(values: list[float], window: int) -> float:
    """Rolling mean over last `window` promo flags (0/1)."""
    if not values:
        return 0.0
    return float(np.mean(values[-window:] if len(values) >= window else values))


# ── Feature construction helpers ──────────────────────────────────────────────

def _resolve_promo_value(promo_mode: str, day_of_week: int) -> int:
    if promo_mode == "always_on":
        return 1
    if promo_mode == "weekends_only":
        return 1 if day_of_week in (6, 7) else 0
    return 0


def _resolve_open_value(day_of_week: int, weekend_open: bool) -> int:
    if day_of_week in (6, 7) and not weekend_open:
        return 0
    return 1


def _resolve_confidence_z(confidence_level: float) -> float:
    clamped = min(0.99, max(0.5, confidence_level))
    return float(NormalDist().inv_cdf(0.5 + clamped / 2.0))


def _build_feature_row(
    store_id: int,
    forecast_date: pd.Timestamp,
    sales_history: list[float],
    promo_history: list[float],
    store_meta: pd.Series,
    base_days_since_start: int,
    step: int,
    controls: ForecastControls,
) -> dict:
    """
    Build a single feature row for one forecast step.
    Must stay in sync with ml/features.py FEATURE_COLS.
    """
    day_of_week = int(forecast_date.dayofweek + 1)
    rolling_7 = _safe_mean(sales_history, 7)
    rolling_28 = _safe_mean(sales_history, 28)
    competition_distance = float(store_meta["competition_distance"])

    return {
        # Store identifier
        "store_id": int(store_id),
        # Demand drivers
        "promo": _resolve_promo_value(controls.promo_mode, day_of_week),
        "school_holiday": int(controls.school_holiday),
        "open": _resolve_open_value(day_of_week, controls.weekend_open),
        # Store metadata
        "competition_distance": competition_distance,
        "competition_distance_log": float(np.log1p(competition_distance)),  # NEW
        "promo2": int(store_meta["promo2"]),
        # Calendar — basic
        "day_of_week": day_of_week,
        "month": int(forecast_date.month),
        "quarter": int((forecast_date.month - 1) // 3 + 1),
        "week_of_year": int(forecast_date.isocalendar().week),
        "is_weekend": int(day_of_week in [6, 7]),
        "day_of_month": int(forecast_date.day),                             # NEW
        "is_month_start": int(forecast_date.day <= 3),                      # NEW
        "is_month_end": int(forecast_date.day >= 28),                       # NEW
        "days_since_start": int(base_days_since_start + step),
        # Lag features (expanded)
        "lag_1": _safe_lag(sales_history, 1),
        "lag_3": _safe_lag(sales_history, 3),                               # NEW
        "lag_7": _safe_lag(sales_history, 7),
        "lag_14": _safe_lag(sales_history, 14),
        "lag_21": _safe_lag(sales_history, 21),                             # NEW
        "lag_28": _safe_lag(sales_history, 28),
        "lag_364": _safe_lag(sales_history, 364) if len(sales_history) >= 364  # NEW
                   else rolling_28,  # fallback if history < 1yr
        # Rolling statistics (expanded)
        "rolling_mean_7": rolling_7,
        "rolling_mean_14": _safe_mean(sales_history, 14),
        "rolling_mean_28": rolling_28,
        "rolling_mean_56": _safe_mean(sales_history, 56),                   # NEW
        "rolling_std_7": _safe_std(sales_history, 7),
        "rolling_std_14": _safe_std(sales_history, 14),
        "rolling_std_28": _safe_std(sales_history, 28),
        "rolling_std_56": _safe_std(sales_history, 56),                     # NEW
        # Derived ratios & trends
        "lag_1_to_mean_7_ratio": (_safe_lag(sales_history, 1) / rolling_7) if rolling_7 > 0 else 1.0,
        "sales_velocity": (rolling_7 / rolling_28) if rolling_28 > 0 else 1.0,          # NEW
        "lag_364_to_mean_28_ratio": (_safe_lag(sales_history, 364) / rolling_28)         # NEW
                                    if len(sales_history) >= 364 and rolling_28 > 0
                                    else 1.0,
        # Promo density (NEW)
        "promo_density_7": _safe_density(promo_history, 7),
        "promo_density_14": _safe_density(promo_history, 14),
        # Categoricals (one-hot encoded downstream)
        "state_holiday": "0",
        "store_type": str(store_meta["store_type"]),
        "assortment": str(store_meta["assortment"]),
    }


def _prepare_model_input(row: dict, categorical_columns: list[str], feature_columns: list[str]) -> pd.DataFrame:
    x_raw = pd.DataFrame([row])
    encoded = pd.get_dummies(x_raw, columns=categorical_columns, drop_first=False)
    encoded = encoded.reindex(columns=feature_columns, fill_value=0)
    return encoded


def _inverse_target_transform(prediction: float, target_transform: str) -> float:
    if target_transform == "log1p":
        return float(np.expm1(prediction))
    return float(prediction)


def _postprocess_prediction(prediction: float, floor: float, cap: float | None) -> float:
    pred = max(prediction, floor)
    if cap is not None:
        pred = min(pred, cap)
    return float(pred)


def _horizon_sigma(base_sigma: float, step: int) -> float:
    """
    Scale prediction uncertainty with forecast horizon.
    Uses linear growth (+3% per day) capped at 90 days to avoid
    unbounded widening on long horizons.
    """
    growth = 1.0 + 0.03 * min(step - 1, 89)
    return base_sigma * growth


def _run_recursive_forecast(
    *,
    model,
    categorical_columns: list[str],
    feature_columns: list[str],
    target_transform: str,
    floor: float,
    cap: float | None,
    sigma: float,
    store_id: int,
    horizon_days: int,
    history: pd.DataFrame,
    store_meta: pd.Series,
    controls: ForecastControls,
) -> list[dict]:
    sales_history: list[float] = history["sales"].astype(float).tolist()
    promo_history: list[float] = (
        history["promo"].astype(float).tolist()
        if "promo" in history.columns
        else [0.0] * len(sales_history)
    )
    last_date = history["full_date"].max()
    base_days_since_start = len(sales_history) - 1
    z_score = _resolve_confidence_z(controls.confidence_level)

    output: list[dict] = []
    for step in range(1, horizon_days + 1):
        forecast_date = last_date + pd.Timedelta(days=step)
        day_of_week = int(forecast_date.dayofweek + 1)
        promo_value = _resolve_promo_value(controls.promo_mode, day_of_week)

        row = _build_feature_row(
            store_id=store_id,
            forecast_date=forecast_date,
            sales_history=sales_history,
            promo_history=promo_history,
            store_meta=store_meta,
            base_days_since_start=base_days_since_start,
            step=step,
            controls=controls,
        )
        x = _prepare_model_input(row, categorical_columns, feature_columns)

        pred_model = float(model.predict(x)[0])
        pred = _inverse_target_transform(pred_model, target_transform)
        pred = pred * (1.0 + controls.demand_shift_pct / 100.0)
        pred = _postprocess_prediction(pred, floor, cap)

        # Horizon-dependent uncertainty — bands widen with forecast distance
        step_sigma = _horizon_sigma(sigma, step)
        lower = _postprocess_prediction(pred - z_score * step_sigma, floor, cap)
        upper = _postprocess_prediction(pred + z_score * step_sigma, floor, cap)

        sales_history.append(pred)
        promo_history.append(float(promo_value))  # track future promo for promo_density

        output.append(
            {
                "date": forecast_date.date(),
                "predicted_sales": pred,
                "predicted_lower": lower,
                "predicted_upper": upper,
            }
        )

    return output


def _load_artifact() -> dict:
    model_path = _resolve_model_path()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    current_mtime = model_path.stat().st_mtime
    if (
        _ARTIFACT_CACHE["payload"] is not None
        and _ARTIFACT_CACHE["path"] == model_path
        and _ARTIFACT_CACHE["mtime"] == current_mtime
    ):
        return _ARTIFACT_CACHE["payload"]  # type: ignore[return-value]

    payload = joblib.load(model_path)
    _ARTIFACT_CACHE["path"] = model_path
    _ARTIFACT_CACHE["mtime"] = current_mtime
    _ARTIFACT_CACHE["payload"] = payload
    return payload


class _EnsembleWrapper:
    """Averages predictions from a dict of {name: model} sub-models."""
    def __init__(self, models: dict) -> None:
        self._models = models

    def predict(self, x: Any) -> np.ndarray:
        preds = [np.asarray(m.predict(x), dtype=float) for m in self._models.values()]
        return np.mean(preds, axis=0)


def _extract_artifact_parts(artifact: dict) -> tuple:
    raw_model = artifact["model"]
    # Ensemble artifacts store a dict of sub-models
    model = _EnsembleWrapper(raw_model) if isinstance(raw_model, dict) else raw_model
    categorical_columns = artifact["categorical_columns"]
    feature_columns = artifact["feature_columns"]
    target_transform = str(artifact.get("target_transform", "none"))
    floor = float(artifact.get("prediction_floor", 0.0))
    cap = float(artifact["prediction_cap"]) if artifact.get("prediction_cap") is not None else None
    sigma = float(artifact.get("prediction_interval_sigma", 0.0))
    return model, categorical_columns, feature_columns, target_transform, floor, cap, sigma


def _new_run_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"


def _record_forecast_run(
    *,
    run_id: str,
    run_type: str,
    status: str,
    data_source_id: int,
    store_id: int | None,
    request_json: dict[str, Any],
    summary_json: dict[str, Any] | None = None,
    error_message: str | None = None,
    created_at: datetime,
) -> None:
    upsert_forecast_run(
        {
            "run_id": run_id,
            "created_at": created_at,
            "run_type": run_type,
            "status": status,
            "data_source_id": data_source_id,
            "store_id": store_id,
            "request_json": request_json,
            "summary_json": summary_json or {},
            "error_message": error_message,
        }
    )


def _forecast_cache_get(key: tuple) -> list[dict] | None:
    """Return cached forecast if within TTL, else None. Moves hit to MRU position."""
    entry = _FORECAST_CACHE.get(key)
    if entry is None:
        return None
    cached_at, result = entry
    age = (datetime.now(timezone.utc) - cached_at).total_seconds()
    if age > _FORECAST_CACHE_TTL_SECONDS:
        _FORECAST_CACHE.pop(key, None)
        return None
    _FORECAST_CACHE.move_to_end(key)
    return result


def _forecast_cache_set(key: tuple, result: list[dict]) -> None:
    """Insert or refresh entry; evict LRU entries beyond 500-item cap."""
    if key in _FORECAST_CACHE:
        _FORECAST_CACHE.move_to_end(key)
    _FORECAST_CACHE[key] = (datetime.now(timezone.utc), result)
    while len(_FORECAST_CACHE) > 500:
        _FORECAST_CACHE.popitem(last=False)  # evict least-recently-used


# ── Public service functions ──────────────────────────────────────────────────

def forecast_for_store(
    store_id: int,
    horizon_days: int,
    data_source_id: int | None = None,
    *,
    _record_run: bool = True,
) -> list[dict]:
    if store_id <= 0:
        raise ValueError("store_id must be positive")
    _validate_horizon(horizon_days)

    resolved_data_source_id = resolve_data_source_id(data_source_id)
    run_id = _new_run_id("forecast") if _record_run else None
    started_at = datetime.now(timezone.utc)
    request_json = {
        "store_id": int(store_id),
        "horizon_days": int(horizon_days),
        "data_source_id": resolved_data_source_id,
    }
    if _record_run and run_id is not None:
        _record_forecast_run(
            run_id=run_id,
            run_type="forecast",
            status="RUNNING",
            data_source_id=resolved_data_source_id,
            store_id=store_id,
            request_json=request_json,
            created_at=started_at,
        )

    try:
        artifact = _load_artifact()
        model, categorical_columns, feature_columns, target_transform, floor, cap, sigma = _extract_artifact_parts(artifact)

        # Check short-lived cache (avoids repeated DB + recursive computation)
        cache_key = (store_id, horizon_days, started_at.date().isoformat())
        cached = _forecast_cache_get(cache_key)

        if cached is not None:
            result = cached
        else:
            history = _fetch_history(engine, store_id=store_id, history_days=400)
            store_meta = _fetch_store_meta(engine, store_id=store_id)
            result = _run_recursive_forecast(
                model=model,
                categorical_columns=categorical_columns,
                feature_columns=feature_columns,
                target_transform=target_transform,
                floor=floor,
                cap=cap,
                sigma=sigma,
                store_id=store_id,
                horizon_days=horizon_days,
                history=history,
                store_meta=store_meta,
                controls=ForecastControls(),
            )
            _forecast_cache_set(cache_key, result)

        if _record_run and run_id is not None:
            _record_forecast_run(
                run_id=run_id,
                run_type="forecast",
                status="COMPLETED",
                data_source_id=resolved_data_source_id,
                store_id=store_id,
                request_json=request_json,
                summary_json={
                    "points_count": len(result),
                    "total_predicted_sales": float(sum(float(row["predicted_sales"]) for row in result)),
                },
                created_at=started_at,
            )
        return result
    except Exception as exc:
        if _record_run and run_id is not None:
            _record_forecast_run(
                run_id=run_id,
                run_type="forecast",
                status="FAILED",
                data_source_id=resolved_data_source_id,
                store_id=store_id,
                request_json=request_json,
                summary_json={},
                error_message=str(exc),
                created_at=started_at,
            )
        raise


def _summarize_store_series(store_id: int, points: list[dict]) -> dict:
    total = float(sum(float(item["predicted_sales"]) for item in points))
    avg = float(total / len(points)) if points else 0.0
    peak_point = max(points, key=lambda item: float(item["predicted_sales"])) if points else None
    interval_widths = [
        float(item["predicted_upper"]) - float(item["predicted_lower"])
        for item in points
        if item.get("predicted_upper") is not None and item.get("predicted_lower") is not None
    ]
    return {
        "store_id": store_id,
        "total_predicted_sales": total,
        "avg_daily_sales": avg,
        "peak_date": peak_point["date"] if peak_point else None,
        "peak_sales": float(peak_point["predicted_sales"]) if peak_point else 0.0,
        "avg_interval_width": float(np.mean(interval_widths)) if interval_widths else 0.0,
    }


def forecast_batch_for_stores(
    store_ids: list[int],
    horizon_days: int,
    data_source_id: int | None = None,
) -> dict:
    normalized_store_ids = _validate_store_ids(store_ids)
    _validate_horizon(horizon_days)

    resolved_data_source_id = resolve_data_source_id(data_source_id)
    run_id = _new_run_id("forecast_batch")
    started_at = datetime.now(timezone.utc)
    request_json = {
        "store_ids": normalized_store_ids,
        "horizon_days": int(horizon_days),
        "data_source_id": resolved_data_source_id,
    }
    _record_forecast_run(
        run_id=run_id,
        run_type="batch",
        status="RUNNING",
        data_source_id=resolved_data_source_id,
        store_id=None,
        request_json=request_json,
        created_at=started_at,
    )

    try:
        store_series: dict[int, list[dict]] = {}
        for store_id in normalized_store_ids:
            store_series[store_id] = forecast_for_store(
                store_id=store_id,
                horizon_days=horizon_days,
                data_source_id=resolved_data_source_id,
                _record_run=False,
            )

        store_summaries = [_summarize_store_series(sid, pts) for sid, pts in store_series.items()]

        portfolio_series: list[dict] = []
        for index in range(horizon_days):
            date_value = next(iter(store_series.values()))[index]["date"]
            portfolio_series.append(
                {
                    "date": date_value,
                    "predicted_sales": float(sum(pts[index]["predicted_sales"] for pts in store_series.values())),
                    "predicted_lower": float(sum(pts[index]["predicted_lower"] for pts in store_series.values())),
                    "predicted_upper": float(sum(pts[index]["predicted_upper"] for pts in store_series.values())),
                }
            )

        portfolio_total = float(sum(row["predicted_sales"] for row in portfolio_series))
        portfolio_avg_daily = float(portfolio_total / horizon_days) if horizon_days > 0 else 0.0
        portfolio_peak = max(portfolio_series, key=lambda r: r["predicted_sales"]) if portfolio_series else None
        interval_widths = [
            row["predicted_upper"] - row["predicted_lower"]
            for row in portfolio_series
            if row.get("predicted_upper") is not None and row.get("predicted_lower") is not None
        ]

        response = {
            "request": request_json,
            "store_summaries": store_summaries,
            "portfolio_summary": {
                "stores_count": len(normalized_store_ids),
                "horizon_days": horizon_days,
                "total_predicted_sales": portfolio_total,
                "avg_daily_sales": portfolio_avg_daily,
                "peak_date": portfolio_peak["date"] if portfolio_peak else None,
                "peak_sales": float(portfolio_peak["predicted_sales"]) if portfolio_peak else 0.0,
                "avg_interval_width": float(np.mean(interval_widths)) if interval_widths else 0.0,
            },
            "portfolio_series": portfolio_series,
        }

        _record_forecast_run(
            run_id=run_id,
            run_type="batch",
            status="COMPLETED",
            data_source_id=resolved_data_source_id,
            store_id=None,
            request_json=request_json,
            summary_json={
                "stores_count": len(normalized_store_ids),
                "total_predicted_sales": portfolio_total,
                "avg_daily_sales": portfolio_avg_daily,
            },
            created_at=started_at,
        )
        return response
    except Exception as exc:
        _record_forecast_run(
            run_id=run_id,
            run_type="batch",
            status="FAILED",
            data_source_id=resolved_data_source_id,
            store_id=None,
            request_json=request_json,
            summary_json={},
            error_message=str(exc),
            created_at=started_at,
        )
        raise


def forecast_scenario_for_store(
    *,
    store_id: int,
    horizon_days: int,
    promo_mode: str,
    weekend_open: bool,
    school_holiday: int,
    demand_shift_pct: float,
    confidence_level: float,
    data_source_id: int | None = None,
    _record_run: bool = True,
) -> dict:
    if store_id <= 0:
        raise ValueError("store_id must be positive")
    _validate_horizon(horizon_days)
    resolved_data_source_id = resolve_data_source_id(data_source_id)
    run_id = _new_run_id("forecast_scenario") if _record_run else None
    started_at = datetime.now(timezone.utc)
    request_json = {
        "store_id": int(store_id),
        "horizon_days": int(horizon_days),
        "promo_mode": str(promo_mode),
        "weekend_open": bool(weekend_open),
        "school_holiday": int(school_holiday),
        "demand_shift_pct": float(demand_shift_pct),
        "confidence_level": float(confidence_level),
        "data_source_id": resolved_data_source_id,
    }
    if _record_run and run_id is not None:
        _record_forecast_run(
            run_id=run_id,
            run_type="scenario",
            status="RUNNING",
            data_source_id=resolved_data_source_id,
            store_id=store_id,
            request_json=request_json,
            created_at=started_at,
        )

    try:
        artifact = _load_artifact()
        model, categorical_columns, feature_columns, target_transform, floor, cap, sigma = _extract_artifact_parts(artifact)

        history = _fetch_history(engine, store_id=store_id, history_days=400)
        store_meta = _fetch_store_meta(engine, store_id=store_id)

        baseline = _run_recursive_forecast(
            model=model,
            categorical_columns=categorical_columns,
            feature_columns=feature_columns,
            target_transform=target_transform,
            floor=floor,
            cap=cap,
            sigma=sigma,
            store_id=store_id,
            horizon_days=horizon_days,
            history=history,
            store_meta=store_meta,
            controls=ForecastControls(confidence_level=confidence_level),
        )

        scenario_controls = ForecastControls(
            promo_mode=promo_mode,
            weekend_open=weekend_open,
            school_holiday=school_holiday,
            demand_shift_pct=demand_shift_pct,
            confidence_level=confidence_level,
        )
        scenario = _run_recursive_forecast(
            model=model,
            categorical_columns=categorical_columns,
            feature_columns=feature_columns,
            target_transform=target_transform,
            floor=floor,
            cap=cap,
            sigma=sigma,
            store_id=store_id,
            horizon_days=horizon_days,
            history=history,
            store_meta=store_meta,
            controls=scenario_controls,
        )

        points: list[dict] = []
        for baseline_row, scenario_row in zip(baseline, scenario, strict=True):
            delta = float(scenario_row["predicted_sales"] - baseline_row["predicted_sales"])
            points.append(
                {
                    "date": baseline_row["date"],
                    "baseline_sales": float(baseline_row["predicted_sales"]),
                    "scenario_sales": float(scenario_row["predicted_sales"]),
                    "delta_sales": delta,
                    "scenario_lower": float(scenario_row["predicted_lower"]),
                    "scenario_upper": float(scenario_row["predicted_upper"]),
                }
            )

        total_baseline = float(sum(r["baseline_sales"] for r in points))
        total_scenario = float(sum(r["scenario_sales"] for r in points))
        total_delta = float(total_scenario - total_baseline)
        uplift_pct = float((total_delta / total_baseline) * 100.0) if total_baseline > 0 else 0.0
        avg_daily_delta = float(total_delta / horizon_days) if horizon_days > 0 else 0.0
        max_delta_point = max(points, key=lambda r: r["delta_sales"]) if points else None

        response = {
            "request": {
                "store_id": store_id,
                "horizon_days": horizon_days,
                "promo_mode": promo_mode,
                "weekend_open": weekend_open,
                "school_holiday": school_holiday,
                "demand_shift_pct": demand_shift_pct,
                "confidence_level": confidence_level,
                "data_source_id": resolved_data_source_id,
            },
            "summary": {
                "total_baseline_sales": total_baseline,
                "total_scenario_sales": total_scenario,
                "total_delta_sales": total_delta,
                "uplift_pct": uplift_pct,
                "avg_daily_delta": avg_daily_delta,
                "max_delta_date": max_delta_point["date"] if max_delta_point else None,
                "max_delta_value": float(max_delta_point["delta_sales"]) if max_delta_point else 0.0,
            },
            "points": points,
        }

        if _record_run and run_id is not None:
            _record_forecast_run(
                run_id=run_id,
                run_type="scenario",
                status="COMPLETED",
                data_source_id=resolved_data_source_id,
                store_id=store_id,
                request_json=request_json,
                summary_json={
                    "points_count": len(points),
                    "uplift_pct": uplift_pct,
                    "total_delta_sales": total_delta,
                },
                created_at=started_at,
            )
        return response
    except Exception as exc:
        if _record_run and run_id is not None:
            _record_forecast_run(
                run_id=run_id,
                run_type="scenario",
                status="FAILED",
                data_source_id=resolved_data_source_id,
                store_id=store_id,
                request_json=request_json,
                summary_json={},
                error_message=str(exc),
                created_at=started_at,
            )
        raise
