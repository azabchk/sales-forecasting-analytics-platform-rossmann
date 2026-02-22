from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import sqlalchemy as sa

from app.config import get_settings
from app.db import fetch_all, fetch_one
from app.schemas import ChatInsight, ChatResponse
from app.services.forecast_service import forecast_for_store
from app.services.kpi_service import get_kpi_summary
from app.services.system_service import get_model_metadata, get_system_summary

_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_STORE_PATTERN = re.compile(
    r"(?:store(?:_id)?\s*#?\s*|store_id\s*=?\s*|(?:ل)?(?:ل)?(?:ال)?متجر\s*#?\s*|(?:ال)?متجر\s*#?\s*)(\d+)",
    re.IGNORECASE,
)
_HORIZON_PATTERN = re.compile(r"\b(\d{1,3})\s*(?:day|days|d|يوم|ايام)\b", re.IGNORECASE)


def _format_number(value: float) -> str:
    return f"{value:,.0f}"


def _extract_store_id(message: str) -> int | None:
    match = _STORE_PATTERN.search(message)
    if not match:
        return None
    return int(match.group(1))


def _extract_horizon(message: str, default_days: int = 30) -> int:
    match = _HORIZON_PATTERN.search(message)
    if not match:
        return default_days
    return max(1, min(180, int(match.group(1))))


def _latest_data_date() -> date:
    row = fetch_one(
        sa.text(
            """
            SELECT MAX(d.full_date) AS latest_date
            FROM fact_sales_daily f
            JOIN dim_date d ON d.date_id = f.date_id
            """
        )
    )
    latest_date = row.get("latest_date") if row else None
    if latest_date is None:
        return date.today()
    return latest_date


def _extract_date_range(message: str) -> tuple[date, date]:
    matches = _DATE_PATTERN.findall(message)
    if len(matches) >= 2:
        first = date.fromisoformat(matches[0])
        second = date.fromisoformat(matches[1])
        return (first, second) if first <= second else (second, first)

    latest = _latest_data_date()
    if len(matches) == 1:
        end_date = date.fromisoformat(matches[0])
        start_date = end_date - timedelta(days=29)
        return start_date, end_date

    return latest - timedelta(days=29), latest


def _chat_system_summary() -> ChatResponse:
    summary = get_system_summary()
    return ChatResponse(
        answer=(
            f"Current platform coverage includes {summary['stores_count']:,} stores and "
            f"{summary['sales_rows_count']:,} daily sales rows from {summary['date_from']} to {summary['date_to']}."
        ),
        insights=[
            ChatInsight(label="Stores", value=f"{summary['stores_count']:,}"),
            ChatInsight(label="Sales Rows", value=f"{summary['sales_rows_count']:,}"),
            ChatInsight(label="Date Range", value=f"{summary['date_from']} to {summary['date_to']}"),
        ],
        suggestions=[
            "Show top 5 stores by total sales",
            "What is the promo impact for store 1?",
            "Forecast store 1 for 30 days",
        ],
    )


def _chat_model_summary() -> ChatResponse:
    metadata = get_model_metadata()
    metrics = metadata.get("metrics", {})
    selected = metadata.get("selected_model", "unknown")
    selected_metrics = metrics.get(selected, {})
    mae = selected_metrics.get("mae")
    rmse = selected_metrics.get("rmse")
    mape = selected_metrics.get("mape")

    answer = (
        f"The active model is {selected}. "
        f"Validation quality is MAE={mae:.2f}, RMSE={rmse:.2f}, MAPE={mape:.2f}%."
        if isinstance(mae, (int, float)) and isinstance(rmse, (int, float)) and isinstance(mape, (int, float))
        else f"The active model is {selected}. Detailed metrics are available in Model Intelligence."
    )

    top_features = metadata.get("top_feature_importance", [])[:3]
    feature_text = ", ".join(str(item.get("feature")) for item in top_features if item.get("feature"))
    if feature_text:
        answer = f"{answer} Top drivers: {feature_text}."

    insights = [ChatInsight(label="Selected Model", value=str(selected))]
    if isinstance(mae, (int, float)):
        insights.append(ChatInsight(label="MAE", value=f"{mae:.2f}"))
    if isinstance(rmse, (int, float)):
        insights.append(ChatInsight(label="RMSE", value=f"{rmse:.2f}"))
    if isinstance(mape, (int, float)):
        insights.append(ChatInsight(label="MAPE", value=f"{mape:.2f}%"))

    return ChatResponse(
        answer=answer,
        insights=insights,
        suggestions=[
            "What is the system data coverage?",
            "Show top 5 stores by total sales",
            "Forecast store 1 for 30 days",
        ],
    )


