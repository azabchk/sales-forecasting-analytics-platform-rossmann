from __future__ import annotations

import numpy as np
import pandas as pd

LAG_WINDOWS = [1, 3, 7, 14, 21, 28]   # +lag_3, lag_21 vs original [1,7,14,28]
ROLL_WINDOWS = [7, 14, 28, 56]          # +56-day (8-week) window
YEARLY_LAG = 364                         # 52-week seasonality anchor


def add_calendar_features(df: pd.DataFrame, date_col: str = "full_date") -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out["day_of_week"] = out[date_col].dt.dayofweek + 1   # 1=Mon … 7=Sun
    out["month"] = out[date_col].dt.month
    out["quarter"] = out[date_col].dt.quarter
    out["week_of_year"] = out[date_col].dt.isocalendar().week.astype(int)
    out["is_weekend"] = out["day_of_week"].isin([6, 7]).astype(int)
    out["day_of_month"] = out[date_col].dt.day                       # NEW — intra-month patterns
    out["is_month_start"] = (out[date_col].dt.day <= 3).astype(int)  # NEW — start-of-month effect
    out["is_month_end"] = (out[date_col].dt.day >= 28).astype(int)   # NEW — end-of-month effect
    return out


def add_lag_and_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["store_id", "full_date"]).copy()
    out["days_since_start"] = out.groupby("store_id").cumcount()

    # ── Standard lags (expanded) ──────────────────────────────────────────────
    for lag in LAG_WINDOWS:
        out[f"lag_{lag}"] = out.groupby("store_id")["sales"].shift(lag)

    # ── Yearly lag (52-week) with graceful fill for early data ────────────────
    out["lag_364"] = out.groupby("store_id")["sales"].shift(YEARLY_LAG)

    # ── Rolling statistics (4 windows) ───────────────────────────────────────
    for window in ROLL_WINDOWS:
        out[f"rolling_mean_{window}"] = out.groupby("store_id")["sales"].transform(
            lambda s: s.shift(1).rolling(window=window, min_periods=1).mean()
        )
        out[f"rolling_std_{window}"] = (
            out.groupby("store_id")["sales"]
            .transform(lambda s: s.shift(1).rolling(window=window, min_periods=2).std())
            .fillna(0.0)
        )

    # Fill lag_364 NaN (first ~year per store) with rolling_mean_28 as proxy
    out["lag_364"] = out["lag_364"].fillna(out["rolling_mean_28"])

    # ── Derived ratio / trend features ───────────────────────────────────────
    mean_7 = out["rolling_mean_7"].replace(0, np.nan)
    mean_28 = out["rolling_mean_28"].replace(0, np.nan)

    out["lag_1_to_mean_7_ratio"] = (out["lag_1"] / mean_7).fillna(1.0).astype(float)
    out["sales_velocity"] = (out["rolling_mean_7"] / mean_28).fillna(1.0).astype(float)  # NEW short vs long trend
    out["lag_364_to_mean_28_ratio"] = (out["lag_364"] / mean_28).fillna(1.0).astype(float)  # NEW yearly vs recent

    # ── Promo density (NEW) — rolling share of promo days ────────────────────
    if "promo" in out.columns:
        out["promo_density_7"] = out.groupby("store_id")["promo"].transform(
            lambda s: s.shift(1).rolling(7, min_periods=1).mean()
        )
        out["promo_density_14"] = out.groupby("store_id")["promo"].transform(
            lambda s: s.shift(1).rolling(14, min_periods=1).mean()
        )
    else:
        out["promo_density_7"] = 0.0
        out["promo_density_14"] = 0.0

    # ── Log-compressed competition distance (NEW) — right-skewed feature ─────
    if "competition_distance" in out.columns:
        out["competition_distance_log"] = np.log1p(out["competition_distance"])
    else:
        out["competition_distance_log"] = 0.0

    return out


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = add_calendar_features(df)
    out = add_lag_and_rolling_features(out)
    # Drop only rows where short-horizon lags are NaN (lag_364 is pre-filled)
    out = out.dropna(subset=[f"lag_{w}" for w in LAG_WINDOWS])
    return out


def encode_features(
    df: pd.DataFrame,
    categorical_cols: list[str],
    feature_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    encoded = pd.get_dummies(df, columns=categorical_cols, drop_first=False)
    if feature_columns is not None:
        encoded = encoded.reindex(columns=feature_columns, fill_value=0)
        return encoded, feature_columns
    return encoded, encoded.columns.tolist()
