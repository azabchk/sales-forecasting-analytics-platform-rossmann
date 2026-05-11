from datetime import date
from typing import Literal

import sqlalchemy as sa

from app.db import fetch_all, fetch_one
from app.schemas import SalesTimeseriesPoint, StoreComparisonMetrics, StoreItem


def list_stores() -> list[StoreItem]:
    """Return all stores — used by internal services (forecast, chat)."""
    query = sa.text(
        """
        SELECT store_id, store_type, assortment
        FROM dim_store
        ORDER BY store_id;
        """
    )
    rows = fetch_all(query)
    return [StoreItem(**row) for row in rows]


def list_stores_paginated(
    *,
    page: int = 1,
    page_size: int = 100,
    store_type: str | None = None,
    assortment: str | None = None,
) -> dict:
    filters: list[str] = []
    params: dict = {}
    if store_type:
        filters.append("store_type = :store_type")
        params["store_type"] = store_type
    if assortment:
        filters.append("assortment = :assortment")
        params["assortment"] = assortment

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    count_row = fetch_one(sa.text(f"SELECT COUNT(*) AS total FROM dim_store {where}"), params=params)
    total = int(count_row["total"]) if count_row else 0

    data_params = {**params, "limit": page_size, "offset": (page - 1) * page_size}
    rows = fetch_all(
        sa.text(
            f"SELECT store_id, store_type, assortment FROM dim_store {where}"
            " ORDER BY store_id LIMIT :limit OFFSET :offset"
        ),
        params=data_params,
    )
    return {"items": [StoreItem(**r) for r in rows], "total": total, "page": page, "page_size": page_size}


def get_store_by_id(store_id: int) -> StoreItem | None:
    row = fetch_one(
        sa.text("SELECT store_id, store_type, assortment FROM dim_store WHERE store_id = :sid"),
        params={"sid": store_id},
    )
    return StoreItem(**row) if row else None


def get_store_comparison(
    store_ids: list[int],
    date_from: date,
    date_to: date,
) -> list[StoreComparisonMetrics]:
    query = sa.text(
        """
        SELECT
            s.store_id,
            s.store_type,
            s.assortment,
            COALESCE(s.competition_distance, 0)                             AS competition_distance,
            COALESCE(SUM(f.sales), 0)                                       AS total_sales,
            COALESCE(AVG(f.sales), 0)                                       AS avg_daily_sales,
            COALESCE(SUM(f.customers), 0)                                   AS total_customers,
            COALESCE(AVG(f.customers), 0)                                   AS avg_daily_customers,
            SUM(CASE WHEN COALESCE(f.promo,0)=1 THEN 1 ELSE 0 END)         AS promo_days,
            SUM(CASE WHEN COALESCE(f.open,1)=1 THEN 1 ELSE 0 END)          AS open_days,
            AVG(CASE WHEN COALESCE(f.promo,0)=1 THEN f.sales ELSE NULL END) AS avg_promo_sales,
            AVG(CASE WHEN COALESCE(f.promo,0)=0 THEN f.sales ELSE NULL END) AS avg_no_promo_sales
        FROM dim_store s
        LEFT JOIN fact_sales_daily f ON f.store_id = s.store_id
        LEFT JOIN dim_date d ON d.date_id = f.date_id AND d.full_date BETWEEN :date_from AND :date_to
        WHERE s.store_id = ANY(:store_ids)
        GROUP BY s.store_id, s.store_type, s.assortment, s.competition_distance
        ORDER BY total_sales DESC
        """
    )
    rows = fetch_all(query, params={"store_ids": store_ids, "date_from": date_from, "date_to": date_to})
    results: list[StoreComparisonMetrics] = []
    for row in rows:
        promo_s = float(row.get("avg_promo_sales") or 0.0)
        no_promo_s = float(row.get("avg_no_promo_sales") or 0.0)
        uplift = round((promo_s - no_promo_s) / no_promo_s * 100, 2) if no_promo_s > 0 else None
        results.append(
            StoreComparisonMetrics(
                store_id=int(row["store_id"]),
                store_type=row.get("store_type"),
                assortment=row.get("assortment"),
                competition_distance=float(row.get("competition_distance") or 0.0),
                total_sales=float(row["total_sales"]),
                avg_daily_sales=float(row["avg_daily_sales"]),
                total_customers=float(row["total_customers"]),
                avg_daily_customers=float(row["avg_daily_customers"]),
                promo_days=int(row["promo_days"]),
                open_days=int(row["open_days"]),
                promo_uplift_pct=uplift,
            )
        )
    return results


def get_sales_timeseries(
    granularity: Literal["daily", "monthly"],
    date_from: date,
    date_to: date,
    store_id: int | None = None,
) -> list[SalesTimeseriesPoint]:
    if granularity == "daily":
        view_name = "v_sales_timeseries_daily"
        date_col = "full_date"
        select_cols = "full_date AS date, store_id, sales, customers, promo, open"
    else:
        view_name = "v_sales_timeseries_monthly"
        date_col = "month_start"
        select_cols = "month_start AS date, store_id, sales, customers, NULL::int AS promo, NULL::int AS open"

    filters = [f"{date_col} BETWEEN :date_from AND :date_to"]
    params: dict = {"date_from": date_from, "date_to": date_to}

    if store_id is not None:
        filters.append("store_id = :store_id")
        params["store_id"] = store_id

    query = sa.text(
        f"""
        SELECT {select_cols}
        FROM {view_name}
        WHERE {' AND '.join(filters)}
        ORDER BY date, store_id;
        """
    )

    rows = fetch_all(query, params=params)
    return [SalesTimeseriesPoint(**row) for row in rows]
