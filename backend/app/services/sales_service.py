from datetime import date
from typing import Literal

import sqlalchemy as sa

from app.db import fetch_all
from app.schemas import SalesTimeseriesPoint, StoreItem


def list_stores() -> list[StoreItem]:
    query = sa.text(
        """
        SELECT store_id, store_type, assortment
        FROM dim_store
        ORDER BY store_id;
        """
    )
    rows = fetch_all(query)
    return [StoreItem(**row) for row in rows]


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
