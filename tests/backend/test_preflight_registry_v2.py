from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_registry import (  # noqa: E402
    get_latest_preflight,
    insert_preflight_run,
    list_preflight_runs,
)


def _sqlite_url(tmp_path: Path, name: str) -> str:
    return f"sqlite+pysqlite:///{(tmp_path / name).resolve()}"


def _build_record(run_id: str, *, source_name: str = "train", created_at: datetime | None = None) -> dict:
    return {
        "run_id": run_id,
        "source_name": source_name,
        "created_at": created_at or datetime.now(timezone.utc),
        "mode": "report_only",
        "validation_status": "PASS",
        "semantic_status": "PASS",
        "final_status": "PASS",
        "used_input_path": "/tmp/input.csv",
        "used_unified": False,
        "artifact_dir": "/tmp/artifacts",
        "validation_report_path": "/tmp/validation.json",
        "manifest_path": "/tmp/manifest.json",
        "summary_json": {},
        "blocked": False,
        "block_reason": None,
    }


def test_preflight_registry_keeps_legacy_rows_and_v2_fields(tmp_path: Path):
    db_url = _sqlite_url(tmp_path, "preflight_registry.db")

    legacy = _build_record("legacy_run")
    insert_preflight_run(legacy, database_url=db_url)

    v2 = _build_record("v2_run", created_at=datetime.now(timezone.utc))
    v2["data_source_id"] = 5
    v2["contract_id"] = "rossmann_input_contract"
    v2["contract_version"] = "v1"
    insert_preflight_run(v2, database_url=db_url)

    rows = list_preflight_runs(limit=10, database_url=db_url)
    assert len(rows) == 2

    legacy_row = next(row for row in rows if row["run_id"] == "legacy_run")
    assert legacy_row.get("data_source_id") is None
    assert legacy_row.get("contract_id") is None
    assert legacy_row.get("contract_version") is None

    v2_row = next(row for row in rows if row["run_id"] == "v2_run")
    assert int(v2_row["data_source_id"]) == 5
    assert v2_row["contract_id"] == "rossmann_input_contract"
    assert v2_row["contract_version"] == "v1"

    latest_for_ds = get_latest_preflight(data_source_id=5, database_url=db_url)
    assert latest_for_ds is not None
    assert latest_for_ds["run_id"] == "v2_run"
