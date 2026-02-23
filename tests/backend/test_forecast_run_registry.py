from __future__ import annotations

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.forecast_run_registry import upsert_forecast_run


def test_upsert_forecast_run_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "forecast_run_registry.sqlite3"
    db_url = f"sqlite+pysqlite:///{db_path}"
    run_id = "scenario_run_smoke"
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    upsert_forecast_run(
        {
            "run_id": run_id,
            "created_at": created_at,
            "run_type": "scenario_v2",
            "status": "RUNNING",
            "request_json": {"store_id": 1},
            "summary_json": {},
        },
        database_url=db_url,
    )
    upsert_forecast_run(
        {
            "run_id": run_id,
            "created_at": created_at,
            "run_type": "scenario_v2",
            "status": "COMPLETED",
            "request_json": {"store_id": 1},
            "summary_json": {"uplift_pct": 1.5},
        },
        database_url=db_url,
    )

    engine = sa.create_engine(db_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT run_id, status, summary_json FROM forecast_run_registry WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).mappings().first()

    assert row is not None
    assert row["run_id"] == run_id
    assert row["status"] == "COMPLETED"
    summary_json = row["summary_json"]
    if isinstance(summary_json, str):
        summary_json = json.loads(summary_json)
    assert summary_json["uplift_pct"] == 1.5
