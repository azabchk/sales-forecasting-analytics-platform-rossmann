from __future__ import annotations

import argparse
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
import yaml
from dotenv import load_dotenv
from psycopg2.extras import execute_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_runner import PreflightEnforcementError, PreflightResult, run_preflight
from src.etl.data_source_registry import resolve_data_source_id
from src.etl.etl_run_registry import upsert_etl_run

SUPPORTED_PREFLIGHT_MODES = {"off", "report_only", "enforce"}


@dataclass
class ETLConfig:
    train_csv: str
    store_csv: str
    db_url: str
    truncate_reload: bool
    chunksize: int
    preflight_mode: str
    preflight_profile_train: str
    preflight_profile_store: str
    preflight_contract_path: str
    preflight_artifact_dir: str
    preflight_contract_id: str = "rossmann_input_contract"
    data_source_id: int | None = None


def _resolve_path(value: str, base_dir: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path.resolve())
    return str((base_dir / path).resolve())


def _resolve_preflight_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized not in SUPPORTED_PREFLIGHT_MODES:
        raise ValueError(f"Unsupported preflight mode '{mode}'. Expected one of {sorted(SUPPORTED_PREFLIGHT_MODES)}")
    return normalized


def _parse_optional_int(value: str | int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def load_config(path: str, cli_overrides: dict[str, str | None] | None = None) -> ETLConfig:
    config_path = Path(path).resolve()
    project_root = config_path.parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)
    overrides = cli_overrides or {}

    with open(config_path, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    db_url = os.getenv(cfg["database"]["url_env"])
    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment or .env")

    preflight_cfg = cfg.get("preflight", {})
    if not isinstance(preflight_cfg, dict):
        preflight_cfg = {}

    cfg_profile_mapping = preflight_cfg.get("profile_mapping", {})
    if not isinstance(cfg_profile_mapping, dict):
        cfg_profile_mapping = {}

    profile_fallback = (
        overrides.get("preflight_profile")
        or os.getenv("PREFLIGHT_PROFILE")
        or str(preflight_cfg.get("profile", "")).strip()
        or None
    )
    preflight_profile_train = (
        overrides.get("preflight_profile_train")
        or os.getenv("PREFLIGHT_PROFILE_TRAIN")
        or profile_fallback
        or str(cfg_profile_mapping.get("train", "rossmann_train"))
    )
    preflight_profile_store = (
        overrides.get("preflight_profile_store")
        or os.getenv("PREFLIGHT_PROFILE_STORE")
        or profile_fallback
        or str(cfg_profile_mapping.get("store", "rossmann_store"))
    )

    mode_value = overrides.get("preflight_mode") or os.getenv("PREFLIGHT_MODE") or str(preflight_cfg.get("mode", "off"))
    preflight_mode = _resolve_preflight_mode(mode_value)

    contract_from_cfg = str(preflight_cfg.get("contract_path", "../config/input_contract/contract_v1.yaml"))
    contract_from_override = overrides.get("preflight_contract") or os.getenv("PREFLIGHT_CONTRACT_PATH")
    preflight_contract_path = (
        _resolve_path(contract_from_override, project_root)
        if contract_from_override
        else _resolve_path(contract_from_cfg, config_path.parent)
    )

    artifacts_from_cfg = str(preflight_cfg.get("artifact_dir", "reports/preflight"))
    artifacts_from_override = overrides.get("preflight_artifact_dir") or os.getenv("PREFLIGHT_ARTIFACT_DIR")
    preflight_artifact_dir = (
        _resolve_path(artifacts_from_override, project_root)
        if artifacts_from_override
        else _resolve_path(artifacts_from_cfg, config_path.parent)
    )

    preflight_contract_id = (
        overrides.get("preflight_contract_id")
        or os.getenv("PREFLIGHT_CONTRACT_ID")
        or str(preflight_cfg.get("contract_id", "rossmann_input_contract"))
    )

    data_source_raw = overrides.get("data_source_id") or os.getenv("DATA_SOURCE_ID") or cfg.get("etl", {}).get("data_source_id")
    data_source_id = _parse_optional_int(data_source_raw, field_name="data_source_id")

    return ETLConfig(
        train_csv=str((config_path.parent / cfg["paths"]["train_csv"]).resolve()),
        store_csv=str((config_path.parent / cfg["paths"]["store_csv"]).resolve()),
        db_url=db_url,
        truncate_reload=bool(cfg["etl"].get("truncate_reload", True)),
        chunksize=int(cfg["etl"].get("chunksize", 50000)),
        preflight_mode=preflight_mode,
        preflight_profile_train=preflight_profile_train,
        preflight_profile_store=preflight_profile_store,
        preflight_contract_path=preflight_contract_path,
        preflight_artifact_dir=preflight_artifact_dir,
        preflight_contract_id=str(preflight_contract_id).strip() or "rossmann_input_contract",
        data_source_id=data_source_id,
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


def run_preflight_hook(cfg: ETLConfig) -> tuple[str, str, dict[str, PreflightResult]]:
    if cfg.preflight_mode == "off":
        print("[ETL][Preflight] mode=off -> using raw inputs")
        return cfg.train_csv, cfg.store_csv, {}

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"[ETL][Preflight] mode={cfg.preflight_mode} run_id={run_id}")

    results: dict[str, PreflightResult] = {}
    items = [
        ("train", cfg.train_csv, cfg.preflight_profile_train),
        ("store", cfg.store_csv, cfg.preflight_profile_store),
    ]

    for source_name, source_path, profile_name in items:
        print(f"[ETL][Preflight][{source_name}] validating '{source_path}' with profile '{profile_name}'")
        try:
            result = run_preflight(
                raw_input_path=source_path,
                profile_name=profile_name,
                contract_path=cfg.preflight_contract_path,
                mode=cfg.preflight_mode,
                artifact_root=cfg.preflight_artifact_dir,
                source_name=source_name,
                run_id=run_id,
                data_source_id=cfg.data_source_id,
                contract_id=cfg.preflight_contract_id,
            )
        except PreflightEnforcementError as exc:
            result = exc.result
            print(
                f"[ETL][Preflight][{source_name}] status="
                f"validation={result.validation_status}, semantic={result.semantic_status} (blocked in enforce mode)"
            )
            if result.validation_report_path:
                print(f"[ETL][Preflight][{source_name}] validation report: {result.validation_report_path}")
            if result.semantic_report_path:
                print(f"[ETL][Preflight][{source_name}] semantic report: {result.semantic_report_path}")
            if result.semantic_summary:
                print(result.semantic_summary)
            raise ValueError(
                f"Preflight blocked ETL for '{source_name}'. "
                f"Fix input errors or switch mode to report_only/off. "
                f"Validation report: {result.validation_report_path}; "
                f"Semantic report: {result.semantic_report_path}"
            ) from exc

        results[source_name] = result
        print(
            f"[ETL][Preflight][{source_name}] status="
            f"validation={result.validation_status}, semantic={result.semantic_status}"
        )
        if result.validation_report_path:
            print(f"[ETL][Preflight][{source_name}] validation report: {result.validation_report_path}")
        if result.semantic_report_path:
            print(f"[ETL][Preflight][{source_name}] semantic report: {result.semantic_report_path}")
        if result.semantic_summary:
            print(result.semantic_summary)
        if result.unification_manifest_path:
            print(f"[ETL][Preflight][{source_name}] unification manifest: {result.unification_manifest_path}")
        if result.preflight_report_path:
            print(f"[ETL][Preflight][{source_name}] preflight report: {result.preflight_report_path}")
        if result.mode == "enforce":
            print(f"[ETL][Preflight][{source_name}] ETL input switched to unified: {result.etl_input_path}")
        else:
            print(f"[ETL][Preflight][{source_name}] ETL input remains raw: {result.etl_input_path}")

    return results["train"].etl_input_path, results["store"].etl_input_path, results


def run_etl(cfg: ETLConfig) -> None:
    resolved_data_source_id = resolve_data_source_id(cfg.data_source_id)
    cfg.data_source_id = resolved_data_source_id
    run_id = f"etl_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(timezone.utc)
    upsert_etl_run(
        {
            "run_id": run_id,
            "status": "RUNNING",
            "started_at": started_at,
            "data_source_id": resolved_data_source_id,
            "preflight_mode": cfg.preflight_mode,
            "train_input_path": cfg.train_csv,
            "store_input_path": cfg.store_csv,
            "summary_json": {},
        }
    )

    print("[ETL] Loading source data...")
    try:
        train_input, store_input, _ = run_preflight_hook(cfg)
        train_raw, store_raw = load_raw_data(train_input, store_input)

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

        upsert_etl_run(
            {
                "run_id": run_id,
                "status": "COMPLETED",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc),
                "data_source_id": resolved_data_source_id,
                "preflight_mode": cfg.preflight_mode,
                "train_input_path": train_input,
                "store_input_path": store_input,
                "summary_json": {
                    "dim_store_rows": int(len(dim_store)),
                    "train_rows": int(len(train)),
                    "dim_date_rows": int(len(dim_date)),
                    "fact_rows": int(len(fact)),
                },
            }
        )
        print("[ETL] Completed successfully.")
    except Exception as exc:
        upsert_etl_run(
            {
                "run_id": run_id,
                "status": "FAILED",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc),
                "data_source_id": resolved_data_source_id,
                "preflight_mode": cfg.preflight_mode,
                "summary_json": {},
                "error_message": str(exc),
            }
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL: load Rossmann dataset into PostgreSQL")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument(
        "--preflight-mode",
        choices=sorted(SUPPORTED_PREFLIGHT_MODES),
        default=None,
        help="Preflight mode override: off | report_only | enforce",
    )
    parser.add_argument("--preflight-profile", default=None, help="Preflight profile override for both train/store")
    parser.add_argument("--preflight-profile-train", default=None, help="Preflight profile override for train input")
    parser.add_argument("--preflight-profile-store", default=None, help="Preflight profile override for store input")
    parser.add_argument("--preflight-contract", default=None, help="Path to input contract YAML")
    parser.add_argument("--preflight-artifact-dir", default=None, help="Directory root for preflight artifacts")
    parser.add_argument("--data-source-id", default=None, help="Optional data source id override")
    args = parser.parse_args()

    cfg = load_config(
        args.config,
        cli_overrides={
            "preflight_mode": args.preflight_mode,
            "preflight_profile": args.preflight_profile,
            "preflight_profile_train": args.preflight_profile_train,
            "preflight_profile_store": args.preflight_profile_store,
            "preflight_contract": args.preflight_contract,
            "preflight_artifact_dir": args.preflight_artifact_dir,
            "data_source_id": args.data_source_id,
        },
    )
    run_etl(cfg)


if __name__ == "__main__":
    main()
