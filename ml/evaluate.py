from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa
import yaml
from dotenv import load_dotenv
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from features import build_training_frame, encode_features


def load_config(config_path: str) -> tuple[dict, Path]:
    cfg_path = Path(config_path).resolve()
    with open(cfg_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file), cfg_path


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def load_eval_data(engine: sa.Engine) -> pd.DataFrame:
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


def inverse_target_transform(predictions: np.ndarray, target_transform: str) -> np.ndarray:
    if target_transform == "log1p":
        return np.expm1(predictions)
    return predictions


def postprocess_predictions(predictions: np.ndarray, floor: float, cap: float | None) -> np.ndarray:
    clipped = np.maximum(predictions, floor)
    if cap is not None:
        clipped = np.minimum(clipped, cap)
    return clipped


def evaluate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    eps = 1e-8
    y_true_np = np.asarray(y_true, dtype=float)
    y_pred_np = np.asarray(y_pred, dtype=float)
    abs_error = np.abs(y_true_np - y_pred_np)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = root_mean_squared_error(y_true, y_pred)
    mape = np.mean(abs_error / np.maximum(np.abs(y_true_np), 1.0)) * 100
    wape = np.sum(abs_error) / np.maximum(np.sum(np.abs(y_true_np)), eps) * 100
    nonzero_mask = np.abs(y_true_np) > 1.0
    mape_nonzero = (
        np.mean(abs_error[nonzero_mask] / np.maximum(np.abs(y_true_np[nonzero_mask]), eps)) * 100
        if nonzero_mask.any()
        else None
    )
    smape = np.mean((2.0 * abs_error) / np.maximum(np.abs(y_true_np) + np.abs(y_pred_np), eps)) * 100
    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "mape": float(mape),
        "mape_nonzero": float(mape_nonzero) if mape_nonzero is not None else None,
        "smape": float(smape),
        "wape": float(wape),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate saved model")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()

    cfg, cfg_path = load_config(args.config)
    project_root = cfg_path.parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)

    db_url = os.getenv(cfg["database"]["url_env"])
    if not db_url:
        raise ValueError("DATABASE_URL not found")

    model_path = resolve_path(cfg_path.parent, cfg["training"].get("model_path", "artifacts/model.joblib"))
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    artifact = joblib.load(model_path)

    engine = sa.create_engine(db_url)
    df = build_training_frame(load_eval_data(engine))

    max_date = df["full_date"].max()
    cutoff = max_date - pd.Timedelta(days=int(cfg["training"].get("validation_days", 60)))
    val_df = df[df["full_date"] > cutoff].copy()
    if val_df.empty:
        raise ValueError("Validation slice is empty")

    x_raw = val_df[artifact["raw_feature_columns"]].copy()
    y_true = val_df["sales"].astype(float).to_numpy()

    x, _ = encode_features(
        x_raw,
        artifact["categorical_columns"],
        feature_columns=artifact["feature_columns"],
    )

    model = artifact["model"]
    y_pred = model.predict(x)
    y_pred = inverse_target_transform(y_pred, str(artifact.get("target_transform", "none")))
    y_pred = postprocess_predictions(
        y_pred,
        float(artifact.get("prediction_floor", 0.0)),
        float(artifact["prediction_cap"]) if artifact.get("prediction_cap") is not None else None,
    )

    metrics = evaluate_metrics(y_true, y_pred)

    result = {
        "model_name": artifact.get("model_name", "unknown"),
        "validation_rows": int(len(val_df)),
        "metrics": metrics,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
