from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import sqlalchemy as sa

from app.db import engine
from app.services.forecast_service import forecast_scenario_for_store

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.data_source_registry import resolve_data_source_id
from src.etl.forecast_run_registry import upsert_forecast_run


def _max_segment_stores() -> int:
    raw = str(os.getenv("SCENARIO_MAX_SEGMENT_STORES", "50")).strip()
    try:
        value = int(raw)
    except ValueError:
        value = 50
    return max(1, min(value, 500))


def _price_elasticity() -> float:
    raw = str(os.getenv("SCENARIO_PRICE_ELASTICITY", "1.0")).strip()
    try:
        value = float(raw)
    except ValueError:
        value = 1.0
    return value


def _resolve_segment_store_ids(
    *,
    store_type: str | None = None,
    assortment: str | None = None,
    promo2: int | None = None,
    limit: int,
) -> list[int]:
    filters: list[str] = []
    params: dict[str, Any] = {}
    if store_type is not None and str(store_type).strip():
        filters.append("LOWER(COALESCE(store_type, '')) = :store_type")
        params["store_type"] = str(store_type).strip().lower()
    if assortment is not None and str(assortment).strip():
        filters.append("LOWER(COALESCE(assortment, '')) = :assortment")
        params["assortment"] = str(assortment).strip().lower()
    if promo2 is not None:
        filters.append("COALESCE(promo2, 0) = :promo2")
        params["promo2"] = int(promo2)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = sa.text(
        f"""
        SELECT store_id
        FROM dim_store
        {where_clause}
        ORDER BY store_id
        LIMIT :limit
        """
    )
    params["limit"] = int(limit)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [int(row["store_id"]) for row in rows]


def _aggregate_scenario_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"points": [], "summary": {}}
    horizon_days = len(results[0]["points"])
    points: list[dict[str, Any]] = []
    for index in range(horizon_days):
        date_value = results[0]["points"][index]["date"]
        baseline = float(sum(float(item["points"][index]["baseline_sales"]) for item in results))
        scenario = float(sum(float(item["points"][index]["scenario_sales"]) for item in results))
        delta = float(scenario - baseline)
        scenario_lower = float(sum(float(item["points"][index]["scenario_lower"]) for item in results))
        scenario_upper = float(sum(float(item["points"][index]["scenario_upper"]) for item in results))
        points.append(
            {
                "date": date_value,
                "baseline_sales": baseline,
                "scenario_sales": scenario,
                "delta_sales": delta,
                "scenario_lower": scenario_lower,
                "scenario_upper": scenario_upper,
            }
        )

    total_baseline = float(sum(point["baseline_sales"] for point in points))
    total_scenario = float(sum(point["scenario_sales"] for point in points))
    total_delta = float(total_scenario - total_baseline)
    uplift_pct = float((total_delta / total_baseline) * 100.0) if total_baseline > 0 else 0.0
    avg_daily_delta = float(total_delta / len(points)) if points else 0.0
    max_delta_point = max(points, key=lambda item: float(item["delta_sales"])) if points else None

    return {
        "points": points,
        "summary": {
            "total_baseline_sales": total_baseline,
            "total_scenario_sales": total_scenario,
            "total_delta_sales": total_delta,
            "uplift_pct": uplift_pct,
            "avg_daily_delta": avg_daily_delta,
            "max_delta_date": max_delta_point["date"] if max_delta_point else None,
            "max_delta_value": float(max_delta_point["delta_sales"]) if max_delta_point else 0.0,
        },
    }


