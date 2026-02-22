from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_registry import insert_preflight_run  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _insert_registry_record(
    *,
    run_id: str,
    source_name: str,
    artifact_dir: Path,
    validation_report_path: str | None,
    manifest_path: str | None,
    used_input_path: str,
    database_url: str,
) -> None:
    insert_preflight_run(
        {
            "run_id": run_id,
            "source_name": source_name,
            "created_at": datetime.now(timezone.utc),
            "mode": "report_only",
            "validation_status": "PASS",
            "semantic_status": "WARN",
            "final_status": "WARN",
            "used_input_path": used_input_path,
            "used_unified": True,
            "artifact_dir": str(artifact_dir.resolve()),
            "validation_report_path": validation_report_path,
            "manifest_path": manifest_path,
            "summary_json": {"mode": "report_only"},
            "blocked": False,
            "block_reason": None,
        },
        database_url=database_url,
    )


def _prepare_env(monkeypatch, tmp_path: Path) -> tuple[str, Path]:
    db_path = tmp_path / "diagnostics_artifacts.db"
    database_url = f"sqlite+pysqlite:///{db_path.resolve()}"
    artifact_root = (tmp_path / "preflight_root").resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PREFLIGHT_ARTIFACT_ROOT", str(artifact_root))
    return database_url, artifact_root


def test_artifact_endpoints_return_validation_semantic_manifest(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    run_id = "run_artifacts_ok"
    source_name = "train"
    artifact_dir = artifact_root / run_id / source_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    validation_path = artifact_dir / "validation_report.json"
    semantic_path = artifact_dir / "semantic_report.json"
    manifest_path = artifact_dir / "manifest.json"
    preflight_path = artifact_dir / "preflight_report.json"
    unified_path = artifact_dir / "unified.csv"

    _write_json(
        validation_path,
        {
            "status": "PASS",
            "contract_version": "v1",
            "profile": "rossmann_train",
            "checks": {"required_columns": "PASS", "types": "PASS"},
            "errors": [],
            "warnings": [],
            "summary": "Validation passed.",
            "metadata": {"rows": 2},
        },
    )
    _write_json(
        semantic_path,
        {
            "status": "WARN",
            "summary": "Semantic quality checks completed with warnings.",
            "counts": {"total": 1, "passed": 0, "warned": 1, "failed": 0},
            "rules": [
                {
                    "rule_id": "customers_null_ratio",
                    "rule_type": "max_null_ratio",
                    "severity": "WARN",
                    "status": "WARN",
                    "message": "Null ratio exceeds threshold.",
                    "target": ["customers"],
                    "observed": {"null_ratio": 0.25},
                }
            ],
        },
    )
    _write_json(
        manifest_path,
        {
            "contract_version": "v1",
            "profile": "rossmann_train",
            "validation_status": "PASS",
            "renamed_columns": {"Store": "store_id"},
            "extra_columns_dropped": [],
            "coercion_stats": {"sales": {"expected_dtype": "float", "invalid_to_null": 0, "null_count_after": 0}},
            "final_canonical_columns": ["store_id", "sales"],
            "retained_extra_columns": [],
            "output_row_count": 2,
            "output_column_count": 2,
        },
    )
    _write_json(
        preflight_path,
        {
            "mode": "report_only",
            "semantic": {
                "status": "WARN",
                "summary": "Semantic quality checks completed with warnings.",
                "counts": {"total": 1, "passed": 0, "warned": 1, "failed": 0},
                "rules": [],
            },
        },
    )
    unified_path.write_text("store_id,sales\n1,100.0\n", encoding="utf-8")

    _insert_registry_record(
        run_id=run_id,
        source_name=source_name,
        artifact_dir=artifact_dir,
        validation_report_path=str(validation_path.resolve()),
        manifest_path=str(manifest_path.resolve()),
        used_input_path=str(unified_path.resolve()),
        database_url=database_url,
    )

    artifacts_response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["run_id"] == run_id
    assert artifacts_payload["source_name"] == source_name
    assert len(artifacts_payload["artifacts"]) == 5
    assert any(item["artifact_type"] == "semantic" and item["available"] is True for item in artifacts_payload["artifacts"])

    validation_response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation")
    assert validation_response.status_code == 200
    validation_payload = validation_response.json()
    assert validation_payload["status"] == "PASS"
    assert validation_payload["checks"]["required_columns"] == "PASS"

    semantic_response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic")
    assert semantic_response.status_code == 200
    semantic_payload = semantic_response.json()
    assert semantic_payload["status"] == "WARN"
    assert semantic_payload["counts"]["warned"] == 1
    assert semantic_payload["rules"][0]["rule_id"] == "customers_null_ratio"

    manifest_response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest")
    assert manifest_response.status_code == 200
    manifest_payload = manifest_response.json()
    assert manifest_payload["profile"] == "rossmann_train"
    assert manifest_payload["renamed_columns"]["Store"] == "store_id"

    download_response = client.get(
        f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/manifest"
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/json")


def test_missing_artifact_returns_404(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    run_id = "run_artifacts_missing"
    source_name = "train"
    artifact_dir = artifact_root / run_id / source_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    missing_validation_path = artifact_dir / "validation_report.json"

    _insert_registry_record(
        run_id=run_id,
        source_name=source_name,
        artifact_dir=artifact_dir,
        validation_report_path=str(missing_validation_path.resolve()),
        manifest_path=None,
        used_input_path=str((artifact_dir / "unified.csv").resolve()),
        database_url=database_url,
    )

    response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"].lower() or "not found" in response.json()["detail"].lower()


def test_traversal_like_registered_path_rejected(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    run_id = "run_artifacts_traversal"
    source_name = "train"
    artifact_dir = artifact_root / run_id / source_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    bad_validation_path = artifact_dir / ".." / "outside_validation_report.json"
    _insert_registry_record(
        run_id=run_id,
        source_name=source_name,
        artifact_dir=artifact_dir,
        validation_report_path=str(bad_validation_path),
        manifest_path=None,
        used_input_path=str((artifact_dir / "unified.csv").resolve()),
        database_url=database_url,
    )

    response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation")
    assert response.status_code == 403
    assert "outside" in response.json()["detail"].lower()


def test_source_run_mismatch_returns_404(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)

    run_id = "run_artifacts_source_mismatch"
    artifact_dir = artifact_root / run_id / "train"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    validation_path = artifact_dir / "validation_report.json"
    _write_json(
        validation_path,
        {
            "status": "PASS",
            "checks": {"required_columns": "PASS"},
            "errors": [],
            "warnings": [],
            "metadata": {},
        },
    )

    _insert_registry_record(
        run_id=run_id,
        source_name="train",
        artifact_dir=artifact_dir,
        validation_report_path=str(validation_path.resolve()),
        manifest_path=None,
        used_input_path=str((artifact_dir / "unified.csv").resolve()),
        database_url=database_url,
    )

    response = client.get(f"/api/v1/diagnostics/preflight/runs/{run_id}/sources/store/validation")
    assert response.status_code == 404
    assert "source 'store'" in response.json()["detail"].lower()
