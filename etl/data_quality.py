import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
import yaml
from dotenv import load_dotenv


def load_db_url(config_path: str) -> str:
    cfg_path = Path(config_path).resolve()
    project_root = cfg_path.parents[1]
    load_dotenv(dotenv_path=project_root / ".env", override=False)

    with open(cfg_path, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    env_name = cfg["database"]["url_env"]
    db_url = os.getenv(env_name)
    if not db_url:
        raise ValueError(f"Переменная окружения {env_name} не задана")
    return db_url


def check_missing_values(conn) -> list[str]:
    issues = []
    query = """
    SELECT
      SUM(CASE WHEN store_id IS NULL THEN 1 ELSE 0 END) AS miss_store,
      SUM(CASE WHEN date_id IS NULL THEN 1 ELSE 0 END) AS miss_date,
      SUM(CASE WHEN sales IS NULL THEN 1 ELSE 0 END) AS miss_sales
    FROM fact_sales_daily;
    """
    row = conn.execute(sa.text(query)).mappings().first()
    if row and (row["miss_store"] > 0 or row["miss_date"] > 0 or row["miss_sales"] > 0):
        issues.append(f"Найдены NULL в fact_sales_daily: {dict(row)}")
    return issues


def check_duplicates(conn) -> list[str]:
    issues = []
    query = """
    SELECT store_id, date_id, COUNT(*) AS cnt
    FROM fact_sales_daily
    GROUP BY store_id, date_id
    HAVING COUNT(*) > 1
    LIMIT 10;
    """
    dup_df = pd.read_sql(query, conn)
    if not dup_df.empty:
        issues.append(f"Найдены дубликаты store_id/date_id, примеры: {dup_df.to_dict(orient='records')}")
    return issues


def check_date_coverage(conn) -> list[str]:
    issues = []
    range_query = """
    SELECT MIN(full_date) AS min_date, MAX(full_date) AS max_date
    FROM dim_date;
    """
    range_row = conn.execute(sa.text(range_query)).mappings().first()

    gap_query = """
    SELECT COUNT(*) AS gap_days
    FROM (
      SELECT d.full_date,
             LEAD(d.full_date) OVER (ORDER BY d.full_date) AS next_date
      FROM dim_date d
    ) t
    WHERE next_date IS NOT NULL
      AND next_date <> full_date + INTERVAL '1 day';
    """
    gap_row = conn.execute(sa.text(gap_query)).mappings().first()

    if range_row:
        print(f"[DQ] Диапазон дат: {range_row['min_date']} .. {range_row['max_date']}")
    if gap_row and gap_row["gap_days"] > 0:
        issues.append(f"Найдены разрывы в dim_date: {gap_row['gap_days']}")
    return issues


def check_fk_integrity(conn) -> list[str]:
    issues = []
    query = """
    SELECT COUNT(*) AS broken_fk
    FROM fact_sales_daily f
    LEFT JOIN dim_store s ON s.store_id = f.store_id
    LEFT JOIN dim_date d ON d.date_id = f.date_id
    WHERE s.store_id IS NULL OR d.date_id IS NULL;
    """
    row = conn.execute(sa.text(query)).mappings().first()
    if row and row["broken_fk"] > 0:
        issues.append(f"Нарушена ссылочная целостность fact -> dims: {row['broken_fk']}")
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Data quality checks for Rossmann DWH")
    parser.add_argument("--config", required=True, help="Путь к YAML конфигу")
    args = parser.parse_args()

    db_url = load_db_url(args.config)
    engine = sa.create_engine(db_url)

    all_issues: list[str] = []
    with engine.connect() as conn:
        all_issues.extend(check_missing_values(conn))
        all_issues.extend(check_duplicates(conn))
        all_issues.extend(check_date_coverage(conn))
        all_issues.extend(check_fk_integrity(conn))

    if all_issues:
        print("[DQ] Обнаружены проблемы:")
        for issue in all_issues:
            print(f"- {issue}")
        sys.exit(1)

    print("[DQ] Все проверки пройдены успешно.")


if __name__ == "__main__":
    main()
