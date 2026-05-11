from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sqlalchemy as sa
import yaml
from catboost import CatBoostRegressor, Pool
from dotenv import load_dotenv
import lightgbm as lgb
import xgboost as xgb
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from features import build_training_frame, encode_features

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.data_source_registry import resolve_data_source_id  # noqa: E402
from src.etl.ml_experiment_registry import upsert_experiment  # noqa: E402

# ── Feature column specification ─────────────────────────────────────────────
# Must stay in sync with features.py and forecast_service._build_feature_row
FEATURE_COLS: list[str] = [
    # Store-level identifiers
    "store_id",
    # Demand drivers
    "promo",
    "school_holiday",
    "open",
    # Store metadata
    "competition_distance",
    "competition_distance_log",   # NEW — log-transform of right-skewed distance
    "promo2",
    # Calendar — basic
    "day_of_week",
    "month",
    "quarter",
    "week_of_year",
    "is_weekend",
    "day_of_month",               # NEW — intra-month effects
    "is_month_start",             # NEW — pay-day / restocking patterns
    "is_month_end",               # NEW — end-of-month behaviour
    "days_since_start",
    # Lag features (expanded: +lag_3, lag_21, lag_364)
    "lag_1",
    "lag_3",                      # NEW — 3-day recency signal
    "lag_7",
    "lag_14",
    "lag_21",                     # NEW — 3-week lag
    "lag_28",
    "lag_364",                    # NEW — 52-week yearly seasonality
    # Rolling stats (expanded: +56-day window)
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",
    "rolling_mean_56",            # NEW — 8-week trend baseline
    "rolling_std_7",
    "rolling_std_14",
    "rolling_std_28",
    "rolling_std_56",             # NEW
    # Derived ratios & trends
    "lag_1_to_mean_7_ratio",
    "sales_velocity",             # NEW — rolling_mean_7 / rolling_mean_28
    "lag_364_to_mean_28_ratio",   # NEW — yearly vs recent level
    # Promo density (NEW)
    "promo_density_7",
    "promo_density_14",
    # Categoricals (will be one-hot encoded)
    "state_holiday",
    "store_type",
    "assortment",
]

CATEGORICAL_COLS: list[str] = ["state_holiday", "store_type", "assortment"]


class _EnsembleWrapper:
    """Average predictions from a dict of {name: model} — used when ensemble wins selection."""
    def __init__(self, models: dict) -> None:
        self._models = models

    def predict(self, x) -> np.ndarray:
        preds = [np.asarray(m.predict(x), dtype=float) for m in self._models.values()]
        return np.mean(preds, axis=0)

    def get_feature_importance(self, **kwargs):
        cb = self._models.get("catboost")
        if cb is not None:
            return cb.get_feature_importance(**kwargs)
        raise AttributeError("No CatBoost sub-model for feature importance")


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
    return df[df["full_date"] <= cutoff].copy(), df[df["full_date"] > cutoff].copy()