def run_scenario_v2(
    *,
    store_id: int | None,
    segment: dict[str, Any] | None,
    price_change_pct: float,
    promo_mode: str,
    weekend_open: bool,
    school_holiday: int,
    demand_shift_pct: float,
    confidence_level: float,
    horizon_days: int,
    data_source_id: int | None = None,
) -> dict[str, Any]:
    run_id = f"scenario_v2_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    resolved_data_source_id = resolve_data_source_id(data_source_id)
    started_at = datetime.now(timezone.utc)
    request_json: dict[str, Any] = {
        "store_id": store_id,
        "segment": segment or {},
        "price_change_pct": price_change_pct,
        "promo_mode": promo_mode,
        "weekend_open": weekend_open,
        "school_holiday": school_holiday,
        "demand_shift_pct": demand_shift_pct,
        "confidence_level": confidence_level,
        "horizon_days": horizon_days,
        "data_source_id": resolved_data_source_id,
    }

    upsert_forecast_run(
        {
            "run_id": run_id,
            "created_at": started_at,
            "run_type": "scenario_v2",
            "status": "RUNNING",
            "data_source_id": resolved_data_source_id,
            "store_id": store_id,
            "request_json": request_json,
            "summary_json": {},
        }
    )

    try:
        elasticity = _price_elasticity()
        price_effect_pct = -elasticity * float(price_change_pct)
        effective_demand_shift_pct = float(demand_shift_pct) + price_effect_pct

        if store_id is not None and segment:
            raise ValueError("Use either store_id or segment, not both")
        if store_id is None and not segment:
            raise ValueError("Either store_id or segment is required")

        if store_id is not None:
            scenario_result = forecast_scenario_for_store(
                store_id=int(store_id),
                horizon_days=int(horizon_days),
                promo_mode=promo_mode,
                weekend_open=weekend_open,
                school_holiday=int(school_holiday),
                demand_shift_pct=effective_demand_shift_pct,
                confidence_level=confidence_level,
                data_source_id=resolved_data_source_id,
                _record_run=False,
            )
            response = {
                "run_id": run_id,
                "target": {"mode": "store", "store_id": int(store_id)},
                "assumptions": {
                    "price_change_pct": float(price_change_pct),
                    "price_elasticity": elasticity,
                    "price_effect_pct": price_effect_pct,
                    "effective_demand_shift_pct": effective_demand_shift_pct,
                },
                "request": request_json,
                "summary": scenario_result["summary"],
                "points": scenario_result["points"],
            }
        else:
            segment_payload = segment or {}
            store_ids = _resolve_segment_store_ids(
                store_type=segment_payload.get("store_type"),
                assortment=segment_payload.get("assortment"),
                promo2=segment_payload.get("promo2"),
                limit=_max_segment_stores(),
            )
            if not store_ids:
                raise ValueError("No stores found for the provided segment filter")

            scenario_results: list[dict[str, Any]] = []
            for resolved_store_id in store_ids:
                scenario_results.append(
                    forecast_scenario_for_store(
                        store_id=resolved_store_id,
                        horizon_days=int(horizon_days),
                        promo_mode=promo_mode,
                        weekend_open=weekend_open,
                        school_holiday=int(school_holiday),
                        demand_shift_pct=effective_demand_shift_pct,
                        confidence_level=confidence_level,
                        data_source_id=resolved_data_source_id,
                        _record_run=False,
                    )
                )

            aggregate = _aggregate_scenario_results(scenario_results)
            response = {
                "run_id": run_id,
                "target": {
                    "mode": "segment",
                    "segment": segment_payload,
                    "stores_count": len(store_ids),
                    "store_ids": store_ids,
                },
                "assumptions": {
                    "price_change_pct": float(price_change_pct),
                    "price_elasticity": elasticity,
                    "price_effect_pct": price_effect_pct,
                    "effective_demand_shift_pct": effective_demand_shift_pct,
                },
                "request": request_json,
                "summary": aggregate["summary"],
                "points": aggregate["points"],
            }

        upsert_forecast_run(
            {
                "run_id": run_id,
                "created_at": started_at,
                "run_type": "scenario_v2",
                "status": "COMPLETED",
                "data_source_id": resolved_data_source_id,
                "store_id": store_id,
                "request_json": request_json,
                "summary_json": {
                    "total_points": len(response.get("points", [])),
                    "target_mode": response.get("target", {}).get("mode"),
                    "uplift_pct": response.get("summary", {}).get("uplift_pct"),
                },
            }
        )
        return response
    except Exception as exc:
        upsert_forecast_run(
            {
                "run_id": run_id,
                "created_at": started_at,
                "run_type": "scenario_v2",
                "status": "FAILED",
                "data_source_id": resolved_data_source_id,
                "store_id": store_id,
                "request_json": request_json,
                "summary_json": {},
                "error_message": str(exc),
            }
        )
        raise
