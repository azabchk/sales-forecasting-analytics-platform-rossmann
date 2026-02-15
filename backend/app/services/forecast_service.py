from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa

from app.config import get_settings

settings = get_settings()


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


def _build_feature_row(
    store_id: int,
    forecast_date: pd.Timestamp,
    sales_history: list[float],
    store_meta: pd.Series,
    base_days_since_start: int,
    step: int,
) -> dict:
    rolling_7 = _safe_mean(sales_history, 7)

    return {
        "store_id": int(store_id),
        "promo": 0,
        "school_holiday": 0,
        "open": 1,
        "competition_distance": float(store_meta["competition_distance"]),
        "promo2": int(store_meta["promo2"]),
        "day_of_week": int(forecast_date.dayofweek + 1),
        "month": int(forecast_date.month),
        "quarter": int((forecast_date.month - 1) // 3 + 1),
        "week_of_year": int(forecast_date.isocalendar().week),
        "is_weekend": int((forecast_date.dayofweek + 1) in [6, 7]),
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


def forecast_for_store(store_id: int, horizon_days: int) -> list[dict]:
    model_path = _resolve_model_path()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    artifact = joblib.load(model_path)
    model = artifact["model"]
    categorical_columns = artifact["categorical_columns"]
    feature_columns = artifact["feature_columns"]
    target_transform = str(artifact.get("target_transform", "none"))
    floor = float(artifact.get("prediction_floor", 0.0))
    cap = float(artifact["prediction_cap"]) if artifact.get("prediction_cap") is not None else None
    sigma = float(artifact.get("prediction_interval_sigma", 0.0))
    z_score = 1.28

    engine = sa.create_engine(settings.database_url)
    history = _fetch_history(engine, store_id=store_id, history_days=90)
    store_meta = _fetch_store_meta(engine, store_id=store_id)

    sales_history = history["sales"].astype(float).tolist()
    last_date = history["full_date"].max()
    base_days_since_start = len(sales_history) - 1

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
        )
        x = _prepare_model_input(row, categorical_columns, feature_columns)

        pred_model = float(model.predict(x)[0])
        pred = _inverse_target_transform(pred_model, target_transform)
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
