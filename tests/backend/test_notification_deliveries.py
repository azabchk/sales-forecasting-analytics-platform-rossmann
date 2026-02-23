from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.preflight_notifications_service import get_notification_deliveries  # noqa: E402
from src.etl.preflight_notification_attempt_registry import (  # noqa: E402
    complete_delivery_attempt,
    insert_delivery_attempt_started,
)


def _sqlite_url(tmp_path: Path, name: str) -> str:
    return f"sqlite+pysqlite:///{(tmp_path / name).resolve()}"


def _seed_attempt(
    *,
    db_url: str,
    outbox_item_id: str,
    attempt_number: int,
    status: str,
) -> None:
    started = insert_delivery_attempt_started(
        {
            "outbox_item_id": outbox_item_id,
            "channel_target": "webhook_sales",
            "event_type": "ALERT_FIRING",
            "alert_id": "alert_1",
            "policy_id": "policy_1",
            "attempt_number": attempt_number,
            "started_at": datetime.now(timezone.utc),
        },
        database_url=db_url,
    )
    complete_delivery_attempt(
        started["attempt_id"],
        attempt_status=status,
        completed_at=datetime.now(timezone.utc),
        http_status=200 if status == "SENT" else 500,
        error_message_safe="failed" if status != "SENT" else None,
        database_url=db_url,
    )


def test_notification_deliveries_pagination_and_status_filter(tmp_path: Path):
    db_url = _sqlite_url(tmp_path, "notification_deliveries.db")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        _seed_attempt(db_url=db_url, outbox_item_id="outbox_a", attempt_number=1, status="SENT")
        _seed_attempt(db_url=db_url, outbox_item_id="outbox_b", attempt_number=1, status="DEAD")

        page_all = get_notification_deliveries(page=1, page_size=1)
        assert page_all["page"] == 1
        assert page_all["page_size"] == 1
        assert page_all["total"] == 2
        assert len(page_all["items"]) == 1

        sent_only = get_notification_deliveries(page=1, page_size=10, status="SENT")
        assert sent_only["status"] == "SENT"
        assert sent_only["total"] == 1
        assert len(sent_only["items"]) == 1
        assert sent_only["items"][0]["attempt_status"] == "SENT"
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
