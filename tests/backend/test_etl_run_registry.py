from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.etl_run_registry import list_etl_runs, upsert_etl_run


def test_upsert_etl_run_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "etl_registry.sqlite3"
    db_url = f"sqlite+pysqlite:///{db_path}"
    run_id = "etl_smoke_test_run"
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    finished_at = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)

    upsert_etl_run(
        {
            "run_id": run_id,
            "started_at": started_at,
            "status": "RUNNING",
            "summary_json": {"step": "start"},
        },
        database_url=db_url,
    )
    upsert_etl_run(
        {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": "COMPLETED",
            "summary_json": {"step": "finish"},
        },
        database_url=db_url,
    )

    rows = list_etl_runs(limit=10, database_url=db_url)
    assert len(rows) == 1
    assert rows[0]["run_id"] == run_id
    assert rows[0]["status"] == "COMPLETED"
    assert rows[0]["summary_json"] == {"step": "finish"}
