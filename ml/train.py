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
    eps = 1e-8
    y_true_np = y_true.to_numpy(dtype=float)
    y_pred_np = np.asarray(y_pred, dtype=float)
    abs_error = np.abs(y_true_np - y_pred_np)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = root_mean_squared_error(y_true, y_pred)
    mape = np.mean(abs_error / np.maximum(np.abs(y_true_np), 1.0)) * 100
    wape = np.sum(abs_error) / np.maximum(np.sum(np.abs(y_true_np)), eps) * 100

    nonzero_mask = np.abs(y_true_np) > 1.0
    if nonzero_mask.any():
        mape_nonzero = np.mean(abs_error[nonzero_mask] / np.maximum(np.abs(y_true_np[nonzero_mask]), eps)) * 100
    else:
        mape_nonzero = None

    smape = np.mean((2.0 * abs_error) / np.maximum(np.abs(y_true_np) + np.abs(y_pred_np), eps)) * 100

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "mape": float(mape),
        "mape_nonzero": float(mape_nonzero) if mape_nonzero is not None else None,
        "smape": float(smape),
        "wape": float(wape),
    }


def inverse_target_transform(predictions: np.ndarray, target_transform: str) -> np.ndarray:
    if target_transform == "log1p":
        return np.expm1(predictions)
    return predictions


def postprocess_predictions(predictions: np.ndarray, floor: float, cap: float | None) -> np.ndarray:
    clipped = np.maximum(predictions, floor)
    if cap is not None:
        clipped = np.minimum(clipped, cap)
    return clipped


