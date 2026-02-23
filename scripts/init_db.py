from __future__ import annotations

import argparse
import os
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv

DEFAULT_SQL_FILES = ["01_schema.sql", "02_views_kpi.sql", "03_indexes.sql", "04_v2_ecosystem.sql"]


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def load_database_url(repo_root: Path) -> str:
    load_dotenv(dotenv_path=repo_root / ".env", override=False)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found. Create .env from .env.example first.")
    return db_url


def run_sql_file(conn: sa.Connection, sql_file: Path) -> None:
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")

    sql_script = sql_file.read_text(encoding="utf-8-sig")
    raw_conn = conn.connection
    with raw_conn.cursor() as cursor:
        cursor.execute(sql_script)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize PostgreSQL schema/views/indexes from SQL scripts")
    parser.add_argument("--sql-dir", default="sql", help="Directory with SQL files")
    parser.add_argument(
        "--files",
        nargs="+",
        default=DEFAULT_SQL_FILES,
        help="SQL files execution order",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sql_dir = resolve_path(repo_root, args.sql_dir)
    db_url = load_database_url(repo_root)

    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        for file_name in args.files:
            sql_path = resolve_path(sql_dir, file_name)
            print(f"[DB INIT] Running {sql_path}")
            run_sql_file(conn, sql_path)

    print("[DB INIT] Completed successfully.")


if __name__ == "__main__":
    main()
