from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
import yaml
from dotenv import load_dotenv
from psycopg2.extras import execute_values


@dataclass
class ETLConfig:
    train_csv: str
    store_csv: str
    db_url: str
    truncate_reload: bool
    chunksize: int


def load_config(path: str) -> ETLConfig:
    config_path = Path(path).resolve()
    project_root = config_path.parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)

    with open(config_path, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    db_url = os.getenv(cfg["database"]["url_env"])
    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment or .env")

    return ETLConfig(
        train_csv=str((config_path.parent / cfg["paths"]["train_csv"]).resolve()),
        store_csv=str((config_path.parent / cfg["paths"]["store_csv"]).resolve()),
        db_url=db_url,
        truncate_reload=bool(cfg["etl"].get("truncate_reload", True)),
        chunksize=int(cfg["etl"].get("chunksize", 50000)),
    )


def load_raw_data(train_csv: str, store_csv: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not os.path.exists(train_csv):
        raise FileNotFoundError(f"train.csv not found: {train_csv}")
    if not os.path.exists(store_csv):
        raise FileNotFoundError(f"store.csv not found: {store_csv}")

    train_df = pd.read_csv(train_csv, low_memory=False)
    store_df = pd.read_csv(store_csv, low_memory=False)
    return train_df, store_df


def clean_store(store_df: pd.DataFrame) -> pd.DataFrame:
    df = store_df.copy()
    df.columns = [c.strip() for c in df.columns]

    df = df.rename(
        columns={
            "Store": "store_id",
            "StoreType": "store_type",
            "Assortment": "assortment",
            "CompetitionDistance": "competition_distance",
            "CompetitionOpenSinceMonth": "competition_open_since_month",
            "CompetitionOpenSinceYear": "competition_open_since_year",
            "Promo2": "promo2",
            "Promo2SinceWeek": "promo2_since_week",
            "Promo2SinceYear": "promo2_since_year",
            "PromoInterval": "promo_interval",
        }
    )

    numeric_cols = [
        "competition_distance",
        "competition_open_since_month",
        "competition_open_since_year",
        "promo2",
        "promo2_since_week",
        "promo2_since_year",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["competition_distance"] = df["competition_distance"].fillna(df["competition_distance"].median())
    df["promo2"] = df["promo2"].fillna(0).astype(int)
    df["store_type"] = df["store_type"].fillna("unknown")
    df["assortment"] = df["assortment"].fillna("unknown")
    df["promo_interval"] = df["promo_interval"].fillna("none")

    for col in ["competition_open_since_month", "competition_open_since_year", "promo2_since_week", "promo2_since_year"]:
        df[col] = df[col].fillna(0).astype(int)

    df["store_id"] = df["store_id"].astype(int)
    return df[
        [
            "store_id",
            "store_type",
            "assortment",
            "competition_distance",
            "competition_open_since_month",
            "competition_open_since_year",
            "promo2",
            "promo2_since_week",
            "promo2_since_year",
            "promo_interval",
        ]
    ]


def clean_train(train_df: pd.DataFrame) -> pd.DataFrame:
    df = train_df.copy()
    df.columns = [c.strip() for c in df.columns]

    df = df.rename(
        columns={
            "Store": "store_id",
            "DayOfWeek": "day_of_week",
            "Date": "full_date",
            "Sales": "sales",
            "Customers": "customers",
            "Open": "open",
            "Promo": "promo",
            "StateHoliday": "state_holiday",
            "SchoolHoliday": "school_holiday",
        }
    )

    df["full_date"] = pd.to_datetime(df["full_date"], errors="coerce")
    df = df.dropna(subset=["full_date", "store_id", "sales"])

    df["store_id"] = df["store_id"].astype(int)
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0.0)
    df["customers"] = pd.to_numeric(df["customers"], errors="coerce").fillna(0).astype(int)
    df["promo"] = pd.to_numeric(df["promo"], errors="coerce").fillna(0).astype(int)
    df["school_holiday"] = pd.to_numeric(df["school_holiday"], errors="coerce").fillna(0).astype(int)

    if "open" in df.columns:
        df["open"] = pd.to_numeric(df["open"], errors="coerce").fillna(1).astype(int)
    else:
        df["open"] = 1

    df["state_holiday"] = df["state_holiday"].astype(str).replace({"nan": "0"}).fillna("0")

    return df[
        [
            "store_id",
            "full_date",
            "sales",
            "customers",
            "promo",
            "state_holiday",
            "school_holiday",
            "open",
        ]
    ]


def build_date_dimension(train_df: pd.DataFrame) -> pd.DataFrame:
    min_date = train_df["full_date"].min().date()
    max_date = train_df["full_date"].max().date()
    calendar = pd.date_range(min_date, max_date, freq="D")

    dim_date = pd.DataFrame({"full_date": calendar})
    dim_date["day"] = dim_date["full_date"].dt.day
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["year"] = dim_date["full_date"].dt.year
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["week_of_year"] = dim_date["full_date"].dt.isocalendar().week.astype(int)
    dim_date["day_of_week"] = dim_date["full_date"].dt.dayofweek + 1
    dim_date["is_weekend"] = dim_date["day_of_week"].isin([6, 7])
    dim_date["full_date"] = dim_date["full_date"].dt.date
    return dim_date


def prepare_fact(train_df: pd.DataFrame, dim_date_map: pd.DataFrame) -> pd.DataFrame:
    df = train_df.copy()
    df["full_date"] = df["full_date"].dt.date
    fact = df.merge(dim_date_map, on="full_date", how="inner")

    agg = (
        fact.groupby(["store_id", "date_id"], as_index=False)
        .agg(
            sales=("sales", "sum"),
            customers=("customers", "sum"),
            promo=("promo", "max"),
            state_holiday=("state_holiday", "max"),
            school_holiday=("school_holiday", "max"),
            open=("open", "max"),
        )
        .sort_values(["store_id", "date_id"])
    )
    return agg


def insert_dataframe(
    conn,
    table: str,
    columns: list[str],
    rows: list[tuple],
    on_conflict: list[str] | None = None,
    update_columns: list[str] | None = None,
    page_size: int = 5000,
) -> None:
    if not rows:
        return

    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s"
    if on_conflict and update_columns:
        updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
        query += f" ON CONFLICT ({', '.join(on_conflict)}) DO UPDATE SET {updates}"

    with conn.cursor() as cursor:
        execute_values(cursor, query, rows, page_size=page_size)


def run_etl(cfg: ETLConfig) -> None:
    print("[ETL] Loading source data...")
    train_raw, store_raw = load_raw_data(cfg.train_csv, cfg.store_csv)

    print("[ETL] Cleaning and preparing datasets...")
    dim_store = clean_store(store_raw)
    train = clean_train(train_raw)
    dim_date = build_date_dimension(train)
    print(f"[ETL] Rows: dim_store={len(dim_store)}, train={len(train)}, dim_date={len(dim_date)}")

    engine = sa.create_engine(cfg.db_url)

    with engine.begin() as conn:
        raw_conn = conn.connection

        if cfg.truncate_reload:
            print("[ETL] Running truncate + reload strategy...")
            conn.execute(sa.text("TRUNCATE TABLE fact_sales_daily RESTART IDENTITY CASCADE"))
            conn.execute(sa.text("TRUNCATE TABLE dim_date RESTART IDENTITY CASCADE"))
            conn.execute(sa.text("TRUNCATE TABLE dim_store RESTART IDENTITY CASCADE"))

        print("[ETL] Loading dim_store...")
        store_rows = list(dim_store.itertuples(index=False, name=None))
        insert_dataframe(
            raw_conn,
            "dim_store",
            [
                "store_id",
                "store_type",
                "assortment",
                "competition_distance",
                "competition_open_since_month",
                "competition_open_since_year",
                "promo2",
                "promo2_since_week",
                "promo2_since_year",
                "promo_interval",
            ],
            store_rows,
            on_conflict=["store_id"],
            update_columns=[
                "store_type",
                "assortment",
                "competition_distance",
                "competition_open_since_month",
                "competition_open_since_year",
                "promo2",
                "promo2_since_week",
                "promo2_since_year",
                "promo_interval",
            ],
            page_size=cfg.chunksize,
        )

        print("[ETL] Loading dim_date...")
        date_rows = list(dim_date.itertuples(index=False, name=None))
        insert_dataframe(
            raw_conn,
            "dim_date",
            [
                "full_date",
                "day",
                "month",
                "year",
                "quarter",
                "week_of_year",
                "day_of_week",
                "is_weekend",
            ],
            date_rows,
            on_conflict=["full_date"],
            update_columns=["day", "month", "year", "quarter", "week_of_year", "day_of_week", "is_weekend"],
            page_size=cfg.chunksize,
        )

        dim_date_map = pd.read_sql("SELECT date_id, full_date FROM dim_date", conn)
        fact = prepare_fact(train, dim_date_map)
        print(f"[ETL] Rows: fact_sales_daily={len(fact)}")

        print("[ETL] Loading fact_sales_daily...")
        fact_rows = list(fact.itertuples(index=False, name=None))
        insert_dataframe(
            raw_conn,
            "fact_sales_daily",
            [
                "store_id",
                "date_id",
                "sales",
                "customers",
                "promo",
                "state_holiday",
                "school_holiday",
                "open",
            ],
            fact_rows,
            on_conflict=["store_id", "date_id"],
            update_columns=["sales", "customers", "promo", "state_holiday", "school_holiday", "open"],
            page_size=cfg.chunksize,
        )

    print("[ETL] Completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL: load Rossmann dataset into PostgreSQL")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    args = parser.parse_args()

    cfg = load_config(args.config)
    run_etl(cfg)


if __name__ == "__main__":
    main()
