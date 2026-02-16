from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa

from app.config import get_settings

settings = get_settings()


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


def _fetch_history(engine: sa.Engine, store_id: int, history_days: int = 90) -> pd.DataFrame:
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
    df = pd.read_sql(query, engine, params={"store_id": store_id, "history_days": history_days})
    if df.empty:
        raise ValueError(f"No data found for store_id={store_id}")
    df["full_date"] = pd.to_datetime(df["full_date"])
    return df.sort_values("full_date").reset_index(drop=True)


def _fetch_store_meta(engine: sa.Engine, store_id: int) -> pd.Series:
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
    df = pd.read_sql(query, engine, params={"store_id": store_id})
    if df.empty:
        raise ValueError(f"store_id={store_id} not found in dim_store")
    return df.iloc[0]


def _safe_lag(values: list[float], offset: int) -> float:
    if len(values) >= offset:
        return float(values[-offset])
    return float(values[-1])


def _safe_mean(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    slice_values = values[-window:] if len(values) >= window else values
    return float(np.mean(slice_values))


def _safe_std(values: list[float], window: int) -> float:
    if len(values) < 2:
        return 0.0
    slice_values = values[-window:] if len(values) >= window else values
    return float(np.std(slice_values, ddof=0))


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
    store_meta: pd.Series,
    base_days_since_start: int,
    step: int,
    controls: ForecastControls,
) -> dict:
    rolling_7 = _safe_mean(sales_history, 7)
    day_of_week = int(forecast_date.dayofweek + 1)

    return {
        "store_id": int(store_id),
        "promo": _resolve_promo_value(controls.promo_mode, day_of_week),
        "school_holiday": int(controls.school_holiday),
        "open": _resolve_open_value(day_of_week, controls.weekend_open),
        "competition_distance": float(store_meta["competition_distance"]),
        "promo2": int(store_meta["promo2"]),
        "day_of_week": day_of_week,
        "month": int(forecast_date.month),
        "quarter": int((forecast_date.month - 1) // 3 + 1),
        "week_of_year": int(forecast_date.isocalendar().week),
        "is_weekend": int(day_of_week in [6, 7]),
        "days_since_start": int(base_days_since_start + step),
        "lag_1": _safe_lag(sales_history, 1),
        "lag_7": _safe_lag(sales_history, 7),
        "lag_14": _safe_lag(sales_history, 14),
        "lag_28": _safe_lag(sales_history, 28),
        "rolling_mean_7": rolling_7,
        "rolling_mean_14": _safe_mean(sales_history, 14),
        "rolling_mean_28": _safe_mean(sales_history, 28),
        "rolling_std_7": _safe_std(sales_history, 7),
        "rolling_std_14": _safe_std(sales_history, 14),
        "rolling_std_28": _safe_std(sales_history, 28),
        "lag_1_to_mean_7_ratio": _safe_lag(sales_history, 1) / rolling_7 if rolling_7 > 0 else 1.0,
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
    sales_history = history["sales"].astype(float).tolist()
    last_date = history["full_date"].max()
    base_days_since_start = len(sales_history) - 1
    z_score = _resolve_confidence_z(controls.confidence_level)

    output: list[dict] = []
    for step in range(1, horizon_days + 1):
        forecast_date = last_date + pd.Timedelta(days=step)
        row = _build_feature_row(
            store_id=store_id,
            forecast_date=forecast_date,
            sales_history=sales_history,
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

        lower = _postprocess_prediction(pred - z_score * sigma, floor, cap)
        upper = _postprocess_prediction(pred + z_score * sigma, floor, cap)

        sales_history.append(pred)
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
    return joblib.load(model_path)


def forecast_for_store(store_id: int, horizon_days: int) -> list[dict]:
    artifact = _load_artifact()
    model = artifact["model"]
    categorical_columns = artifact["categorical_columns"]
    feature_columns = artifact["feature_columns"]
    target_transform = str(artifact.get("target_transform", "none"))
    floor = float(artifact.get("prediction_floor", 0.0))
    cap = float(artifact["prediction_cap"]) if artifact.get("prediction_cap") is not None else None
    sigma = float(artifact.get("prediction_interval_sigma", 0.0))

    engine = sa.create_engine(settings.database_url)
    history = _fetch_history(engine, store_id=store_id, history_days=90)
    store_meta = _fetch_store_meta(engine, store_id=store_id)

    baseline_controls = ForecastControls()
    return _run_recursive_forecast(
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
        controls=baseline_controls,
    )


def forecast_scenario_for_store(
    *,
    store_id: int,
    horizon_days: int,
    promo_mode: str,
    weekend_open: bool,
    school_holiday: int,
    demand_shift_pct: float,
    confidence_level: float,
) -> dict:
    artifact = _load_artifact()
    model = artifact["model"]
    categorical_columns = artifact["categorical_columns"]
    feature_columns = artifact["feature_columns"]
    target_transform = str(artifact.get("target_transform", "none"))
    floor = float(artifact.get("prediction_floor", 0.0))
    cap = float(artifact["prediction_cap"]) if artifact.get("prediction_cap") is not None else None
    sigma = float(artifact.get("prediction_interval_sigma", 0.0))

    engine = sa.create_engine(settings.database_url)
    history = _fetch_history(engine, store_id=store_id, history_days=90)
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

    total_baseline = float(sum(row["baseline_sales"] for row in points))
    total_scenario = float(sum(row["scenario_sales"] for row in points))
    total_delta = float(total_scenario - total_baseline)
    uplift_pct = float((total_delta / total_baseline) * 100.0) if total_baseline > 0 else 0.0
    avg_daily_delta = float(total_delta / horizon_days) if horizon_days > 0 else 0.0

    max_delta_point = max(points, key=lambda row: row["delta_sales"]) if points else None

    return {
        "request": {
            "store_id": store_id,
            "horizon_days": horizon_days,
            "promo_mode": promo_mode,
            "weekend_open": weekend_open,
            "school_holiday": school_holiday,
            "demand_shift_pct": demand_shift_pct,
            "confidence_level": confidence_level,
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
