from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.ml_experiment_registry import get_experiment, list_experiments


def _normalize_experiment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload.get("experiment_id"),
        "data_source_id": payload.get("data_source_id"),
        "model_type": payload.get("model_type"),
        "hyperparameters": payload.get("hyperparameters_json")
        if isinstance(payload.get("hyperparameters_json"), dict)
        else {},
        "training_period": {
            "start": payload.get("train_period_start"),
            "end": payload.get("train_period_end"),
        },
        "validation_period": {
            "start": payload.get("validation_period_start"),
            "end": payload.get("validation_period_end"),
        },
        "metrics": payload.get("metrics_json") if isinstance(payload.get("metrics_json"), dict) else {},
        "status": payload.get("status"),
        "artifact_path": payload.get("artifact_path"),
        "metadata_path": payload.get("metadata_path"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }


def list_ml_experiments(*, limit: int = 100, data_source_id: int | None = None) -> list[dict[str, Any]]:
    rows = list_experiments(limit=limit, data_source_id=data_source_id)
    return [_normalize_experiment_payload(row) for row in rows]


def get_ml_experiment(experiment_id: str) -> dict[str, Any] | None:
    row = get_experiment(experiment_id)
    if row is None:
        return None
    return _normalize_experiment_payload(row)
