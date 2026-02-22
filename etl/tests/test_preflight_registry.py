from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_registry import (  # noqa: E402
    get_latest_preflight,
    get_preflight_run,
    insert_preflight_run,
    list_preflight_runs,
)


def _db_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{(tmp_path / 'preflight_registry.db').resolve()}"


def test_registry_insert_and_get_run(tmp_path: Path):
    database_url = _db_url(tmp_path)
    created_at = datetime(2026, 2, 21, 19, 30, tzinfo=timezone.utc)

    insert_preflight_run(
        {
            "run_id": "run_001",
            "source_name": "train",
            "created_at": created_at,
            "mode": "enforce",
            "validation_status": "PASS",
            "semantic_status": "WARN",
            "final_status": "WARN",
            "used_input_path": "/tmp/train.csv",
            "used_unified": False,
            "artifact_dir": "/tmp/artifacts/train",
            "validation_report_path": "/tmp/artifacts/train/validation_report.json",
            "manifest_path": "/tmp/artifacts/train/manifest.json",
            "summary_json": {"status": "WARN"},
            "blocked": False,
            "block_reason": None,
        },
        database_url=database_url,
    )
    insert_preflight_run(
        {
            "run_id": "run_001",
            "source_name": "store",
            "created_at": created_at,
            "mode": "enforce",
            "validation_status": "PASS",
            "semantic_status": "PASS",
            "final_status": "PASS",
            "used_input_path": "/tmp/store.csv",
            "used_unified": True,
            "artifact_dir": "/tmp/artifacts/store",
            "validation_report_path": "/tmp/artifacts/store/validation_report.json",
            "manifest_path": "/tmp/artifacts/store/manifest.json",
            "summary_json": {"status": "PASS"},
            "blocked": False,
            "block_reason": None,
        },
        database_url=database_url,
    )

    payload = get_preflight_run("run_001", database_url=database_url)
    assert payload is not None
    assert payload["run_id"] == "run_001"
    assert payload["final_status"] == "WARN"
    assert len(payload["records"]) == 2


def test_registry_list_and_latest(tmp_path: Path):
    database_url = _db_url(tmp_path)

    insert_preflight_run(
        {
            "run_id": "run_101",
            "source_name": "train",
            "created_at": datetime(2026, 2, 21, 19, 0, tzinfo=timezone.utc),
            "mode": "report_only",
            "validation_status": "PASS",
            "semantic_status": "PASS",
            "final_status": "PASS",
            "used_input_path": "/tmp/train_101.csv",
            "used_unified": False,
            "artifact_dir": "/tmp/artifacts/run_101/train",
            "validation_report_path": "/tmp/artifacts/run_101/train/validation_report.json",
            "manifest_path": "/tmp/artifacts/run_101/train/manifest.json",
            "summary_json": {"status": "PASS"},
            "blocked": False,
            "block_reason": None,
        },
        database_url=database_url,
    )
    insert_preflight_run(
        {
            "run_id": "run_102",
            "source_name": "train",
            "created_at": datetime(2026, 2, 21, 20, 0, tzinfo=timezone.utc),
            "mode": "enforce",
            "validation_status": "FAIL",
            "semantic_status": "SKIPPED",
            "final_status": "FAIL",
            "used_input_path": "/tmp/train_102.csv",
            "used_unified": False,
            "artifact_dir": "/tmp/artifacts/run_102/train",
            "validation_report_path": "/tmp/artifacts/run_102/train/validation_report.json",
            "manifest_path": None,
            "summary_json": {"status": "FAIL"},
            "blocked": True,
            "block_reason": "validation_fail",
        },
        database_url=database_url,
    )

    rows = list_preflight_runs(limit=5, source_name="train", database_url=database_url)
    assert len(rows) == 2
    assert rows[0]["run_id"] == "run_102"
    assert rows[1]["run_id"] == "run_101"

    latest_source = get_latest_preflight(source_name="train", database_url=database_url)
    assert latest_source is not None
    assert latest_source["run_id"] == "run_102"
    assert latest_source["blocked"] is True

    latest_grouped = get_latest_preflight(source_name=None, database_url=database_url)
    assert latest_grouped is not None
    assert latest_grouped["run_id"] == "run_102"