def evaluate_model(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    eps = 1e-8
    y_true_np = y_true.to_numpy(dtype=float)
    y_pred_np = np.asarray(y_pred, dtype=float)
    abs_error = np.abs(y_true_np - y_pred_np)

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    mape = float(np.mean(abs_error / np.maximum(np.abs(y_true_np), 1.0)) * 100)
    wape = float(np.sum(abs_error) / np.maximum(np.sum(np.abs(y_true_np)), eps) * 100)

    nonzero_mask = np.abs(y_true_np) > 1.0
    mape_nonzero = (
        float(np.mean(abs_error[nonzero_mask] / np.maximum(np.abs(y_true_np[nonzero_mask]), eps)) * 100)
        if nonzero_mask.any()
        else None
    )
    smape = float(np.mean((2.0 * abs_error) / np.maximum(np.abs(y_true_np) + np.abs(y_pred_np), eps)) * 100)

    return {
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "mape_nonzero": mape_nonzero,
        "smape": smape,
        "wape": wape,
    }


def composite_score(metrics: dict, y_val_mean: float) -> float:
    """Lower is better. Normalised RMSE (scale-free) + WAPE combined."""
    nrmse = metrics["rmse"] / max(y_val_mean, 1.0)   # normalised RMSE
    wape = metrics["wape"] / 100.0                     # 0–1 scale
    return 0.5 * nrmse + 0.5 * wape


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
    # 6 diverse candidates covering depth / LR / regularisation tradeoffs
    default_grid = [
        # shallow + fast — low variance, strong regularisation
        {"depth": 6,  "learning_rate": 0.08, "l2_leaf_reg": 2.0, "iterations": 500},
        # balanced — good general baseline
        {"depth": 8,  "learning_rate": 0.05, "l2_leaf_reg": 3.0, "iterations": 700},
        # deep + regularised — captures complex patterns
        {"depth": 10, "learning_rate": 0.03, "l2_leaf_reg": 5.0, "iterations": 1000},
        # wide + slow LR — strong convergence
        {"depth": 8,  "learning_rate": 0.02, "l2_leaf_reg": 4.0, "iterations": 1200},
        # aggressive depth + moderate LR — often best on tabular data
        {"depth": 10, "learning_rate": 0.05, "l2_leaf_reg": 3.0, "iterations": 800},
        # shallow + aggressive LR — quick learner, good for dense feature sets
        {"depth": 6,  "learning_rate": 0.10, "l2_leaf_reg": 1.5, "iterations": 400},
    ]
    raw = cfg.get("training", {}).get("catboost_param_grid")
    if raw and isinstance(raw, list):
        normalized = [item for item in raw if isinstance(item, dict)]
        if normalized:
            return normalized
    return default_grid


def get_xgboost_param_grid(cfg: dict) -> list[dict]:
    default_grid = [
        {"max_depth": 6, "learning_rate": 0.05, "n_estimators": 700, "reg_lambda": 1.0, "subsample": 0.8, "colsample_bytree": 0.8},
        {"max_depth": 8, "learning_rate": 0.03, "n_estimators": 1000, "reg_lambda": 2.0, "subsample": 0.8, "colsample_bytree": 0.7},
        {"max_depth": 6, "learning_rate": 0.08, "n_estimators": 500,  "reg_lambda": 0.5, "subsample": 0.9, "colsample_bytree": 0.9},
    ]
    raw = cfg.get("training", {}).get("xgboost_param_grid")
    if raw and isinstance(raw, list):
        normalized = [item for item in raw if isinstance(item, dict)]
        if normalized:
            return normalized
    return default_grid


def get_lgbm_param_grid(cfg: dict) -> list[dict]:
    default_grid = [
        # balanced general-purpose
        {"num_leaves": 63,  "learning_rate": 0.05, "n_estimators": 700,  "reg_lambda": 1.0, "min_child_samples": 20},
        # deeper — more capacity
        {"num_leaves": 127, "learning_rate": 0.03, "n_estimators": 1000, "reg_lambda": 2.0, "min_child_samples": 30},
        # shallow + fast — low-variance baseline
        {"num_leaves": 31,  "learning_rate": 0.08, "n_estimators": 500,  "reg_lambda": 0.5, "min_child_samples": 15},
    ]
    raw = cfg.get("training", {}).get("lgbm_param_grid")
    if raw and isinstance(raw, list):
        normalized = [item for item in raw if isinstance(item, dict)]
        if normalized:
            return normalized
    return default_grid


def resolve_optional_data_source_id() -> int:
    raw_value = str(os.getenv("DATA_SOURCE_ID", "")).strip()
    if not raw_value:
        return resolve_data_source_id(None)
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError("DATA_SOURCE_ID must be an integer when provided") from exc
    return resolve_data_source_id(parsed)


def is_smoke_mode_enabled() -> bool:
    return str(os.getenv("ML_SMOKE_MODE", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _walk_forward_cv(
    *,
    model,
    framed: pd.DataFrame,
    val_start: pd.Timestamp,
    window_days: int,
    n_folds: int,
    feature_cols: list[str],
    model_feature_columns: list[str],
    target_transform: str,
    prediction_floor: float,
    prediction_cap: float | None,
) -> list[dict]:
    """
    Evaluate model on N earlier time windows to estimate generalisation.
    Windows are immediately before the primary validation period.
    Returns list of metric dicts (one per fold).
    """
    cv_results: list[dict] = []
    for fold in range(n_folds):
        fold_end = val_start - pd.Timedelta(days=fold * window_days + 1)
        fold_start = fold_end - pd.Timedelta(days=window_days - 1)
        fold_mask = (framed["full_date"] >= fold_start) & (framed["full_date"] <= fold_end)
        fold_df = framed[fold_mask].copy()
        if fold_df.empty:
            continue
        x_fold_raw = fold_df[[c for c in feature_cols if c in fold_df.columns]].copy()
        # Ensure all feature cols present
        for col in feature_cols:
            if col not in x_fold_raw.columns:
                x_fold_raw[col] = 0
        x_fold_raw = x_fold_raw[feature_cols]
        x_fold, _ = encode_features(x_fold_raw, CATEGORICAL_COLS, feature_columns=model_feature_columns)
        y_fold_raw = fold_df["sales"].astype(float)
        fold_pred = model.predict(x_fold)
        fold_pred = inverse_target_transform(fold_pred, target_transform)
        fold_pred = postprocess_predictions(fold_pred, prediction_floor, prediction_cap)
        cv_results.append(
            {
                "fold": fold + 1,
                "date_from": fold_start.date().isoformat(),
                "date_to": fold_end.date().isoformat(),
                "rows": int(len(fold_df)),
                "metrics": evaluate_model(y_fold_raw, fold_pred),
            }
        )
    return cv_results


def _per_group_metrics(
    val_df: pd.DataFrame,
    best_pred: np.ndarray,
    group_col: str = "store_type",
) -> dict[str, dict]:
    """Break down validation metrics by store group."""
    result: dict[str, dict] = {}
    if group_col not in val_df.columns:
        return result
    val_copy = val_df.reset_index(drop=True).copy()
    val_copy["_pred"] = best_pred
    for group_val, grp in val_copy.groupby(group_col):
        result[str(group_val)] = evaluate_model(grp["sales"], grp["_pred"].to_numpy())
    return result


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

    data_source_id = resolve_optional_data_source_id()
    experiment_id = f"ml_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    experiment_started_at = datetime.now(timezone.utc)

    training_cfg = cfg.get("training", {})
    validation_days = int(training_cfg.get("validation_days", 90))
    target_transform = str(training_cfg.get("target_transform", "log1p"))
    prediction_floor = float(training_cfg.get("prediction_floor", 0.0))
    prediction_cap_quantile = float(training_cfg.get("prediction_cap_quantile", 0.997))
    early_stopping_rounds = int(training_cfg.get("early_stopping_rounds", 60))
    random_state = int(training_cfg.get("random_state", 42))
    cv_window_days = int(training_cfg.get("cv_window_days", 30))
    cv_folds = int(training_cfg.get("cv_folds", 2))
    catboost_grid = get_catboost_param_grid(cfg)
    lgbm_grid = get_lgbm_param_grid(cfg)

    upsert_experiment(
        {
            "experiment_id": experiment_id,
            "data_source_id": data_source_id,
            "model_type": "pending",
            "hyperparameters_json": {
                "random_state": random_state,
                "validation_days": validation_days,
                "target_transform": target_transform,
                "prediction_floor": prediction_floor,
                "prediction_cap_quantile": prediction_cap_quantile,
                "early_stopping_rounds": early_stopping_rounds,
                "catboost_param_grid": catboost_grid,
            },
            "metrics_json": {},
            "status": "RUNNING",
            "created_at": experiment_started_at,
            "updated_at": experiment_started_at,
        }
    )

    train_period_start: str | None = None
    train_period_end: str | None = None
    validation_period_start: str | None = None
    validation_period_end: str | None = None

    try:
        engine = sa.create_engine(db_url)
        raw_df = load_training_data(engine)
        smoke_mode = is_smoke_mode_enabled()

        if smoke_mode:
            smoke_max_rows = max(5000, int(os.getenv("ML_SMOKE_MAX_ROWS", "150000")))
            raw_df = raw_df.sort_values("full_date").tail(smoke_max_rows).reset_index(drop=True)
            print(f"[ML][Smoke] Enabled with max_rows={smoke_max_rows}")

        framed = build_training_frame(raw_df)
        if framed.empty:
            raise ValueError("Training frame is empty after feature engineering")

        if smoke_mode:
            requested_validation_days = int(os.getenv("ML_SMOKE_VALIDATION_DAYS", "30"))
            date_span_days = int((framed["full_date"].max() - framed["full_date"].min()).days)
            max_safe_validation_days = max(1, date_span_days // 3)
            validation_days = max(1, min(validation_days, requested_validation_days, max_safe_validation_days))
            early_stopping_rounds = min(early_stopping_rounds, int(os.getenv("ML_SMOKE_EARLY_STOPPING", "20")))
            catboost_grid = [
                {
                    "depth": int(os.getenv("ML_SMOKE_CATBOOST_DEPTH", "6")),
                    "learning_rate": float(os.getenv("ML_SMOKE_CATBOOST_LR", "0.08")),
                    "l2_leaf_reg": float(os.getenv("ML_SMOKE_CATBOOST_L2", "3.0")),
                    "iterations": int(os.getenv("ML_SMOKE_CATBOOST_ITERS", "120")),
                }
            ]
            print(f"[ML][Smoke] validation_days={validation_days}")

        train_df, val_df = time_split(framed, validation_days=validation_days)

        if (train_df.empty or val_df.empty) and smoke_mode:
            unique_dates = np.sort(framed["full_date"].dropna().unique())
            if len(unique_dates) >= 2:
                split_idx = min(max(1, int(len(unique_dates) * 0.8)), len(unique_dates) - 1)
                cutoff = pd.Timestamp(unique_dates[split_idx - 1])
                train_df = framed[framed["full_date"] <= cutoff].copy()
                val_df = framed[framed["full_date"] > cutoff].copy()

        if train_df.empty or val_df.empty:
            raise ValueError("Insufficient data for time-based split")

        train_period_start = train_df["full_date"].min().date().isoformat()
        train_period_end = train_df["full_date"].max().date().isoformat()
        validation_period_start = val_df["full_date"].min().date().isoformat()
        validation_period_end = val_df["full_date"].max().date().isoformat()

        # Keep only feature columns that actually exist in the frame
        available_feature_cols = [c for c in FEATURE_COLS if c in framed.columns]
        missing = set(FEATURE_COLS) - set(available_feature_cols)
        if missing:
            print(f"[ML][Warn] Missing feature columns (will be skipped): {sorted(missing)}")

        x_train_raw = train_df[available_feature_cols].copy()
        y_train_raw = train_df["sales"].astype(float)
        y_train_model = np.log1p(y_train_raw) if target_transform == "log1p" else y_train_raw

        x_val_raw = val_df[available_feature_cols].copy()
        y_val_raw = val_df["sales"].astype(float)
        y_val_model = np.log1p(y_val_raw) if target_transform == "log1p" else y_val_raw

        y_val_mean = float(y_val_raw.mean())
        prediction_cap = float(np.quantile(train_df["sales"].astype(float), prediction_cap_quantile))

        x_train, model_feature_columns = encode_features(x_train_raw, CATEGORICAL_COLS)
        x_val, _ = encode_features(x_val_raw, CATEGORICAL_COLS, feature_columns=model_feature_columns)

        # ── Ridge baseline ────────────────────────────────────────────────────
        ridge = Ridge(random_state=random_state)
        ridge.fit(x_train, y_train_model)
        ridge_pred = ridge.predict(x_val)
        ridge_pred = inverse_target_transform(ridge_pred, target_transform)
        ridge_pred = postprocess_predictions(ridge_pred, prediction_floor, prediction_cap)
        ridge_metrics = evaluate_model(y_val_raw, ridge_pred)

        # ── CatBoost grid search ──────────────────────────────────────────────
        catboost_candidates: list[dict] = []
        best_catboost_model: CatBoostRegressor | None = None
        best_catboost_metrics: dict | None = None
        best_catboost_params: dict | None = None
        best_catboost_score: float = float("inf")

        for idx, params in enumerate(catboost_grid):
            print(f"[ML] CatBoost candidate {idx + 1}/{len(catboost_grid)}: {params}")
            model = CatBoostRegressor(
                loss_function="RMSE",
                random_seed=random_state,
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
            score = composite_score(metrics, y_val_mean)
            print(
                f"[ML]   → RMSE={metrics['rmse']:.2f}, WAPE={metrics['wape']:.2f}%, "
                f"MAE={metrics['mae']:.2f}, composite={score:.4f}"
            )

            catboost_candidates.append({"params": params, "metrics": metrics, "composite_score": score})

            if score < best_catboost_score:
                best_catboost_model = model
                best_catboost_metrics = metrics
                best_catboost_params = params
                best_catboost_score = score

        if best_catboost_model is None or best_catboost_metrics is None:
            raise RuntimeError("Failed to train CatBoost candidates")

        # ── LightGBM grid search ──────────────────────────────────────────────
        lgbm_candidates: list[dict] = []
        best_lgbm_model: lgb.LGBMRegressor | None = None
        best_lgbm_metrics: dict | None = None
        best_lgbm_params: dict | None = None
        best_lgbm_score: float = float("inf")

        for idx, params in enumerate(lgbm_grid):
            print(f"[ML] LightGBM candidate {idx + 1}/{len(lgbm_grid)}: {params}")
            model = lgb.LGBMRegressor(
                objective="regression",
                random_state=random_state,
                verbose=-1,
                **params,
            )
            model.fit(
                x_train,
                y_train_model,
                eval_set=[(x_val, y_val_model)],
                callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False),
                           lgb.log_evaluation(period=-1)],
            )
            pred = model.predict(x_val)
            pred = inverse_target_transform(pred, target_transform)
            pred = postprocess_predictions(pred, prediction_floor, prediction_cap)
            metrics = evaluate_model(y_val_raw, pred)
            score = composite_score(metrics, y_val_mean)
            print(
                f"[ML]   → RMSE={metrics['rmse']:.2f}, WAPE={metrics['wape']:.2f}%, "
                f"MAE={metrics['mae']:.2f}, composite={score:.4f}"
            )
            lgbm_candidates.append({"params": params, "metrics": metrics, "composite_score": score})

            if score < best_lgbm_score:
                best_lgbm_model = model
                best_lgbm_metrics = metrics
                best_lgbm_params = params
                best_lgbm_score = score

        if best_lgbm_model is None or best_lgbm_metrics is None:
            raise RuntimeError("Failed to train LightGBM candidates")

        # ── XGBoost grid search ───────────────────────────────────────────────
        xgboost_grid = get_xgboost_param_grid(cfg)
        xgboost_candidates: list[dict] = []
        best_xgboost_model: xgb.XGBRegressor | None = None
        best_xgboost_metrics: dict | None = None
        best_xgboost_params: dict | None = None
        best_xgboost_score: float = float("inf")

        for idx, params in enumerate(xgboost_grid):
            print(f"[ML] XGBoost candidate {idx + 1}/{len(xgboost_grid)}: {params}")
            n_est = params.pop("n_estimators", 700)
            xgb_model = xgb.XGBRegressor(
                objective="reg:squarederror",
                random_state=random_state,
                verbosity=0,
                early_stopping_rounds=early_stopping_rounds,
                n_estimators=n_est,
                **params,
            )
            xgb_model.fit(
                x_train, y_train_model,
                eval_set=[(x_val, y_val_model)],
                verbose=False,
            )
            params["n_estimators"] = n_est  # restore
            pred = xgb_model.predict(x_val)
            pred = inverse_target_transform(pred, target_transform)
            pred = postprocess_predictions(pred, prediction_floor, prediction_cap)
            metrics = evaluate_model(y_val_raw, pred)
            score = composite_score(metrics, y_val_mean)
            print(
                f"[ML]   → RMSE={metrics['rmse']:.2f}, WAPE={metrics['wape']:.2f}%, "
                f"MAE={metrics['mae']:.2f}, composite={score:.4f}"
            )
            xgboost_candidates.append({"params": dict(params), "metrics": metrics, "composite_score": score})
            if score < best_xgboost_score:
                best_xgboost_model = xgb_model
                best_xgboost_metrics = metrics
                best_xgboost_params = dict(params)
                best_xgboost_score = score

        if best_xgboost_model is None or best_xgboost_metrics is None:
            raise RuntimeError("Failed to train XGBoost candidates")

        # ── Model selection using composite score ─────────────────────────────
        ridge_score = composite_score(ridge_metrics, y_val_mean)
        candidates = {
            "ridge": (ridge, ridge_metrics, ridge_score),
            "catboost": (best_catboost_model, best_catboost_metrics, best_catboost_score),
            "lightgbm": (best_lgbm_model, best_lgbm_metrics, best_lgbm_score),
            "xgboost": (best_xgboost_model, best_xgboost_metrics, best_xgboost_score),
        }
        best_model_name = min(candidates.keys(), key=lambda n: candidates[n][2])
        best_model, best_metrics, _ = candidates[best_model_name]

        # ── Blend ensemble: average top-3 tree models ─────────────────────────
        try:
            tree_models = [best_catboost_model, best_lgbm_model, best_xgboost_model]
            ensemble_preds = np.zeros(len(y_val_raw), dtype=float)
            for tm in tree_models:
                p = tm.predict(x_val)
                p = inverse_target_transform(p, target_transform)
                p = postprocess_predictions(p, prediction_floor, prediction_cap)
                ensemble_preds += p
            ensemble_preds /= len(tree_models)
            ensemble_metrics = evaluate_model(y_val_raw, ensemble_preds)
            ensemble_score = composite_score(ensemble_metrics, y_val_mean)
            best_individual_score = candidates[best_model_name][2]
            print(f"[ML] Ensemble blend: composite={ensemble_score:.4f} (best individual={best_individual_score:.4f})")
            if ensemble_score < best_individual_score:
                print("[ML] Ensemble is better — selecting blend model")
                best_model_name = "ensemble"
                # Store as _EnsembleWrapper so predict() works in CV and artifact generation
                best_model = _EnsembleWrapper({"catboost": best_catboost_model, "lightgbm": best_lgbm_model, "xgboost": best_xgboost_model})
                best_metrics = ensemble_metrics
        except Exception as ens_exc:  # noqa: BLE001
            print(f"[ML][Warn] Ensemble computation failed: {ens_exc}")

        print(
            f"[ML] Selected model: {best_model_name} "
            f"(composite scores: ridge={ridge_score:.4f}, "
            f"catboost={best_catboost_score:.4f}, "
            f"lightgbm={best_lgbm_score:.4f}, "
            f"xgboost={best_xgboost_score:.4f})"
        )

        # ── Compute residuals on validation set ───────────────────────────────
        # _EnsembleWrapper.predict() already averages all sub-models
        best_pred = best_model.predict(x_val)
        best_pred = inverse_target_transform(best_pred, target_transform)
        best_pred = postprocess_predictions(best_pred, prediction_floor, prediction_cap)
        residual_std = float(np.std(y_val_raw.to_numpy() - best_pred))

        # ── Per-store-type metric breakdown (NEW) ─────────────────────────────
        per_group_metrics = _per_group_metrics(val_df, best_pred, group_col="store_type")
        if per_group_metrics:
            print("[ML] Validation metrics by store_type:")
            for stype, m in per_group_metrics.items():
                print(f"[ML]   {stype}: RMSE={m['rmse']:.2f}, WAPE={m['wape']:.2f}%, MAE={m['mae']:.2f}")

        # ── Walk-forward cross-validation on best model (NEW) ─────────────────
        cv_results: list[dict] = []
        if not smoke_mode:
            val_start_ts = val_df["full_date"].min()
            cv_results = _walk_forward_cv(
                model=best_model,
                framed=framed,
                val_start=val_start_ts,
                window_days=cv_window_days,
                n_folds=cv_folds,
                feature_cols=available_feature_cols,
                model_feature_columns=model_feature_columns,
                target_transform=target_transform,
                prediction_floor=prediction_floor,
                prediction_cap=prediction_cap,
            )
            if cv_results:
                cv_wapes = [r["metrics"]["wape"] for r in cv_results]
                cv_rmses = [r["metrics"]["rmse"] for r in cv_results]
                print(
                    f"[ML] Walk-forward CV ({cv_folds} folds, {cv_window_days}d each): "
                    f"avg RMSE={np.mean(cv_rmses):.2f}, avg WAPE={np.mean(cv_wapes):.2f}%"
                )

        # ── Persist artifacts ─────────────────────────────────────────────────
        model_path = resolve_path(cfg_path.parent, training_cfg.get("model_path", "artifacts/model.joblib"))
        metadata_path = resolve_path(cfg_path.parent, training_cfg.get("metadata_path", "artifacts/model_metadata.json"))
        model_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Save sub-models dict for ensemble (not the wrapper) so joblib can serialize it cleanly
        artifact_model = best_model._models if isinstance(best_model, _EnsembleWrapper) else best_model
        artifact = {
            "model": artifact_model,
            "model_name": best_model_name,
            "feature_columns": model_feature_columns,
            "categorical_columns": CATEGORICAL_COLS,
            "raw_feature_columns": available_feature_cols,
            "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "target_transform": target_transform,
            "prediction_floor": prediction_floor,
            "prediction_cap": prediction_cap,
            "prediction_interval_sigma": residual_std,
        }
        joblib.dump(artifact, model_path)

        # ── Feature importance (split-based) ─────────────────────────────────
        # For ensemble use catboost sub-model for split-based importance
        _ref_model = best_catboost_model if best_model_name == "ensemble" else best_model
        if best_model_name in ("catboost", "ensemble"):
            raw_importances = best_catboost_model.get_feature_importance()
        elif best_model_name == "lightgbm":
            raw_importances = best_model.feature_importances_
        elif best_model_name == "xgboost":
            raw_importances = best_model.feature_importances_
        else:
            raw_importances = np.abs(np.asarray(best_model.coef_))

        feature_importance_split = sorted(
            (
                {"feature": feat, "importance": float(imp)}
                for feat, imp in zip(model_feature_columns, raw_importances, strict=False)
            ),
            key=lambda x: x["importance"],
            reverse=True,
        )[:20]

        # ── SHAP-based feature importance ─────────────────────────────────────
        shap_importance: list[dict] = feature_importance_split  # default fallback
        try:
            if best_model_name in ("catboost", "ensemble"):
                _cb = best_model if best_model_name == "catboost" else best_catboost_model
                val_pool = Pool(x_val, label=y_val_model)
                shap_vals = _cb.get_feature_importance(type="ShapValues", data=val_pool)
                mean_abs_shap = np.abs(shap_vals[:, :-1]).mean(axis=0)  # drop bias col
                shap_importance = sorted(
                    [{"feature": f, "importance": float(v)} for f, v in zip(model_feature_columns, mean_abs_shap, strict=False)],
                    key=lambda x: -x["importance"],
                )[:20]
                print("[ML] SHAP importance computed via CatBoost ShapValues")
            elif best_model_name == "lightgbm":
                shap_matrix = best_model.predict(x_val, pred_contrib=True)
                mean_abs_shap = np.abs(shap_matrix[:, :-1]).mean(axis=0)
                shap_importance = sorted(
                    [{"feature": f, "importance": float(v)} for f, v in zip(model_feature_columns, mean_abs_shap, strict=False)],
                    key=lambda x: -x["importance"],
                )[:20]
                print("[ML] SHAP importance computed via LightGBM pred_contrib")
            elif best_model_name == "xgboost":
                dval = xgb.DMatrix(x_val)
                shap_matrix = best_model.get_booster().predict(dval, pred_contribs=True)
                mean_abs_shap = np.abs(shap_matrix[:, :-1]).mean(axis=0)
                shap_importance = sorted(
                    [{"feature": f, "importance": float(v)} for f, v in zip(model_feature_columns, mean_abs_shap, strict=False)],
                    key=lambda x: -x["importance"],
                )[:20]
                print("[ML] SHAP importance computed via XGBoost pred_contribs")
        except Exception as shap_exc:  # noqa: BLE001
            print(f"[ML][Warn] SHAP computation failed ({shap_exc}), using split importance as fallback")

        metadata = {
            "selected_model": best_model_name,
            "metrics": {
                "ridge": ridge_metrics,
                "catboost": best_catboost_metrics,
                "lightgbm": best_lgbm_metrics,
                "xgboost": best_xgboost_metrics,
                "best": best_metrics,
            },
            "model_scores": {
                "ridge_composite": float(ridge_score),
                "catboost_composite": float(best_catboost_score),
                "lightgbm_composite": float(best_lgbm_score),
                "xgboost_composite": float(best_xgboost_score),
            },
            "catboost_candidates": catboost_candidates,
            "catboost_selected_params": best_catboost_params,
            "lgbm_candidates": lgbm_candidates,
            "lgbm_selected_params": best_lgbm_params,
            "xgboost_candidates": xgboost_candidates,
            "xgboost_selected_params": best_xgboost_params,
            "per_store_type_metrics": per_group_metrics,
            "walk_forward_cv": cv_results,
            "target_transform": target_transform,
            "prediction_floor": prediction_floor,
            "prediction_cap": prediction_cap,
            "prediction_interval_sigma": residual_std,
            "top_feature_importance": shap_importance,
            "top_feature_importance_split": feature_importance_split,
            "train_period": {"date_from": train_period_start, "date_to": train_period_end},
            "validation_period": {"date_from": validation_period_start, "date_to": validation_period_end},
            "feature_columns": model_feature_columns,
            "raw_feature_columns": available_feature_cols,
            "rows": {"train": int(len(train_df)), "validation": int(len(val_df))},
        }
        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)

        upsert_experiment(
            {
                "experiment_id": experiment_id,
                "data_source_id": data_source_id,
                "model_type": best_model_name,
                "hyperparameters_json": {
                    "random_state": random_state,
                    "validation_days": validation_days,
                    "target_transform": target_transform,
                    "prediction_floor": prediction_floor,
                    "prediction_cap_quantile": prediction_cap_quantile,
                    "prediction_cap_value": prediction_cap,
                    "early_stopping_rounds": early_stopping_rounds,
                    "catboost_selected_params": best_catboost_params or {},
                    "xgboost_selected_params": best_xgboost_params or {},
                },
                "train_period_start": train_period_start,
                "train_period_end": train_period_end,
                "validation_period_start": validation_period_start,
                "validation_period_end": validation_period_end,
                "metrics_json": {
                    "best": best_metrics,
                    "ridge": ridge_metrics,
                    "catboost": best_catboost_metrics,
                    "lightgbm": best_lgbm_metrics,
                    "xgboost": best_xgboost_metrics,
                    "per_store_type": per_group_metrics,
                },
                "status": "COMPLETED",
                "artifact_path": str(model_path),
                "metadata_path": str(metadata_path),
                "created_at": experiment_started_at,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        print("\n[ML] ── Training complete ──────────────────────────────────────")
        print(f"[ML] Best model    : {best_model_name}")
        print(
            f"[ML] Metrics       : MAE={best_metrics['mae']:.2f}, "
            f"RMSE={best_metrics['rmse']:.2f}, "
            f"MAPE={best_metrics['mape']:.2f}%, "
            f"WAPE={best_metrics['wape']:.2f}%"
        )
        print(f"[ML] Prediction cap: {prediction_cap:.2f}")
        print(f"[ML] Interval sigma: {residual_std:.2f}")
        print(f"[ML] Features used : {len(available_feature_cols)} raw → {len(model_feature_columns)} encoded")
        print(f"[ML] Model saved   : {model_path}")
        print(f"[ML] Metadata      : {metadata_path}")

    except Exception as exc:
        upsert_experiment(
            {
                "experiment_id": experiment_id,
                "data_source_id": data_source_id,
                "model_type": "failed",
                "hyperparameters_json": {
                    "random_state": random_state,
                    "validation_days": validation_days,
                    "target_transform": target_transform,
                    "prediction_floor": prediction_floor,
                    "prediction_cap_quantile": prediction_cap_quantile,
                    "early_stopping_rounds": early_stopping_rounds,
                },
                "train_period_start": train_period_start,
                "train_period_end": train_period_end,
                "validation_period_start": validation_period_start,
                "validation_period_end": validation_period_end,
                "metrics_json": {"error": str(exc)},
                "status": "FAILED",
                "created_at": experiment_started_at,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        raise


if __name__ == "__main__":
    main()
