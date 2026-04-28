from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import MLExperimentListItemResponse, MLExperimentsResponse
from app.services.ml_experiment_service import get_ml_experiment, list_ml_experiments

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ML_CONFIG    = _PROJECT_ROOT / "ml" / "config.yaml"
_PYTHON       = sys.executable          # same Python that runs the backend


@router.post("/ml/retrain")
def trigger_retrain() -> dict[str, Any]:
    """Launch ml/train.py in a background subprocess. Returns immediately."""
    if not _ML_CONFIG.exists():
        raise HTTPException(status_code=500, detail="ml/config.yaml not found")

    experiment_id = f"ml_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)

    try:
        proc = subprocess.Popen(
            [_PYTHON, str(_PROJECT_ROOT / "ml" / "train.py"), "--config", str(_ML_CONFIG)],
            cwd=str(_PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "status": "started",
            "pid": proc.pid,
            "experiment_hint": experiment_id,
            "message": "Training started in background. Check /ml/experiments for progress.",
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to start training: {exc}") from exc


@router.get("/ml/drift")
def get_model_drift() -> dict[str, Any]:
    """Compare the two most recent COMPLETED experiments to detect metric drift."""
    rows = list_ml_experiments(limit=10)
    completed = [r for r in rows if str(r.get("status", "")).upper() == "COMPLETED"]
    if len(completed) < 2:
        return {"status": "insufficient_data", "message": "Need at least 2 completed experiments to compare.", "drift": []}

    latest   = completed[0]
    previous = completed[1]

    def _m(exp: dict, key: str) -> float | None:
        metrics = exp.get("metrics_json") or exp.get("metrics") or {}
        best = metrics.get("best") or {}
        val = best.get(key)
        return float(val) if val is not None else None

    metrics_to_compare = ["mae", "rmse", "wape", "mape"]
    drift_items: list[dict] = []
    for m in metrics_to_compare:
        cur = _m(latest, m)
        prv = _m(previous, m)
        if cur is None or prv is None:
            continue
        delta_pct = ((cur - prv) / max(abs(prv), 1e-8)) * 100.0
        # For error metrics: lower is better → positive delta = degrading
        drift_status = "stable"
        if abs(delta_pct) > 3:
            drift_status = "degrading" if delta_pct > 0 else "improving"
        drift_items.append({
            "metric": m.upper(),
            "current": round(cur, 4),
            "previous": round(prv, 4),
            "delta_pct": round(delta_pct, 2),
            "drift_status": drift_status,
        })

    overall = "stable"
    if any(d["drift_status"] == "degrading" for d in drift_items):
        overall = "degrading"
    elif all(d["drift_status"] == "improving" for d in drift_items):
        overall = "improving"

    return {
        "overall_drift": overall,
        "latest_experiment_id": latest.get("experiment_id"),
        "previous_experiment_id": previous.get("experiment_id"),
        "latest_trained_at": str(latest.get("created_at", "")),
        "previous_trained_at": str(previous.get("created_at", "")),
        "drift": drift_items,
    }


@router.get("/ml/experiments", response_model=MLExperimentsResponse)
def get_experiments(
    limit: int = Query(default=100, ge=1, le=500),
    data_source_id: int | None = Query(default=None, gt=0),
) -> MLExperimentsResponse:
    try:
        rows = list_ml_experiments(limit=limit, data_source_id=data_source_id)
        return MLExperimentsResponse(
            items=[MLExperimentListItemResponse.model_validate(item) for item in rows],
            limit=limit,
            data_source_id=data_source_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ML experiment error: {exc}") from exc


@router.get("/ml/experiments/{experiment_id}", response_model=MLExperimentListItemResponse)
def get_experiment(experiment_id: str) -> MLExperimentListItemResponse:
    try:
        payload = get_ml_experiment(experiment_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_id}")
        return MLExperimentListItemResponse.model_validate(payload)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ML experiment error: {exc}") from exc