def _chat_top_stores() -> ChatResponse:
    rows = fetch_all(
        sa.text(
            """
            SELECT store_id, total_sales
            FROM v_top_stores_by_sales
            ORDER BY total_sales DESC
            LIMIT 5
            """
        )
    )
    if not rows:
        return ChatResponse(answer="No sales rows are available yet for top-store analysis.")

    ranked = ", ".join(f"Store {row['store_id']} ({_format_number(float(row['total_sales']))})" for row in rows)
    return ChatResponse(
        answer=f"Top 5 stores by total sales: {ranked}.",
        insights=[
            ChatInsight(label="Top Store", value=str(rows[0]["store_id"])),
            ChatInsight(label="Top Store Sales", value=_format_number(float(rows[0]["total_sales"]))),
            ChatInsight(label="Stores Ranked", value="5"),
        ],
        suggestions=[
            "What is the promo impact for store 1?",
            "Forecast store 1 for 30 days",
            "Show KPI summary for 2015-07-01 to 2015-07-31",
        ],
    )


def _chat_promo_impact(message: str) -> ChatResponse:
    store_id = _extract_store_id(message)
    if store_id is not None:
        rows = fetch_all(
            sa.text(
                """
                SELECT promo_flag, avg_sales
                FROM v_promo_impact
                WHERE store_id = :store_id
                """
            ),
            {"store_id": store_id},
        )
        if len(rows) < 2:
            return ChatResponse(answer=f"Promo impact is not available for store {store_id}.")
        promo_sales = next((float(row["avg_sales"]) for row in rows if row["promo_flag"] == "promo"), 0.0)
        base_sales = next((float(row["avg_sales"]) for row in rows if row["promo_flag"] == "no_promo"), 0.0)
        uplift = ((promo_sales - base_sales) / base_sales * 100.0) if base_sales > 0 else 0.0
        return ChatResponse(
            answer=(
                f"For store {store_id}, average sales are {_format_number(promo_sales)} on promo days "
                f"vs {_format_number(base_sales)} on non-promo days ({uplift:+.1f}% uplift)."
            ),
            insights=[
                ChatInsight(label="Store", value=str(store_id)),
                ChatInsight(label="Promo Avg Sales", value=_format_number(promo_sales)),
                ChatInsight(label="No-Promo Avg Sales", value=_format_number(base_sales)),
            ],
            suggestions=[
                f"Forecast store {store_id} for 30 days",
                "Show top 5 stores by total sales",
                "What is the system data coverage?",
            ],
        )

    rows = fetch_all(
        sa.text(
            """
            SELECT promo_flag, AVG(avg_sales) AS avg_sales
            FROM v_promo_impact
            GROUP BY promo_flag
            """
        )
    )
    promo_sales = next((float(row["avg_sales"]) for row in rows if row["promo_flag"] == "promo"), 0.0)
    base_sales = next((float(row["avg_sales"]) for row in rows if row["promo_flag"] == "no_promo"), 0.0)
    uplift = ((promo_sales - base_sales) / base_sales * 100.0) if base_sales > 0 else 0.0
    return ChatResponse(
        answer=(
            f"Across all stores, average sales are {_format_number(promo_sales)} on promo days "
            f"vs {_format_number(base_sales)} on non-promo days ({uplift:+.1f}% uplift)."
        ),
        insights=[
            ChatInsight(label="Promo Avg Sales", value=_format_number(promo_sales)),
            ChatInsight(label="No-Promo Avg Sales", value=_format_number(base_sales)),
            ChatInsight(label="Promo Uplift", value=f"{uplift:+.1f}%"),
        ],
        suggestions=[
            "What is the promo impact for store 1?",
            "Show top 5 stores by total sales",
            "Forecast store 1 for 30 days",
        ],
    )


def _chat_kpi_summary(message: str) -> ChatResponse:
    store_id = _extract_store_id(message)
    date_from, date_to = _extract_date_range(message)
    kpi = get_kpi_summary(date_from=date_from, date_to=date_to, store_id=store_id)
    scope = f"store {store_id}" if store_id is not None else "all stores"

    return ChatResponse(
        answer=(
            f"KPI summary for {scope} from {date_from} to {date_to}: total sales "
            f"{_format_number(kpi.total_sales)}, average daily sales {_format_number(kpi.avg_daily_sales)}, "
            f"and total customers {_format_number(kpi.total_customers)}."
        ),
        insights=[
            ChatInsight(label="Date Range", value=f"{date_from} to {date_to}"),
            ChatInsight(label="Total Sales", value=_format_number(kpi.total_sales)),
            ChatInsight(label="Avg Daily Sales", value=_format_number(kpi.avg_daily_sales)),
        ],
        suggestions=[
            "Show top 5 stores by total sales",
            "What is the promo impact for store 1?",
            "Forecast store 1 for 30 days",
        ],
    )


