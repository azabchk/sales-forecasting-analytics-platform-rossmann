from __future__ import annotations

import pandas as pd

LAG_WINDOWS = [1, 7, 14, 28]
ROLL_WINDOWS = [7, 14, 28]


def add_calendar_features(df: pd.DataFrame, date_col: str = "full_date") -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out["day_of_week"] = out[date_col].dt.dayofweek + 1
    out["month"] = out[date_col].dt.month
    out["quarter"] = out[date_col].dt.quarter
    out["week_of_year"] = out[date_col].dt.isocalendar().week.astype(int)
    out["is_weekend"] = out["day_of_week"].isin([6, 7]).astype(int)
    return out


def add_lag_and_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["store_id", "full_date"]).copy()
    out["days_since_start"] = out.groupby("store_id").cumcount()

    for lag in LAG_WINDOWS:
        out[f"lag_{lag}"] = out.groupby("store_id")["sales"].shift(lag)

    for window in ROLL_WINDOWS:
        out[f"rolling_mean_{window}"] = (
            out.groupby("store_id")["sales"].transform(lambda s: s.shift(1).rolling(window=window, min_periods=1).mean())
        )
        out[f"rolling_std_{window}"] = (
            out.groupby("store_id")["sales"]
            .transform(lambda s: s.shift(1).rolling(window=window, min_periods=2).std())
            .fillna(0.0)
        )

    out["lag_1_to_mean_7_ratio"] = out["lag_1"] / out["rolling_mean_7"].replace(0, pd.NA)
    out["lag_1_to_mean_7_ratio"] = out["lag_1_to_mean_7_ratio"].fillna(1.0)

    return out


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = add_calendar_features(df)
    out = add_lag_and_rolling_features(out)
    out = out.dropna(subset=[f"lag_{w}" for w in LAG_WINDOWS])
    return out


def encode_features(df: pd.DataFrame, categorical_cols: list[str], feature_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    encoded = pd.get_dummies(df, columns=categorical_cols, drop_first=False)
    if feature_columns is not None:
        encoded = encoded.reindex(columns=feature_columns, fill_value=0)
        return encoded, feature_columns
    return encoded, encoded.columns.tolist()
