from __future__ import annotations

import argparse
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa
import yaml
from dotenv import load_dotenv

from features import encode_features


def load_config(config_path: str) -> tuple[dict, Path]:
    cfg_path = Path(config_path).resolve()
    with open(cfg_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file), cfg_path


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def load_artifact(model_path: Path) -> dict:
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found: {model_path}")
    return joblib.load(model_path)


def fetch_history(engine: sa.Engine, store_id: int, history_days: int = 90) -> pd.DataFrame:
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
        raise ValueError(f"No history found for store_id={store_id}")
    df["full_date"] = pd.to_datetime(df["full_date"])
    return df.sort_values("full_date").reset_index(drop=True)


def fetch_store_meta(engine: sa.Engine, store_id: int) -> pd.Series:
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
        raise ValueError(f"store_id={store_id} does not exist in dim_store")
    return df.iloc[0]


def safe_lag(values: list[float], offset: int) -> float:
    if len(values) >= offset:
        return float(values[-offset])
    return float(values[-1])


def safe_mean(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    window_slice = values[-window:] if len(values) >= window else values
    return float(np.mean(window_slice))


def safe_std(values: list[float], window: int) -> float:
    if len(values) < 2:
        return 0.0
    window_slice = values[-window:] if len(values) >= window else values
    return float(np.std(window_slice, ddof=0))


def inverse_target_transform(prediction: float, target_transform: str) -> float:
    if target_transform == "log1p":
        return float(np.expm1(prediction))
    return float(prediction)


def postprocess_prediction(prediction: float, floor: float, cap: float | None) -> float:
    pred = max(prediction, floor)
    if cap is not None:
        pred = min(pred, cap)
    return float(pred)


def build_feature_row(
    store_id: int,
    forecast_date: pd.Timestamp,
    sales_history: list[float],
    store_meta: pd.Series,
    base_days_since_start: int,
    step: int,
) -> dict:
    rolling_7 = safe_mean(sales_history, 7)

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
        "lag_1": safe_lag(sales_history, 1),
        "lag_7": safe_lag(sales_history, 7),
        "lag_14": safe_lag(sales_history, 14),
        "lag_28": safe_lag(sales_history, 28),
        "rolling_mean_7": rolling_7,
        "rolling_mean_14": safe_mean(sales_history, 14),
        "rolling_mean_28": safe_mean(sales_history, 28),
        "rolling_std_7": safe_std(sales_history, 7),
        "rolling_std_14": safe_std(sales_history, 14),
        "rolling_std_28": safe_std(sales_history, 28),
        "lag_1_to_mean_7_ratio": safe_lag(sales_history, 1) / rolling_7 if rolling_7 > 0 else 1.0,
        "state_holiday": "0",
        "store_type": str(store_meta["store_type"]),
        "assortment": str(store_meta["assortment"]),
    }


def forecast_store(
    engine: sa.Engine,
    artifact: dict,
    store_id: int,
    horizon_days: int,
    history_days: int = 90,
) -> list[dict]:
    history = fetch_history(engine, store_id=store_id, history_days=history_days)
    store_meta = fetch_store_meta(engine, store_id=store_id)

    model = artifact["model"]
    categorical_columns = artifact["categorical_columns"]
    feature_columns = artifact["feature_columns"]
    target_transform = str(artifact.get("target_transform", "none"))
    floor = float(artifact.get("prediction_floor", 0.0))
    cap = float(artifact["prediction_cap"]) if artifact.get("prediction_cap") is not None else None
    sigma = float(artifact.get("prediction_interval_sigma", 0.0))
    z_score = 1.28

    sales_history = history["sales"].astype(float).tolist()
    last_date = history["full_date"].max()
    base_days_since_start = len(sales_history) - 1

    predictions: list[dict] = []
    for step in range(1, horizon_days + 1):
        forecast_date = last_date + pd.Timedelta(days=step)
        feature_row = build_feature_row(
            store_id=store_id,
            forecast_date=forecast_date,
            sales_history=sales_history,
            store_meta=store_meta,
            base_days_since_start=base_days_since_start,
            step=step,
        )

        x_raw = pd.DataFrame([feature_row])
        x, _ = encode_features(x_raw, categorical_columns, feature_columns=feature_columns)

        pred_model = float(model.predict(x)[0])
        pred = inverse_target_transform(pred_model, target_transform)
        pred = postprocess_prediction(pred, floor, cap)

        lower = postprocess_prediction(pred - z_score * sigma, floor, cap)
        upper = postprocess_prediction(pred + z_score * sigma, floor, cap)

        sales_history.append(pred)
        predictions.append(
            {
                "date": forecast_date.date().isoformat(),
                "predicted_sales": pred,
                "predicted_lower": lower,
                "predicted_upper": upper,
            }
        )

    return predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Forecast sales for a store")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--store-id", type=int, required=True, help="Store ID")
    parser.add_argument("--horizon-days", type=int, default=30, help="Forecast horizon")
    args = parser.parse_args()

    cfg, cfg_path = load_config(args.config)
    project_root = cfg_path.parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)

    db_url = os.getenv(cfg["database"]["url_env"])
    if not db_url:
        raise ValueError("DATABASE_URL not found")

    model_path = resolve_path(cfg_path.parent, cfg["training"].get("model_path", "artifacts/model.joblib"))
    artifact = load_artifact(model_path)

    engine = sa.create_engine(db_url)
    result = forecast_store(
        engine=engine,
        artifact=artifact,
        store_id=args.store_id,
        horizon_days=args.horizon_days,
        history_days=int(cfg["forecast"].get("history_days", 90)),
    )

    for row in result:
        print(row)


if __name__ == "__main__":
    main()