def _chat_forecast(message: str) -> ChatResponse:
    store_id = _extract_store_id(message)
    if store_id is None:
        return ChatResponse(
            answer="Please provide a store id, for example: Forecast store 1 for 30 days.",
            suggestions=[
                "Forecast store 1 for 30 days",
                "Forecast store 25 for 90 days",
                "What is the promo impact for store 1?",
            ],
        )

    horizon = _extract_horizon(message)
    points = forecast_for_store(store_id=store_id, horizon_days=horizon)
    if not points:
        return ChatResponse(answer=f"No forecast output was generated for store {store_id}.")

    total_sales = sum(float(point["predicted_sales"]) for point in points)
    avg_daily = total_sales / len(points)
    peak_day = max(points, key=lambda point: float(point["predicted_sales"]))

    return ChatResponse(
        answer=(
            f"Forecast for store {store_id} over {horizon} days: total projected sales "
            f"{_format_number(total_sales)} with average daily sales {_format_number(avg_daily)}. "
            f"Peak expected day is {peak_day['date']} with {_format_number(float(peak_day['predicted_sales']))}."
        ),
        insights=[
            ChatInsight(label="Store", value=str(store_id)),
            ChatInsight(label="Horizon", value=f"{horizon} days"),
            ChatInsight(label="Projected Sales", value=_format_number(total_sales)),
        ],
        suggestions=[
            f"What is the promo impact for store {store_id}?",
            "Show top 5 stores by total sales",
            "What is the system data coverage?",
        ],
    )


def _chat_help() -> ChatResponse:
    return ChatResponse(
        answer=(
            "I can answer KPI, model quality, promo impact, top stores, and forecasting questions. "
            "Use natural language with optional store id and date range."
        ),
        suggestions=[
            "What is the system data coverage?",
            "Show top 5 stores by total sales",
            "Forecast store 1 for 30 days",
        ],
    )


def _heuristic_intent(message: str) -> str:
    lowered = message.lower()
    if any(term in lowered for term in ["hello", "hi", "hey", "مرحبا", "اهلا", "ازيك"]):
        return "greeting"
    if any(
        term in lowered
        for term in ["coverage", "how many stores", "rows", "system summary", "data range", "عدد المتاجر", "حجم الداتا"]
    ):
        return "system_summary"
    if any(term in lowered for term in ["model", "accuracy", "mae", "rmse", "mape", "feature importance", "المودل", "دقة"]):
        return "model_summary"
    if ("top" in lowered and "store" in lowered) or "اعلى المتاجر" in lowered:
        return "top_stores"
    if "promo" in lowered or "برومو" in lowered or "promot" in lowered:
        return "promo_impact"
    if any(term in lowered for term in ["forecast", "predict", "توقع", "فوركاست", "تنبؤ"]):
        return "forecast"
    if any(term in lowered for term in ["kpi", "summary", "sales", "customers", "revenue", "ملخص", "مبيعات", "عملاء"]):
        return "kpi_summary"
    return "help"


@lru_cache(maxsize=1)
def _load_chat_intent_artifact() -> dict[str, Any] | None:
    settings = get_settings()
    model_path = Path(settings.chat_model_path)
    if not model_path.is_absolute():
        model_path = (Path(__file__).resolve().parents[3] / model_path).resolve()
    if not model_path.exists():
        return None
    return joblib.load(model_path)


def _predict_intent(message: str) -> tuple[str | None, float]:
    artifact = _load_chat_intent_artifact()
    if not artifact:
        return None, 0.0

    pipeline = artifact.get("pipeline")
    if pipeline is None:
        return None, 0.0

    try:
        probs = pipeline.predict_proba([message])[0]
        labels = pipeline.classes_.tolist()
        best_idx = int(probs.argmax())
        return str(labels[best_idx]), float(probs[best_idx])
    except Exception:  # noqa: BLE001
        return None, 0.0


def _resolve_intent(message: str) -> str:
    predicted_intent, confidence = _predict_intent(message)
    settings = get_settings()
    threshold = max(settings.chat_min_confidence, 0.0)
    if predicted_intent and confidence >= threshold:
        return predicted_intent
    return _heuristic_intent(message)


def answer_chat_query(message: str) -> ChatResponse:
    normalized = message.strip()
    if not normalized:
        return ChatResponse(answer="Please enter a question.")

    intent = _resolve_intent(normalized)
    if intent == "greeting":
        return _chat_help()
    if intent == "system_summary":
        return _chat_system_summary()
    if intent == "model_summary":
        return _chat_model_summary()
    if intent == "top_stores":
        return _chat_top_stores()
    if intent == "promo_impact":
        return _chat_promo_impact(normalized)
    if intent == "forecast":
        return _chat_forecast(normalized)
    if intent == "kpi_summary":
        return _chat_kpi_summary(normalized)
    return _chat_help()
