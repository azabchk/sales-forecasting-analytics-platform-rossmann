from datetime import date

import sqlalchemy as sa

from app.db import fetch_all, fetch_one
from app.schemas import KpiSummaryResponse, PromoImpactPoint


def get_kpi_summary(date_from: date, date_to: date, store_id: int | None = None) -> KpiSummaryResponse:
    filters = ["full_date BETWEEN :date_from AND :date_to"]
    params: dict = {"date_from": date_from, "date_to": date_to}

    if store_id is not None:
        filters.append("store_id = :store_id")
        params["store_id"] = store_id

    query = sa.text(
        f"""
        WITH filtered AS (
            SELECT full_date, store_id, total_sales, total_customers, promo_days, open_days
            FROM v_kpi_summary
            WHERE {' AND '.join(filters)}
        ),
        per_day AS (
            SELECT
                full_date,
                SUM(total_sales) AS day_sales
            FROM filtered
            GROUP BY full_date
        )
        SELECT
            COALESCE((SELECT SUM(total_sales) FROM filtered), 0) AS total_sales,
            COALESCE((SELECT SUM(total_customers) FROM filtered), 0) AS total_customers,
            COALESCE((SELECT AVG(day_sales) FROM per_day), 0) AS avg_daily_sales,
            COALESCE((SELECT SUM(promo_days) FROM filtered), 0) AS promo_days,
            COALESCE((SELECT SUM(open_days) FROM filtered), 0) AS open_days;
        """
    )

    row = fetch_one(query, params=params) or {}

    return KpiSummaryResponse(
        date_from=date_from,
        date_to=date_to,
        store_id=store_id,
        total_sales=float(row.get("total_sales", 0.0)),
        total_customers=float(row.get("total_customers", 0.0)),
        avg_daily_sales=float(row.get("avg_daily_sales", 0.0)),
        promo_days=int(row.get("promo_days", 0)),
        open_days=int(row.get("open_days", 0)),
    )


def get_promo_impact(store_id: int | None = None) -> list[PromoImpactPoint]:
    query = "SELECT store_id, promo_flag, avg_sales, avg_customers, num_days FROM v_promo_impact"
    params: dict = {}
    if store_id is not None:
        query += " WHERE store_id = :store_id"
        params["store_id"] = store_id
    query += " ORDER BY store_id, promo_flag"

    rows = fetch_all(sa.text(query), params=params)
    return [PromoImpactPoint(**row) for row in rows]
