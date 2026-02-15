from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa
import yaml
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from features import build_training_frame, encode_features


def load_config(config_path: str) -> tuple[dict, Path]:
    cfg_path = Path(config_path).resolve()
    with open(cfg_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file), cfg_path


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def load_training_data(engine: sa.Engine) -> pd.DataFrame:
    query = """
    SELECT
        f.store_id,
        d.full_date,
        f.sales,
        COALESCE(f.promo, 0) AS promo,
        COALESCE(f.school_holiday, 0) AS school_holiday,
        COALESCE(f.open, 1) AS open,
        COALESCE(f.state_holiday, '0') AS state_holiday,
        s.store_type,
        s.assortment,
        COALESCE(s.competition_distance, 0) AS competition_distance,
        COALESCE(s.promo2, 0) AS promo2
    FROM fact_sales_daily f
    JOIN dim_date d ON d.date_id = f.date_id
    JOIN dim_store s ON s.store_id = f.store_id
    ORDER BY f.store_id, d.full_date;
    """
    df = pd.read_sql(query, engine)
    df["full_date"] = pd.to_datetime(df["full_date"])
    return df


def time_split(df: pd.DataFrame, validation_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_date = df["full_date"].max()
    cutoff = max_date - pd.Timedelta(days=validation_days)
    train_df = df[df["full_date"] <= cutoff].copy()
    val_df = df[df["full_date"] > cutoff].copy()
    return train_df, val_df


def evaluate_model(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(root_mean_squared_error(y_true, y_pred)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train sales forecasting model")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()

    cfg, cfg_path = load_config(args.config)
    project_root = cfg_path.parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)

    db_url = os.getenv(cfg["database"]["url_env"])
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")

    engine = sa.create_engine(db_url)
    raw_df = load_training_data(engine)

    framed = build_training_frame(raw_df)
    validation_days = int(cfg["training"].get("validation_days", 60))

    train_df, val_df = time_split(framed, validation_days=validation_days)
    if train_df.empty or val_df.empty:
        raise ValueError("Недостаточно данных для time-based split")

    feature_cols = [
        "store_id",
        "promo",
        "school_holiday",
        "open",
        "competition_distance",
        "promo2",
        "day_of_week",
        "month",
        "quarter",
        "week_of_year",
        "is_weekend",
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_28",
        "state_holiday",
        "store_type",
        "assortment",
    ]

    categorical_cols = ["state_holiday", "store_type", "assortment"]

    x_train_raw = train_df[feature_cols].copy()
    y_train = train_df["sales"].astype(float)

    x_val_raw = val_df[feature_cols].copy()
    y_val = val_df["sales"].astype(float)

    x_train, model_feature_columns = encode_features(x_train_raw, categorical_cols)
    x_val, _ = encode_features(x_val_raw, categorical_cols, feature_columns=model_feature_columns)

    ridge = Ridge(random_state=int(cfg["training"].get("random_state", 42)))
    ridge.fit(x_train, y_train)
    ridge_pred = ridge.predict(x_val)
    ridge_metrics = evaluate_model(y_val, ridge_pred)

    catboost = CatBoostRegressor(
        iterations=400,
        depth=8,
        learning_rate=0.05,
        loss_function="RMSE",
        random_seed=int(cfg["training"].get("random_state", 42)),
        verbose=False,
    )
    catboost.fit(x_train, y_train)
    catboost_pred = catboost.predict(x_val)
    catboost_metrics = evaluate_model(y_val, catboost_pred)

    candidates = {
        "ridge": (ridge, ridge_metrics),
        "catboost": (catboost, catboost_metrics),
    }
    best_model_name = min(candidates.keys(), key=lambda name: candidates[name][1]["rmse"])
    best_model, best_metrics = candidates[best_model_name]

    model_path = resolve_path(cfg_path.parent, cfg["training"].get("model_path", "artifacts/model.joblib"))
    metadata_path = resolve_path(cfg_path.parent, cfg["training"].get("metadata_path", "artifacts/model_metadata.json"))
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model": best_model,
        "model_name": best_model_name,
        "feature_columns": model_feature_columns,
        "categorical_columns": categorical_cols,
        "raw_feature_columns": feature_cols,
        "trained_at": datetime.utcnow().isoformat() + "Z",
    }
    joblib.dump(artifact, model_path)

    metadata = {
        "selected_model": best_model_name,
        "metrics": {
            "ridge": ridge_metrics,
            "catboost": catboost_metrics,
            "best": best_metrics,
        },
        "train_period": {
            "date_from": train_df["full_date"].min().date().isoformat(),
            "date_to": train_df["full_date"].max().date().isoformat(),
        },
        "validation_period": {
            "date_from": val_df["full_date"].min().date().isoformat(),
            "date_to": val_df["full_date"].max().date().isoformat(),
        },
        "feature_columns": model_feature_columns,
        "raw_feature_columns": feature_cols,
        "rows": {
            "train": int(len(train_df)),
            "validation": int(len(val_df)),
        },
    }

    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)

    print("[ML] Training completed")
    print(f"[ML] Best model: {best_model_name}")
    print(f"[ML] Best metrics: MAE={best_metrics['mae']:.2f}, RMSE={best_metrics['rmse']:.2f}")
    print(f"[ML] Model saved to: {model_path}")
    print(f"[ML] Metadata saved to: {metadata_path}")


if __name__ == "__main__":
    main()