def get_catboost_param_grid(cfg: dict) -> list[dict]:
    default_grid = [
        {"depth": 8, "learning_rate": 0.05, "l2_leaf_reg": 3.0, "iterations": 500},
        {"depth": 10, "learning_rate": 0.03, "l2_leaf_reg": 5.0, "iterations": 700},
        {"depth": 6, "learning_rate": 0.07, "l2_leaf_reg": 2.0, "iterations": 450},
    ]
    raw = cfg.get("training", {}).get("catboost_param_grid")
    if not raw:
        return default_grid
    if not isinstance(raw, list):
        return default_grid

    normalized: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            normalized.append(item)

    return normalized or default_grid


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
    target_transform = str(cfg["training"].get("target_transform", "log1p"))
    prediction_floor = float(cfg["training"].get("prediction_floor", 0.0))
    prediction_cap_quantile = float(cfg["training"].get("prediction_cap_quantile", 0.997))
    early_stopping_rounds = int(cfg["training"].get("early_stopping_rounds", 60))

    train_df, val_df = time_split(framed, validation_days=validation_days)
    if train_df.empty or val_df.empty:
        raise ValueError("Insufficient data for time-based split")

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
        "days_since_start",
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_28",
        "rolling_std_7",
        "rolling_std_14",
        "rolling_std_28",
        "lag_1_to_mean_7_ratio",
        "state_holiday",
        "store_type",
        "assortment",
    ]

    categorical_cols = ["state_holiday", "store_type", "assortment"]

    x_train_raw = train_df[feature_cols].copy()
    y_train_raw = train_df["sales"].astype(float)
    y_train_model = np.log1p(y_train_raw) if target_transform == "log1p" else y_train_raw

    x_val_raw = val_df[feature_cols].copy()
    y_val_raw = val_df["sales"].astype(float)
    y_val_model = np.log1p(y_val_raw) if target_transform == "log1p" else y_val_raw

    prediction_cap = float(np.quantile(train_df["sales"].astype(float), prediction_cap_quantile))

    x_train, model_feature_columns = encode_features(x_train_raw, categorical_cols)
    x_val, _ = encode_features(x_val_raw, categorical_cols, feature_columns=model_feature_columns)

    ridge = Ridge(random_state=int(cfg["training"].get("random_state", 42)))
    ridge.fit(x_train, y_train_model)
    ridge_pred = ridge.predict(x_val)
    ridge_pred = inverse_target_transform(ridge_pred, target_transform)
    ridge_pred = postprocess_predictions(ridge_pred, prediction_floor, prediction_cap)
    ridge_metrics = evaluate_model(y_val_raw, ridge_pred)

    catboost_grid = get_catboost_param_grid(cfg)
    catboost_candidates: list[dict] = []
    best_catboost_model: CatBoostRegressor | None = None
    best_catboost_metrics: dict | None = None
    best_catboost_params: dict | None = None

    for params in catboost_grid:
        model = CatBoostRegressor(
            loss_function="RMSE",
            random_seed=int(cfg["training"].get("random_state", 42)),
            verbose=False,
            **params,
        )

        model.fit(
            x_train,
            y_train_model,
            eval_set=(x_val, y_val_model),
            use_best_model=True,
            early_stopping_rounds=early_stopping_rounds,
        )

        pred = model.predict(x_val)
        pred = inverse_target_transform(pred, target_transform)
        pred = postprocess_predictions(pred, prediction_floor, prediction_cap)
        metrics = evaluate_model(y_val_raw, pred)

        candidate = {
            "params": params,
            "metrics": metrics,
        }
        catboost_candidates.append(candidate)

        if best_catboost_metrics is None or metrics["rmse"] < best_catboost_metrics["rmse"]:
            best_catboost_model = model
            best_catboost_metrics = metrics
            best_catboost_params = params

    if best_catboost_model is None or best_catboost_metrics is None:
        raise RuntimeError("Failed to train CatBoost candidates")

    candidates = {
        "ridge": (ridge, ridge_metrics),
        "catboost": (best_catboost_model, best_catboost_metrics),
    }
    best_model_name = min(candidates.keys(), key=lambda name: candidates[name][1]["rmse"])
    best_model, best_metrics = candidates[best_model_name]

    best_pred = best_model.predict(x_val)
    best_pred = inverse_target_transform(best_pred, target_transform)
    best_pred = postprocess_predictions(best_pred, prediction_floor, prediction_cap)
    residual_std = float(np.std(y_val_raw - best_pred))

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
        "target_transform": target_transform,
        "prediction_floor": prediction_floor,
        "prediction_cap": prediction_cap,
        "prediction_interval_sigma": residual_std,
    }
    joblib.dump(artifact, model_path)

    if best_model_name == "catboost":
        importances = best_model.get_feature_importance()
        feature_importance = sorted(
            (
                {"feature": feature, "importance": float(score)}
                for feature, score in zip(model_feature_columns, importances, strict=False)
            ),
            key=lambda x: x["importance"],
            reverse=True,
        )[:20]
    else:
        coefs = np.abs(np.asarray(best_model.coef_))
        feature_importance = sorted(
            (
                {"feature": feature, "importance": float(score)}
                for feature, score in zip(model_feature_columns, coefs, strict=False)
            ),
            key=lambda x: x["importance"],
            reverse=True,
        )[:20]

    metadata = {
        "selected_model": best_model_name,
        "metrics": {
            "ridge": ridge_metrics,
            "catboost": best_catboost_metrics,
            "best": best_metrics,
        },
        "catboost_candidates": catboost_candidates,
        "catboost_selected_params": best_catboost_params,
        "target_transform": target_transform,
        "prediction_floor": prediction_floor,
        "prediction_cap": prediction_cap,
        "prediction_interval_sigma": residual_std,
        "top_feature_importance": feature_importance,
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
    print(
        f"[ML] Metrics: MAE={best_metrics['mae']:.2f}, RMSE={best_metrics['rmse']:.2f}, "
        f"MAPE={best_metrics['mape']:.2f}%, WAPE={best_metrics['wape']:.2f}%"
    )
    print(f"[ML] Prediction cap (quantile): {prediction_cap:.2f}")
    print(f"[ML] Interval sigma: {residual_std:.2f}")
    print(f"[ML] Model saved to: {model_path}")
    print(f"[ML] Metadata saved to: {metadata_path}")


if __name__ == "__main__":
    main()
