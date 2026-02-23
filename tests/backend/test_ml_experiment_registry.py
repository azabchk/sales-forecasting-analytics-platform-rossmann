from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.ml_experiment_registry import get_experiment, upsert_experiment


def test_upsert_experiment_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "ml_experiment_registry.sqlite3"
    db_url = f"sqlite+pysqlite:///{db_path}"
    experiment_id = "ml_exp_smoke"
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    upsert_experiment(
        {
            "experiment_id": experiment_id,
            "model_type": "pending",
            "status": "RUNNING",
            "created_at": created_at,
            "updated_at": created_at,
            "metrics_json": {},
            "hyperparameters_json": {"a": 1},
        },
        database_url=db_url,
    )
    upsert_experiment(
        {
            "experiment_id": experiment_id,
            "model_type": "ridge",
            "status": "COMPLETED",
            "created_at": created_at,
            "updated_at": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            "metrics_json": {"rmse": 12.34},
            "hyperparameters_json": {"alpha": 0.1},
        },
        database_url=db_url,
    )

    record = get_experiment(experiment_id, database_url=db_url)
    assert record is not None
    assert record["experiment_id"] == experiment_id
    assert record["status"] == "COMPLETED"
    assert record["model_type"] == "ridge"
    assert record["metrics_json"] == {"rmse": 12.34}

